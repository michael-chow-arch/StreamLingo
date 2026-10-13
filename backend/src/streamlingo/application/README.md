# 字幕业务层

`session.py` 已实现单会话占用、有界音频队列、字幕 ID 与 revision、最终结果冻结。分段复用 ASR 引擎；独立单 worker 翻译稳定片段，有队列上限、过期跳过、超时、失败回退与取消。

- SessionRegistry 占用和释放单活动会话，传输层协调启停和清理。
- SubtitleSession 接收引擎事件，持有 segment ID 与 revision，冻结最终英文并生成字幕快照。
- 独立翻译 worker 通过注入的 Ollama 或 demo provider 处理稳定片段，最多 3 条等待任务，中文更新对应 segment ID 并递增 revision。

本层只依赖 domain 与 ports。由创建应用的入口注入具体 ASR 和翻译适配器，不直接导入 WhisperLiveKit、Ollama HTTP 客户端或 FastAPI。

ASR 的最终片段不一定是完整自然句；适配器复用上游标点与推理进度，并限制无标点长段。翻译默认单任务执行，避免本地模型资源争抢。

停止或连接断开时取消会话任务与正在进行的翻译 HTTP；迟到结果在会话边界丢弃。音频积压时结束会话并报错，不静默丢掉中间音频继续识别。翻译积压只跳过对应片段，英文会话继续。
