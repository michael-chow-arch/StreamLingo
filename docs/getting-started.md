# Getting started

[English overview](../README.md) · [中文快速开始](../README.zh-CN.md)

StreamLingo has three running parts: the Chrome extension, the local StreamLingo service, and your existing Ollama service. Installing the extension alone is not enough. The steps below use Windows, the currently tested platform.

## 1. Prepare your computer

| Requirement | Details |
| --- | --- |
| Chrome | Version 116 or newer; use a current stable version |
| Node.js | Only for source builds: version 22 or newer with npm on `PATH`. Not required by the prebuilt Windows preview ZIP. |
| Python | Version 3.11, 3.12, or 3.13; 3.14 is outside the supported range. Setup can offer Python 3.12 installation through `winget` if none is found. |
| Ollama | Running locally with a text/chat model you have already installed |
| NVIDIA GPU and runtime | CUDA 12 cuBLAS + complete cuDNN 9 for CUDA 12, available on `PATH`; verified combination CUDA 12.4.1 + cuDNN 9.3. Compatible NVIDIA driver and x64 Visual C++ runtime required. See [runtime requirements](runtime-requirements.md). |
| Internet | Needed to install dependencies and download speech models |
| Disk and compute | Allow several GB for the Python speech stack, caches, and your Ollama model; live speed depends on your hardware |

Official installers: [Chrome](https://www.google.com/chrome/), [Node.js](https://nodejs.org/en/download), [Python](https://www.python.org/downloads/windows/), and [Ollama](https://ollama.com/download/windows). Reopen your terminal after installing tools so it sees the updated `PATH`.

This project does not install or replace your Ollama models. Run `ollama list` to see the models you already have. Choose one that can translate between your source and target languages and runs comfortably on your machine. `qwen3.5:9b` has been used in local testing; you do not need that exact model. A large model may compete with speech recognition for GPU resources.

## 2. Download and set up

Download **[streamlingo-windows-0.2.0.zip](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-windows-0.2.0.zip)** and extract it to a permanent folder. It includes `dist/extension`, so no Node.js installation is needed. The [release page](https://github.com/michael-chow-arch/StreamLingo/releases/tag/v0.2.0) includes a `.zip.sha256` file; compare it with `Get-FileHash .\streamlingo-windows-0.2.0.zip -Algorithm SHA256` if you want to verify the download. This is a preview ZIP, not a signed installer or Chrome Web Store installation.

For a source installation, open the [repository](https://github.com/michael-chow-arch/StreamLingo), select **Code → Download ZIP**, and extract the archive. This source archive requires Node.js to build the extension. Do not run launchers inside a ZIP. Git users can instead run:

```powershell
git clone https://github.com/michael-chow-arch/StreamLingo.git
cd StreamLingo
```

Keep Ollama running and double-click **`Setup-StreamLingo.cmd`** in that folder. Setup detects your installed models. It reuses a saved valid choice, otherwise prefers an installed `qwen3.5:9b`; if there is just one model, it selects it. With multiple other models, it asks for a number. Choose a text/chat model capable of translation, not an embeddings-only model.

Setup installs the local service into `backend/.venv`, prepares the multilingual Whisper `base` model in `models/whisper-base`, and uses or builds `dist/extension`. The speech download uses a pinned revision of [`Systran/faster-whisper-base`](https://huggingface.co/Systran/faster-whisper-base); the revision is recorded in `scripts/download-model.py` and the downloaded model's `streamlingo-model.json`. Setup stores your local choice in `.streamlingo.json`, which is excluded from Git. It does not install, download, or replace Ollama models.

The first installation downloads Python packages, including the optional WhisperLiveKit speech dependencies, and model files. Download time and size depend on platform and existing caches. Let setup finish before starting the service. Additional upstream model files may be fetched on the first real startup; do not assume that copying only `model.bin` is enough for offline operation.

If Windows or your organization blocks a downloaded script, review its source and follow your organization's policy. Do not disable system security settings globally to run it. The equivalent PowerShell entry point is:

```powershell
.\scripts\setup.ps1
```

## 3. Start the local service

Keep Ollama running, then double-click **`Start-StreamLingo.cmd`**. The launcher uses your saved model and waits for the local subtitle service to load. To select another installed model, stop the service and rerun setup with the model name:

```powershell
.\scripts\setup.ps1 -OllamaModel YOUR_INSTALLED_MODEL
```

Model loading can take time. Check [local service health](http://127.0.0.1:8765/health), or use the extension's connection test after loading it. `asr: ready` means the recognizer has loaded. `translation: configured` means a translator was configured; it is not proof that a translation request has succeeded.

On Windows, the service checks the CUDA 12 / cuDNN 9 runtime files and requires a CUDA device visible to CTranslate2 before loading the speech engine. Missing requirements produce an explicit error; there is no automatic CPU fallback. File/device checks alone do not establish binary compatibility or sufficient memory. Check the [runtime requirements](runtime-requirements.md) before setup.

Do not start a second copy on the same port. **`Stop-StreamLingo.cmd`** stops the subtitle service started by the launcher; it does not stop Ollama or remove models. Diagnostic logs are under `output/service/`.

## 4. Load the Chrome extension

1. Open `chrome://extensions` in Chrome.
2. Turn on **Developer mode**.
3. Click **Load unpacked** and select the project's **`dist/extension`** directory. Select the directory containing `manifest.json`, not the repository root or the `extension` source directory.
4. Pin StreamLingo from Chrome's Extensions menu if you want easy toolbar access.

The development build has a fixed extension ID, `ggakbplmndfijhdcepbafoibilffbhmg`, and the launchers allow that exact origin. If you change the manifest key or install a separately distributed build, its ID may differ. Match the actual ID in `chrome://extensions` or the popup's backend connection details:

```powershell
.\scripts\start.ps1 -ExtensionId YOUR_ACTUAL_32_CHARACTER_EXTENSION_ID
```

The public development key stabilizes the ID; it is not a password or authentication secret. Do not replace the origin allowlist with a wildcard to work around a mismatch.

## 5. Watch with subtitles

Play a YouTube video or live stream and open the StreamLingo popup. The default backend address is `http://127.0.0.1:8765`.

Choose one of four translation modes, test the connection, and start subtitles. English → Chinese is the default. Chinese → English and either automatic mode require a multilingual ASR model such as `base`. Automatic mode uses Whisper's source-language detection, then asks Ollama to output the selected target language. It may misdetect short, noisy, or mixed-language passages.

The popup's English/中文 switch changes interface text only. Font size and source-text display are separate settings. To change translation direction during a session, stop capture and start a new session with the new mode.

Close the popup if desired; capture continues. Use **Stop** in the popup to release tab audio capture. Refreshing or changing the YouTube video ends the current session, so start again afterward. StreamLingo currently supports one active capture session per local service.

## Reading behavior

Long completed translations are split at sentence and word boundaries where possible. Chinese output uses at most 48 non-whitespace Unicode code points per page; English output uses at most 120 characters, counting collapsed spaces. The English limit is characters, not words. These are text limits, not fixed numbers of screen lines. Original characters and whitespace are preserved across the pages. Up to two adjacent short translations of the same target language share a screen when they fit that language's page limit; their source texts remain paired with the correct translations.

Each page or group receives four to eight seconds of reading time. Chinese uses a character-based budget; English also counts words, at a default three words per second. Pages advance automatically; the last one hides twelve seconds after appearing if nothing follows. Switching tabs freezes reading time, including queued pages, but does not stop capture. Stop capture if you want audio processing to stop.

Completed translations remain queued until displayed or the session ends. Fast speech can create increasing display delay. Recognition failures, inference overload, and translations that time out or are skipped before completion are separate limits: retaining completed pages cannot recover text the backend never translated. There is no subtitle history browser or manual paging.

## Update an existing installation

Stop capture and the local service. Replace the preview bundle or update the source files, rerun setup, and then restart the service. Source users should also run `npm ci` and `npm run build` to rebuild changed extension code. In `chrome://extensions`, click StreamLingo's **Reload** button. Refresh any already-open YouTube page before starting a new session so it uses the new content script.

If you downloaded a new ZIP to a different location, load that location's `dist/extension` and keep it in place. Do not delete your old model or configuration files before deciding whether you need them. Older installations using `models/whisper-base.en` need the new multilingual model for Chinese or automatic modes; the old model can remain on disk.

## Troubleshooting

Double-click **`Doctor-StreamLingo.cmd`** for a local check of your Python environment, speech model, built extension, configured Ollama model, service status, and advertised language modes. It does not upload logs or audio. Model presence and a configured translator do not prove successful inference; report any actual subtitle error too.

| Symptom | What to check |
| --- | --- |
| Setup cannot find Node or Python | Check `node --version`, `npm --version`, and your Python installation; use Node 22+ and Python 3.11–3.13. Open a new terminal after installing. |
| Extension will not load | Run setup/build first and select `dist/extension`. Check Chrome's version and extension error details. |
| Connection refused | Start the local service; open `/health`; check `output/service/stderr.log`. The extension cannot start a missing service by itself. |
| Model still loading | Wait for `asr: ready`; inspect logs for a failed download or missing speech dependencies. |
| Origin denied | Compare the installed extension ID with the allowed ID. Restart the service with the actual `-ExtensionId`. |
| A language mode is unavailable | Use multilingual `base`, and update both extension and backend. Old backends may only advertise English support. |
| Source text appears, translation does not | Confirm Ollama is running and the selected model exists. `translation: configured` alone does not test inference. Inspect translation errors. |
| Speech recognition falls behind | Check GPU memory and model load. ASR and Ollama share resources; try a smaller installed translator or reduce other compute-heavy work. Record your hardware when reporting the problem. |
| Translations are readable but behind the video | Completed pages wait for reading time rather than being discarded. This display queue is different from ASR overload. |
| Repeated or implausible words | Check the source language and audio quality. Wrong-language speech, music, and noise can mislead recognition; automatic detection is not infallible. |
| Session conflict | Stop the active StreamLingo session in its tab before starting another. |
| Port 8765 is already used | Use the running StreamLingo service or stop its launcher-managed instance. Do not kill an unrelated process to free the port. |

Before filing an [issue](https://github.com/michael-chow-arch/StreamLingo/issues), include your OS, Chrome/Python/Node versions, translation mode, model names, hardware, error code, and minimal reproduction. Redact logs; dependencies may print recognized words. Do not upload private recordings, account details, or an entire live-stream capture.

## Lightweight demo and developer setup

The demo verifies browser capture, transport, and rendering without installing WhisperLiveKit or contacting Ollama. It emits clearly marked fixed sample text after audio arrives. **It does not recognize or translate the audio.** Real mode never silently falls back to demo.

From the repository root in PowerShell:

```powershell
npm ci
npm run build
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -e .\backend
.\scripts\start-demo.ps1
```

Load the extension as above and start capture on a playing YouTube tab. Stop the demo with Ctrl+C before starting the real service. The demo uses the same port.

For a manual real installation, add the speech extras to that environment:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -e '.\backend[asr]'
.\backend\.venv\Scripts\streamlingo-server.exe --model base --ollama-model YOUR_INSTALLED_MODEL --allow-origin chrome-extension://ggakbplmndfijhdcepbafoibilffbhmg
```

This manual command permits upstream speech-model downloads. Add `--model-dir` for an existing compatible faster-whisper model directory. Language direction is selected per session in the popup, not through a separate CLI language flag. See the [backend reference](../backend/README.md) for advanced settings and [CONTRIBUTING](../CONTRIBUTING.md) for model-free tests.
