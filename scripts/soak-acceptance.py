"""Prepare original System.Speech fixtures and run real-time, real-model soak tests.

prepare synthesizes locally; describe/self-test/review never connect. run defaults to
two sequential sessions, en->zh-CN then zh->en, each at least 30 minutes of speech.
review --input summary.json prints a read-only reassessment without modifying it.
No server lifecycle or Ollama model installation is performed by this script.
"""

import argparse
import asyncio
from collections import Counter
from contextlib import suppress
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from time import monotonic
from uuid import uuid4
import wave

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "output/release-acceptance/fixtures"
BPS, PACKET = 32000, 5120
TOPICS = [
    ("a neighborhood library", "books are easier to find near clear signs", "move the information desk closer to the entrance", "社区图书馆", "清楚的标志让读者更容易找到书籍", "把咨询台移到入口附近"),
    ("a shared vegetable garden", "young plants grow differently in shaded soil", "compare watering schedules in two small beds", "共享菜园", "幼苗在阴凉土壤中的生长速度不同", "比较两块小菜地的浇水时间"),
    ("a local train journey", "travelers need more time to change platforms", "put simple directions beside the ticket machines", "本地火车旅行", "旅客换站台需要更充足的时间", "在售票机旁增加简单的路线说明"),
    ("a weekend cooking class", "fresh vegetables need very little seasoning", "prepare the ingredients before heating the pan", "周末烹饪课", "新鲜蔬菜只需要少量调料", "在热锅之前准备好全部食材"),
    ("a small bicycle workshop", "a loose brake cable changes the feel of the ride", "check each wheel before adjusting the brakes", "小型自行车维修活动", "松动的刹车线会影响骑行感受", "先检查两个车轮再调整刹车"),
    ("a science exhibition", "children understand an experiment after trying it themselves", "place a short explanation beside each activity", "科学展览", "孩子亲手尝试以后更容易理解实验", "给每项活动配上简短的说明"),
    ("a walking route by the river", "some paths stay wet after the rain has stopped", "mark the dry route on a new visitor map", "河边步行路线", "雨停以后部分小路仍然很湿", "在新的游客地图上标出干燥的路线"),
    ("a music rehearsal", "the quiet instruments disappear when everyone plays loudly", "listen to each section before playing together", "音乐排练", "大家同时大声演奏时轻柔的乐器容易被盖住", "先分别听各组演奏再进行合练"),
    ("a school reading program", "students enjoy choosing their own stories", "offer several books with different reading levels", "学校阅读计划", "学生喜欢自己选择感兴趣的故事", "准备几种难度不同的读物"),
    ("a community weather station", "nearby walls can change a temperature reading", "move the sensor away from the sunny wall", "社区气象站", "附近的墙面可能影响温度读数", "把传感器移到远离向阳墙面的位置"),
    ("a museum visit", "people spend longer near objects with a clear story", "connect each display to a familiar everyday question", "博物馆参观", "有清楚故事的展品会让观众停留更久", "把每件展品和日常生活中的问题联系起来"),
    ("a furniture repair project", "the original wood is stronger than it first appears", "clean the joints before applying fresh glue", "家具修复项目", "原来的木材比最初看起来更加结实", "先清理接缝再涂上新的胶水"),
    ("a public speaking workshop", "a short pause helps an audience follow a difficult idea", "practice one clear example before adding more details", "公开演讲练习", "适当停顿能帮助听众理解复杂的想法", "先练习一个清楚的例子再补充细节"),
    ("a neighborhood bakery", "bread cools more evenly on an open rack", "leave enough space between the warm loaves", "社区面包店", "面包放在通风架上能够更均匀地冷却", "让刚出炉的面包之间保持足够距离"),
    ("a coastal cleanup", "small pieces of plastic gather behind the rocks", "separate reusable tools from collected waste", "海岸清理活动", "细小的塑料碎片容易聚集在岩石后面", "把可重复使用的工具和收集的垃圾分开放置"),
    ("an evening astronomy club", "bright streetlights make faint stars harder to see", "choose a darker meeting place with a clear horizon", "夜间天文活动", "明亮的路灯会让微弱的星光难以看清", "选择光线较暗而且视野开阔的集合地点"),
    ("a local history interview", "old photographs help people remember everyday details", "ask open questions and leave time for an answer", "地方历史访谈", "老照片能帮助人们回忆日常生活的细节", "提出开放的问题并留出充分回答时间"),
    ("a park picnic", "families need both shade and room to play", "keep the walking path clear while arranging the tables", "公园野餐", "家庭既需要阴凉处也需要活动空间", "摆放桌子时保持步行道路畅通"),
    ("a simple software prototype", "clear labels prevent many avoidable mistakes", "test the main task before adding extra features", "简单软件原型", "清楚的标签能够避免许多不必要的操作错误", "先测试主要任务再增加其他功能"),
    ("a family photo collection", "dates become confusing when albums are separated", "write a short description beside each scanned picture", "家庭照片整理", "相册分散保存以后日期很容易混淆", "给每张扫描的照片补充简短说明"),
    ("a volunteer delivery service", "short messages help drivers find unfamiliar doors", "confirm the meeting point before leaving the office", "志愿配送服务", "简短的信息能帮助司机找到陌生的入口", "离开办公室之前确认交接地点"),
    ("a language exchange group", "ordinary conversations build confidence over time", "choose a familiar topic and let everyone finish speaking", "语言交流小组", "日常交谈能够逐渐建立表达信心", "选择熟悉的话题并让每个人把话说完"),
    ("a neighborhood sports day", "beginners join more easily when the rules are simple", "show the activity slowly before starting the game", "社区运动会", "规则简单时初学者更容易参与", "正式比赛之前先慢慢演示活动步骤"),
    ("a recycling lesson", "similar containers may need different treatment", "compare the labels before sorting the empty packages", "回收分类课程", "外观相似的容器可能需要不同处理方式", "分类空包装之前先比较上面的标志"),
]


def corpus():
    people = [("Anna", "小林"), ("David", "小陈"), ("Emma", "小周"), ("James", "小李"),
              ("Sarah", "小王"), ("Michael", "小张"), ("Helen", "小赵"), ("Peter", "小吴")]
    settings = [("on a quiet Monday morning", "在安静的周一早上"), ("during a cloudy afternoon", "在一个阴天的下午"),
                ("after the weekend meeting", "在周末会议结束以后"), ("before the evening discussion", "在晚间讨论之前"),
                ("during the spring workshop", "在春季工作坊期间"), ("after a short lunch break", "在简短的午休以后"),
                ("at the beginning of the summer program", "在暑期活动开始的时候"), ("during an autumn planning session", "在秋季计划讨论期间")]
    result = {"en": [], "zh": []}
    # Topic and scene change every paragraph. Templates supply original
    # controlled prose with varied details, never a repeated audio loop.
    for turn in range(16):
        for index in range(len(TOPICS)):
            topic = TOPICS[(index * 7 + turn) % len(TOPICS)]
            person, chinese_person = people[(index + turn) % len(people)]
            setting, chinese_setting = settings[(index // 8 + turn) % len(settings)]
            detail = ("a paper notebook" if turn < 8 else "a simple wall chart")
            zh_detail = "纸质笔记本" if turn < 8 else "简易记录板"
            en = (f"{person} is reviewing {topic[0]} {setting}. "
                  f"While discussing this project, {person} explains that {topic[1]}. "
                  f"For this visit {setting}, the group decides to {topic[2]}. "
                  f"Their observations about {topic[0]} go into {detail}, so {person} can compare practical results with the original plan.")
            zh = (f"{chinese_setting}，{chinese_person}正在讨论{topic[3]}。"
                  f"谈到这个项目时，{chinese_person}说明了一个发现：{topic[4]}。"
                  f"这次{chinese_setting[1:]}，小组决定{topic[5]}。"
                  f"关于{topic[3]}的观察会写进{zh_detail}，方便{chinese_person}比较实际结果与原来的计划。")
            if en not in result["en"]:
                result["en"].append(en)
            if zh not in result["zh"]:
                result["zh"].append(zh)
    # Entire paragraphs must differ. Reusable connective wording is expected
    # in controlled narration and remains in the reference for human review.
    for language, paragraphs in result.items():
        if len(paragraphs) < 120 or len(set(paragraphs)) != len(paragraphs):
            raise ValueError(f"Insufficient distinct {language} paragraphs")
    return result


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def prepare(args):
    args.fixtures.mkdir(parents=True, exist_ok=True)
    write_json(args.fixtures / "corpus.json", corpus())
    for language in (("en", "zh") if args.languages == "both" else (args.languages,)):
        subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts/synthesize-soak.ps1"), "-Corpus", str(args.fixtures / "corpus.json"),
                        "-OutputDirectory", str(args.fixtures), "-MinimumSeconds", str(args.minimum_seconds),
                        "-Languages", language], check=True)
        directory = args.fixtures / language
        manifest = json.loads((directory / "paragraphs.json").read_text(encoding="utf-8-sig"))
        frames = 0
        destination = directory / "speech.wav"
        with wave.open(str(destination), "wb") as merged:
            merged.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            for paragraph in manifest["paragraphs"]:
                with wave.open(str(directory / paragraph["file"]), "rb") as audio:
                    if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
                        raise ValueError("System.Speech produced an unexpected format")
                    pcm = audio.readframes(audio.getnframes())
                paragraph["start_s"] = frames / 16000
                paragraph["duration_s"] = len(pcm) / BPS
                frames += len(pcm) // 2
                merged.writeframesraw(pcm)
        sentences = [s.strip() for p in manifest["paragraphs"] for s in re.split(r"(?<=[.!?。！？])\s*", p["text"]) if s.strip()]
        manifest.update(duration_s=frames / 16000, wav_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                        repeated_complete_paragraphs=0, repeated_sentence_templates=len(sentences) - len(set(sentences)), looped_audio=False)
        write_json(directory / "manifest.json", manifest)
        (directory / "reference.txt").write_text("\n\n".join(p["text"] for p in manifest["paragraphs"]), encoding="utf-8")
        print(f"Prepared {language}: {frames / 16000:.3f}s, {len(manifest['paragraphs'])} distinct paragraphs", flush=True)


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, max(0, math.ceil(len(ordered) * percent / 100) - 1))], 3)


def normalize(text):
    return "".join(re.findall(r"[a-z0-9\u3400-\u9fff]+", text.casefold()))


def repetition_diagnostics(latest, reference):
    candidates = []
    finals = sorted((e for e in latest.values() if e.get("source_final")), key=lambda e: e["segment_id"])
    for field in ("source", "translation"):
        previous, run = "", []
        for event in finals:
            text = event["source_text"] if field == "source" else event.get("translation", {}).get("text") or ""
            key = normalize(text)
            if len(key) >= 6 and key == previous:
                run.append(event["segment_id"])
            else:
                if len(run) >= 3:
                    candidates.append({"kind": "consecutive_identical_segments", "field": field, "segment_ids": run,
                                       "normalized_text": previous, "reference_occurrences": normalize(reference).count(previous) if field == "source" else None})
                previous, run = key, [event["segment_id"]]
            # Three adjacent repetitions within a cue, ignoring spaces/case.
            match = re.search(r"(.{6,80}?)\1{2,}", key)
            if match:
                candidates.append({"kind": "phrase_repeated_within_segment", "field": field,
                                   "segment_ids": [event["segment_id"]], "normalized_phrase": match[1],
                                   "repetitions": len(match[0]) // len(match[1])})
        if len(run) >= 3:
            candidates.append({"kind": "consecutive_identical_segments", "field": field,
                               "segment_ids": run, "normalized_text": previous})
    return {"diagnostic_only": True, "candidates": candidates,
            "note": "Candidates require review; no output is filtered. Rephrased translations and legitimate repeats are not automatically accuracy failures."}


def metrics(events, latest, speech_seconds):
    first_final, completed = {}, {}
    for event in events:
        if event.get("type") != "subtitle" or not event.get("source_final"):
            continue
        first_final.setdefault(event["segment_id"], event)
        translation = event.get("translation", {})
        if (translation.get("status") == "complete" and translation.get("is_mock") is False
                and isinstance(translation.get("text"), str) and translation["text"].strip()):
            completed.setdefault(event["segment_id"], event)
    times = [event["stream_after_s"] for event in completed.values() if 0 <= event.get("stream_after_s", -1) <= speech_seconds]
    final_times = [event["stream_after_s"] for event in first_final.values() if 0 <= event.get("stream_after_s", -1) <= speech_seconds]
    states = Counter(event.get("translation", {}).get("status", "missing") for event in latest.values() if event.get("source_final"))
    windows = [{"start_s": start, "end_s": min(start + 60, speech_seconds),
                "complete_arrivals": sum(start <= t < min(start + 60, speech_seconds) for t in times),
                "final_arrivals": sum(start <= t < min(start + 60, speech_seconds) for t in final_times)}
               for start in range(0, math.ceil(speech_seconds), 60)]
    boundaries = [0.0, *sorted(times), speech_seconds]
    latencies = [e["stream_after_s"] - e["end_ms"] / 1000 for e in completed.values() if "stream_after_s" in e]
    return {"completed": len(completed), "failed": states["error"], "skipped": states["skipped"],
            "pending": states["pending"], "disabled": states["disabled"], "final_segments": len(first_final),
            "partial_segments": sum(not e.get("source_final") for e in latest.values()),
            "first_final_s": min(final_times) if final_times else None,
            "first_complete_s": min(times) if times else None,
            "completed_during_speech": len(times),
            "max_complete_gap_during_speech_s": round(max((b - a for a, b in zip(boundaries, boundaries[1:])), default=0), 3),
            "end_to_complete_delay_s": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95), "max": percentile(latencies, 100)},
            "minute_windows": windows}


def translation_integrity(events):
    """Reconcile IDs, not just counts; every final must receive a real nonempty text."""
    final_ids, completed_ids, invalid = set(), set(), []
    for event in events:
        if event.get("type") != "subtitle":
            continue
        segment_id = event["segment_id"]
        if event.get("source_final") is True:
            final_ids.add(segment_id)
        translation = event.get("translation", {})
        if translation.get("status") != "complete":
            continue
        reasons = []
        if event.get("source_final") is not True:
            reasons.append("complete requires a final source")
        if translation.get("is_mock") is not False:
            reasons.append("complete must be explicitly non-mock")
        if not isinstance(translation.get("text"), str) or not translation["text"].strip():
            reasons.append("complete requires nonempty text")
        if reasons:
            invalid.append({"segment_id": segment_id, "revision": event.get("revision"), "reasons": reasons})
        else:
            completed_ids.add(segment_id)
    missing = sorted(final_ids - completed_ids)
    return {"passed": bool(final_ids) and not missing and not invalid,
            "final_segment_count": len(final_ids), "valid_complete_segment_count": len(completed_ids),
            "missing_translation_segment_ids": missing, "invalid_completions": invalid}


def assess_recording(report, max_translation_gap=20, max_send_lateness=1):
    """Shared live/offline verdict. Rebuild translation evidence from raw events."""
    events = report["events"]
    latest = {event["segment_id"]: event for event in events if event.get("type") == "subtitle"}
    values = metrics(events, latest, report["metadata"]["speech_seconds"])
    integrity = translation_integrity(events)
    # Reassessment must not erase a previously recorded failure.
    failures = list(report.get("acceptance_failures", []))
    if not report.get("feed_finished"):
        failures.append("The whole speech fixture and tail were not sent")
    if not report.get("stopped_acknowledged"):
        failures.append("No normal stop acknowledgement")
    if (report.get("errors") or report.get("violations") or report.get("disconnects") or report.get("failure")
            or report.get("interrupted") or any(event.get("type") == "error" for event in events)):
        failures.append("Errors, protocol violations, disconnects, or exception recorded")
    if (not integrity["passed"] or values["failed"] or values["skipped"] or values["pending"]
            or values["disabled"] or values["partial_segments"]):
        failures.append("Missing, invalid, failed, skipped or unfinished real translations")
    if values["max_complete_gap_during_speech_s"] > max_translation_gap:
        failures.append("Translation arrival gap exceeded the acceptance limit")
    if any(w["end_s"] - w["start_s"] >= 15 and (not w["complete_arrivals"] or not w["final_arrivals"])
           for w in values["minute_windows"]):
        failures.append("A speech minute lacked final/complete arrivals")
    if report["max_send_lateness_s"] > max_send_lateness:
        failures.append("Client could not sustain real-time sending within pacing tolerance")
    failures = list(dict.fromkeys(failures))
    return {"passed": not failures, "acceptance_failures": failures,
            "continuous_metrics": values, "translation_integrity": integrity}


def review(path, max_translation_gap=20, max_send_lateness=1):
    """Read and print only: no optional inference imports, network or writes."""
    raw = path.read_bytes()
    report = json.loads(raw)
    assessment = assess_recording(report, max_translation_gap, max_send_lateness)
    result = {"validation_kind": "offline reassessment of recorded events; no model or browser execution",
              "input_path": str(path.resolve()), "input_sha256": hashlib.sha256(raw).hexdigest(),
              "session_id": report["session_id"], "original_passed": report.get("passed"),
              "thresholds": {"max_translation_gap_s": max_translation_gap, "max_send_lateness_s": max_send_lateness},
              "quality_review_required": report.get("quality_review_required"), **assessment}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


class NumericServiceLog:
    def __init__(self, path):
        self.path, self.offset, self.values = path, None, []

    def begin(self):
        if self.path and self.path.is_file():
            self.offset = self.path.stat().st_size

    def sample(self):
        if self.offset is None or not self.path.is_file():
            return
        with self.path.open("rb") as handle:
            if self.path.stat().st_size < self.offset:
                self.values.append({"log_truncated": True})
                self.offset = 0
            handle.seek(self.offset)
            data = handle.read()
            # Keep an incomplete final line for the next pass.
            end = data.rfind(b"\n") + 1
            self.offset += end
        for line in data[:end].decode("utf-8", errors="replace").splitlines():
            match = re.search(r"internal_buffer=([\d.]+)s\s*\|\s*lag=([\d.]+)s", line)
            if match:
                self.values.append({"internal_buffer_seconds": float(match[1]), "raw_audio_lag_seconds": float(match[2])})
            if "ASR_BACKLOG" in line:
                values = {key: float(value) for key, value in re.findall(r"(\w+)=([\d.]+)", line)}
                self.values.append({"fatal_asr_backlog": values})

    def summary(self):
        self.sample()
        return {"path": str(self.path) if self.path else None, "available": self.offset is not None,
                "samples": len(self.values),
                "max_upstream_raw_audio_lag_s": max((e.get("raw_audio_lag_seconds", 0) for e in self.values), default=None),
                "max_internal_buffer_s": max((e.get("internal_buffer_seconds", 0) for e in self.values), default=None),
                "fatal_backlog_records": [e for e in self.values if "fatal_asr_backlog" in e],
                "note": "Upstream raw audio lag includes silence; only ASR_BACKLOG speech_backlog_seconds is the service voiced backlog guard."}


async def run_one(args, language, output):
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed
    import httpx
    directory = args.fixtures / language
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    wav_path = directory / "speech.wav"
    with wave.open(str(wav_path), "rb") as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Expected 16 kHz mono PCM16 fixture")
        speech_seconds = audio.getnframes() / 16000
    if speech_seconds < args.minimum_seconds or manifest.get("looped_audio") is not False:
        raise ValueError("Fixture is too short or is not a declared non-looped original speech fixture")
    if hashlib.sha256(wav_path.read_bytes()).hexdigest() != manifest["wav_sha256"]:
        raise ValueError("Fixture hash mismatch")
    reference = (directory / "reference.txt").read_text(encoding="utf-8")
    output.mkdir(parents=True, exist_ok=False)
    session_id, started = str(uuid4()), monotonic()
    target = "zh-CN" if language == "en" else "en"
    report = {"session_id": session_id, "events": [], "passed": False,
              "metadata": {"source_language": language, "target_language": target, "fixture": str(wav_path),
                           "fixture_sha256": manifest["wav_sha256"], "voice": manifest["voice"],
                           "speech_seconds": speech_seconds, "tail_silence_seconds": args.tail_seconds,
                           "started_at_utc": datetime.now(timezone.utc).isoformat(), "is_chrome_test": False},
              "errors": [], "violations": [], "disconnects": [], "stopped_acknowledged": False}
    latest, stream_begin, sender = {}, None, None
    bytes_sent, max_send_lateness, feed_finished, last_subtitle_at = 0, 0.0, None, None
    log = NumericServiceLog(args.service_log)
    raw = (output / "events.jsonl").open("w", encoding="utf-8", buffering=1)

    def record(event):
        nonlocal last_subtitle_at
        item = {**event, "received_after_s": round(monotonic() - started, 6)}
        if stream_begin is not None:
            item["stream_after_s"] = round(monotonic() - stream_begin, 6)
        report["events"].append(item)
        raw.write(json.dumps(item, ensure_ascii=False) + "\n")
        if event.get("session_id") not in (None, session_id):
            report["violations"].append("Message belongs to another session")
        if event.get("type") == "error":
            report["errors"].append(item)
        if event.get("type") == "subtitle":
            last_subtitle_at = monotonic()
            previous = latest.get(event["segment_id"])
            if previous and event["revision"] <= previous["revision"]:
                report["violations"].append(f"Non-increasing revision for {event['segment_id']}")
            if previous and previous["source_final"] and any(previous[k] != event[k] for k in ("source_final", "source_text", "start_ms", "end_ms")):
                report["violations"].append(f"Final source mutated for {event['segment_id']}")
            if event.get("source_language") != language or event.get("target_language") != target:
                report["violations"].append("Wrong subtitle language metadata")
            if event.get("translation", {}).get("status") == "complete" and event["translation"].get("is_mock") is not False:
                report["violations"].append("Mock completion in real-model test")
            if event.get("translation", {}).get("status") == "complete" and (
                    not isinstance(event["translation"].get("text"), str) or not event["translation"]["text"].strip()):
                report["violations"].append(f"Empty or non-text completion for {event['segment_id']}")
            latest[event["segment_id"]] = item

    def progress():
        elapsed = monotonic() - started
        view = {"session_id": session_id, "language": language, "elapsed_s": round(elapsed, 3),
                "audio_sent_s": round(bytes_sent / BPS, 3), "planned_speech_s": speech_seconds,
                "events": len(report["events"]), "errors": len(report["errors"]),
                "metrics": metrics(report["events"], latest, min(speech_seconds, bytes_sent / BPS)),
                "service_backlog": log.summary()}
        write_json(output / "progress.json", view)
        print(json.dumps({k: v for k, v in view.items() if k not in ("metrics", "service_backlog")} |
                         {"complete": view["metrics"]["completed"], "failed": view["metrics"]["failed"], "skipped": view["metrics"]["skipped"]}), flush=True)

    try:
        async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
            health = (await client.get(args.health_url)).json()
        report["health_before"] = health
        if health.get("mode") != "whisperlivekit" or health.get("status") != "ready" or health.get("translation") != "configured":
            raise RuntimeError("Real ASR and configured Ollama must already be ready")
        async with connect(args.url, origin=args.origin, open_timeout=10, close_timeout=5, max_queue=64) as ws:
            await ws.send(json.dumps({"type": "start", "protocol_version": 1, "session_id": session_id,
                                      "source_language": language, "target_language": target,
                                      "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1}}))
            ready = json.loads(await asyncio.wait_for(ws.recv(), 20))
            record(ready)
            if ready.get("type") != "ready" or ready.get("mode") != "whisperlivekit" or ready.get("translation") != "configured":
                raise RuntimeError(f"Session not accepted as real-model mode: {ready.get('code', ready.get('type'))}")
            if ready.get("source_language") != language or ready.get("target_language") != target:
                raise RuntimeError("Incorrect acknowledged language direction")
            log.begin()
            stream_begin = monotonic()

            async def feed():
                nonlocal bytes_sent, max_send_lateness, feed_finished
                async def send_packet(pcm):
                    nonlocal bytes_sent, max_send_lateness
                    deadline = stream_begin + bytes_sent / BPS
                    await asyncio.sleep(max(0, deadline - monotonic()))
                    max_send_lateness = max(max_send_lateness, monotonic() - deadline)
                    await asyncio.wait_for(ws.send(pcm), 5)
                    bytes_sent += len(pcm)
                with wave.open(str(wav_path), "rb") as audio:
                    while pcm := audio.readframes(PACKET // 2):
                        await send_packet(pcm)
                await asyncio.sleep(max(0, stream_begin + bytes_sent / BPS - monotonic()))
                report["speech_send_wall_seconds"] = round(monotonic() - stream_begin, 6)
                remaining = round(args.tail_seconds * BPS)
                while remaining:
                    size = min(PACKET, remaining)
                    await send_packet(bytes(size))
                    remaining -= size
                await asyncio.sleep(max(0, stream_begin + bytes_sent / BPS - monotonic()))
                feed_finished = monotonic()

            sender = asyncio.create_task(feed())
            next_progress = monotonic() + 60
            try:
                deadline = stream_begin + speech_seconds + args.tail_seconds + args.drain_seconds + 20
                while monotonic() < deadline:
                    if sender.done():
                        sender.result()
                    if monotonic() >= next_progress:
                        progress()
                        next_progress = monotonic() + 60
                    if feed_finished is not None:
                        pending = any(e.get("translation", {}).get("status") == "pending" or not e.get("source_final") for e in latest.values())
                        idle = monotonic() - (last_subtitle_at or feed_finished)
                        if not pending and idle >= 3:
                            break
                        if monotonic() - feed_finished >= args.drain_seconds:
                            report["violations"].append("Drain deadline exceeded with unfinished segments")
                            break
                    try:
                        event = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                    except asyncio.TimeoutError:
                        continue
                    record(event)
                    if event.get("type") == "error" and event.get("fatal"):
                        raise RuntimeError(f"Fatal service error: {event.get('code')}")
                    if event.get("type") == "stopped":
                        raise RuntimeError("Service stopped before client requested stop")
                else:
                    raise RuntimeError("Session deadline exceeded")
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await sender
                try:
                    await ws.send(json.dumps({"type": "stop", "session_id": session_id}))
                    async with asyncio.timeout(10):
                        while True:
                            event = json.loads(await ws.recv())
                            record(event)
                            if event.get("type") == "stopped":
                                report["stopped_acknowledged"] = True
                                break
                except (ConnectionClosed, asyncio.TimeoutError) as exc:
                    report["disconnects"].append({"phase": "stop", "type": type(exc).__name__, "detail": str(exc)})
    except BaseException as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, ConnectionClosed):
            report["disconnects"].append({"phase": "stream", "type": type(exc).__name__, "detail": str(exc)})
        if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError)):
            report["interrupted"] = True
    finally:
        if sender is not None and not sender.done():
            sender.cancel()
            with suppress(asyncio.CancelledError):
                await sender
        report["elapsed_seconds"] = round(monotonic() - started, 6)
        report["audio_sent_seconds"] = round(bytes_sent / BPS, 6)
        report["max_send_lateness_s"] = round(max_send_lateness, 6)
        report["feed_finished"] = feed_finished is not None
        report["continuous_metrics"] = metrics(report["events"], latest, speech_seconds)
        report["service_backlog"] = log.summary()
        report["repetition_review"] = repetition_diagnostics(latest, reference)
        report["latest_segments"] = list(latest.values())
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        report.update(assess_recording(report, args.max_translation_gap, args.max_send_lateness))
        # Keep an explicit quality-review flag separate from transport success.
        report["quality_review_required"] = bool(report["repetition_review"]["candidates"])
        progress()
        write_json(output / "service-numeric-samples.json", log.values)
        write_json(output / "summary.json", report)
        raw.close()
    return report


async def run(args):
    output = args.output or ROOT / "output/release-acceptance" / datetime.now().strftime("soak-%Y%m%d-%H%M%S")
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    for language in (("en", "zh") if args.languages == "both" else (args.languages,)):
        try:
            report = await run_one(args, language, output / language)
            runs.append({"language": language, "passed": report["passed"], "quality_review_required": report["quality_review_required"],
                         "report": str(output / language / "summary.json"), "elapsed_seconds": report["elapsed_seconds"],
                         "interrupted": report.get("interrupted", False)})
        except Exception as exc:
            runs.append({"language": language, "passed": False, "failure": f"{type(exc).__name__}: {exc}"})
        write_json(output / "suite.json", {"passed": all(r["passed"] for r in runs), "runs": runs})
        if runs[-1].get("interrupted") or (not runs[-1]["passed"] and not args.continue_on_failure):
            break
    expected = 2 if args.languages == "both" else 1
    passed = len(runs) == expected and all(r["passed"] for r in runs)
    write_json(output / "suite.json", {"passed": passed, "expected_sessions": expected, "runs": runs})
    print(f"{'PASS' if passed else 'FAIL'}: {output / 'suite.json'}", flush=True)
    return passed


def describe(args):
    languages = ("en", "zh") if args.languages == "both" else (args.languages,)
    records = []
    for language in languages:
        manifest = json.loads((args.fixtures / language / "manifest.json").read_text(encoding="utf-8"))
        records.append({"source_language": language, "target_language": "zh-CN" if language == "en" else "en",
                        "speech_seconds": manifest["duration_s"], "paragraphs": len(manifest["paragraphs"]),
                        "voice": manifest["voice"], "tail_silence_seconds": args.tail_seconds,
                        "maximum_drain_seconds": args.drain_seconds})
    print(json.dumps({"connects_to_service": False, "sessions": records}, ensure_ascii=False, indent=2))


def self_test():
    passages = corpus()
    assert len(passages["en"]) == len(passages["zh"]) >= 120
    assert len(set(passages["en"])) == len(passages["en"])
    events, latest = [], {}
    for identifier, timestamp, status in ((1, 2.0, "complete"), (2, 5.0, "skipped"), (3, 9.0, "error")):
        event = {"type": "subtitle", "segment_id": identifier, "source_final": True, "end_ms": identifier * 1000,
                 "source_text": "controlled speech", "stream_after_s": timestamp,
                 "translation": {"status": status, "text": "test output" if status == "complete" else None, "is_mock": False}}
        events.append(event); latest[identifier] = event
    result = metrics(events, latest, 10)
    assert (result["completed"], result["skipped"], result["failed"]) == (1, 1, 1)
    assert result["first_complete_s"] == 2 and result["max_complete_gap_during_speech_s"] == 8
    assert repetition_diagnostics(latest, "")['candidates']
    print("Offline self-test passed: corpus uniqueness, failure counts, timing and repetition diagnostics. No network/model calls.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "describe", "run", "self-test", "review"))
    parser.add_argument("--input", type=Path, help="Existing summary.json for read-only offline review")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--minimum-seconds", type=float, default=1800)
    parser.add_argument("--languages", choices=("en", "zh", "both"), default="both")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--url", default="ws://127.0.0.1:8765/ws/live")
    parser.add_argument("--health-url", default="http://127.0.0.1:8765/health")
    parser.add_argument("--origin", default="chrome-extension://ggakbplmndfijhdcepbafoibilffbhmg")
    parser.add_argument("--service-log", type=Path, default=ROOT / "output/service/stderr.log")
    parser.add_argument("--tail-seconds", type=float, default=12)
    parser.add_argument("--drain-seconds", type=float, default=30)
    parser.add_argument("--max-translation-gap", type=float, default=20)
    parser.add_argument("--max-send-lateness", type=float, default=1)
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    if not all(math.isfinite(value) and value > 0 for value in (args.minimum_seconds, args.tail_seconds, args.drain_seconds,
                                                              args.max_translation_gap, args.max_send_lateness)):
        parser.error("Timing parameters must be finite and positive")
    if args.command == "prepare":
        prepare(args)
    elif args.command == "describe":
        describe(args)
    elif args.command == "self-test":
        self_test()
    elif args.command == "review":
        if args.input is None:
            parser.error("review requires --input summary.json")
        raise SystemExit(0 if review(args.input, args.max_translation_gap, args.max_send_lateness)["passed"] else 1)
    else:
        raise SystemExit(0 if asyncio.run(run(args)) else 1)


if __name__ == "__main__":
    main()
