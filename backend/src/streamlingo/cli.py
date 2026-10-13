import argparse
import logging

import uvicorn

from streamlingo.runtime_requirements import RuntimeRequirementsError, require_windows_asr_runtime
from streamlingo.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="StreamLingo local subtitle server")
    parser.add_argument("--mode", choices=("demo", "whisperlivekit"), default="whisperlivekit")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="Exact chrome-extension://<ID>; repeat for multiple development installs")
    parser.add_argument("--model", default="base", help="Whisper model size: base supports en/zh/auto; .en models support English only")
    parser.add_argument("--model-dir", default=None, help="Existing faster-whisper CTranslate2 model directory")
    parser.add_argument("--model-cache-dir", default=None)
    parser.add_argument("--asr-beam-size", type=int, default=1,
                        help="Whisper search width: 1 favors speed, 5 favors accuracy")
    parser.add_argument("--asr-coalesce-seconds", type=float, default=0.8,
                        help="Minimum new speech per inference (0.1–2 seconds)")
    parser.add_argument("--asr-buffer-seconds", type=float, default=8.0,
                        help="Trim committed audio after this many seconds (4–30)")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-model", default=None, help="Enable real translation, e.g. qwen3.5:9b")
    parser.add_argument("--translation-timeout", type=float, default=20.0, help="Maximum seconds per translation")
    parser.add_argument("--translation-max-age", type=float, default=15.0, help="Total segment budget in seconds, including queue and inference")
    parser.add_argument("--translation-queue-size", type=int, default=3, help="Waiting segments, excluding one active translation")
    args = parser.parse_args()
    try:
        settings = Settings(mode=args.mode, host=args.host, port=args.port,
                            allowed_origins=tuple(args.allow_origin), model=args.model,
                            model_dir=args.model_dir, model_cache_dir=args.model_cache_dir,
                            asr_beam_size=args.asr_beam_size,
                            asr_coalesce_seconds=args.asr_coalesce_seconds,
                            asr_buffer_seconds=args.asr_buffer_seconds,
                            ollama_url=args.ollama_url, ollama_model=args.ollama_model,
                            translation_timeout=args.translation_timeout,
                            translation_max_age=args.translation_max_age,
                            translation_queue_size=args.translation_queue_size)
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO)
    if not settings.allowed_origins:
        logging.warning("No extension origins configured: WebSocket connections will be rejected")
    if settings.mode == "demo":
        logging.warning("DEMO MODE: synthetic subtitles only; no speech recognition or real translation")
    else:
        try:
            require_windows_asr_runtime()
        except RuntimeRequirementsError as exc:
            parser.error(str(exc))
    # Report missing runtime files before the app/ASR import graph initializes.
    from streamlingo.app import create_app

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port,
                ws_max_size=max(settings.max_audio_packet_bytes, settings.max_control_bytes),
                ws_max_queue=8, proxy_headers=False, workers=1)


if __name__ == "__main__":
    main()
