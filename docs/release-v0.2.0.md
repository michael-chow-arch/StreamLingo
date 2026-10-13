# StreamLingo v0.2.0 — Windows preview / Windows 预览版

**Live streams. AI-translated. / 让 YouTube 直播说你的语言。**

Real-time AI-translated captions for YouTube livestreams, using local speech recognition and the Ollama model you already run. No captions from the streamer are required.

从 YouTube 直播原声生成实时 AI 翻译字幕，支持本地大模型，复用你已有的 Ollama。无需主播提供字幕。

## Download / 下载

- **[Windows preview ZIP](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-windows-0.2.0.zip)** — includes the built Chrome extension and the local service setup scripts; no Node.js needed. 包含已构建扩展与本地服务安装脚本，无需 Node.js。
- [SHA-256 checksum / 校验文件](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-windows-0.2.0.zip.sha256)

Choose the Windows ZIP above for installation. GitHub's automatically generated **Source code** archives need Node.js to build the extension.

安装请选择上面的 Windows ZIP；GitHub 自动生成的 **Source code** 压缩包是源码，构建扩展还需 Node.js。

## See it in 32 seconds / 32 秒查看实际效果

[English demo](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-en-horizontal.mp4) · [中文演示](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-zh-CN-horizontal.mp4) · [English vertical](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-en-vertical.mp4) · [中文竖版](https://github.com/michael-chow-arch/StreamLingo/releases/download/v0.2.0/streamlingo-zh-CN-vertical.mp4)

Actual Chrome tab capture with real English-to-Chinese captions, localized AI narration and original music. This is YouTube playback of an open film, not a livestream recording. Captions retain the original output and reading delay; they were not rewritten in editing. The older `streamlingo-demo-*` attachments are historical silent UI walkthroughs.

真实 Chrome 标签页采集与实际英译中字幕，配中英文 AI 旁白及原创背景音乐。片段来自开放电影的 YouTube 回放，并非直播录屏；字幕保留实际识别、翻译与阅读延迟，后期未改写。旧 `streamlingo-demo-*` 附件为历史静音界面演示。

Footage / 片段：**Tears of Steel — Blender Foundation**. [Source](https://www.youtube.com/watch?v=R6MlUcmOul8) · [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) · [Official film information](https://mango.blender.org/about/). Cropped excerpt with actual generated captions and promotional editing. AI narration: MeloTTS / Piper via sherpa-onnx. Original backing music: StreamLingo.

## Start / 开始使用

1. Check the [runtime requirements](https://github.com/michael-chow-arch/StreamLingo/blob/v0.2.0/docs/runtime-requirements.md), then extract the entire ZIP to a permanent folder. 检查运行条件，将完整 ZIP 解压到固定目录。
2. Keep your existing Ollama running. Double-click `Setup-StreamLingo.cmd` once to select an installed model and prepare speech recognition. 保持 Ollama 运行，首次双击 Setup，选择已安装模型并准备识别环境。
3. In `chrome://extensions`, enable Developer mode and load the unpacked `dist/extension` folder. 在 Chrome 开发者模式中加载 `dist/extension`。
4. Double-click `Start-StreamLingo.cmd`, open a YouTube livestream, choose a direction, and start subtitles. 双击 Start，打开直播，选择翻译方向后开始字幕。

**Daily use: double-click Start → open a livestream → start subtitles.**

**日常使用：双击 Start → 打开直播 → 开始字幕。**

## Requirements / 运行条件

Windows x64, Chrome 116+, 64-bit Python 3.11–3.13, an NVIDIA GPU, CUDA 12 cuBLAS, and complete cuDNN 9 for CUDA 12. The verified combination is CUDA 12.4.1 + cuDNN 9.3 with a compatible driver. Existing Ollama and a text/chat model are required. Setup needs internet access for speech dependencies and models; it does not install GPU drivers or CUDA/cuDNN. Missing runtime requirements stop startup with an explanation; there is no automatic CPU fallback.

需要 Windows x64、Chrome 116+、64 位 Python 3.11–3.13、NVIDIA GPU、CUDA 12 cuBLAS，以及适用于 CUDA 12 的完整 cuDNN 9。已验证组合为 CUDA 12.4.1 + cuDNN 9.3 与兼容驱动。需已有 Ollama 和文本/聊天模型。首次安装需联网下载语音依赖与模型；Setup 不安装显卡驱动或 CUDA/cuDNN，缺少运行要求会明确停止，不自动降级 CPU。

## Included / 本版功能

- English → Chinese, Chinese → English, and automatic language detection with Chinese or English output. 英译中、中译英、自动识别后译中或译英。
- Direct tab audio capture with original audio playback; English and Chinese interfaces. 直接采集标签页音频、保留原声，中英文界面可切换。
- Automatic subtitle pages with protected reading time; completed translations are retained until displayed or the session ends. 字幕自动分页并保留阅读时间，完整译文依次显示至读完或会话结束。
- Setup, Start, Stop, and Doctor launchers. 提供安装、启动、停止与本机诊断入口。

## Validation and limits / 验证与限制

Two 30-minute real-model tests used original synthesized English and Chinese speech, followed by offline caption replay. A separate short test checked the installed extension on a real YouTube English livestream, with the user operating toolbar controls and confirming original audio playback. [Measurements](https://github.com/michael-chow-arch/StreamLingo/blob/v0.2.0/docs/benchmarks.md) and [validation notes](https://github.com/michael-chow-arch/StreamLingo/blob/v0.2.0/docs/validation.md) separate these results and their limits.

两轮约 30 分钟真实模型测试使用原创英文/中文合成语音，字幕显示另做离线回放；另在真实 YouTube 英语直播上完成短测，由用户点击工具栏开始/停止并确认原声。实测表和验证记录分别说明覆盖范围。

This is an early preview. Recognition and translation can be wrong, including proper names. Fast speech can accumulate reading delay; uncompleted work can still fail or time out. Validation covers the Windows configuration listed in the measurements; other hardware, Linux/macOS, and long Chrome capture sessions remain unverified. The extension is not in the Chrome Web Store; this ZIP is not a signed installer.

当前是早期预览版，识别和翻译仍会出错，包括人名、地名；快速讲话可能积累阅读延迟，未完成的任务仍可能失败或超时。验证覆盖实测表列出的 Windows 配置，其他硬件、Linux/macOS 与长时间 Chrome 采音尚未验证。扩展尚未上架 Chrome 商店，ZIP 不是签名安装器。

[Installation guide / 安装指南](https://github.com/michael-chow-arch/StreamLingo/blob/v0.2.0/docs/getting-started.md) · [Report a problem / 反馈问题](https://github.com/michael-chow-arch/StreamLingo/issues) · [Privacy / 隐私](https://github.com/michael-chow-arch/StreamLingo/blob/v0.2.0/docs/privacy-policy.md)

MIT · [michael-chow-arch](https://github.com/michael-chow-arch) · [michael.chow.tech@gmail.com](mailto:michael.chow.tech@gmail.com)
