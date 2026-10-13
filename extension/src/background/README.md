# 会话协调模块

运行位置是 Manifest V3 Service Worker。文件划分：

- `index.ts`：注册 action、runtime、tabs 等事件。
- `session-controller.ts`：串行处理启动和停止，绑定唯一目标标签页。
- `offscreen-host.ts`：创建 Offscreen，获取采集流 ID，发送启动配置。
- `settings-store.ts`：通过 `chrome.storage.local` 读写基础设置。
- `policy.ts`：纯函数验证本地服务地址、字幕设置、YouTube 播放页和插件页面来源。

会话准入与停止清理串行执行，长时间的采音握手在队列外运行。快照只等待首次状态恢复；启动中也能立即发送停止请求。准备与获取流 ID 的步骤使用 AbortSignal 检查取消，停止先失效会话，再释放资源；旧启动的迟到结果不能复活会话或关闭后来启动的进程。清理结束前不接纳新会话。

Offscreen 事件单独确认，防止启动操作等待事件回执形成死锁。音频进程停止超时后关闭 Offscreen 强制释放。

采音流程参考 Google 官方 [tabcapture-recorder](https://github.com/GoogleChrome/chrome-extensions-samples/tree/main/functional-samples/sample.tabcapture-recorder)（Apache-2.0）与 [Chrome 采音文档](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture)，使用其 Chrome 116+ 的 Service Worker → Offscreen 机制。本模块独立实现会话管理、来源验证与错误处理。

Service Worker 负责注入页面字幕、获取 tabCapture 授权和路由字幕消息。持续音频处理和 WebSocket 归 Offscreen。Worker 重新启动后，先向 Offscreen 查询真实会话，不能仅凭模块变量或旧存储判断正在采集。

只接受本插件上下文的控制消息；校验 content 消息发送者的 tab ID 与当前目标一致。停止操作需要幂等，启动中的第二次请求不得创建重复采集。
