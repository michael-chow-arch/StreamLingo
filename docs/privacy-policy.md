# StreamLingo 隐私说明 / Privacy policy

版本：0.2.0；更新日期：2026-10-13。

维护者：michael-chow-arch。联系：[michael.chow.tech@gmail.com](mailto:michael.chow.tech@gmail.com)。项目：[StreamLingo](https://github.com/michael-chow-arch/StreamLingo)。

## 中文

StreamLingo 的用途是在用户指定的 YouTube 视频或直播页面显示语音识别和翻译字幕。扩展需要另行安装、运行本机识别服务与翻译模型。安装扩展不会自动安装这些服务。

**点击“开始字幕”后，扩展采集该标签页的直接音频并发送至用户配置的本机服务。**它不使用麦克风，也不通过扬声器录音。服务将音频识别为文本，并将待翻译文本及最多两个前文片段发送至用户配置的 Ollama 地址；返回的原文与译文在视频内显示。这个过程会处理音频中实际包含的信息，请只在你希望进行字幕处理的标签页启动。

扩展只允许连接 `http://127.0.0.1` 或 `http://localhost` 的本机服务。默认 Ollama 地址也是本机地址。**若用户将后端的 Ollama 地址改为远程服务器，转写文本与上下文会发送至该服务器**，其运营方的数据处理、日志及保留规则随之适用。扩展不能保证此配置下数据始终留在设备上。模型首次下载以及依赖安装也会访问对应下载来源；它们与直播字幕处理是不同的网络活动。

扩展读取当前标签页 URL 和标识，用于确认是 YouTube 播放页、定位字幕及在导航时停止采集；这些页面地址不作为字幕协议内容发给识别/翻译服务。扩展不读取账号密码、Cookie、评论、浏览历史列表或其他标签页的音频。开发者没有接收字幕数据的托管服务，扩展没有分析统计、广告追踪或数据销售功能。

音频以流式缓冲用于当前会话，原文、译文和待读页面保留在当前会话的内存中。停止字幕、刷新、切换视频或开始新会话会清空扩展的字幕内存。切换到后台标签页会暂停字幕阅读推进，但正在运行的采音和服务处理会继续，直到用户停止或会话结束。扩展不将音频或字幕保存为录音/历史文件，也不把它们写入 Chrome 存储。服务、识别库、Ollama 和操作系统可能保留运行诊断日志或缓存；通过启动脚本产生的日志由用户本机管理，不能将此说明理解为对第三方组件的零保留承诺。

服务地址、翻译方向、字号、原文开关和界面语言保存在设备上的 `chrome.storage.local`；运行状态保存在扩展后台及音频处理页面的内存中。它们不通过 Chrome Sync 同步。可在弹窗修改设置，卸载扩展可删除扩展存储；删除服务配置、模型缓存和本机日志需在服务所在设备另行完成。

“停止字幕”会释放音频采集。关闭弹窗本身不会停止采集。点击项目、隐私或联系链接时，由浏览器或邮件程序打开 GitHub/邮件服务，适用相应第三方政策。主动发送的反馈、日志或邮件内容会提供给接收方；请先移除不希望分享的直播文本或个人信息。

StreamLingo 对扩展权限获得的数据的使用遵守 Chrome Web Store User Data Policy，包括 Limited Use 要求：仅为所述字幕功能使用数据，不用于个性化广告，不出售数据，不向开发者自动上传音频或字幕，不安排人工阅读字幕数据。远程服务配置与用户主动提供的支持材料按前述说明处理。本说明将随实质性数据处理变更更新。

## English

StreamLingo displays recognized and translated captions on a YouTube video or live stream selected by the user. A local speech service and translation model must be installed and run separately; installing the extension does not install them.

**Clicking Start captions captures the selected tab's direct audio and sends it to your configured local service.** It does not use a microphone or record sound from speakers. The service transcribes the audio and sends source text, with up to two preceding text segments, to your configured Ollama endpoint for translation. Source text and translations appear inside the player. Any information spoken in the captured audio is processed for this purpose.

The extension connects only to a service at `http://127.0.0.1` or `http://localhost`. Ollama also defaults to a local address. **If you configure the backend to use a remote Ollama endpoint, transcripts and context are transmitted to that server** and become subject to its operator's handling, logging, and retention practices. We cannot promise that data remains on your device in that configuration. Installing dependencies and downloading models may contact their download providers separately from caption processing.

The extension reads the selected tab's URL and identifier to validate YouTube playback pages, attach captions, and stop on navigation. These page URLs are not sent in the speech/translation protocol. It does not read passwords, cookies, comments, a browsing history list, or other tabs' audio. There is no developer-operated caption collection endpoint, analytics, advertising tracking, or data sale feature.

Audio is streamed through working buffers. Captions and unread pages remain in current-session memory. Stop, refresh, video navigation, or a new session clears the extension's caption memory. Hiding the tab pauses reading progress, while capture and backend processing continue until stopped or ended. The extension does not save audio recordings or transcript files and does not write captions to Chrome storage. The service, speech libraries, Ollama, and operating system may retain diagnostic logs or caches. Launcher logs are managed locally by the user; this policy does not promise zero retention by third-party components.

Service address, translation direction, font size, source-text visibility, and interface language are stored in `chrome.storage.local`. Runtime state stays in extension background and audio-processing page memory. These settings are not synced through Chrome Sync. You can change settings in the popup; uninstalling removes extension storage. Backend configuration, model caches, and local logs must be removed separately on the machine running them.

Stop captions releases capture; closing the popup does not. Project/privacy/contact links open GitHub or your mail service, whose policies apply. Support messages and logs you voluntarily send are received by the chosen recipient; remove private content before sharing.

StreamLingo's use of data obtained through extension permissions complies with the Chrome Web Store User Data Policy, including Limited Use requirements. Data is used for the stated caption purpose, not sold or used for personalized advertising; audio and captions are not automatically uploaded to the developer or made available for developer human review. User-configured remote services and voluntarily provided support material are handled as described above. Material changes to data handling will be reflected in this policy.
