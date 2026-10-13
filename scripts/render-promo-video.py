#!/usr/bin/env python3
"""Assemble original browser JPEG keyframes into a silent 30-second promo.

No browser, model, GPU or download is used. Requires an existing FFmpeg binary.
The visible disclosures are part of the original captured UI, not added here.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYFRAMES = [0, 6, 12, 16, 18, 24, 30, 36, 44, 48, 54]


def jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
        raise ValueError(f"Not an original complete JPEG: {path}")
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 255:
            break
        offset += 1
        while offset < len(data) and data[offset] == 255:
            offset += 1
        if offset + 3 > len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (217, 218):
            break
        if marker == 1 or 208 <= marker <= 215:
            continue
        length = struct.unpack_from(">H", data, offset)[0]
        if length < 2 or offset + length > len(data):
            break
        if marker in (192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207):
            if length < 8:
                break
            height, width = struct.unpack_from(">HH", data, offset + 3)
            return width, height
        offset += length
    raise ValueError(f"JPEG dimensions unavailable: {path}")


def schedule(args: argparse.Namespace) -> list[tuple[int, float]]:
    if args.timestamps:
        loaded = json.loads(args.timestamps.read_text(encoding="utf-8"))
        rows = loaded["frames"] if isinstance(loaded, dict) else loaded
        result = [(row["frame"], float(row["time"])) for row in rows]
    elif args.all_frames:
        result = [(frame, frame / args.input_fps) for frame in range(round(args.duration * args.input_fps))]
    else:
        result = [(frame, frame / 2) for frame in KEYFRAMES]
    if not result or result[0][1] != 0:
        raise ValueError("The first capture must start at time 0")
    previous = -1.0
    indices = set()
    for frame, time in result:
        if isinstance(frame, bool) or not isinstance(frame, int) or not 0 <= frame <= 99999 or frame in indices:
            raise ValueError("Frame indices must be unique integers in 0..99999")
        if not math.isfinite(time) or time <= previous or time >= args.duration:
            raise ValueError("Times must increase strictly and precede video duration")
        indices.add(frame)
        previous = time
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=["en", "zh-CN"], required=True)
    parser.add_argument("--frames", type=Path, help="Default: output/promo-video/<lang>")
    parser.add_argument("--output", type=Path, help="Default: dist/streamlingo-demo-<lang>.mp4")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keyframes", action="store_true", help="11 fixed keyframes held for 30 seconds (default)")
    group.add_argument("--all-frames", action="store_true", help="Sequential JPEG files at --input-fps")
    group.add_argument("--timestamps", type=Path, help="JSON [{frame: 0, time: 0}, ...], or /plan.json response")
    parser.add_argument("--input-fps", type=float, default=2)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"), help="Existing FFmpeg executable; never installed automatically")
    parser.add_argument("--no-fade", action="store_true", help="Keep first/last frames unchanged")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly replace an existing output MP4")
    parser.add_argument("--dry-run", action="store_true", help="Validate captures and print the command without rendering")
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("FFmpeg is not on PATH. Pass --ffmpeg with an already installed executable.")
    if not math.isfinite(args.duration) or not 1 <= args.duration <= 600:
        parser.error("--duration must be 1..600 seconds")
    if not math.isfinite(args.input_fps) or not 0 < args.input_fps <= 60:
        parser.error("--input-fps must be greater than 0 and at most 60")
    frames_dir = (args.frames or ROOT / "output" / "promo-video" / args.lang).resolve()
    output = (args.output or ROOT / "dist" / f"streamlingo-demo-{args.lang}.mp4").resolve()
    if output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    if output.exists() and not args.overwrite:
        parser.error(f"Output exists; pass --overwrite to replace it: {output}")
    try:
        frames = schedule(args)
        lines = ["ffconcat version 1.0"]
        for index, (frame, time) in enumerate(frames):
            path = frames_dir / f"frame-{frame:05d}.jpg"
            if jpeg_size(path) != (1280, 800):
                raise ValueError(f"Capture must be exactly 1280 x 800: {path}")
            # A fixed basename avoids concat path/quote injection. The manifest
            # lives beside the captures, and FFmpeg's safe-path mode stays on.
            end = frames[index + 1][1] if index + 1 < len(frames) else args.duration
            lines.extend([f"file '{path.name}'", f"duration {end - time:.9f}"])
        lines.append(f"file 'frame-{frames[-1][0]:05d}.jpg'")
        manifest = frames_dir / "frames.ffconcat"
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Pad the last still before trimming so concat's final timestamp cannot
        # leave the CFR output one frame short of the requested duration.
        filters = "fps=30,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1,setsar=1,format=yuv420p"
        if not args.no_fade:
            filters += f",fade=t=in:st=0:d=0.25,fade=t=out:st={args.duration - 0.25}:d=0.25"
        command = [str(args.ffmpeg), "-hide_banner", "-nostdin", "-y" if args.overwrite else "-n",
                   "-f", "concat", "-safe", "1", "-i", str(manifest), "-an", "-vf", filters,
                   "-r", "30", "-fps_mode", "cfr", "-t", str(args.duration),
                   "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "2",
                   "-movflags", "+faststart", "-metadata", "title=StreamLingo UI demonstration",
                   "-metadata", "comment=Silent edited replay of original sample UI; simulated controls; not live inference or an accuracy benchmark.",
                   str(output)]
        if args.dry_run:
            print(json.dumps({"command":command,"frames":len(frames),"duration":args.duration,"output":str(output)}, ensure_ascii=False, indent=2))
            return 0
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True)
        print(f"Rendered {output} ({len(frames)} original captures, {args.duration:g} seconds, silent)")
        print("Keep the MP4 as a Release attachment; do not commit it to Git.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Promo rendering failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
