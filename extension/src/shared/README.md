# 插件内部共享类型

`config.ts` 定义浏览器设置，`session.ts` 定义界面可以观察到的会话状态。

`runtime-messages.ts` 定义 popup、background、offscreen、content 之间的 Chrome 消息，并包含发送目标和会话 ID。插件内部消息使用 camelCase；服务端协议使用 `@streamlingo/protocol` 中的 snake_case 字段。

本目录不持有全局音频流或网络连接，也不作为不同扩展运行上下文之间的共享内存。
# 界面语言与错误描述

`i18n.ts` 定义简体中文/英文文案、结构化状态、可本地化错误码和未知错误的有界纯文本兜底。界面语言与音频源语言分开，界面切换不改变 `en → zh-CN` 的语音识别/翻译方向。

`language-preference.ts` 只读写独立的 `chrome.storage.local.uiLanguage` 键。不会读改写 `settings`，因此语言选择和设置保存可并发，未保存的表单输入不会被语言操作持久化。观察器先注册变更监听，再读取已有值，旧读取结果不能覆盖新的变更事件。默认语言为 `zh-CN`。
