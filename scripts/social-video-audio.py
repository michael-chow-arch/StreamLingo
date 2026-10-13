"""Generate original promo narration, timing files, and a simple music bed.

Run with an isolated Python environment containing sherpa-onnx and soundfile:
  python scripts/social-video-audio.py --engine local
The local mode requires the documented model archives in --models.
Optional online mode uses edge-tts==7.2.8; SAPI is a standard-voice backup.
Requires ffmpeg on PATH; SAPI also requires Windows System.Speech.
Only the optional neural/Edge mode sends original narration text online.
No browser, microphone, ASR, Ollama, or product configuration is accessed.
"""

import argparse
from array import array
import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import wave

RATE = 48_000
DURATION = 32.0
DEMO = (11.5, 17.5)
SEGMENTS = [
    ("hook", 0.30, 2.80, "看直播，听不懂？", "Live stream. Lost in translation?",
     "Solid-color opening card with large question text; no YouTube footage"),
    ("discovery", 3.10, 5.45, "发现个好用的工具。", "Found a handy tool: StreamLingo.",
     "Show StreamLingo extension icon / name"),
    ("choose", 5.65, 9.40, "在 YouTube 打开扩展，选择英译中。", "On YouTube, choose English to Chinese.",
     "Show the actual subtitle demo; narration explains the extension setting, without a fabricated button click"),
    ("start", 9.65, 11.30, "点击开始字幕。", "Then start subtitles.",
     "Transition to actual translated subtitles; do not fabricate a button click"),
    ("local", 17.80, 23.10, "直接取浏览器音频，用已有的 Ollama 本地模型翻译。",
     "It captures browser audio and translates with your local Ollama model.",
     "Continue actual subtitles; briefly show local Ollama model setting"),
    ("modes", 23.45, 27.10, "也能中译英，或自动识别语言。",
     "Chinese to English, or automatic language detection, too.",
     "Brief on-screen mode labels over actual demo footage; no toolbar capture needed"),
    ("project", 27.50, 31.65, "项目叫 StreamLingo，GitHub 上能找到。", "Find StreamLingo on GitHub.",
     "End card: StreamLingo / github.com/michael-chow-arch/StreamLingo"),
]
VOICES = {
    "local": {"zh": "MeloTTS Chinese female (MIT), sherpa-onnx VITS", "en": "Piper en_US-ljspeech-medium female, sherpa-onnx VITS"},
    "neural": {"zh": "zh-CN-XiaoxiaoNeural", "en": "en-US-JennyNeural"},
    "sapi": {"zh": "Microsoft Huihui Desktop", "en": "Microsoft Zira Desktop"},
}


def synthesize_local(directory, models):
    import sherpa_onnx
    import soundfile as sf

    chinese_root = models / "vits-melo-tts-zh_en"
    # Melo's English frontend is lexicon-based. Add only brand-word pronunciations
    # to a derived lexicon; leave all downloaded model files unchanged.
    lexicon = directory / "lexicon-streamlingo.txt"
    base = (chinese_root / "lexicon.txt").read_text(encoding="utf-8")
    additions = {
        "youtube": "y uw t uw b 7 9 7 9 7",
        "github": "g ih t hh ah b 7 9 7 7 8 7",
        "ollama": "ow l aa m ah 9 7 9 7 8",
        "streamlingo": "s t r iy m l ih ng g ow 7 7 7 9 7 7 9 7 7 8",
    }
    lexicon.write_text(base.rstrip() + "\n" + "\n".join(f"{word} {phones}" for word, phones in additions.items()) + "\n", encoding="utf-8")
    for language in ("zh", "en"):
        if language == "zh":
            root = chinese_root
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(root / "model.onnx"), tokens=str(root / "tokens.txt"),
                lexicon=str(lexicon), dict_dir=str(root / "dict"))
        else:
            root = models / "vits-piper-en_US-ljspeech-medium"
            vits = sherpa_onnx.OfflineTtsVitsModelConfig(
                model=str(root / "en_US-ljspeech-medium.onnx"), tokens=str(root / "tokens.txt"),
                data_dir=str(root / "espeak-ng-data"))
        config = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=vits, num_threads=2, provider="cpu"), max_num_sentences=1)
        tts = sherpa_onnx.OfflineTts(config)
        for key, _, _, chinese, english, _ in SEGMENTS:
            text = chinese if language == "zh" else english
            spoken = text if language == "zh" else text.replace("StreamLingo", "Stream Lingo")
            destination = directory / f"{language}-{key}-raw.wav"
            audio = tts.generate(spoken, sid=0, speed=1.0)
            if len(audio.samples) == 0:
                raise RuntimeError(f"Local TTS produced no audio for {language}/{key}")
            sf.write(destination, audio.samples, audio.sample_rate, subtype="PCM_16")
            destination.with_suffix(".txt").write_text(spoken, encoding="utf-8")
            print(f"local: {language}/{key} ({len(audio.samples)/audio.sample_rate:.2f}s)", flush=True)
        del tts


def run(*args):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def write_wav(path, samples):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        data = array("h", (round(max(-1.0, min(1.0, value)) * 32767) for value in samples))
        if sys.byteorder != "little":
            data.byteswap()
        output.writeframes(data.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as source:
        assert source.getnchannels() == 1 and source.getsampwidth() == 2 and source.getframerate() == RATE
        data = array("h", source.readframes(source.getnframes()))
        if sys.byteorder != "little":
            data.byteswap()
        return data


def srt_time(seconds):
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


async def synthesize_neural(directory):
    import edge_tts

    for language in ("zh", "en"):
        for key, _, _, chinese, english, _ in SEGMENTS:
            destination = directory / f"{language}-{key}-raw.mp3"
            text = chinese if language == "zh" else english
            text_cache = destination.with_suffix(".txt")
            if (destination.exists() and destination.stat().st_size > 1000
                    and text_cache.exists() and text_cache.read_text(encoding="utf-8") == text):
                continue
            # Separate requests preserve the deliberate six-second demo gap.
            speech = edge_tts.Communicate(text,
                                         VOICES["neural"][language], rate="+0%",
                                         connect_timeout=15, receive_timeout=30)
            await speech.save(str(destination))
            text_cache.write_text(text, encoding="utf-8")
            print(f"neural: {language}/{key}", flush=True)


def synthesize_sapi(directory):
    manifest = []
    for language in ("zh", "en"):
        for key, _, _, chinese, english, _ in SEGMENTS:
            destination = directory / f"{language}-{key}-raw.wav"
            text = chinese if language == "zh" else english
            text_cache = destination.with_suffix(".txt")
            if (destination.exists() and destination.stat().st_size > 1000
                    and text_cache.exists() and text_cache.read_text(encoding="utf-8") == text):
                continue
            manifest.append({"voice": VOICES["sapi"][language], "text": text,
                             "path": str(destination)})
    manifest_path = directory / "sapi-requests.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    powershell_path = directory / "synthesize-sapi.ps1"
    powershell_path.write_text("""param([string]$Manifest)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskRequests = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($taskRequest in $taskRequests) {
    $taskVoice = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $taskVoice.SelectVoice($taskRequest.voice)
        $taskVoice.Rate = 0
        $taskFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(48000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $taskVoice.SetOutputToWaveFile($taskRequest.path, $taskFormat)
        $taskVoice.Speak($taskRequest.text)
    } finally { $taskVoice.Dispose() }
}
""", encoding="utf-8-sig")
    run("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", powershell_path, "-Manifest", manifest_path)
    for request in manifest:
        Path(request["path"]).with_suffix(".txt").write_text(request["text"], encoding="utf-8")


def prepare_narration(engine, directory):
    timeline = {"duration_seconds": DURATION, "sample_rate": RATE, "engine": engine,
                "voices": VOICES[engine], "demo_gap": {"start": DEMO[0], "end": DEMO[1]}, "languages": {}}
    for language in ("zh", "en"):
        voice = array("h", [0]) * round(DURATION * RATE)
        cues = []
        for key, start, end, chinese, english, visual in SEGMENTS:
            raw = directory / f"{language}-{key}-raw.{'mp3' if engine == 'neural' else 'wav'}"
            trimmed = directory / f"{language}-{key}-trim.wav"
            # Remove leading/trailing padding only, retaining sentence pauses.
            trim = "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.06,areverse"
            run("ffmpeg", "-v", "error", "-y", "-i", raw, "-af", trim, "-ac", 1, "-ar", RATE, "-c:a", "pcm_s16le", trimmed)
            source_seconds = len(read_wav(trimmed)) / RATE
            tempo = max(1.0, source_seconds / (end - start))
            if tempo > 1.30:
                raise RuntimeError(f"{engine}/{language}/{key} is too long ({source_seconds:.2f}s / {end-start:.2f}s); shorten the text instead of rushing it")
            fitted = directory / f"{language}-{key}.wav"
            run("ffmpeg", "-v", "error", "-y", "-i", trimmed, "-af",
                f"atempo={tempo:.8f},loudnorm=I=-18:TP=-2:LRA=7", "-ac", 1, "-ar", RATE, "-c:a", "pcm_s16le", fitted)
            data = read_wav(fitted)
            actual_end = start + len(data) / RATE
            if actual_end > end + 0.08:
                raise RuntimeError(f"Narration exceeds slot: {engine}/{language}/{key}")
            index = round(start * RATE)
            voice[index:index + len(data)] = data
            cues.append({"id": key, "start": start, "end": round(actual_end, 3), "slot_end": end,
                         "text": chinese if language == "zh" else english,
                         "source_duration": round(source_seconds, 3), "tempo_multiplier": round(tempo, 4),
                         "visual": visual})
        assert len(voice) == round(DURATION * RATE)
        assert max(map(abs, voice[round(DEMO[0] * RATE):round(DEMO[1] * RATE)])) == 0
        with wave.open(str(directory / f"voice-{language}.wav"), "wb") as output:
            output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            output.writeframes(voice.tobytes())
        subtitles = "\n\n".join(f"{index}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n{cue['text']}" for index, cue in enumerate(cues, 1))
        (directory / f"narration-{language}.srt").write_text(subtitles + "\n", encoding="utf-8")
        timeline["languages"][language] = cues
    (directory / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
    return timeline


def make_music(path):
    """Original 96 BPM C-major instrumental, synthesized with no sampled audio."""
    buffer = array("f", [0.0]) * round(DURATION * RATE)
    random_source = random.Random(20261013)

    def note(start, seconds, midi, amplitude, decay=2.2):
        frequency = 440 * 2 ** ((midi - 69) / 12)
        beginning = round(start * RATE)
        count = min(round(seconds * RATE), len(buffer) - beginning)
        for offset in range(count):
            t = offset / RATE
            envelope = min(1.0, t / 0.014) * math.exp(-decay * t) * min(1.0, (seconds - t) / 0.12)
            tone = math.sin(2 * math.pi * frequency * t) + 0.16 * math.sin(4 * math.pi * frequency * t)
            buffer[beginning + offset] += amplitude * envelope * tone

    chords = [(60, 64, 67, 71), (57, 60, 64, 67), (53, 57, 60, 64), (55, 59, 62, 64)]
    melody = [76, 79, 74, 76, 72, 76, 71, 74, 69, 72, 76, 74, 71, 74, 79, 76]
    for block in range(7):
        chord = chords[block % len(chords)]
        for index, midi in enumerate(chord):
            note(block * 5 + index * 0.035, 4.6, midi, 0.019, 0.65)
        note(block * 5, 2.8, chord[0] - 12, 0.016, 1.0)
    for index in range(26):
        note(index * 1.25 + 0.12, 1.2, melody[index % len(melody)], 0.018)
    for beat in range(52):
        start = round(beat * 0.625 * RATE)
        if beat % 4 == 0:
            for offset in range(min(round(0.18 * RATE), len(buffer) - start)):
                t = offset / RATE
                buffer[start + offset] += 0.014 * math.sin(2 * math.pi * (57 * t + 4 * (1 - math.exp(-32 * t)))) * math.exp(-27 * t)
        for offset in range(min(round(0.035 * RATE), len(buffer) - start)):
            t = offset / RATE
            buffer[start + offset] += 0.0025 * random_source.uniform(-1, 1) * math.exp(-130 * t)
    for index in range(len(buffer)):
        t = index / RATE
        fade = min(1.0, t / 0.7, max(0.0, (DURATION - t) / 1.4))
        # Lower the music for actual stream speech and live translated captions.
        duck = 0.20 if DEMO[0] <= t <= DEMO[1] else 1.0
        if DEMO[0] - 0.25 < t < DEMO[0]:
            duck = 1.0 - 0.8 * (t - DEMO[0] + 0.25) / 0.25
        if DEMO[1] < t < DEMO[1] + 0.25:
            duck = 0.2 + 0.8 * (t - DEMO[1]) / 0.25
        buffer[index] *= fade * duck
    write_wav(path, buffer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("local", "sapi", "neural", "both"), default="local")
    parser.add_argument("--output", type=Path, default=Path("output/social-video"))
    parser.add_argument("--models", type=Path, default=Path("output/social-video-tools/models"))
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg is required")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    music = output / "music-original.wav"
    make_music(music)
    engines = ("sapi", "neural") if args.engine == "both" else (args.engine,)
    reports = {}
    for engine in engines:
        directory = output / ("neural-local" if engine == "local" else engine)
        directory.mkdir(exist_ok=True)
        if engine == "local":
            synthesize_local(directory, args.models.resolve())
        elif engine == "sapi":
            synthesize_sapi(directory)
        else:
            asyncio.run(synthesize_neural(directory))
        reports[engine] = prepare_narration(engine, directory)
        for language in ("zh", "en"):
            run("ffmpeg", "-v", "error", "-y", "-i", directory / f"voice-{language}.wav",
                "-af", "pan=stereo|c0=c0|c1=c0,loudnorm=I=-18:TP=-2:LRA=7",
                "-ar", RATE, "-c:a", "pcm_s16le", directory / f"voice-stereo-{language}.wav")
            run("ffmpeg", "-v", "error", "-y", "-i", directory / f"voice-{language}.wav", "-i", music,
                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89:level=disabled",
                "-ar", RATE, "-ac", 2, "-c:a", "pcm_s16le", directory / f"premix-{language}.wav")
        print(f"Finished {engine}: {directory}", flush=True)
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "duration": DURATION,
              "music": "Original instrumental synthesized for this project: 96 BPM; no external samples or songs.",
              "sources": {"local": "Local CPU neural inference with sherpa-onnx 1.13.8: MeloTTS Chinese and Piper LJ Speech, no custom voice cloning",
                          "neural": "Microsoft Edge online neural voices via third-party edge-tts 7.2.8; no cloned voice",
                          "sapi": "Installed Windows System.Speech standard voices, not neural voices"},
              "mixing": "Use separate voice and music stems; bring recorded stream audio up during 11.5–17.5 seconds. Premix excludes recorded stream audio.",
              "timelines": reports}
    (output / "audio-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    preferred = "neural-local" if "local" in reports else "neural" if "neural" in reports else "sapi"
    lines = ["# Promo audio assets", "", f"Duration: {DURATION:.0f} seconds. All WAV assets are 48 kHz / 16-bit.", "",
             f"Available preferred stems: `{preferred}/voice-zh.wav` and `{preferred}/voice-en.wav` with `music-original.wav`.",
             "The `voice-stereo-zh.wav` and `voice-stereo-en.wav` variants are stereo narration stems normalized near -18 LUFS.",
             "The premix files combine narration and music only. Add the recorded YouTube audio during 11.5–17.5s.",
             "SAPI files are an ordinary system-voice backup, not neural AI voiceover.", "",
             "| Time | Picture / action |", "| --- | --- |"]
    for key, start, end, _, _, visual in SEGMENTS:
        lines.append(f"| {start:.2f}–{end:.2f}s | {visual} |")
        if key == "start":
            lines.append("| 11.50–17.50s | No narration. Let the audience hear the real stream and read the actual translated subtitles. |")
    (output / "EDITING.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
