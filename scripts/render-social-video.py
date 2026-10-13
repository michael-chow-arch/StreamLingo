"""Render a truthful 32-second StreamLingo promo from a real YouTube recording.

No recording, downloading, model calls, synthetic demo or publication occurs here.
Normal rendering requires a WebM video with its original audio. Only the explicit
--intro-preview mode may run without it; that mode outputs a 3-second title card.

Examples:
  python scripts/render-social-video.py --intro-preview --language zh-CN --layout vertical
  python scripts/render-social-video.py --video real.webm --start 0 --narration voice-zh.wav \
      --music music-original.wav --language zh-CN --layout vertical --caption-crop 100:650:1000:200
Add --dry-run to validate inputs and write a render plan without running FFmpeg.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "output/social-video"
DURATION, DEMO_START, DEMO_END = 32.0, 3.0, 27.5
DEMO_DURATION = DEMO_END - DEMO_START
BLUE, NAVY = "0x2563eb", "0x0b1220"
URL = "github.com/michael-chow-arch/StreamLingo"


def run(command, *, cwd=None):
    result = subprocess.run([str(value) for value in command], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stderr[-8000:]}")
    return result


def inspect_media(path, ffprobe):
    metadata = json.loads(run([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", path]).stdout)
    durations = []
    for record in [metadata.get("format", {}), *metadata.get("streams", [])]:
        try:
            value = float(record.get("duration", "nan"))
            if math.isfinite(value):
                durations.append(value)
        except ValueError:
            pass
    # Validate each stream independently: a long audio track cannot make a short
    # video pass. Chrome WebM commonly lacks duration and reports 1000/1 fps;
    # packet timestamps provide the end instead of that timebase-derived rate.
    streams = metadata.get("streams", [])
    ends = {}
    for stream in streams:
        try:
            end = float(stream["duration"]) + float(stream.get("start_time", 0))
            if math.isfinite(end):
                ends[stream["index"]] = end
        except (KeyError, TypeError, ValueError):
            pass
    if any(stream["index"] not in ends for stream in streams):
        packets = json.loads(run([ffprobe, "-v", "error", "-show_packets", "-show_entries",
                                  "packet=stream_index,pts_time,duration_time", "-of", "json", path]).stdout)
        for packet in packets.get("packets", []):
            try:
                end = float(packet["pts_time"]) + float(packet.get("duration_time", 0))
                if math.isfinite(end):
                    index = packet["stream_index"]
                    ends[index] = max(ends.get(index, 0), end)
            except (KeyError, TypeError, ValueError):
                pass
    for stream in streams:
        stream["observed_end_seconds"] = ends.get(stream["index"], 0)
    durations.extend(ends.values())
    return metadata, max(durations, default=0.0)


def parse_crop(value):
    try:
        x, y, width, height = (int(part) for part in value.split(":"))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("Use x:y:width:height in original recording pixels")
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("Crop offsets must be nonnegative and dimensions positive")
    return x, y, width, height


def filter_path(path):
    # This is FFmpeg filter syntax escaping, not shell escaping. All commands use
    # subprocess argument lists; text itself is read from UTF-8 files.
    value = path.resolve().as_posix()
    return "'" + value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''") + "'"


def choose_font(language, bold, override):
    if override:
        path = override.resolve()
    elif sys.platform == "win32":
        name = ("msyhbd.ttc" if bold else "msyh.ttc") if language == "zh-CN" else ("segoeuib.ttf" if bold else "segoeui.ttf")
        path = Path("C:/Windows/Fonts") / name
    else:
        raise ValueError("On non-Windows systems supply --font and --font-bold; include CJK glyphs for Chinese")
    if not path.is_file():
        raise ValueError(f"Font is missing: {path}")
    return path


def build_video_graph(args, assets, fonts, size, duration):
    width, height = size
    vertical, chinese = args.layout == "vertical", args.language == "zh-CN"
    graph = []
    current, count = "0:v", 0
    def apply(expression):
        nonlocal current, count
        count += 1
        target = f"canvas{count}"
        graph.append(f"[{current}]{expression}[{target}]")
        current = target
    def text(name, value, y, font_size, *, bold=False, color="white", enable="lt(t,3)", x="(w-text_w)/2", latin=False, cjk=False):
        (assets / f"{name}.txt").write_text(value, encoding="utf-8")
        font = fonts["latin_bold" if bold else "latin"] if latin else fonts["bold" if bold else "regular"]
        if cjk:
            font = fonts["cjk"]
        apply(f"drawtext=fontfile={filter_path(font)}:textfile='{name}.txt':expansion=none:"
              f"fontcolor={color}:fontsize={font_size}:x={x}:y={y}:enable='{enable}'")

    if vertical:
        text("intro-brand", "StreamLingo", 455, 48, bold=True, latin=True)
        if chinese:
            text("hook-a", "看直播，", 650, 118, bold=True)
            text("hook-b", "听不懂？", 815, 118, bold=True)
            text("hook-secondary", "Live stream. Lost in translation?", 1040, 38, latin=True, color="0xdbeafe")
        else:
            text("hook-a", "Live stream.", 620, 100, bold=True)
            text("hook-b", "Lost in", 760, 100, bold=True)
            text("hook-c", "translation?", 900, 100, bold=True)
            text("hook-secondary", "看直播，听不懂？", 1080, 38, cjk=True, color="0xdbeafe")
    else:
        text("intro-brand", "StreamLingo", 250, 48, bold=True, latin=True)
        text("hook-a", "看直播，听不懂？" if chinese else "Live stream. Lost in translation?", 455, 105 if chinese else 84, bold=True)
        if chinese:
            text("hook-secondary", "Live stream. Lost in translation?", 625, 42, latin=True, color="0xdbeafe")
        else:
            text("hook-secondary", "看直播，听不懂？", 625, 42, cjk=True, color="0xdbeafe")
    if args.intro_preview:
        graph.append(f"[{current}]format=yuv420p[vout]")
        return graph

    during = "gte(t,3)*lt(t,27.5)"
    apply(f"drawbox=x=0:y=0:w=iw:h=ih:color={NAVY}:t=fill:enable='{during}'")
    if vertical:
        main_box = (60, 430, 960, 500)
        text("demo-brand", "StreamLingo", 245, 54, bold=True, latin=True, enable=during)
        text("demo-label", "YouTube 回放实录" if chinese else "YouTube playback demo", 355, 38, enable=during)
    else:
        main_box = (80, 135, 1760, 825)
        text("demo-brand", "StreamLingo", 42, 42, bold=True, latin=True, enable=during, x="80")
        text("demo-label", "YouTube 回放实录" if chinese else "YouTube playback demo", 54, 30, enable=during, x="w-text_w-80")
    base = f"[1:v]trim=start={args.start:.6f}:duration={DEMO_DURATION},setpts=PTS-STARTPTS,fps=30"
    if vertical and args.caption_crop:
        graph.append(base + ",split=2[screen][caption_source]")
    else:
        graph.append(base + "[screen]")
    x, y, box_width, box_height = main_box
    screen_crop = ""
    if args.screen_crop:
        sx, sy, sw, sh = args.screen_crop
        screen_crop = f"crop={sw}:{sh}:{sx}:{sy},"
    graph.append(f"[screen]{screen_crop}scale={box_width}:{box_height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                 f"pad={box_width}:{box_height}:(ow-iw)/2:(oh-ih)/2:color={NAVY},setsar=1,setpts=PTS+3/TB[screen_fit]")
    count += 1
    graph.append(f"[{current}][screen_fit]overlay={x}:{y}:eof_action=pass:repeatlast=0:enable='{during}'[canvas{count}]")
    current = f"canvas{count}"
    if vertical and args.caption_crop:
        crop_x, crop_y, crop_width, crop_height = args.caption_crop
        graph.append(f"[caption_source]crop={crop_width}:{crop_height}:{crop_x}:{crop_y},"
                     "scale=880:320:force_original_aspect_ratio=decrease:force_divisible_by=2,"
                     f"pad=880:320:(ow-iw)/2:(oh-ih)/2:color={NAVY},setsar=1,setpts=PTS+3/TB[caption_fit]")
        count += 1
        graph.append(f"[{current}][caption_fit]overlay=100:1050:eof_action=pass:repeatlast=0:enable='{during}'[canvas{count}]")
        current = f"canvas{count}"
        text("crop-label", "同帧真实字幕 · 放大展示" if chinese else "Same-frame captions · enlarged", 990, 32, color="0x93c5fd", enable=during)
    elif vertical:
        text("mode-label", "英语 → 中文" if chinese else "English → Chinese", 1140, 48, enable=during)
    callouts = [(3, 11.5, "选方向，开始字幕" if chinese else "Choose a direction. Start captions."),
                (11.5, 17.5, "听原声，看实际翻译" if chinese else "Original audio. Actual captions."),
                (17.5, 23.4, "支持已有的 Ollama 本地模型" if chinese else "Works with your local Ollama model"),
                (23.4, 27.5, "英 ↔ 中 · 自动识别语言" if chinese else "English ↔ Chinese · Auto detect")]
    for index, (start, end, value) in enumerate(callouts):
        text(f"benefit-{index}", value, 1440 if vertical else 953, 36 if vertical else 30,
             enable=f"gte(t,{start})*lt(t,{end})", color="0x93c5fd")
    text("film-credit", "Tears of Steel / Blender Foundation / CC BY 3.0", 1600 if vertical else 1012,
         27 if vertical else 25, latin=True, color="0xcbd5e1", enable=during)

    outro = "gte(t,27.5)"
    if vertical:
        text("outro-brand", "StreamLingo", 650, 82, bold=True, latin=True, enable=outro)
        text("outro-action", "直播 AI 翻译字幕" if chinese else "Live AI-translated captions", 825, 46, enable=outro)
        text("outro-url-a", "github.com/", 995, 40, latin=True, enable=outro)
        text("outro-url-b", "michael-chow-arch/StreamLingo", 1060, 38, latin=True, enable=outro)
    else:
        text("outro-brand", "StreamLingo", 300, 100, bold=True, latin=True, enable=outro)
        text("outro-action", "直播 AI 翻译字幕" if chinese else "Live AI-translated captions", 490, 48, enable=outro)
        text("outro-url", URL, 650, 48, latin=True, enable=outro)
    graph.append(f"[{current}]format=yuv420p[vout]")
    return graph


def build_audio_graph(args):
    # t for the source clip begins at zero; 8.5–14.5 maps to output 11.5–17.5.
    # These are fixed editorial levels, not automatic side-chain ducking.
    return [
        f"[1:a]atrim=start={args.start:.6f}:duration={DEMO_DURATION},asetpts=PTS-STARTPTS,aresample=48000,"
        "aformat=channel_layouts=stereo,volume='if(between(t,8.5,14.5),1.0,0.10)':eval=frame,"
        "adelay=3000|3000,apad,atrim=duration=32[source_audio]",
        "[2:a]atrim=duration=32,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
        "volume='if(between(t,11.5,17.5),0,1)':eval=frame[narration]",
        "[3:a]atrim=duration=32,asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,"
        "volume='if(between(t,11.5,17.5),0.25,0.70)':eval=frame[music]",
        "[source_audio][narration][music]amix=inputs=3:duration=longest:normalize=0,"
        "alimiter=limit=0.794328:level=0:latency=1,atrim=duration=32[aout]",
    ]


def build_intro_audio_graph(keys):
    graph = []
    labels = []
    for index, key in enumerate(keys, 1):
        label = f"intro_{key}"
        level = 0.70 if key == "music" else 1.0
        graph.append(f"[{index}:a]atrim=duration=3,asetpts=PTS-STARTPTS,aresample=48000,"
                     f"aformat=channel_layouts=stereo,volume={level}[{label}]")
        labels.append(f"[{label}]")
    graph.append("".join(labels) + f"amix=inputs={len(keys)}:duration=longest:normalize=0,"
                 "alimiter=limit=0.794328:level=0:latency=1,atrim=duration=3[aout]")
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", type=Path, help="Real YouTube screen recording, WebM with original audio")
    parser.add_argument("--narration", type=Path, help="32-second timed narration WAV")
    parser.add_argument("--music", type=Path, help="32-second original music WAV")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--layout", choices=("vertical", "horizontal"), default="vertical")
    parser.add_argument("--start", type=float, default=0, help="Start offset in the real recording, seconds; never changes speed")
    parser.add_argument("--caption-crop", type=parse_crop, help="x:y:width:height in source pixels; extra same-frame crop on vertical layout")
    parser.add_argument("--screen-crop", type=parse_crop, help="x:y:width:height in source pixels; remove unrelated page regions from the main view")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--font-bold", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--intro-preview", action="store_true", help="Only a 3-second solid-blue title card; no demo media required")
    parser.add_argument("--dry-run", action="store_true", help="Validate and save plan/text/filter files; do not render")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace this output and its generated assets; never inputs")
    args = parser.parse_args()
    if not math.isfinite(args.start) or args.start < 0:
        parser.error("--start must be a finite nonnegative number")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        parser.error("ffmpeg and ffprobe must be installed and available on PATH")
    size = (1080, 1920) if args.layout == "vertical" else (1920, 1080)
    duration = 3.0 if args.intro_preview else DURATION
    name = f"{'intro-only' if args.intro_preview else 'streamlingo'}-{args.language}-{args.layout}"
    output = (args.output or ROOT / "output/social-video/render" / f"{name}.mp4").resolve()
    if not output.is_relative_to(OUTPUT_ROOT.resolve()):
        parser.error(f"All generated files must remain under {OUTPUT_ROOT}")
    if output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    assets = output.parent / (output.stem + ".assets")
    generated_paths = [output, assets, *(output.with_suffix(suffix) for suffix in (
        ".render-plan.json", ".preview.png", ".ffmpeg.log", ".audio-validation.log"))]
    if any(not path.resolve().is_relative_to(OUTPUT_ROOT.resolve()) for path in generated_paths):
        parser.error("Generated paths must not link outside output/social-video")
    existing = next((path for path in generated_paths if path.exists()), None)
    if existing and not args.overwrite:
        parser.error(f"Refusing to overwrite existing resource: {existing}; choose a new --output or use --overwrite")
    inputs = {}
    input_keys = [key for key in ("narration", "music") if getattr(args, key)] if args.intro_preview else ["video", "narration", "music"]
    if args.intro_preview and args.video:
        parser.error("--intro-preview does not use or show a recording; omit --video")
    if input_keys:
        for key in input_keys:
            path = getattr(args, key)
            if path is None or not path.is_file() or path.stat().st_size == 0:
                parser.error(f"--{key} must name an existing nonempty real input file")
            setattr(args, key, path.resolve())
            if path.resolve() in generated_paths or path.resolve().is_relative_to(assets.resolve()):
                parser.error("Generated resources must not replace an input")
        if not args.intro_preview and args.video.suffix.lower() != ".webm":
            parser.error("--video must be the original real .webm recording")
        if any(getattr(args, key).suffix.lower() != ".wav" for key in input_keys if key != "video"):
            parser.error("Narration and original music must be WAV files")
        for key in input_keys:
            path = getattr(args, key)
            metadata, length = inspect_media(path, ffprobe)
            streams = metadata.get("streams", [])
            audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
            if audio is None:
                parser.error(f"{key} has no audio stream; record original tab audio for the real demo")
            required = args.start + DEMO_DURATION if key == "video" else duration
            if audio["observed_end_seconds"] + 0.03 < required:
                parser.error(f"{key} audio is too short ({audio['observed_end_seconds']:.3f}s); need at least {required:.3f}s; no looping or freeze-fill")
            inputs[key] = {"path": str(path), "duration_seconds": length,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            if key == "video":
                video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
                if video is None:
                    parser.error("--video must have a real video stream")
                if video["observed_end_seconds"] + 0.04 < required:
                    parser.error(f"Video is too short ({video['observed_end_seconds']:.3f}s); need at least {required:.3f}s; no freeze-fill")
                for crop_name in ("caption_crop", "screen_crop"):
                    crop = getattr(args, crop_name)
                    if crop:
                        x, y, width, height = crop
                        if x + width > video["width"] or y + height > video["height"]:
                            parser.error(f"{crop_name} falls outside {video['width']}×{video['height']} source")
                inputs[key].update(width=video["width"], height=video["height"], video_end_seconds=video["observed_end_seconds"], audio_end_seconds=audio["observed_end_seconds"])
    fonts = {"regular": choose_font(args.language, False, args.font), "bold": choose_font(args.language, True, args.font_bold),
             "latin": choose_font("en", False, args.font), "latin_bold": choose_font("en", True, args.font_bold),
             "cjk": choose_font("zh-CN", False, args.font)}
    assets.mkdir(parents=True, exist_ok=True)
    graph = build_video_graph(args, assets, fonts, size, duration)
    command = [ffmpeg, "-hide_banner", "-nostdin", "-y" if args.overwrite else "-n", "-f", "lavfi", "-i", f"color=c={BLUE}:s={size[0]}x{size[1]}:r=30:d={duration}"]
    for key in input_keys:
        command.extend(["-i", str(getattr(args, key))])
    if not args.intro_preview:
        graph.extend(build_audio_graph(args))
    elif input_keys:
        graph.extend(build_intro_audio_graph(input_keys))
    filter_file = assets / "filtergraph.txt"
    filter_file.write_text(";\n".join(graph), encoding="utf-8")
    command.extend(["-filter_complex_script", str(filter_file), "-map", "[vout]"])
    command.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"] if input_keys else ["-an"])
    command.extend(["-t", str(duration), "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-color_primaries", "bt709", "-color_trc", "bt709",
                    "-colorspace", "bt709", "-metadata", "title=StreamLingo — " + ("intro preview only" if args.intro_preview else "YouTube playback demo"), str(output)])
    plan = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "kind": "intro-preview-only" if args.intro_preview else "real-recording-promo",
            "language": args.language, "layout": args.layout, "output": str(output), "dimensions": size, "duration_seconds": duration,
            "source_start_seconds": args.start, "source_speed": 1.0, "inputs": inputs, "caption_crop": args.caption_crop, "screen_crop": args.screen_crop,
            "caption_method": "Same input video split; crop and scale only, no retyped or generated transcript",
            "original_audio_foreground_seconds": None if args.intro_preview else [11.5, 17.5], "sample_peak_limiter_dbfs": -2,
            "layout_review": "Vertical caption crop ends at y=1370; preview on each target platform before publishing.",
            "cwd": str(assets), "command": command, "dry_run": args.dry_run,
            "verification_scope": "Input file identity/streams checked; the renderer cannot independently prove capture provenance or ASR correctness."}
    plan_path = output.with_suffix(".render-plan.json")
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"plan": str(plan_path), "filtergraph": str(filter_file), "rendered": False}, ensure_ascii=False))
        return
    render = run(command, cwd=assets)
    output.with_suffix(".ffmpeg.log").write_text(render.stderr, encoding="utf-8")
    metadata, length = inspect_media(output, ffprobe)
    if abs(length - duration) > .1:
        raise RuntimeError(f"Output duration mismatch: {length}; expected {duration}")
    screenshot = output.with_suffix(".preview.png")
    run([ffmpeg, "-hide_banner", "-nostdin", "-y" if args.overwrite else "-n", "-ss", "1.5", "-i", output, "-frames:v", "1", "-update", "1", screenshot])
    validation = {"duration_seconds": length, "streams": [{key: stream.get(key) for key in ("codec_type", "codec_name", "width", "height", "sample_rate")}
                                                         for stream in metadata["streams"]], "intro_screenshot": str(screenshot)}
    if input_keys:
        audio_log = run([ffmpeg, "-hide_banner", "-nostdin", "-i", output, "-vn", "-af", "volumedetect", "-f", "null", "-"]).stderr
        output.with_suffix(".audio-validation.log").write_text(audio_log, encoding="utf-8")
        peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", audio_log)
        if not peak or float(peak[1]) >= 0:
            raise RuntimeError("Final AAC audio peak check failed; inspect the saved audio validation log")
        validation["decoded_audio_peak_dbfs"] = float(peak[1])
    plan["validation"] = validation
    plan["rendered"] = True
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "plan": str(plan_path), **validation}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc))
