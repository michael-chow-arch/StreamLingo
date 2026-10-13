# StreamLingo 协议包

此包导出线上类型，以及基于 Zod 的 `parseHealthResponse` 和 `parseServerMessage`。它不访问 Chrome、DOM、网络或模型服务。

协议的行为规则见 [实时通信协议](../../docs/protocol.md)，字段类型见 `src/index.ts`。两者变更时需一起修改。Python 内部领域对象独立定义，由 `backend/src/streamlingo/transport/` 验证和映射线上消息，不直接序列化任意领域对象作为协议。

TypeScript 类型不会验证网络输入。WebSocket 与健康检查已使用这里的运行时解析函数，拒绝错误结构、版本、时间或字幕状态。后端使用 Pydantic 校验输入，通过实际 WebSocket 联调验证两侧契约。
