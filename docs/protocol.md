# StreamLingo 实时通信协议

本协议定义 Chrome 扩展与本地服务的 v1 边界。TypeScript 类型位于 `packages/protocol/src/index.ts`，浏览器使用 `validation.ts` 的 Zod schema 校验服务响应，Python 接入层使用 `transport/messages.py` 的 Pydantic schema 校验客户端消息。以下描述当前实现，不是历史规划。

## 入口与状态

默认服务地址为 `http://127.0.0.1:8765`：

| 入口 | 用途 |
| --- | --- |
| `GET /health` | 协议版本、运行模式、识别状态、翻译配置及可选语言能力 |
| `WS /ws/live` | 单次实时字幕会话 |

`/health` 本身不触发模型下载或推理。服务启动时加载识别模型，期间返回 `status=starting`、`asr=loading`。识别就绪后为 `ready`，加载失败为 `error`。翻译 `configured` 只表示已配置 provider，不保证当前 Ollama 可达、模型存在或推理成功；`disabled` 表示不运行翻译，仍可输出所选源语言的识别文本；`mock` 表示 demo 的固定测试输出。

health 和 ready 必须包含 `mode: "demo" | "whisperlivekit"`，区分固定示例与真实识别。demo 收到音频后才产生示例字幕，译文使用 `is_mock=true`，不能作为真实识别效果的证据。真实模式不会自动回退到 demo。

多语模型就绪时的 health 示例：

```json
{
  "protocol_version": 1,
  "mode": "whisperlivekit",
  "status": "ready",
  "asr": "ready",
  "translation": "configured",
  "source_languages": ["en", "zh", "auto"],
  "target_languages": ["zh-CN", "en"]
}
```

`source_languages` 和 `target_languages` 是可选能力字段。模型加载期间或旧服务可省略；省略不等于支持所有方向。当前扩展先检查模型是否就绪，再检查能力：字段明确不含所选语言时拒绝启动；旧服务缺少能力字段时只允许原有 en→zh-CN 方向，新方向提示升级后端。`LANGUAGE_CAPABILITIES_UNKNOWN` 是扩展内部提示码，不属于下述 WebSocket ErrorCode。

能力数组表示可选设置，不是它们笛卡尔积中的所有方向都有效，也不是对模型翻译准确性的承诺。

## 四种语言方向

| 扩展设置 | source_language | target_language |
| --- | --- | --- |
| en-zh（默认） | en | zh-CN |
| zh-en | zh | en |
| auto-zh | auto | zh-CN |
| auto-en | auto | en |

客户端 start 的源语言枚举为 `en | zh | auto`，目标语言为 `zh-CN | en`；只接受表中四种组合。方向在创建会话时确定，运行中不能通过修改设置或字幕消息切换。

默认语音模型为多语 `base`。后端依据实际加载模型的语言能力公布和校验源语言；`base.en` 仅支持 `en`，即使更改模型目录名也不能启用 `zh` 或 `auto`。

`auto` 使用上游 Whisper/faster-whisper 的语言检测。消息中的 `source_language: "auto"` 只表示所选模式，并非“已检测到某种语言”，协议不提供逐词语言标注。检测范围及效果取决于模型和音源，不保证短句、噪声或中英混说的准确性。Ollama 按所选目标语言翻译识别文本；已是目标语言的内容由提示词要求保留，这仍取决于模型输出。

## 建立会话

每条 WebSocket 只承载一个会话。后端先校验精确的扩展 Origin，未授权来源拒绝连接；session_id 不是访问凭据。首条应用消息必须为 start，默认等待上限 10 秒。插件每次启动生成新的 UUID：

```json
{
  "type": "start",
  "protocol_version": 1,
  "session_id": "f84428dc-f217-4a8b-b034-f3e5a0cc204c",
  "source_language": "en",
  "target_language": "zh-CN",
  "audio": {
    "encoding": "pcm_s16le",
    "sample_rate": 16000,
    "channels": 1
  }
}
```

成功后服务返回 ready：

```json
{
  "type": "ready",
  "protocol_version": 1,
  "session_id": "f84428dc-f217-4a8b-b034-f3e5a0cc204c",
  "mode": "whisperlivekit",
  "translation": "configured",
  "source_language": "en",
  "target_language": "zh-CN"
}
```

ready 的 `source_language` / `target_language` 在当前服务中回显选定方向，在客户端 schema 中可选以接受旧响应。存在时，offscreen 会检查是否与 start 一致，冲突则终止。收到合法 ready 前不发送二进制音频；浏览器握手等待上限为 15 秒。

不支持的版本、格式、语言组合、重复启动或未就绪模型均返回明确错误。JSON 可解析不代表消息有效；校验器拒绝额外字段、错误类型和非法范围。

## 音频格式与分段

每条二进制消息是连续音频的一段：单声道、16 kHz、有符号 16 位小端 PCM，无 WAV 头。推荐每包 100–200 ms，对应 3,200–6,400 字节；当前扩展使用 160 ms 分包。默认服务接受 2–32,000 字节的偶数字节包，拒绝空包和半个采样。

WebSocket 保证同一连接的消息顺序，不增加自定义二进制包头。音频时间按累计采样数计算：`sample_count / 16000 * 1000`。静音仍占据时间，客户端不删除静音后继续假装时间轴连续。

音频包边界不是字幕边界。ASR 适配器复用 WhisperLiveKit 的已提交词和标点分组，按标点、约 3 秒源语音或 120 个源文字字符封段；已有稳定前缀等待 2.5 秒也会最终化。尾静音必须等上游确认对应识别完成且 decoder buffer 清空。未稳定的 hypothesis 只作为临时原文，不进入翻译。

默认浏览器 WebSocket 待发送音频上限为 64,000 字节（2 秒），服务应用音频队列上限为 160,000 字节（5 秒），另有限制输入队列项目数。识别器按实际未处理语音检查积压，扣除对应区间的 VAD 静音；真实语音积压超过 10 秒会报 `AUDIO_BACKLOG`。这些是不同环节的保护，不代表统一的延迟保证。

## 字幕事件与修订

每次字幕消息是一个完整片段快照。同一片段的临时原文、最终原文和翻译状态更新使用相同 segment_id，revision 递增：

```json
{
  "type": "subtitle",
  "session_id": "f84428dc-f217-4a8b-b034-f3e5a0cc204c",
  "segment_id": 12,
  "revision": 2,
  "start_ms": 18300,
  "end_ms": 21700,
  "source_text": "Let's look at the next example.",
  "source_final": true,
  "source_language": "en",
  "target_language": "zh-CN",
  "translation": {
    "status": "pending",
    "text": null
  }
}
```

| 字段 | 约定 |
| --- | --- |
| session_id | 必须属于当前活动会话，旧会话迟到结果忽略 |
| segment_id | 后端在会话内从 1 递增分配；译文可以晚于较新片段返回 |
| revision | 每片段从 1 递增；忽略小于或等于已接收版本的消息 |
| start_ms / end_ms | 采集音频时间；非负整数，start_ms 不大于 end_ms |
| source_text | 所选源语言模式的识别纯文本，不限定为英语；auto 不是逐句检测标签 |
| source_final | true 后源文字及时间范围冻结，后续只能更新翻译状态 |
| source_language / target_language | 可选的会话方向；当前服务发送，旧响应可省略，页面按已知会话设置补齐 |
| translation | 完整状态对象，不通过缺失字段猜测状态 |

翻译状态：

| status | text | 含义 |
| --- | --- | --- |
| disabled | null | 本片段尚无翻译工作；可因服务未配置 translator，或原文尚未最终化 |
| pending | null | 已最终化原文进入翻译工作，结果未完成 |
| complete | 非空字符串，另有必填 is_mock | 所选目标语言的完整结果；只有 source_final=true 才允许 complete |
| error | null | 本片段翻译失败，源文字仍可显示 |
| skipped | null | 尚未完成的翻译因积压或年龄预算跳过 |

真实中文完成结果示例为 `{"status":"complete","text":"我们来看下一个例子。","is_mock":false}`；目标为 en 时 text 是英文。测试输出必须 `is_mock=true`，界面明确标记。不能把是否含汉字作为所有真实翻译的判断条件，例如数字或专有名词可能保持原样。

source_final 与翻译完成是两件事。翻译任务保存对应最终原文快照，即使后端 256 条元数据缓存淘汰了该片段，成功结果仍可以正确更新它。前端保留本会话全部有效片段并接受晚到的 complete，不以“不是最新片段”或旧的 8 条缓存限制拒绝。已最终化源文或时间被改变的消息仍会被拒绝。

## 翻译任务与页面阅读队列

后端默认最多 3 条等待翻译，另有 1 条执行。队列满时最旧的等待任务成为 skipped。默认总年龄为 15 秒（含等待和推理），单次翻译超时为 20 秒，实际使用两者中剩余时间较短的预算。失败或跳过产生对应片段修订和非致命 error 事件。有效结果已经成功返回后，不再仅因调度延迟超过年龄预算而丢弃。

页面对已收到的完整译文按完成到达顺序自动排队；不能用全局“最新字幕”覆盖旧句结果。分页是扩展的阅读策略，不新增 WebSocket 消息或 segment_id：

| target_language | 单页限制 | 4–8 秒阅读预算的基础计算 |
| --- | --- | --- |
| zh-CN | 48 个非空白 Unicode 码点 | 非空白码点数 ÷ 8 秒 |
| en | 120 个字符，重复空白按一个空格计数；不是 120 个词 | 英文词数 ÷ 3 秒与非空白码点数 × 50 ms，取较长值 |

`Intl.Segmenter` 优先选句子和词边界，超长词再按码点切分。分页保存所有原始字符，拼接后等于完整译文。最多两条同目标语言的不同单页片段可在容量内合放，长译文各页连续显示；每个阅读周期固定内容，按合计文字计算时间，不在中途追加。所有时间从实际上屏开始计算。隐藏标签页暂停推进，恢复时继续剩余阅读时间；采音和接收消息不因此停止。没有后续页时，最后一组显示 12 秒后隐藏。

**不丢弃保证仅限当前会话中已生成并成功收到的有效完整译文。** 不对它们设置数量淘汰或等待 TTL，也不通过 CSS 裁掉译文尾部。它不能恢复 ASR 未识别、尚未完成翻译已超时/跳过、网络未送达或会话结束的内容；持续讲话快于阅读时，显示延迟会累积。没有持久化字幕历史、断线重放或交付确认协议。

## 错误与结束

error 包含 code、message、fatal、session_id 与可为空的 segment_id。有效 start 接受前，session_id 允许为 null。错误文本不应包含认证信息或原始模型请求内容。

| 错误码 | 行为 |
| --- | --- |
| INVALID_MESSAGE / UNSUPPORTED_PROTOCOL | fatal，拒绝消息或协议并关闭连接 |
| UNSUPPORTED_LANGUAGE | fatal，拒绝不支持的方向或加载模型不支持的源语言 |
| ASR_NOT_READY / ASR_FAILED | fatal，拒绝启动或停止识别会话 |
| AUDIO_BACKLOG | fatal，停止会话，避免持续落后 |
| SESSION_CONFLICT | fatal，仅拒绝新会话，不影响原有活动会话 |
| TRANSLATION_FAILED / TRANSLATION_TIMEOUT | 非 fatal，对应字幕成为 error，源文字仍可显示 |
| TRANSLATION_BACKLOG | 非 fatal，对应未完成翻译成为 skipped |
| INTERNAL_ERROR | fatal，清理并关闭连接 |

停止时客户端发送 `{"type":"stop","session_id":"..."}`，立即清空页面字幕并禁止后续结果渲染。服务取消待处理工作、释放识别会话，尽可能回复 `{"type":"stopped","session_id":"...","reason":"user"}`，再关闭连接。停止是立即结束，不等待最后一句译文或读完等待页。schema 也允许 stopped.reason 为 error；当前 transport 在 fatal 失败时发送 error 后关闭，不保证另发 stopped。

断开时不依赖 stop/stopped 一定送达，双方自行释放资源。扩展的重复停止操作幂等。再次开始使用新连接和新的 session_id，不续传旧音频。会话占用、音轨、AudioContext 和未完成 HTTP 请求都应随生命周期清理。

## 兼容与协议演进

当前可选语言字段让新版客户端接受旧响应，不等于旧客户端能接受新增字段。旧版也使用严格 schema，可能拒绝新字段，因此应配套升级扩展和本地服务。未知字段不应被当成可任意添加的扩展点。

字段重命名、状态含义或音频格式等破坏性变更应增加 protocol_version。线上 schema、TypeScript 类型、Python 接入层、合法/非法消息测试及本文需同步更新。Python domain 对象用于内部计算，不直接充当线上 JSON schema。
