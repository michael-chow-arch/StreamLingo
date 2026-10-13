"""Prepare the pinned multilingual speech model; does not load GPU or touch Ollama."""
import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download

REPOSITORY = "Systran/faster-whisper-base"
REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "models" / "whisper-base")
    args = parser.parse_args()
    destination = args.output.resolve()
    print(f"Preparing {REPOSITORY} ({REVISION}) in {destination}", flush=True)
    snapshot_download(REPOSITORY, revision=REVISION, local_dir=destination,
                      allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.txt", "README.md"])
    for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
        if not (destination / name).is_file() or (destination / name).stat().st_size == 0:
            raise RuntimeError(f"Model download is incomplete: {name}")
    (destination / "streamlingo-model.json").write_text(json.dumps(
        {"repository": REPOSITORY, "revision": REVISION, "model": "base", "multilingual": True}, indent=2), encoding="utf-8")
    print("Multilingual speech model is ready. Existing Ollama models are unchanged.", flush=True)


if __name__ == "__main__":
    main()
