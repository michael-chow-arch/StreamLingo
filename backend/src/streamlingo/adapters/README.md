# 模型适配层

`whisperlivekit.py` 实现同进程 WhisperLiveKit 0.2.26 的适配，保留连续识别状态，复用上游已提交词、标点分组和进度事件生成 `TranscriptEvent`。固定版本的 API 和 Apache-2.0 依据见 `backend/README.md`。

`demo.py` 包含音频驱动的测试识别和测试翻译。`ollama.py` 通过 `TranslationProvider` 注入真实本机模型调用。

- Mock 只用于开发联调，所有输出必须带 `is_mock=True`。
- Ollama 的地址、模型名、认证信息和请求格式只出现在具体适配器及其配置中。
- 指定 `--ollama-model` 后调用已部署的模型，不下载或部署 Ollama；未指定则禁用真实翻译。

CPU 或 GPU 推理不能阻塞 WebSocket 所在的 asyncio 事件循环；根据引擎执行方式采用受控 worker，限制并发。不能让每个音频包重新加载模型或创建独立识别会话。
