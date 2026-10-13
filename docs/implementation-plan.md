# StreamLingo MVP 进度与后续验收

> **历史计划与阶段记录，非当前功能说明。** 下文保留早期英语→中文、`base.en` 和旧字幕展示策略的实现背景，不应用作当前安装或行为依据。当前安装见 [getting-started.md](getting-started.md)，四模式及阅读策略见 [architecture.md](architecture.md)，线上字段见 [protocol.md](protocol.md)，最新实测结果见 [validation.md](validation.md)。

本轮完成本机语音识别、Ollama / Qwen 翻译和 Chrome 字幕显示的集成。基础浏览器链路与真实模型分别有验证记录，持续 YouTube 直播质量仍需实际使用验收。

| 阶段 | 当前状态 | 尚需验证或实现 |
| --- | --- | --- |
| 插件与本地服务 | 已构建；用户已反馈在日常 Chrome 加载或刷新 | 实际使用反馈 |
| 真实采音与字幕视图 | 已实现；真实 Chromium 标签页音频→PCM→服务→全屏测试字幕通过 | 实际 YouTube 直播、双标签页音频隔离及原声听感 |
| 流式英文识别 | WhisperLiveKit 0.2.26 与 base.en 已安装，CUDA 短音源实测通过 | 真实直播噪声、长句、15 分钟稳定性与准确率 |
| 翻译接口 | 已接入本机 qwen3.5:9b，实现独立队列、超时、取消和过期跳过 | 真实直播持续负载下的质量与延迟 |

## 下一步：真实直播使用验收

启动 scripts/start.ps1，在真实 YouTube 英文直播中连续运行至少 15 分钟，记录硬件、模型、音源、音频到稳定英文及中文的延迟、队列积压和内存。具体操作见仓库 README。

重点检查静音与停顿、连续长句、重复字幕、停止后重启、服务断连。当前复用上游已提交词和标点边界，并限制连续无标点片段长度；真实模型短样例结果不能替代直播长期表现。

## 已实现的翻译行为

OllamaTranslator 使用本机已安装的 qwen3.5:9b，不重新部署或下载 Qwen。最多 3 个等待任务，另加 1 个正在执行任务；总年龄超过 15 秒跳过，英文继续显示，停止时取消请求。

页面最多展示已译片段和当前英文两组，各自保留 12 秒阅读窗口，同时维护 segment_id/revision，迟到译文不与较新的英文混排为同一句。

自动化测试覆盖正常、超时、错误、迟到、队列溢出和停止；短样例使用真实 ASR 与 Qwen 推理。demo 固定示例继续保留测试标记，不能用来评价模型质量。

## 验证入口

- `npm run check`：TypeScript、扩展关键边界测试、esbuild 构建。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q`：本地服务、协议、会话与真实 TCP/WebSocket 测试。
- [验证记录](validation.md)：本轮通过项、证据和未验证边界。
