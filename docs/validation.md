# 验证记录

环境：Windows，i7-13700KF、RTX 3080 10 GB、本地 Python 虚拟环境、Node.js。当前使用 WhisperLiveKit 0.2.26、faster-whisper 1.2.1、多语 `base` 和已有 Ollama 0.34.2 / `qwen3.5:9b`；历史英语回归使用 `base.en`。

## 2026-10-13：Chrome 真实直播短测

在真实 Chrome 已加载的扩展中，选择 [DW News 英语直播](https://www.youtube.com/watch?v=LuKwFajn37U)，采用英语 → 中文。页面显示正在直播且 YouTube 原生字幕不可用。启动检查后，在北京时间 17:37:03–17:38:04 的约一分钟窗口观察真实播放器与字幕：原文和中文译文更新、字幕在播放器内展示、未显示积压或连接异常。运行的本地服务使用真实多语 Whisper base 和已有 Qwen；没有替换音频、模型输出或注入演示字幕。

Chrome 工具栏的开始/停止按钮由用户点击，页面操作与字幕状态由浏览器工具检查。用户确认开启字幕期间原声正常；手动停止后，字幕层消失而视频继续播放。随后切换至 Sky News 检查导航清理：用户确认切换后会话已停止，后来出现的字幕是用户手动重新开始。最初误将这次重新开始判断为导航异常，澄清后未据此修改代码。关闭测试标签页后，本地日志记录识别资源清理完成。

这是单台电脑、单方向的短时功能验收，未计算端到端延迟或识别准确率。采样中仍有专有名词识别错误；不能把该结果宣传为任意直播、口音或混合语言均准确。直播画面和采样文字仅留在本地验收记录，不作为开源宣传素材上传。其他实体电脑的完整安装及 GPU 推理尚待验证。

## 2026-10-13：发布前安装、依赖与长测验收

性能数字、硬件与模型参数、P50/P95 定义及复现命令集中放在[独立性能测试表](benchmarks.md)。不要把额外阅读等待当作 Chrome 端到端延迟，也不要把本机配置当作最低硬件门槛。

- 将 Windows 预览 ZIP 解压到独立目录，确认最初不存在 `.venv` 或语音模型；在不含 Node/npm 的 `PATH` 下完成真实 Setup。使用机器上已有 Python 和 Ollama，下载缓存可复用，并非一台全新的 Windows。安装约 5 分 19 秒，`pip check`、启动到 ready、Doctor、英译中/中译英短测均通过。没有重新安装或替换 Ollama 模型。
- 按真实时间送入原创 TTS 音频，用真实 Whisper + Qwen 完成英译中 30 分 23.280 秒、中译英 30 分 16.215 秒长测：分别 672、675 条 final 全部完成翻译，两轮均为 0 错误、跳过、未完成或断连，收到正常停止确认。
- 两轮完整事件经过生产字幕调度器离线回放：分别 672、675 条译文全部显示，共 672、676 页，分页拼接无字符丢失/改写，最短显示 4 秒。新验收器额外按片段 ID 核对每个 final 必须收到非空、非 mock 的 complete；旧录制以只读 `review` 入口重新验证，原文件不改写。
- Windows 启动要求 CUDA 12 cuBLAS、完整 cuDNN 9 和可见 CUDA 设备。移除测试子进程中的 CUDA 搜索路径后，真实 CLI 在加载 ASR/监听端口前以退出码 2 停止并列出缺失 DLL。没有切换 CPU、改全局环境或影响运行中的服务；无可用 GPU 的路径使用替身验证。运行条件见[版本表](runtime-requirements.md)。
- 两轮长测结束后，通过各自的启动/停止脚本关闭临时安装服务、恢复仓库目录中的日常服务。启用严格运行条件检查后实际启动至 ready，Doctor 全部通过；重新执行真实英译中、中译英短测，均收到非 mock 完整译文及正常停止确认。
- 后端完整环境 **162 项测试通过**；仅 `[test]` 环境 **161 通过、1 跳过**。Windows 启动/诊断脚本 **39 项通过**，含真实 PowerShell 5.1 → Python 的版本/位数参数校验。前端/协议原有 **90 项测试**、类型检查和构建通过，字幕回放脚本的英文阅读预算已与生产实现对齐。
- [CI `003b486`](https://github.com/michael-chow-arch/StreamLingo/actions/runs/38372753031)（严格运行条件）及 [CI `39a3e37`](https://github.com/michael-chow-arch/StreamLingo/actions/runs/38373017929)（长测验收脚本）均在 GitHub 显示成功。CI 不运行大模型或真实 GPU 推理。

本机原始证据在 gitignored 的 `output/release-acceptance/20261013/`，音频/事件/日志不随 Git 推送。测试接入点是生产 WebSocket，不是 Chrome 标签页采音；合成语音稳定性与离线显示完整性不等于真实 YouTube 直播准确率和浏览器长时验收。

## 2026-10-13：0.2.0 多语、安装与发布准备

- 全仓 TypeScript 类型检查、90 项前端/协议测试及开发构建通过；后端完整环境 133 项测试通过。
- 独立干净 Python 3.11 环境仅安装 `[test]`：132 通过、1 跳过（需可选语音依赖的上游契约测试）。未安装 ASR/torch 或连接 Ollama，验证 CI 不必下载模型。[GitHub CI `40c5e1c`](https://github.com/michael-chow-arch/StreamLingo/actions/runs/38367142904) 已确认成功：前端 Node 22、后端 Python 3.11/3.12、Windows 启动脚本 Python 3.11/3.13，共五个作业。后续变更需单独检查新提交的 CI。
- Windows PowerShell 5.1 安装/启动脚本静态解析及 24 项隔离测试通过。覆盖无聊天能力模型、坏配置、模型缺文件、免 Node 发布包、重复启动、带空格路径、停止时 PID/安装目录校验和 CMD 退出码。
- 在本机现有 Python/Ollama 环境实际执行 `setup.ps1 -NonInteractive`，选中已有 Qwen，安装后端 0.2.0、准备固定版本多语 base、重建扩展并保存本机配置；随后真实停止旧服务、启动新服务至 ready，Doctor 全部通过。**没有在一台无 Python 的干净 Windows 电脑上执行 winget 安装分支。**
- 英文和中文原创文本通过系统 TTS 生成 16 kHz 单声道 PCM16，实时发送到生产 WebSocket，经过真实 ASR 与 Qwen。未替换模型输出。四个模式及两个同语场景均正常结束，共收到 24 个 `complete`、`is_mock=false` 的最终片段，无 fatal 错误：

| 输入 | 识别设置 | 目标 | 完成片段 |
| --- | --- | --- | ---: |
| 英文 | en | zh-CN | 4 |
| 中文 | zh | en | 4 |
| 英文 | auto | zh-CN | 4 |
| 中文 | auto | en | 4 |
| 中文 | auto | zh-CN | 4 |
| 英文 | auto | en | 4 |

复现音频：`scripts/make-language-fixtures.ps1`；链路入口：`scripts/smoke-live.py --source-language en|zh|auto --target-language zh-CN|en`。原始本机结果保存在 gitignored 的 `output/languages/`。这验证语言路由、真实推理和会话生命周期，**不等于高准确率验收**：多语 base 在中文示例把“布置”听成“不知”、“浇水”听成“交水”，错误可能传入翻译；自动译中也出现了“交水费”的错误补写。英文同语样例原文保持一致，但提示词不能保证任意模型逐字保留同语输入。不能据此宣传所有口音、混合语言或快速直播均准确。

UI 使用构建后的 popup/content，在内置浏览器的本地 fixture 验证：四模式选择、设置保存/重开、界面语言独立切换、运行时锁定方向、中英文字幕展示。正常折叠状态英文弹窗高 579px，中文 545px，宽 380px。宣传截图为原创场景的 **UI 演示**，模拟 Chrome 消息/连接状态，不是实录直播或真实模型质量展示。本轮未连接 Chrome 自动化，未重新执行 Chrome 标签采音/扩展安装测试；需人工刷新现有扩展和直播页后检查。

开发构建使用固定开发 ID；商店构建去掉开发 key 和 source maps，白名单 ZIP 包含运行文件与第三方许可。Windows ZIP 带已构建扩展、后端源码及 Setup/Start/Stop/Doctor，排除模型、虚拟环境、用户配置、音频和运行日志。所有材料仅保存在本机，未上传 GitHub Release 或提交 Chrome Web Store。

## 2026-10-13：无丢弃自动分页（此前英语→中文回归）

按用户最新要求，界面只自动播放字幕，不提供历史面板、往上翻、暂停按钮或导出。
已移除前端 4 条待显示上限、12 秒排队淘汰和 8 条源缓存淘汰；收到的完整译文逐页依次显示。
长句复用浏览器原生 `Intl.Segmenter` 按句/词边界拆页，每页最多 48 个非空白字符，拼接逐字还原译文。
相邻不同片段的单页短句可两条同屏，合计也不超过 48 字，按合计长度保护至少 4 秒；读到中途不插入新内容。
标签页隐藏时自动冻结阅读时间，返回后保留剩余时间；停止或切换视频仍清空本会话。
异常换行由 CSS 折叠，原始文本保留；无滚动、裁切或 line-clamp。

后端同时修复两个“已有结果却未发送”的路径：有效译文返回后不再按总年龄后置丢弃，翻译任务携带
final cue 快照使 256 条元数据缓存淘汰不吞结果。未完成的翻译仍有排队/超时限制，本轮没有增加持久化或断线重放。
后端两个行为回归先验证旧代码失败，修复后 **100 项测试通过**。前端类型检查、**80 项测试**及构建通过。
服务已重启，健康检查 `status=ready`、`asr=ready`、`translation=configured`。

使用同一份既有真实 ASR/Qwen 事件，离线导入生产 store/presentation 按原到达时间运行全部定时器；
另外使用明确标记的合成压力输入。每条字幕实际显示的所有页拼接，与完整原译文逐字比对：

| 检查 | 真实事件离线回放 | 合成压力回放 |
| --- | ---: | ---: |
| 收到 / 显示完整译文 | 96 / 96 | 240 / 240 |
| 字幕页 / 丢失片段 | 96 / 0 | 400 / 0 |
| 每页最短上屏时间 | 4 秒 | 4 秒 |
| 额外等待中位数 / P95 / 最大值 | 5.235 / 13.357 / 14.354 秒 | 682.500 / 1303.500 / 1372.500 秒 |
| 末次输入 / 自然排空时刻 | 198.155 / 221.662 秒 | 119.500 / 1503.500 秒 |

压力输入每 0.5 秒完成一条且包含多页长句，故保留全部内容时会累积明显延迟；本实现不保证持续超负载仍紧跟直播。
额外等待不含识别/模型推理时间。此次没有重跑模型，不把离线回放描述成真实直播端到端结果。

在 Chrome 的本地模拟播放器中使用最终构建后的 content.js 验证：3 秒内保持原页、4 秒后自动两短句同屏；
长句第 1/4 页到第 2/4 页连续显示；切换界面语言不改正在读的中文；模拟隐藏 12 秒后恢复仍有原页剩余时间；
320×180 小播放器的异常多行文字完整落在字幕区内；停止并推进时间不重新显示。控制台无错误或警告。
测试页模拟浏览器消息、时间与可见性，不包含真实采音，也未自动重载用户的扩展。

成熟项目研究以 [Shaka 字幕显示器](https://github.com/shaka-project/shaka-player/blob/22f11501cff41da1bb116bdacb8478c70fa41d51/lib/text/ui_text_displayer.js)
的 cue 显示与换行方式为参考；未引入完整播放器。Able Player、videojs-transcript 的回看方案经研究后按用户要求不采用，
未保留虚拟滚动依赖。自动分页、保护阅读时长和短句分组为本项目的到达式字幕策略，不声称来自 Shaka。

证据：无丢弃回放摘要（本地文件：`output/no-drop-pagination/summary.md`）、
真实事件离线回放（本地文件：`output/no-drop-pagination/recorded-replay.json`）、
合成压力回放（本地文件：`output/no-drop-pagination/stress-replay.json`）。

```powershell
node --import tsx scripts/replay-reading-window.ts
```

## 2026-10-13：识别短语反复循环

用户截图在英文中已经包含多遍 `Assaam karikum`，中文是对重复英文的翻译。
服务日志默认没有保存字幕文本或音频，所以不能用日志精确还原截图时的原音频和识别提示。
只读探针确认同一结果重复投递不会导致后端多次翻译或前端拼接；但上游模型若产生多个相同词的新 token，
LocalAgreement 会确认这些词，随后适配器按原样传递。未找到正常路径中 token 对象重建导致重复消费的证据。

定位到两个历史提示来源：WhisperLiveKit 每次解码注入已提交历史的约 200 字尾部，
faster-whisper 也默认在内部窗口间使用先前文字。修复同时覆盖 `initial_prompt=None` 与
`condition_on_previous_text=False`；未添加全文去重、禁词或硬性重复 n-gram 屏蔽。
后端 **99 项测试通过**，覆盖跨调用提示清除、原模型/调用参数不变及重复词生成器对象原样返回。

使用原创英文合成音源（20.485 秒，Zira，16 kHz / mono / PCM16）进行真实 base.en 对照，
音源包含两次 `Please wait.`、`very, very` 及其他正常句子。人为给解码器传入截图中的重复短语作为历史提示：

| 音源 | 原配置，无污染提示 | 原配置，重复历史提示 | 修复配置，相同重复提示 |
| --- | --- | --- | --- |
| 20.485 秒英文 | 正常英文，两次 Please wait 与 very, very 均保留 | 输出 28 遍 Assaam karikum | 与无污染基线逐字一致，污染短语 0 次 |
| 8 秒数字静音（直接模型调用，无实时 VAD） | You | 输出 28 遍 Assaam karikum | You，与无污染基线一致 |

这证明重复历史能在本机模型上造成与截图相似的循环，并证明当前参数能切断该反馈；
它不是用户原直播音频的重放，不能确定最初是哪一段音频触发了错误，也不能分别量化两个参数的收益。
直接模型静音测试仍出现单词幻觉，本次不宣称消除了所有错误输出。

最初探针把“直接解码静音必须为空”写成通过条件，因此原始 `prompt-probe.json` / `.log` 保留 `passed=false`。
该断言超出了此次切断历史提示的目标。修正评估后离线复核相同真实模型输出，另存
`prompt-probe-reviewed.json`，注明 `inference_repeated=false`，没有修改原模型文本或重新推理。

服务已重启并应用新配置，真实 WebSocket → ASR → Qwen 回归通过：收到 7 条 `is_mock=false` 的完整中文，
没有异常重复循环或 fatal，停止得到确认，随后 `/health` 为 `ready`。
流式结果只提交了一次 `Please wait.`，但 `very` 两次分在相邻字幕中；这表明直接解码保留重复不等于
流式确认一定不漏词，仍保留此准确率限制，未用已知文本补写输出。
本次仅修改后端识别参数；已运行的识别会话会因重启结束，需要重新点“开始字幕”。

证据：对照原始模型输出（本地文件：`output/regression-repetition/prompt-probe.json`）、
限定范围的离线复核（本地文件：`output/regression-repetition/prompt-probe-reviewed.json`）、
真实翻译链路（本地文件：`output/regression-repetition/live-repeat.json`）、
新配置服务日志（本地文件：`output/regression-repetition/after-service.log`）。
官方参数说明见 [faster-whisper 1.2.1](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)。

```powershell
.\scripts\make-repeat-fixture.ps1
# GPU 对照测试前停止字幕服务，避免与直播争用模型资源
.\scripts\stop.ps1
.\backend\.venv\Scripts\python.exe scripts/probe-asr-prompts.py
.\scripts\start.ps1 -Background
# 服务 ready 后验证真实流式链路
.\backend\.venv\Scripts\python.exe scripts/smoke-live.py output/regression-repetition/english-repeat.wav --output output/regression-repetition/live-repeat.json
```

## 2026-10-13：快速讲话时字幕阅读保护（历史方案，已由自动分页取代）

用户选择阅读优先：旧实现的 12 秒只是过期时间，新译文仍会立即抢换上一个译文。
新增两个独立阅读槽，已显示中文从上屏开始按长度保护 4–8 秒；空闲时最多显示 12 秒。
新译文按完成顺序排队，最多 4 条、等待最多 12 秒，溢出或过期只跳过未上屏项并显示提示。
当前英文预览不能绕过队列显示中文；源缓存淘汰、重复 revision、语言切换和计时器延迟不能缩短阅读时长。
较早就被源缓存淘汰的消息继续忽略；追赶提示仅统计进入阅读队列后因上限或过期而跳过的译文。

TypeScript 检查通过，前端 **66 项测试通过**，扩展构建成功。
新增用例覆盖快速到达、长句时长、无新消息靠计时器推进、延迟回调、自然隐藏、乱序、重复结果、
缓存淘汰及队列上限；DOM 用例验证英文更新保留原中文节点，切换语言保留阅读内容和计时。

使用下文同一次真实 Whisper + Qwen 的事件记录进行**离线调度回放**，没有重跑模型，也没有把已知文本当模型结果：

| 检查 | 原记录时间回放 | 每 0.5 秒一条的合成压力回放 |
| --- | ---: | ---: |
| 收到完整译文 | 96 | 240 |
| 实际显示 / 跳过 | 95 / 1 | 45 / 195 |
| 最短上屏时长 | 4 秒 | 4 秒 |
| 每条达到其长度对应的阅读时长 | 通过 | 通过 |
| 额外等待中位数 / P95 / 最大值 | 1.832 / 6.847 / 7.485 秒 | 2.000 / 5.500 / 9.000 秒 |
| 最多显示 / 等待条数 | 2 / 4 | 2 / 4 |
| 自然排空、无已显示文本变更或重复播放 | 通过 | 通过 |

原记录跳过的片段为 67；数字翻译 `4。` 正常计为完整译文。
额外等待从翻译完成到上屏计算，不含识别和翻译耗时；阅读优先会增加显示延迟，极端负载下不会保证展示每一条。
原记录最终在 214.367 秒自然隐藏全部字幕。停止消息没有参与自然排空回放，主动停止另通过浏览器检查。

Chrome 中使用构建后的 `content.js` 和本地模拟播放器检查：第 1 秒第三条译文到达时仍显示前两条；
第 4 秒由定时器自动轮换第一条；语言切换不改中文或截止点；无新输入时自然隐藏；
停止后推进时钟不会重新显示排队字幕。控制台无错误，普通 960 × 540 播放器布局可读。
测试页模拟 Chrome 消息与时钟，不包含真实采音或 YouTube 直播，未自动重新加载用户的扩展。
仍保留原有普通播放器中文最多两行、小播放器最多一行的限制，未增加长句分页。

证据：离线回放摘要（本地文件：`output/readability/summary.md`）、
录制事件回放（本地文件：`output/readability/recorded-replay.json`）、
密集输入压力回放（本地文件：`output/readability/stress-replay.json`）。

上述 `output/readability/` 保留的是旧实现结果。当前 `scripts/replay-reading-window.ts` 已改为检查无丢弃自动分页，
使用相同原始事件但另写 `output/no-drop-pagination/`，不覆盖旧报告。输出证据位于被 Git 忽略的 `output/`。

## 2026-10-13：持续讲话分段、真实积压与界面国际化

本次用户日志显示输入 131.840 秒、处理进度 120.386 秒、未处理静音 1.446 秒，
实际语音积压为 10.008 秒。这次触发的是处理速度不足，不是下文已修复的静音误计问题。
原日志保存在 `output/regression-continuous/before-service.log`。

持续讲话现在以已提交词分段：约 3 秒音频或 120 字符时封尾，首个稳定词等待 2.5 秒后也会提交；
新增词和重复快照不会延长该等待时间。不把尚未稳定的识别假设提前当作最终文字。
这里的 2.5 秒从首个稳定词开始计时，不是从声音输入起算的端到端延迟保证。
复用 WhisperLiveKit 的合并和裁剪配置，默认合并间隔 0.8 秒、缓冲裁剪 8 秒；
使用薄模型代理将 faster-whisper 解码设为 beam size 1、best of 1、temperature 0，降低持续推理成本。
真实语音积压超过 10 秒仍保留停止保护。识别继续限定英语，本次没有加入印地语支持。

| 检查 | 结果 |
| --- | --- |
| 后端 pytest | 97 项通过，覆盖稳定词超时、长度分段、配置边界及现有静音/积压保护 |
| 前端 | TypeScript strict 检查通过，57 项测试通过，扩展构建成功 |
| 连续英文真实推理 | 197.875 秒合成讲话，96 条 final 对应 96 条真实完整翻译；其中 95 条含汉字，另 1 条为数字翻译 |
| 中文到达 | 首条约 4.834 秒，含汉字译文最大到达间隔约 4.933 秒；每个 30 秒讲话窗口均有 final 与中文 |
| 连续字幕长度 | 此样本最大 final 为 71 字符 / 3.5 秒，最大 partial 为 62 字符 |
| 连续会话状态 | 无 fatal 或非致命错误，final 冻结、revision 与停止确认检查通过，无未完成译文 |
| 两次 16 秒静音后恢复 | 新配置下复测通过，整体 91.207 秒；三段讲话分别收到 8 / 9 / 9 条真实翻译，无错误 |
| 本地服务 | 已按新配置重启，测试后 `/health` 为 `ready`，ASR 为 `ready`，翻译为 `configured` |

连续回归首次运行的脚本错误地要求每一条译文必须含汉字，将有效的 `4.` → `4。` 数字翻译判为缺失，
导致额外等待并报告失败。原始 `continuous.json` 保留不改；修正断言后离线复核同一次真实事件记录，
结果保存在 `continuous-reviewed.json`，明确标注 `inference_repeated: false`。
没有重新运行模型或替换其输出，原运行总耗时 234.417 秒包含该额外等待。
识别仍出现个别误词和多余短句；本样本仅验证持续产出和故障回归，不能代表直播准确率。

界面将 MVP 标记替换为中文 / English 选择器，语言偏好独立持久化；切换不会覆盖设置草稿、
改变英译中方向或重启采集。使用构建后的 popup 在本地 HTTP 测试页中验证中文、英文、键盘切换、
刷新后偏好保留、未保存草稿保留、运行中切换及积压错误本地化；380 px 布局无横向溢出，控制台无错误。
该测试页的 Chrome API 为模拟实现，不能替代已安装扩展验收。字幕 DOM 测试另验证语言切换不会延长原有 12 秒显示期限。
浏览器安全策略禁止自动访问 `chrome://extensions`，因此本轮没有自动重新加载用户的扩展；
用户需手动刷新 StreamLingo，再刷新 YouTube 页面以加载新的内容脚本。

证据：连续讲话复核报告（本地文件：`output/regression-continuous/continuous-reviewed.json`）、
原始连续讲话报告（本地文件：`output/regression-continuous/continuous.json`）、
静音恢复报告（本地文件：`output/regression-continuous/silence.json`）、
修复后服务日志（本地文件：`output/regression-continuous/after-service.log`）。这些本地输出不随源码提交。

复现命令（需要本地服务运行，会占用唯一识别会话）：

```powershell
.\scripts\make-continuous-fixture.ps1
.\backend\.venv\Scripts\python.exe scripts/regression-silence.py --continuous --output output/regression-continuous/continuous.json
.\backend\.venv\Scripts\python.exe scripts/regression-silence.py --output output/regression-continuous/silence.json
```

## 2026-10-13：静音后恢复说话误报积压（前一次修复）

用户报告翻译数句后停止，弹窗提示 `Speech recognition is over 10 seconds behind`。
对应会话持续 36.48 秒；恢复说话前有约 15.62 秒静音，上游随后已推进处理进度，适配器却仍拿旧结果的延迟减去已清空的“当前静音”，把静音误算为语音积压。

修复改用按序消费的音频进度与语音边界事件，对照当前 ASR 处理进度，只计算未处理区间中的语音时长。
已结束的静音区间保留到处理进度跨过它，旧结果快照不再参与积压计算。真正超过 10 秒的语音积压仍会停止会话，并记录数值诊断。

后端自动化测试共 **79 项通过**。新增最小恢复用例已先确认旧代码会失败；修复后覆盖旧快照重放、两轮长停顿、
输入/VAD 事件尚未消费的竞态、静音与未处理区间交集、真实语音超过 10 秒的保护，以及尚无结果快照时的积压检查。

新增专用真实模型回归脚本，同一会话播放三段已知合成英文，两次间隔各 16 秒静音：

```powershell
.\backend\.venv\Scripts\python.exe scripts/regression-silence.py --output output/regression-20261013/silence-regression.json
```

脚本按真实速度送音频，逐个语音窗口检查最终英文及 `is_mock=false` 的中文，同时检查 final 冻结、revision 递增、无 fatal 和停止确认。
需要本地服务运行，会短暂占用唯一识别会话；仅使用已有合成测试音源。
原故障服务日志保存在 `output/regression-20261013/before-service.log`，不随源码提交。

修复部署后的真实 Whisper + Qwen 回归**通过**：88.955 秒音频，整体耗时 91.566 秒。
初始语音、第一次恢复、第二次恢复分别收到 5 / 6 / 4 条最终英文和真实中文，共 15 条翻译，
fatal 与非致命错误均为 0，final/revision 检查通过，收到 `stopped` 确认。
测试后本地服务仍为 `ready`，扩展代码无需变更或重新加载。
这是合成音源的故障回归，不代表已完成真实 YouTube 直播的长期准确率验收。

证据：完整回归报告（本地文件：`output/regression-20261013/silence-regression.json`）、
修复后服务日志（本地文件：`output/regression-20261013/after-service.log`）。

## 2026-10-12 自动化检查

| 命令 | 结果 | 覆盖范围 |
| --- | --- | --- |
| `npm run check` | 类型检查通过、47 个测试通过、构建成功 | 控制来源、启停竞态、Worker 恢复、字幕阅读窗口与版本、PCM、握手、断连、发送积压、服务响应校验 |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 71 个测试通过 | HTTP/WS、来源限制、真实 TCP、会话清理、ASR 适配、翻译队列/超时/过期与取消 |

本轮检查无失败测试。单元测试中的 ASR 输出映射使用结构替身；真实模型单独按下文验证。

## 本机真实模型与 WebSocket 联调

识别模型为 Systran/faster-whisper-base.en，固定 revision `3d3d5dee26484f91867d81cb899cfcf72b96be6c`。
model.bin 大小 145,216,508 字节，SHA-256 为 `2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef`。
存放于 `models/whisper-base.en`，实际使用 CUDA / int8_float16；已有 CUDA 12.4 路径可用，没有修改全局环境。

音源由 Microsoft Zira Desktop 合成，16 kHz / mono / PCM16，16.985 秒。音频已知内容仅用于人工核对，ASR 与 Qwen 均进行真实推理，没有把已知文字替换为识别输出。

| 检查 | 结果 |
| --- | --- |
| 依赖 | WhisperLiveKit 0.2.26、faster-whisper 1.2.1，pip check 通过 |
| 独立 ASR | 5 条稳定 final，首条 2.711 秒；追加 16 秒静音无积压错误 |
| Ollama 单独调用 | qwen3.5:9b 首次 10.501 秒、同句热请求 0.570 秒，返回真实中文 |
| 最新代码的 WS + ASR + Qwen | 按真实速度发送音频及尾静音，收到 6 个 complete，全部 is_mock=false，无 fatal 错误，stop 得到 stopped |
| 最新全链路首条英文 / 中文 | 从 WS 客户端启动起约 1.571 秒 / 9.929 秒，包含识别及首次翻译等待；不包含 Chrome 采音 |
| 后台启动与停止脚本 | 启动健康检查 ready；停止同时释放 Windows venv 启动器及实际 Python 服务进程、释放 8765 端口，随后重新启动成功 |
| Chrome 安装 | 用户反馈已手动加载或刷新新版扩展，未通过自动化再次核验日常 Chrome 界面 |

实际译文包括“大家好。”“欢迎来到我们的直播。”“浏览器将音频直接发送至本地语音识别服务。”。
最新全链样例的最后一句完整翻译后，上游额外提交了一次 `Chinese.`，因此出现第 6 条“中文。”。
这是已观察到的识别重复词限制；没有通过按文本强行去重掩盖模型输出。该短样例不代表所有直播的准确率或持续延迟。

联调修复了两类会阻止真实翻译的适配问题：上游默认显示行不及时最终化，以及推理落后时仅凭输入侧静音提前封尾。
现在复用上游标点分组及 `silence_transcription_ready` 进度事件，只将已提交词交给翻译。

本地证据和复现命令：

- 独立 ASR 记录（本地文件：`output/asr/asr-verification.json`）
- 最新真实识别及中文事件（本地文件：`output/asr/live-qwen-final.json`）

```powershell
.\backend\.venv\Scripts\python.exe scripts/asr-smoke.py
.\backend\.venv\Scripts\python.exe scripts/smoke-live.py output/asr/english-synthetic.wav --output output/asr/live-qwen-final.json
```

第二条命令需要字幕服务运行，会短暂占用唯一识别会话。输出位于忽略的 output/，不随源码提交。

## 基础链路的浏览器联调

将构建后的扩展加载到专用 Chromium 测试 profile，使用真实扩展按钮授予 activeTab，操作真实弹窗启动采集。后端运行 demo 模式并严格限制扩展 Origin。

测试地址采用 YouTube 播放页 URL，但页面响应被测试工具替换成可控 fixture，包含 `#movie_player`、Web Audio 测试音源和全屏按钮。**这不是实际 YouTube 页面或真实直播验收。** tabCapture、Offscreen、AudioContext、AudioWorklet、PCM、WebSocket 和字幕 DOM 均为真实实现，未用麦克风或模拟音频流代替。

| 检查项 | 结果 |
| --- | --- |
| 从真实扩展弹窗启动 | 成功，Chrome 报告目标标签页 capture active |
| 标签页音频传输 | 服务累计收到超过 200 秒 PCM，持续产生明确标记的 demo 字幕 |
| 全屏字幕 | 字幕挂载在播放器内，进入全屏后可见 |
| 弹窗尺寸 | 380 px 宽，测试时约 501 px 高；长错误区域设有上限 |
| 主动停止 | capture stopped，Offscreen 文档消失，字幕层数量为 0 |
| 停止后再次启动 | 成功重新采集并显示字幕 |
| 页面刷新 | 自动停止，Offscreen 文档消失，字幕层数量为 0 |

浏览器联调发现并修复了 Chrome 旧式 `mandatory` 采音约束与标准音频约束混用导致的启动失败，同时补充回归测试。启动期间的取消不会被长握手阻塞，相关竞态另有单元测试。

以下是前一阶段 demo 的截图，未展示本轮新增的双组字幕阅读窗口（位于忽略的 `output/`，不会随源码提交）：

- 普通播放视图（本地文件：`output/playwright/subtitles.png`）
- 全屏视图（本地文件：`output/playwright/subtitles-fullscreen.png`）

## 未验证范围

- 实际 YouTube DOM 变化、影院模式、直播长时间运行和多个有声标签页隔离。
- 人耳确认原声质量、不同输出设备、Chrome 各平台版本和浏览器媒体限制。
- 不同机器上的 GPU/CPU 兼容性、真实直播识别准确率、15 分钟运行和延迟趋势。
- 真实直播中持续翻译负载、术语准确性和迟到译文的阅读体验。

demo 只证明链路收到音频，静音也会触发固定字幕，不能证明识别或翻译正确。真实模型已使用短句、持续英文和长静音音源回归，具体结果见上文；仍需完成上述真实直播验收。
