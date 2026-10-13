# 服务接入层

`live.py` 提供 `WS /ws/live`，`messages.py` 做运行时验证，`app.py` 装配 `GET /health`。

负责协议版本检查、消息结构和长度校验、音频格式校验、WebSocket Origin 检查、会话握手、事件序列化及断开清理。业务规则交给 application，模型调用交给注入的适配器。

`messages.py` 使用 Pydantic 严格模型表达 docs/protocol.md 的入站契约，并与 TypeScript 类型保持一致。测试覆盖合法与非法消息、Origin、会话竞争和断开清理。

服务默认只监听 127.0.0.1。HTTP CORS 与 WebSocket Origin 分别检查；仅允许明确配置的扩展来源，不放开任意网页来源。日志默认记录状态、耗时和错误，不记录音频内容、整段字幕或模型凭据。
