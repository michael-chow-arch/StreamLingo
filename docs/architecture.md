# StreamLingo 包结构与模块边界

StreamLingo 以 YouTube 直播为主要场景，直接从标签页音频生成 AI 翻译字幕，不依赖主播提供字幕；同样的流程兼容普通视频。运行时包含一个 Chrome 扩展、一个本地 Python 服务，以及用户已有的 Ollama。扩展管理操作、采音和字幕视图；本地服务管理识别会话、字幕版本和独立翻译队列。Ollama 通过 TranslationProvider 的异步 HTTP 实现接入。

本文描述当前实现；安装见 [getting-started.md](getting-started.md)，实测结果和未验证范围见 [validation.md](validation.md)。

## 目录结构

以下目录已有功能实现，运行入口和构建输出见后文。

```text
StreamLingo/
├── extension/
│   ├── package.json
│   └── src/
│       ├── popup/                  控制界面与基础设置
│       ├── background/             启停、权限、目标标签页和消息路由
│       ├── offscreen/              持续采音、音频处理与 WebSocket
│       ├── content/                YouTube 播放器适配与字幕视图
│       └── shared/
│           ├── config.ts           插件设置类型与默认值
│           └── session.ts          会话界面状态
├── backend/
│   ├── pyproject.toml
│   └── src/streamlingo/
│       ├── domain/
│       │   └── models.py           内部音频、识别和翻译值对象
│       ├── ports/
│       │   ├── asr.py              流式识别端口
│       │   └── translator.py       翻译端口
│       ├── application/            单会话占用、有界音频队列和字幕版本
│       ├── adapters/               WhisperLiveKit、Ollama 薄适配及音频驱动 demo
│       └── transport/              HTTP、WebSocket 与输入验证
├── packages/
│   └── protocol/
│       └── src/                    消息类型与 Zod 运行时校验
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   └── implementation-plan.md
├── package.json                    npm workspace 与检查入口
└── tsconfig.json                   TypeScript 严格检查
```

`extension/manifest.json` 声明 MV3 权限和入口，`popup.html` / `offscreen.html` 承载页面。`scripts/build.mjs` 将各入口打包到可加载的 `dist/extension`；商店构建输出独立的 `dist/store-extension`，不带开发公钥。服务的 `cli.py`、`app.py` 与 `settings.py` 负责启动、依赖装配和配置，不把启动代码放进领域包。

Windows 的 Setup/Start/Stop/Doctor 入口调用 `scripts/` 下的安装、启动、停止和诊断脚本。Setup 将服务放入 `backend/.venv`，准备 `models/whisper-base`，将本机 Ollama 模型及扩展 ID 选择保存到不提交 Git 的 `.streamlingo.json`。预构建 Windows 包不需要 Node.js；源码构建需要。

## 运行上下文与状态归属

| 模块 | 持有的状态 | 与其他模块的交互 |
| --- | --- | --- |
| popup | 当前界面输入 | 向 background 发送控制与配置消息 |
| background | 目标 tab、启停协调和配置 | 创建 offscreen，向 content 投递字幕 |
| offscreen | 活动音频流、AudioContext、连接和真实采集状态 | 直接连接后端，通过 runtime 与 background 通信 |
| content | 当前会话字幕记录、自动分页阅读游标、播放器挂载点 | 接收字幕，报告目标视频变化 |
| application | 后端会话、有限音频/翻译队列和字幕版本 | 调用 ports，向 transport 输出源语言文字及所选目标语言译文 |
| adapters | 模型实例、识别引擎会话和 provider 客户端 | 实现 ports，不访问浏览器 |

浏览器上下文之间没有共享内存。background 被回收后，通过查询 offscreen 恢复当前状态，不能把 service worker 的模块变量作为唯一事实来源。`chrome.storage.local` 保存设置，浏览器会话存储可保存恢复所需的运行状态；上次记录的 running 不能代替对实际采集状态的确认。字幕正文不写入 Chrome 存储。

## 数据流

```text
popup --开始/停止--> background --流 ID 与配置--> offscreen
                                                     │
YouTube 标签页音频 ------------------------------------┤
                                                     ├--> 原声回放
                                                     └--> PCM / WebSocket
                                                              │
                                                              ▼
                        transport -> application -> ASR adapter
                                           │
                                           └------> TranslationProvider -> Ollama
                                                              │
                        transport <-------- 字幕更新 <----------┘
                            │
                            ▼
                        offscreen -> background -> content
```

音频包直接从 offscreen 发往后端，避免高频音频数据经过 Chrome 消息转发。返回的字幕是低频结构化消息，由后台投递到明确绑定的标签页。

## 语言方向与能力协商

| 弹窗设置 | start.source_language | start.target_language |
| --- | --- | --- |
| en-zh（默认） | en | zh-CN |
| zh-en | zh | en |
| auto-zh | auto | zh-CN |
| auto-en | auto | en |

界面中文/English 切换与翻译方向独立。方向在一次会话开始时确定，改变方向需停止后重新开始。

ASR 默认使用多语 `base`，由固定版本 WhisperLiveKit 0.2.26 / faster-whisper 执行。适配器检查已加载模型的真实语言能力，而非只看目录名；旧的 `base.en` 仍可显式使用，但仅允许英语输入，中文与 auto 会被拒绝。每次识别会话设置对应的源语言；auto 交给上游检测，不是逐词语言标签，也不保证短语音或混合语言的准确识别。

`/health` 在模型加载完成后公布可选的 `source_languages` / `target_languages`。旧服务或加载期间可能省略这两个字段；当前扩展只允许能力未知的旧服务尝试原有 en→zh-CN 方向，不据此开放新方向。`ready` 和 `subtitle` 可携带本次选定的 `source_language` / `target_language`；`auto` 保持表示用户选择的自动模式，不冒充模型已检测出的语言。完整字段规则见 [protocol.md](protocol.md)。

Ollama 适配器按会话方向生成提示词。自动模式将识别文本翻译为所选目标语言，提示模型保留已经是目标语言的部分；这属于推理指令，不构成语义正确性的保证。

## 后端依赖方向

```text
domain                         无框架依赖
ports        -> domain         定义应用所需能力
application  -> ports, domain   编排识别、字幕和翻译
adapters     -> ports, domain   实现具体引擎与模型服务调用
transport    -> application     验证输入并序列化输出
app.py       -> 上述模块        装配和生命周期管理
```

application 不导入 FastAPI、WhisperLiveKit 或 Ollama 客户端。transport 不能绕过 application 直接调用模型。Python 内部领域类型与线上协议分开，通过接入层映射。

前端协议包包含线上消息类型及 Zod 校验器。插件内部的设置、Chrome 消息和会话状态放在 `extension/src/shared/`，不混入跨语言协议包。

## MVP 技术选择

| 范围 | 选择与理由 |
| --- | --- |
| 插件 | Manifest V3、TypeScript、原生 HTML/CSS；界面规模小 |
| 构建 | esbuild 多入口打包，输出可加载扩展目录 |
| 音频 | 复用 Chrome 官方 tabCapture / Offscreen 模式；浏览器原生重采样，AudioWorklet 编码 |
| 网络 | 单条 WebSocket，JSON 控制消息与二进制音频共用 |
| 后端 | Python、FastAPI、asyncio，推理交由受控执行单元 |
| ASR | 固定 WhisperLiveKit 0.2.26，复用识别、VAD、流式上下文和停顿分段 |
| 翻译 | TranslationProvider + Ollama /api/chat 异步 HTTP；复用用户已安装的文本模型 |
| 存储 | 浏览器保存基础设置；启动脚本保存本机服务及模型配置；正常字幕流水线仅在会话内存中保存字幕，诊断日志可能包含识别文字 |

Python 基础包和默认 CI 不安装大型识别栈；WhisperLiveKit 及推理依赖由 `[asr]` 可选组提供，Windows Setup 会安装该组并准备语音模型。demo 使用固定示例、不加载真实模型，不是模型识别能力的验证。不自行开发识别引擎或 JavaScript 重采样器。具体复用与许可见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## 生命周期与失败行为

会话依次经过 idle、starting、running、stopping，再回到 idle。异常进入 error，资源清理后允许重新开始。

- 同一时间只允许一个活动采集会话。用户在另一个标签页启动时提示已有会话，先结束原会话再开始。
- 关闭弹窗或切换浏览器当前标签，不影响已绑定目标的采集。
- 目标标签页关闭、刷新、跳转离开或切换视频时结束会话并清除字幕；全屏和影院模式变化只调整挂载点。
- 停止请求幂等，页面立即隐藏字幕，后台取消网络与模型任务，超时后强制释放。旧 session 的迟到结果全部忽略。
- WebSocket 断开时停止采集，恢复播放器正常输出并提示重新开始。首版由用户手动重试，不回放断线期间的旧音频。
- 音频积压过多则结束会话，避免持续落后。浏览器发送缓存限 2 秒，服务应用队列限 5 秒；识别适配器另设输入队列和延迟上限。
- 翻译独立串行执行，默认最多 3 条等待，另有 1 条执行；未完成任务受默认 15 秒总年龄及 20 秒单次超时的较小值限制，失败后源语言文字仍可显示。等待队列满时跳过最旧的等待任务。有效结果成功返回后不再按年龄丢弃；任务携带原字幕快照，256 条后端元数据缓存淘汰不能吞掉成功结果。停止和断连取消 HTTP 请求，清空等待任务。未指定 Ollama 模型时声明 `translation=disabled`。

会话管理和字幕流水线在一个后端进程内，只允许一个识别会话。模型加载在线程中执行，翻译 HTTP 不阻塞识别。ASR 和 Ollama 仍可能争用同一 GPU 的显存和算力，异步编排不保证推理速度足够快。

识别适配器仅将上游已提交词交给最终化逻辑：标点、约 3 秒源语音或 120 个源文字字符可触发封段；已有稳定前缀等待 2.5 秒也会最终化，未稳定假设不送翻译。尾静音需等上游确认对应推理完成且 decoder buffer 清空。积压检查从未处理的音频区间扣除 VAD 静音，真实未处理语音超过 10 秒才报错。这些 ASR 界限与下述目标语言阅读分页是不同层的策略。

## 自动字幕阅读

页面保留当前会话有效字幕，避免较晚返回的译文被源缓存淘汰拒绝。完整译文按首次完成的到达顺序排队，
不设待显示数量或等待时间淘汰。文字使用浏览器原生 `Intl.Segmenter` 优先沿句子/词语边界自动分页，
所有页面拼接必须逐字还原原译文；页面内使用自然换行，不使用 `line-clamp` 隐藏尾部。
DOM 的文字仍为原文，CSS 折叠重复空白与强制换行，避免模型把几十个字各写一行而撑出播放器。

分页与阅读时间依据 `target_language`，不是界面语言：

| 目标语言 | 单页容量 | 阅读时长计算 |
| --- | --- | --- |
| zh-CN | 最多 48 个非空白 Unicode 码点 | 每秒 8 个非空白码点 |
| en | 最多 120 个字符，重复空白按一个空格计入；不是 120 个词 | 每秒 3 个词与每个非空白码点 50 ms，两者取较长值 |

两种预算都向上取整到毫秒，再限制为 4–8 秒。英文词数由 `Intl.Segmenter("en", { granularity: "word" })` 的 `isWordLike` 计数。上述是阅读产品默认值，不代表个体阅读速度，也不是识别延迟指标。过长单词或 URL 超过容量时，使用码点边界切分；原始空白仍保留在数据中，所有页拼接等于输入译文。

一个阅读周期开始时，最多合放两条同目标语言、不同片段的单页短译文，且按该语言计数后的合计不超过单页容量；多页长译文不参与合放，逐页连续显示。合放内容按一个空格连接计算阅读预算，视图仍保留两条独立字幕及各自原文。期间不再追加或抢换；读完后才自动轮换，没有后续结果时显示满 12 秒后隐藏。
计时使用单调时钟，没有新音频消息也会推进；后台计时器延迟时，新上屏页仍获得完整阅读时长，
不会瞬间追补一串页面。标签页不可见时停止阅读计时，继续接收译文；恢复可见时顺延当前页剩余时间。
源语言文字显示该片段完整原文，不将不对齐的原文切片误标为某页译文的对应原文。已显示页面的快照不可被后来的 revision 改写；有效的不同译文修订会另行入队，相同完成内容不会重复排队。

界面仅增加页码和待读页数，无历史面板、向上翻阅、暂停或导出控件。持续输入快于阅读时，延迟必然增长，
以保留已生成译文为优先，不自动追赶删除。存储仅为本次会话内存；DOM 只保留当前阅读组，
停止、刷新、导航或重新开始会清空记录、等待内容和计时器。**不丢弃仅指会话中已生成并成功收到的有效完整译文**：ASR 失败、翻译超时/跳过、传输中断或用户停止仍可能造成缺失；没有断线重放或持久化交付保证。

## 本地访问边界

服务默认监听 `127.0.0.1:8765`，插件设置只接受本机回环服务地址。后端配置保存运行模式、ASR 模型位置、Ollama 地址和模型名，不下发到 YouTube 页面。

插件权限按实际能力声明：tabCapture、offscreen、activeTab、scripting、storage，以及必要的目标/服务访问范围。不请求麦克风权限。后端校验 WebSocket Origin，HTTP CORS 单独配置；默认不允许任意网页调用本地服务。

## 官方依据

- [Chrome 标签页采音方案](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture)：Chrome 116 起可由 service worker 获取流 ID，并交给 offscreen 消费；页面需接回音频输出以保留原声。
- [Offscreen API](https://developer.chrome.com/docs/extensions/reference/api/offscreen)：offscreen 的扩展 API 使用限于 runtime，适合持有媒体相关 DOM API。
- [WhisperLiveKit 0.2.26 AudioProcessor](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/audio_processor.py)：连续 PCM 输入与识别输出；其内部协议不作为 StreamLingo 的公共契约。
