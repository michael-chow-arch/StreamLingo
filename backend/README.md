# StreamLingo 本地服务

Python 3.11–3.13。一个 FastAPI 进程提供 `GET /health` 和 `WS /ws/live`。
只监听本机回环地址，只接受明确配置的 Chrome 扩展 Origin；无配置时拒绝所有 WebSocket。

## 安装与联调

在仓库的 `backend` 目录运行（PowerShell）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\streamlingo-server.exe --mode demo --allow-origin chrome-extension://替换为你的32位扩展ID
```

扩展 ID 在 Chrome 的扩展管理页开启开发者模式后查看。占位文本必须替换成真实 ID。
服务地址为 `http://127.0.0.1:8765`，扩展 Origin 可重复传入 `--allow-origin`。
完整选项见 `streamlingo-server --help`。关闭服务使用 Ctrl+C。

`demo` 是显式开发模式：每收到 2 秒 PCM 音频产生一条**标注演示的固定字幕**，
源文本包含已接收音频时长，目标文本标注“非识别或翻译结果”，`is_mock=true`。
中文源模式使用中文样例；自动源模式按段交替使用固定中英样例，不实际检测输入语言。
静音音频也会触发，这个模式只验证采音、传输和叠加流程，不评价语音识别效果。
没有输入音频时不会自动播放测试字幕。

## 可选真实语音识别

默认模式为 `whisperlivekit`，不会静默回退到 demo。没有安装识别依赖时仍可启动 HTTP 服务；
`/health` 报告 `mode=whisperlivekit`、`asr=error`，启动会话返回 `ASR_NOT_READY`。
未指定 `--ollama-model` 时真实模式的 `translation=disabled`；指定模型后启用真实翻译，详见下节。

```powershell
# 可选依赖较大，包括 torch / torchaudio / faster-whisper。
.\.venv\Scripts\python.exe -m pip install -e '.[asr]'
.\.venv\Scripts\streamlingo-server.exe --model base --allow-origin chrome-extension://替换为你的32位扩展ID

# 已有兼容的 CTranslate2 Whisper 模型时，可指定本地模型目录。
.\.venv\Scripts\streamlingo-server.exe --model base --model-dir 'D:\models\faster-whisper-base' --allow-origin chrome-extension://替换为你的32位扩展ID
```

模型加载在后台线程执行，期间 `/health` 返回 `starting` / `loading`；成功后才允许握手。
首次真实启动可能由上游下载 Whisper / VAD 模型；`GET /health` 本身不触发下载。
指定 `--model-dir` 不代表所有辅助模型已缓存。离线运行需要提前准备上游所需文件。
PCM 直接输入上游，不需要通过 FFmpeg 解码浏览器的压缩音频。

自动化测试覆盖基础服务、demo、稳定分段和翻译调度。历史英语模型验收曾用 16.985 秒系统 Zira 合成英文加 16 秒尾静音
验证 `base.en` 真实识别（CUDA / int8_float16）：得到 5 个最终片段，规范化单词与输入一致，无重复 ID、无最终片段后修订、
无静音积压误报。首个最终片段在开始送音频后 2.711 秒到达。证据见仓库 `output/asr/asr-verification.json`；
真实 YouTube 音质、口音和长期吞吐仍需直播验证。
上游选择 LocalAgreement + faster-whisper，计算类型沿用该发行版的自动选择。
Windows CLI 启动前检查 CUDA 12 / cuDNN 9 运行库文件，并要求 CTranslate2 能检测到可用 CUDA 设备；缺项时明确停止，不自动降级到 CPU。
文件和设备检查通过后仍需模型初始化验证二进制兼容性及可用显存，不代表已经保证实时速度。
此检查不修改系统环境或已运行的 Ollama。直接调用 `create_app` 的嵌入式用法不执行 CLI 预检。
具体版本要求与本机已验证配置见[运行条件](../docs/runtime-requirements.md)。
默认模型为多语 `base`。可以继续显式使用 `--model base.en`，但 `.en` 模型专门识别英语；
修改模型目录名称、请求语言或插件界面语言不会赋予它中文识别能力。

## 四种字幕语向

协议仍为 v1；每个 WebSocket 的 `start` 决定本次语向，不需要重新加载模型：

| 模式 | `source_language` | `target_language` |
| --- | --- | --- |
| 英语 → 中文 | `en` | `zh-CN` |
| 中文 → 英语 | `zh` | `en` |
| 自动识别 → 中文 | `auto` | `zh-CN` |
| 自动识别 → 英语 | `auto` | `en` |

仅允许以上四个组合。源语言中文使用 `zh`，目标简体中文使用 `zh-CN`；它们不能互换。
缺失字段、未知枚举属于 `INVALID_MESSAGE`；枚举有效但不在四种组合内，返回 `UNSUPPORTED_LANGUAGE`。
识别模型加载完成后，`/health` 增加 `source_languages` 和 `target_languages`：
多语模型分别为 `["en","zh","auto"]` 与 `["zh-CN","en"]`；英语专用模型只报告源语言 `["en"]`。
加载中或失败时省略能力字段，不能据此假定中文/自动模式可用。
能力依据已加载 faster-whisper 模型的 `supported_languages`，不是模型文件名。
英语专用模型遇到中文或自动源请求，会在分配识别会话前明确返回 `UNSUPPORTED_LANGUAGE`，不会偷偷按英语处理。

`ready` 和每次 `subtitle` 修订均携带本次 `source_language` / `target_language`。
它们表示**用户选择的模式**，`source_language=auto` 不是逐词或逐句识别语言的置信声明。
旧录制数据可不含这些可选输出字段；新客户端应结合能力字段判断可选模式。
界面语言仅影响按钮和状态文案，不改变识别/翻译语向。

WLK 0.2.26 原生 `AudioProcessor(language=...)` → `online_factory` → `SessionASRProxy`
在共享锁内设置本次推理语言并在 `finally` 恢复。`auto` 映射为 faster-whisper 的 `language=None`，
使用 Whisper 原生音频语言检测；它可能识别出模型支持的其他语言，并非严格限制在中英之间。
检测作用于推理音频窗口，短片段、口音、噪声、中英快速切换可能判断错误，不能承诺中英逐字混合都准确。
应用没有另外实现猜测音频语言的规则，也没有把中文标签套在英语模型的输出上。
中文与混合文本沿用 faster-whisper token 自带的空格和中文标点，不按英语习惯在每个 token 间插空格。

Ollama 根据本次目标语向生成系统提示。自动源模式让模型从字幕文字判断语言并统一到目标语种；
已经属于目标语种的文本要求原样保留，混合句中已有目标语内容要求保留。这是模型提示约束，
没有用字符规则猜测整句语言，实际措辞仍可能被大模型改写，应通过真实音源验证。
本轮自动化测试使用模型替身和演示音频，证明路由、提示、字段及清理行为；不证明多语识别准确率。

实时识别默认使用以下参数，可在 CLI 启动时覆盖：

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `--asr-beam-size` | 1 | 减少解码搜索开销；可设为 5 使用更宽搜索，但会增加计算量，准确率差异需按音源验证 |
| `--asr-coalesce-seconds` | 0.8 秒 | 累积一定的新语音再推理，避免对每个很小的音频块重复解码 |
| `--asr-buffer-seconds` | 8 秒 | 使用上游逻辑更早修剪已提交的音频上下文；不是强行截断未识别语音 |

faster-whisper 解码使用固定温度 0，关闭逐级升温重试。0.2.26 的 faster-whisper 后端将搜索宽度写死为 5，
因此适配器只在模型公开 `transcribe` 调用入口覆盖这些参数；不修改依赖文件，识别、时间戳与稳定词提交仍由上游处理。
这些是实时性取舍，不能保证所有硬件与音源都能持续跟上；真实积压保护继续生效。

为抑制历史识别错误反复成为新提示的循环，适配器同时设置 `condition_on_previous_text=False` 和
`initial_prompt=None`。前者关闭解码窗口之间的文字回灌，后者清除 WhisperLiveKit 每次调用另行注入的
约 200 字历史文字；只关闭前者不足以切断两条路径。音频上下文、稳定词确认及分段逻辑仍由上游维护。
没有添加全文去重或禁止重复词的规则，解码器输出原样保留。代价是窗口间术语和措辞一致性可能下降，
也不能消除非英语音源、噪音或纯静音上的所有识别幻觉。参数依据见
[faster-whisper 1.2.1 源码及参数说明](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py)。

## 连接本机 Ollama / Qwen

```powershell
.\.venv\Scripts\streamlingo-server.exe --model base --ollama-url http://127.0.0.1:11434 --ollama-model qwen3.5:9b --allow-origin chrome-extension://替换为你的32位扩展ID
```

`--ollama-url` 默认就是 `http://127.0.0.1:11434`。模型名显式配置，不在服务启动时拉取模型。
配置后的 `/health` 和 `ready` 中 `translation=configured` 只表示已经配置 provider，不保证模型正在运行。
Ollama 地址和模型名保存在后端参数中，不传给 YouTube 页面。`demo` 模式始终使用标注测试译文，即使填写了 Ollama 参数。

适配器使用异步 HTTP 客户端调用原生 `POST /api/chat`，请求设置 `stream:false`、`think:false`、
`temperature:0`，只读取最终 `message.content`。参考 [Ollama Chat API](https://docs.ollama.com/api/chat) 和
[Thinking 文档](https://docs.ollama.com/capabilities/thinking)。默认保活 10 分钟，上下文窗口 4,096 tokens、输出预算 768 tokens；
空响应、截断结果或过长响应均显示为本句翻译失败，不伪造译文。

源语言稳定片段先发送 `pending`，由一个独立串行 worker 翻译，完成后用相同 `segment_id`、递增 `revision`
更新为 `complete`（`is_mock=false`）。翻译等待期间原文识别和输出继续。默认策略：

| 参数 | 默认值 | 行为 |
| --- | --- | --- |
| `--translation-queue-size` | 3 | 最多 3 条等待，另加 1 条正在翻译；满时跳过最旧等待项 |
| `--translation-max-age` | 15 秒 | 尚未完成任务从入队起的预算，含等待和推理；到期取消并标记 `skipped`。有效译文已返回时保留结果，不再进行后置过期丢弃 |
| `--translation-timeout` | 20 秒 | 单次调用超时则该片段标记 `error`，继续后续片段 |

每句最多携带前两句原文上下文（各保留最多 1,000 字）。翻译失败、超时或跳过还会发送非致命错误事件；
该句原文保留，会话继续。每个有界翻译任务保存原最终字幕快照；256 条识别元数据缓存淘汰不会吞掉已完成译文。
有效译文返回即发送 `complete`，不再因返回后的时效检查丢弃。停止/断连取消正在进行的 HTTP 请求、丢弃等待队列；服务退出关闭连接池。

2026-10-12 已直接调用本机 Ollama **0.34.2 / qwen3.5:9b** 完成一次短句验收：

> Welcome to the live stream. Today we are testing real-time Chinese subtitles.

实际返回：“欢迎来到直播。今天我们正在测试实时中文字幕。”首次请求耗时 **10.501 秒**，
随后同句热请求耗时 **0.570 秒**。这是翻译接口单独实测，不包含采音、ASR 和直播字幕总延迟，也不保证持续并发负载下的表现。

## 模块与复用边界

| 模块 | 职责 |
| --- | --- |
| `settings.py` / `cli.py` / `app.py` | 配置、启动、模型生命周期和依赖装配 |
| `transport/messages.py` | Pydantic 严格校验协议版本、UUID、字段、语言和音频格式 |
| `transport/live.py` | Origin、握手、接收与发送任务、停止/异常/断连清理 |
| `application/session.py` | 单会话占用、有界输入/翻译队列、字幕 ID 与 revision、最终结果冻结 |
| `adapters/whisperlivekit.py` | 上游流式引擎及输出到领域事件的薄适配 |
| `adapters/demo.py` | 依赖音频输入的测试识别会话及明确标记的测试译文 |
| `adapters/ollama.py` | 异步调用 Ollama、响应校验和连接池关闭 |
| `ports/translator.py` | 模型无关的翻译端口 |

识别/VAD/流式上下文和标点分组由 WhisperLiveKit 处理。适配器不实现另一套 Whisper 分包识别算法，
也不复制第三方工程源码。它采用 `TranscriptionEngine(config=...)`、
`AudioProcessor(..., pcm_input=True, mode="diff")`、`create_tasks()`、`process_audio()`、`cleanup()`。

0.2.26 的非说话人显示行需要长停顿后再次说话才会封段，直接当翻译边界会一直不产生中文。
适配器复用 `tokens_alignment.compute_punctuations_segments()` 对引擎**已经提交的词**分组，标点边界立即封段；
尾部静音达到 1 秒时，必须再等上游 `silence_transcription_ready` 事件确认停顿前推理和快照已处理完成，
并确认 decoder buffer 为空，才会封段；不能因为音频输入钟领先而把延迟提交的词逐个封段。
事件与结果双流同时消费，这也是上游 Deepgram 适配使用的进度屏障。
无标点长段按已提交音频时长 3 秒或约 120 字符分段，在词边界送入翻译。
从本段首次拿到稳定词起，再设置 2.5 秒单调时钟上限；即使没有新的结果快照，也会将已有稳定前缀送去翻译。
这个上限不包含模型首次识别出稳定词或 Qwen 生成译文的耗时，不是端到端延迟保证。
尚未确认的 decoder buffer 不会提升为最终文字；其中后续提交的词进入新的片段。
后续词作为新片段保留，已封片段的原文和时间不再变化。不把未提交的 decoder buffer 当作稳定文字。
消费记录按 token 对象标识去重，随上游 60 秒保留窗口修剪；不会因为两个词时间戳相同而遗漏后一个词。
该适配使用固定版本的对象结构，所以强制检查安装版本。
超过 8,000 字的单片段明确报错，避免发出与浏览器协议不兼容的数据。

## 资源与故障边界

- 单进程、单活动会话；不要以多个 Uvicorn workers 启动，否则内存会话限制不能跨进程生效。
- 首消息限 4 KiB、等待 10 秒；PCM 限 32,000 字节且必须为非空偶数字节。
- 应用输入队列限 160,000 字节（5 秒音频），并限 100 包；没有静默丢音频策略。
- 0.2.26 的识别队列原本无上限。创建工作任务前设置 `asyncio.Queue(maxsize=125)`，约为 5 秒 VAC 块；
  所有上游生产者使用 `await put`，外层 feeder 超时 5 秒会结束会话。队列持续落后不会无限占内存。
- 通过按序消费的 `audio_advanced` / 语音边界事件记录输入时点及静音区间，对照实时 ASR 处理进度，
  只计算尚未处理的语音时长；超过 10 秒时返回 `AUDIO_BACKLOG`。结束的静音区间保留到处理进度跨过它，
  避免恢复说话时把旧快照中的静音延迟误判为积压。实际越限日志只记录时间和队列长度，不记录音频或字幕内容。
- 停止/断连取消输入、输出与识别任务并释放占用；不等待补齐最后一句。清理失败时标记模型不可用。
- 原生推理在线程中执行，Python 取消任务不能立刻终止正在执行的 C/CUDA 调用；停止后该次调用可能短暂继续，
  但不会再向已结束会话发送字幕。该限制需要用实际硬件补充验证。
- 服务不持久化音频或字幕；日志用于状态与错误诊断。HTTP Host 和 Origin 分别校验。
- Origin 是阻止任意网页访问的浏览器边界，不是本机恶意程序的身份认证；MVP 不开放到局域网。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

覆盖协议握手、错误类型/字段/UUID/音频长度、Origin/CORS/Host、音频驱动 demo、停止、断连、
会话冲突、模型未就绪、输入积压、适配器稳定边界映射。模型映射测试使用上游结构的替身，不能代替真实 ASR 实测。
翻译测试覆盖英文不断流、字幕补齐版本、队列满/过期/超时/失败、停止/断连取消、Ollama HTTP 请求与响应校验、连接池生命周期。
语向测试覆盖四模式 demo WebSocket、无效语向、实际模型能力与请求拒绝、原生逐会话语言代理及异常恢复、
中英/混合 token 空格保留，以及每种目标的 Ollama 提示与同语/混合文本样例响应。均不加载 GPU 模型。
`requirements-dev.lock` 记录这轮测试使用的基础运行/测试依赖；可先安装此文件，再 `pip install -e . --no-deps` 复现。

## 上游版本与许可依据

核对日期：2026-10-12。固定复用 **WhisperLiveKit 0.2.26 / Apache-2.0**。

- [GitHub v0.2.26 发行版](https://github.com/QuentinFuxa/WhisperLiveKit/releases/tag/v0.2.26)
- [PyPI 0.2.26](https://pypi.org/project/whisperlivekit/0.2.26/)
- [固定版本许可证](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/LICENSE)
- [固定版本 AudioProcessor](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/audio_processor.py)
- [固定版本官方服务集成](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/basic_server.py)
- [固定版本行整理逻辑](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/tokens_alignment.py)
- [固定版本逐会话语言代理](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/session_asr_proxy.py)
- [固定版本 online_factory](https://github.com/QuentinFuxa/WhisperLiveKit/blob/v0.2.26/whisperlivekit/core.py)

已检查 PyPI wheel 的配置、核心类、音频处理器、时间对象和 LICENSE。
发行 wheel SHA-256：`a94cb09569c543ee78f18ab709df6f8c08c90cdf9db00ceae7bbc1d791d7933e`。
本项目只声明依赖和调用 API，不内嵌上游源码；分发含依赖的安装包时应保留依赖许可证。
