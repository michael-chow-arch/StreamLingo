# Chrome Web Store 发布准备

适用版本：0.2.0。2026-10-13 核查官方资料。本文件和 ZIP 是提交准备材料；没有执行上传、发布或宣称已经通过审核。

## 构建与文件

在开发环境安装 Node/npm 依赖及 Python 后：

```powershell
npm run typecheck
npm test
npm run build
python scripts/package-extension.py
```

`npm run build` 输出 `dist/extension`，使用 `extension/dev-key.json` 的固定**公钥**以保持本地扩展 ID，包含开发 source map。`node scripts/build.mjs --store` 输出干净的 `dist/store-extension`，不含 key 或 source map。`package-extension.py` 重新执行商店构建、检查明确文件白名单，生成 `dist/streamlingo-0.2.0-chrome-web-store.zip`。不需要打包 `.crx`；商店 ZIP 根目录直接包含 manifest。后端、模型、环境配置、开发脚本、测试、日志、依赖目录和源 SVG 不在商店 ZIP 中。

清单使用 Manifest V3、Chrome 116+、`default_locale: en` 及 `_locales/en`、`_locales/zh_CN`。Chrome 商店/安装名称本地化与弹窗持久化界面语言是两套独立机制。版本必须在后续上传时增加；清单描述限制 132 字符。依据：[准备扩展](https://developer.chrome.com/docs/webstore/prepare)、[default_locale](https://developer.chrome.com/docs/extensions/reference/manifest/default-locale)、[开发 key](https://developer.chrome.com/docs/extensions/reference/manifest/key)。

商店安装 ID 与开发 ID 可能不同。首次商店提交建立 ID 后，用弹窗“后端连接信息”的完整 `chrome-extension://…` 配置本地服务允许来源；不能默认沿用开发 ID。服务不应开放通配来源。

## 可用作商店介绍的文字

名称：**StreamLingo**

宣传标题：**YouTube 直播实时 AI 翻译字幕，支持本地大模型。**

首屏文字：**让 YouTube 直播说你的语言。** / **Live speech. AI-translated.**

简述：YouTube 直播实时 AI 翻译字幕，支持本地大模型，不依赖主播提供字幕。英中双向与自动识别；需要另行安装本地语音服务和 Ollama。

英文简述：AI captions for YouTube livestreams, powered by local LLMs. No streamer captions needed. Requires local speech service + Ollama.

详细说明：

> 让 YouTube 直播说你的语言。StreamLingo 将直播中的语音变成播放器内的 AI 翻译字幕，支持你自己部署的本地大模型。无需主播提供字幕，也不依赖 YouTube 已有字幕。看直播、听分享、跟进技术讨论时，用熟悉的语言读懂内容。也兼容普通 YouTube 视频。
>
> 点击开始后，StreamLingo 直接采集当前 YouTube 播放标签页的音频，通过用户安装的本机服务进行语音识别，再交给 Ollama 大模型翻译，在视频播放器内显示结果。支持英语→中文、中文→英语、自动识别→中文、自动识别→英语。可独立切换中英文界面、字幕字号及原文显示。字幕自动分页，每屏至少约四秒；快速讲话时待读内容可能落后直播，已返回的译文不会为追赶而被自动丢弃。停止、刷新或切换视频会清空字幕会话。无历史回看、滚动或人工翻页控件。
>
> 本扩展需要单独安装并运行本地识别服务与 Ollama，且机器性能和模型决定延迟、识别与翻译质量。中文及自动识别需要多语言语音模型，base.en 等仅英语模型不支持这些模式。自动识别由模型决定，不保证逐词语言切换准确。扩展安装本身不包含或安装模型。关闭弹窗后采集继续，可再次点击停止。选择远程 Ollama 地址会将文本发往该地址，请先阅读隐私说明。项目由社区维护，与 YouTube/Google 无隶属或背书关系。

作者/支持：[StreamLingo 仓库](https://github.com/michael-chow-arch/StreamLingo)，[michael.chow.tech@gmail.com](mailto:michael.chow.tech@gmail.com)。使用仓库链接提供安装说明和问题反馈；不在视频字幕上投放宣传。

English listing copy:

> Live speech. AI-translated. Follow YouTube livestreams in your language, powered by your own local language model. StreamLingo works directly from the stream's audio: no captions from the streamer or existing YouTube subtitles are needed. Regular YouTube videos are also supported.
>
> StreamLingo captures audio directly from the YouTube tab you choose, transcribes it through your local speech service, and asks your configured Ollama model for translations. Read the result inside the player. Choose English → Chinese, Chinese → English, Auto-detect → Chinese, or Auto-detect → English. Switch the interface language separately and adjust caption size or original-text visibility.
>
> Automatic reading pages give each screen at least about four seconds. Fast speech can leave a reading backlog; returned translations are retained until displayed or the session ends. There are no scrolling, history, or manual paging controls.
>
> Requires a separately installed local speech service and Ollama. The extension alone does not install models or perform recognition. Chinese and auto-detection require a multilingual speech model. Speed and accuracy depend on your hardware, models, and audio; this is not a zero-latency guarantee. Closing the popup keeps capture running; click Stop captions to end it. If you configure a remote Ollama server, transcripts are sent there. See the setup instructions and privacy policy before use. Independent community project; not affiliated with or endorsed by YouTube or Google.

Both localized listings must include the runtime requirements before submission:

> Windows 预览版需要 NVIDIA GPU、CUDA 12 cuBLAS、适用于 CUDA 12 的完整 cuDNN 9、兼容驱动及 64 位 Python 3.11–3.13。Setup 不自动安装显卡驱动或 CUDA/cuDNN。缺少运行要求时明确停止，不自动降级到 CPU。请先阅读[运行条件](runtime-requirements.md)。

> The Windows preview requires an NVIDIA GPU, CUDA 12 cuBLAS, complete cuDNN 9 for CUDA 12, a compatible driver, and 64-bit Python 3.11–3.13. Setup does not install GPU drivers or CUDA/cuDNN. Missing requirements stop startup with an explanation; there is no automatic CPU fallback. Read the [runtime requirements](runtime-requirements.md) before setup.

## 单一用途、权限及代码

Single purpose：**Display AI-translated captions for YouTube livestream audio explicitly selected by the user, through the user's separately installed local service. Regular YouTube playback is also supported.**

| 权限 | 审核理由 |
| --- | --- |
| `activeTab` | 用户点击扩展后临时访问目标标签页，验证播放页并注入字幕层，无全站常驻脚本。 |
| `tabCapture` | 在明确开始后获取标签页直接音频，不使用麦克风。 |
| `offscreen` | 在弹窗关闭后维持音频处理和 WebSocket 会话，使用 USER_MEDIA 文档原因。 |
| `scripting` | 按需将随包字幕脚本注入用户选择的 YouTube 页面。 |
| `storage` | 保存本机服务地址、翻译方向、显示设置、界面语言及必要运行状态。 |
| `http://127.0.0.1/*`、`http://localhost/*` | 检查并连接用户自己运行的本机服务；支持其自选本机端口，不允许远程后端地址。 |

无需 `<all_urls>`、历史、Cookie、麦克风、`debugger`、`webRequest` 或远程 YouTube host 权限。字幕和本地服务 JSON 是数据，使用运行时校验并通过 `textContent` 展示；所有扩展 JS 和音频 worklet 随包提供，不下载 JS/WASM、不 eval 服务返回值。独立后端执行识别/翻译并不等于向扩展加载远程代码。仍需向审核员提供可复现服务安装/测试方法。依据：[隐私表单与权限理由](https://developer.chrome.com/docs/webstore/cws-dashboard-privacy)、[MV3 代码要求](https://developer.chrome.com/docs/webstore/program-policies/mv3-requirements)。

## 隐私披露

发布前将 [privacy-policy.md](privacy-policy.md) 放在稳定、公开、无需登录的 URL，测试扩展页脚链接可访问，再填入开发者后台。计划使用仓库 main 分支对应文档，若默认分支不同需同步扩展链接。不能仅因服务在本机就填“完全不处理用户数据”；官方说明本地处理也需披露。[User Data FAQ](https://developer.chrome.com/docs/webstore/program-policies/user-data-faq)

根据当前代码实际填写处理的**网站内容/音频及派生转写译文**；对用于限定播放页的 URL/标签页信息如实说明，依据提交时后台字段选择对应类别。不要勾选不符合事实的“无数据处理”。声明无广告、出售或分析追踪、无开发者云收集端点；本机服务使用 HTTP/WS，本机程序通信在官方 FAQ 中有专门说明。后端可配置远程 Ollama，文本可能离机，因此“永不离机”不是产品承诺。权限理由、商店详情、产品内采集提示及隐私政策须一致。

## 素材与人工提交前检查

- 包内图标：`extension/icons/icon16.png`、`icon32.png`、`icon48.png`、`icon128.png`。128 PNG 应为方形；官方建议 96px 主体居中，四周各留 16px 透明区域。
- 小型宣传图：440×280，提交所需；可选大型宣传图：1400×560。
- 至少一张、最多五张截图：1280×800 推荐，也可 640×400；PNG 或 JPEG，按官方要求无额外 padding。使用实际 UI 和原创示例内容，避免私人直播音频/文本、伪造评价、无法支持的实时性承诺。
- 商店截图按语言选择：英文使用 `docs/assets/streamlingo-overview-en.jpg`，中文使用 `docs/assets/streamlingo-overview-zh-CN.jpg`，均为 1280×800 的模拟界面演示。README 使用 `real-demo-cover-en.jpg` 和 `real-demo-cover-zh-CN.jpg` 实录封面；弹窗近景分别为 `popup-en.jpg` 与 `popup-zh-CN.jpg`，不单独作为不合尺寸的商店截图提交。440×280 宣传图为 `docs/assets/store-promo-440x280.png`。原始素材不进入扩展 ZIP。图标不以 YouTube 标志或 Google 认证标识替代自身品牌。
- 从干净用户配置加载商店构建，核对四模式选择、低版本服务提示、English-only 模型拒绝、开始/停止、音频回放、导航清理、前后台阅读时间、语言切换与键盘操作；真实识别/翻译另按后端测试记录说明。Demo 输出须显示测试标签，不能作为真实识别效果宣传。
- 准备开发者账号和两步验证、公开支持与隐私链接、明确服务依赖、可供审核复现的安装步骤，提交 ZIP 前再次核对当前后台要求。许可为 MIT，包内保留第三方许可和归属说明。

图像尺寸与数量依据：[官方素材要求](https://developer.chrome.com/docs/webstore/images)。人工提交和审核通过仍是独立步骤，生成 ZIP 不能证明商店已批准。
