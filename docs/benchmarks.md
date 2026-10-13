# Performance measurements / 性能测试

[English README](../README.md) · [中文 README](../README.zh-CN.md) · [Runtime requirements / 运行条件](runtime-requirements.md)

These are reproducible **local stability measurements**, not a comparison against other projects or a guarantee of livestream accuracy. They use original synthesized speech sent in real time through the production WebSocket, real Whisper recognition, and real Ollama translation. Caption display is measured separately by replaying the resulting events through the production caption scheduler.

## Test environment / 测试环境

| Item / 项目 | Configuration / 配置 |
| --- | --- |
| Date / 日期 | 2026-10-13 |
| Version / 版本 | StreamLingo 0.2.0 preview |
| OS / 系统 | Windows 11 x64 |
| Python | 3.11.9 x64 in the fresh preview installation |
| CPU / RAM | Intel Core i7-13700KF / 32 GiB |
| GPU / VRAM | NVIDIA RTX 3080 / 10 GiB |
| GPU runtime / 运行库 | Driver 616.56; CUDA 12.4.1; cuDNN 9.3.0.75 |
| Speech engine / 识别引擎 | WhisperLiveKit 0.2.26; faster-whisper 1.2.1; CTranslate2 4.8.3 |
| ASR / 识别模型 | Multilingual Whisper `base`, beam size 1, 0.8 s coalescing |
| Translation / 翻译模型 | Existing Ollama 0.34.2 / `qwen3.5:9b`, Q4_K_M quantization (model metadata: 9.7B parameters) |
| Translation options / 翻译参数 | `think: false`, temperature 0, context 4096, maximum output 768 tokens |
| Input / 输入 | Original Microsoft Zira / Huihui System.Speech narration; 16 kHz, mono, PCM16; no audio looping |
| Concurrent load / 并发 | One capture session; ASR and Ollama share this machine |
| Warm/cold state / 预热状态 | Models already initialized after short smoke tests; not cold-start timing |

This hardware is the measured setup, **not the minimum requirement**. The local service was installed from the preview ZIP into a fresh virtual environment and model folder on the same machine. Existing Python, Ollama, CUDA and download caches were available; this was not a clean operating system installation.

## Results / 测量结果

| Metric / 指标 | English → Chinese / 英译中 | Chinese → English / 中译英 |
| --- | ---: | ---: |
| Speech duration / 音频时长 | 30 min 23.280 s | 30 min 16.215 s |
| Completed translations / 完成译文 | 672 | 675 |
| Translation errors / 翻译失败 | 0 | 0 |
| Skipped translations / 后端跳过 | 0 | 0 |
| Disconnects / 断连 | 0 | 0 |
| Pending final translations at stop / 结束时未完成译文 | 0 | 0 |
| Segment end → translation received, P50 / 片段结束到收到译文 | 1.130 s | 1.718 s |
| Segment end → translation received, P95 | 2.414 s | 3.172 s |
| Segment end → translation received, max | 4.453 s | 3.846 s |
| Caption reading wait, P50 / 额外字幕阅读等待 | 1.969 s | 2.785 s |
| Caption reading wait, P95 | 3.859 s | 6.120 s |
| Caption reading wait, max | 5.015 s | 9.200 s |
| Completed translations displayed / 已显示完整译文 | 672 / 672 | 675 / 675 |
| Displayed pages / 已显示字幕页数 | 672 | 676 |
| Lost or changed translated text in replay / 回放丢失或改写译文 | 0 | 0 |
| Shortest display interval / 最短显示时间 | 4.000 s | 4.000 s |
| Maximum queued pages / 最大等待页数 | 3 | 4 |

**P95** means 95% of measured values are at or below that value. It is not an average or a maximum.

- **Segment end → translation received** uses the recognizer's segment-end timestamp and the client's real-time audio clock. It includes recognition and translation delay after that reported end, but does not include Chrome audio capture or the caption reading queue. ASR timestamps are estimates.
- **Caption reading wait** measures from receipt of a completed translation to the first display of its first page in an offline replay. The minimum four-second reading policy can create this wait. It excludes recognition and model inference. **3.859 seconds is not end-to-end latency.**
- **Displayed / lost text** checks every completed translation: concatenating its displayed pages must reproduce the original translation exactly. This does not establish that ASR heard every word or that translation was correct.
- The replay advances a virtual clock through all production scheduler deadlines until the queue drains. It does not measure Chrome rendering, hidden-tab throttling, or human reading comprehension. Stop/navigation intentionally clearing a session is outside this replay.

P50 and P95 from different stages must not be added to claim an end-to-end percentile. These measurements are for this audio and machine; sustained speech faster than the reading rate still accumulates delay.

## Reproduce / 复现

Prepare the [runtime requirements](runtime-requirements.md), start the service, and keep the extension stopped: the test occupies the service's single capture session. From the repository root:

```powershell
# Generate original local TTS audio; requires Windows System.Speech voices.
.\backend\.venv\Scripts\python.exe scripts/soak-acceptance.py prepare
# Two sequential real-time sessions, at least 30 minutes each.
.\backend\.venv\Scripts\python.exe scripts/soak-acceptance.py run --output output/my-soak --service-log output/service/stderr.log
# Replay each recording through the caption scheduler (Node development dependencies).
npx tsx scripts/replay-reading-window.ts output/my-soak/en/summary.json output/my-reading-en
npx tsx scripts/replay-reading-window.ts output/my-soak/zh/summary.json output/my-reading-zh
# Reassess a saved recording without connecting to a model or changing the file.
.\backend\.venv\Scripts\python.exe scripts/soak-acceptance.py review --input output/my-soak/en/summary.json
```

The recorder preserves errors and progress, verifies non-mock translations, final/revision consistency, bounded send timing and stop acknowledgement, and reports candidate repeated output without filtering it. Its `passed` result describes stability checks; it is not an accuracy score. Raw audio, transcripts and logs stay in gitignored `output/` and are not uploaded. Review them before sharing.

## Limits / 尚未覆盖

No WER/CER or translation-quality score is claimed. Multilingual `base` has already shown Chinese homophone errors, and short independent segments can lose context. Automatic language switching, accents, noisy human livestreams, slower hardware, long Chrome tab capture and multi-hour loads require separate measurement. A zero error count means no reported protocol/translation failures in this run, not zero semantic mistakes.

中文：本表区分真实模型处理延迟与译文返回后的阅读等待。测试按真实速度送入原创合成音频，前端显示另用生产字幕调度器离线回放检查；不把它宣传为真实 YouTube 直播端到端测速。以上硬件只是已验证配置，最低显存、内存仍需测量。长句分页保留完整译文，持续超出阅读速度仍会积累延迟。
