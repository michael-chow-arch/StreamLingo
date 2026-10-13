# 音频与传输模块

- `index.ts`：接收启停消息，持有活动会话，统一释放资源；QUERY 支持后台 Worker 恢复状态。
- `capture.ts`：立即消费标签页流 ID，使用设备默认采样率回放原声；第二个 16 kHz AudioContext 由浏览器完成重采样。
- `pcm-worklet.ts` / `pcm.ts`：合并声道、限制样本幅度、编码为小端 PCM16，跨渲染块连续累积为 160 ms 音频包。
- `live-client.ts`：WebSocket 握手、协议运行时校验、会话校验、音频发送和有限积压保护。

音频直接从 Offscreen 发往本地服务，不经过 Service Worker 转发。格式固定为 16 kHz、单声道、有符号 16 位小端 PCM。代码检查 AudioContext 的实际 sampleRate；不满足 16 kHz 时明确失败，不能伪报格式。播放与识别使用两条 Web Audio 路径，ASR 采样率不降低原声回放质量。

采音流在握手前获取并回放；Worklet 在收到 ready 后才打开发送门控，因此启动前样本不会留在首包中。静音样本正常传输，保持音频时间轴。握手超时为 15 秒，WebSocket 未发出音频上限为 64,000 字节（2 秒）；超限停止会话并提示，不静默丢包或无限排队。停止、音轨结束、网络失败、格式错误均释放流、两个 AudioContext、Worklet 和 WebSocket。用户停止不会等待最后一句识别。

Offscreen 只通过 `chrome.runtime` 与后台通信；设置和标签页消息由后台处理。没有使用 Offscreen 不支持的 `chrome.storage` / `chrome.tabs`。音频消息和服务消息均绑定当前 session_id；取消中的启动和迟到事件不能重新激活会话。

## 复用来源与许可

核验日期：2026-10-12。以下项目均为 Apache-2.0，许可证副本见本目录 `LICENSE.apache-2.0.txt`。

1. [GoogleChrome/chrome-extensions-samples：tabcapture-recorder/offscreen.js](https://github.com/GoogleChrome/chrome-extensions-samples/blob/f29c6f8682397ad737142669770a2b90544d186b/functional-samples/sample.tabcapture-recorder/offscreen.js)。`capture.ts` 改编其标签页流获取及 AudioContext 回放模式，保留 Google LLC 版权声明；增加纯音频采集、独立 ASR 图、资源释放和取消处理。[官方说明](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture)说明 Chrome 116 起支持 Worker 获取 stream ID 并交给 Offscreen 消费。
2. [WhisperLiveKit：pcm_worklet.js](https://github.com/QuentinFuxa/WhisperLiveKit/blob/363e4f6d029694d9c81ae548beddd9d3c88a3637/whisperlivekit/web/pcm_worklet.js) 与 [recorder_worker.js](https://github.com/QuentinFuxa/WhisperLiveKit/blob/363e4f6d029694d9c81ae548beddd9d3c88a3637/whisperlivekit/web/recorder_worker.js)。参考其 AudioWorklet 跨线程转移 ArrayBuffer 和 PCM16 小端编码；增加多声道平均、固定分包、非有限值处理和就绪门控。没有移植其 JavaScript 重采样器，采样率转换使用浏览器 Web Audio 实现。

这些是浏览器音频接入与协议适配代码；实际语音识别交由后端复用 WhisperLiveKit。此目录没有自行实现语音识别、降噪或重采样算法。

## 验证

Node 测试验证 PCM 饱和、字节序、多声道合并、连续分包、静音时间轴、握手、取消启动、协议/会话错误、超时、断线和发送积压。另已用真实 Chromium 验证标签页采音、PCM 传输、全屏字幕、停止和刷新清理；使用受控页面音源，未完成实际 YouTube 直播及原声听感验收，详见仓库 docs/validation.md。
