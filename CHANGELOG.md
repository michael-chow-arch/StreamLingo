# Changelog

User-visible changes are recorded here. An entry under **Unreleased** does not imply that a package has been published or accepted by the Chrome Web Store.

## Unreleased

## 0.2.0 — 2026-10-13 (preview)

First Windows preview for users with an existing Ollama installation. Download the prebuilt ZIP and checksum from the [release page](https://github.com/michael-chow-arch/StreamLingo/releases/tag/v0.2.0).

### Added

- Chrome Manifest V3 extension for direct YouTube tab audio capture with original audio playback.
- Local WhisperLiveKit speech recognition and translation through a configurable Ollama model.
- English → Chinese, Chinese → English, and automatic source-language detection with Chinese or English output; multilingual modes require a multilingual speech model.
- English and Simplified Chinese popup interfaces, source-text display, and subtitle font controls.
- Automatic translation pagination, grouping of adjacent short cues, and reading timers that pause when the tab is hidden.
- Windows setup, start/stop launchers, and local diagnostics for users with an existing Ollama installation; the prebuilt preview bundle does not require Node.js.
- Explicit Windows GPU runtime requirements and startup diagnostics: CUDA 12 cuBLAS, complete cuDNN 9 for CUDA 12, and an available CUDA device. Missing requirements stop startup without automatic CPU fallback.
- Explicit demo mode for testing the capture-to-overlay path without speech or translation models.
- Shared protocol validation, model-free tests, and GitHub Actions checks.
- English and Simplified Chinese documentation, contribution and security guidance, and the MIT license.

### Reliability

- Stable source segmentation during continuous speech and long-silence recovery.
- Speech backlog accounting that distinguishes queued speech from silence.
- Reduced decoding overhead and disabled repeated history prompts for the realtime ASR profile.
- Session/revision checks, capture cleanup, and orderly handling of late translations.
- Retention of successfully completed translation pages until displayed or the session ends, without automatic queue eviction or translation line clipping.

### Known limits

- Early preview; no Chrome Web Store listing yet.
- Windows is the tested runtime platform. Linux and macOS live operation remain unverified.
- One active capture session per local service; separate local service and Ollama setup required.
- Accuracy and latency depend on audio, language detection, hardware, and model choice. Pending translation work has bounded capacity and time limits; completed-page retention cannot guarantee that all speech was translated.
