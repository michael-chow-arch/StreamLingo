# Discovery-style usage video / 工具发现短片

Production notes for the 32-second usage videos rendered on 2026-10-13. All four local exports use a real Chrome tab recording, actual StreamLingo captions, AI narration, and original background music. Social posts are not published by these scripts.

2026-10-13 已生成四个 32 秒本地版本：中英文各一份横版与竖版，包含真实 Chrome 标签页录制、实际 StreamLingo 字幕、AI 配音和原创背景音乐；脚本不会自动发布社交内容。

## Message / 主题

**看直播，听不懂？发现个好用的工具。**

**Live stream. Lost in translation? Meet StreamLingo.**

Show the everyday benefit first: AI-translated captions inside YouTube, using an existing local Ollama model. Show actual playback and actual extension output. Keep installation in the written guide. No requests to Star, Watch, or Fork.

先展示日常使用价值：在 YouTube 页面直接阅读 AI 翻译字幕，复用已有的本地 Ollama 模型。演示真实播放与扩展实际输出，安装过程放在图文指南中；不加入 Star、Watch、Fork 引导。

## Deliverables / 成片规格

| Version / 版本 | Canvas / 画布 | Duration / 时长 | Intended use / 使用位置 |
| --- | --- | --- | --- |
| Chinese vertical / 中文竖版 | 1080 × 1920, 9:16 | About 32 seconds / 约 32 秒 | 抖音、小红书、B站竖屏 |
| English vertical / 英文竖版 | 1080 × 1920, 9:16 | About 32 seconds / 约 32 秒 | YouTube Shorts、TikTok |
| Chinese horizontal / 中文横版 | 1920 × 1080, 16:9 | About 32 seconds / 约 32 秒 | B站、中文 README、Release |
| English horizontal / 英文横版 | 1920 × 1080, 16:9 | About 32 seconds / 约 32 秒 | English README、Release |

These are editorial targets, not every platform's upload limits. YouTube classifies eligible square or vertical videos up to three minutes as [Shorts](https://support.google.com/youtube/answer/15424877?hl=en-GB). TikTok recommends a vertical, sound-on presentation in its [creative guidance](https://ads.tiktok.com/business/library/Top_Tips_One_Pager_SMB.pdf). Keep important text away from right-side controls and bottom captions; check each platform's upload preview before posting.

以上是制作规格，并非各平台完整上传限制。竖版需要重新构图，不把整段电脑画面直接缩小：上方保留 YouTube 场景，下方可放大同一时刻、同一录像中的真实字幕像素。关键文字避开右侧互动按钮与底部说明区域，发布前再检查平台预览。

## Edit / 剪辑安排

| Time / 时间 | Picture / 画面 | Sound / 声音 |
| --- | --- | --- |
| 0–3 s | Solid brand blue; large hook, with a smaller second-language line / 品牌蓝纯色背景，大字钩子与较小的另一语言 | Short AI-spoken hook / AI 旁白钩子 |
| 3–11.5 s | Real YouTube playback; explain choosing a translation direction and starting captions / 真实 YouTube 播放，说明选择翻译方向和开始字幕 | Brief usage narration / 简短使用解说 |
| 11.5–17.5 s | Uninterrupted actual translated captions / 连续展示实际翻译字幕 | Original tab audio, no narration, quiet music / 保留原声，旁白留白，配乐压低 |
| 17.5–27.5 s | Continue actual output; short local-Ollama and language-mode callouts / 继续实际画面，简短说明本地模型与翻译方向 | AI narration + low backing music / AI 旁白与低音量配乐 |
| 27.5–32 s | StreamLingo + repository address / 产品名称与仓库地址 | Natural project-name sign-off / 自然介绍项目名称 |

AI narration belongs to the promotional edit. It does not imply that the extension provides spoken translation. Background music is composed for this video; do not reuse an unrelated soundtrack download.

AI 配音属于宣传片后期，不表示扩展已有语音播报功能。背景音乐为本片制作，不下载来历不明的配乐。

The narration is generated locally with [MeloTTS Chinese](https://huggingface.co/myshell-ai/MeloTTS-Chinese) and [Piper LJ Speech English](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/medium/MODEL_CARD), through [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). MeloTTS declares MIT; the Piper voice card identifies the public-domain LJ Speech dataset. Keep their notices and the voice-model metadata with production records. The music is an original 96 BPM instrumental generated without external samples.

Production credit: **AI narration: MeloTTS / Piper via sherpa-onnx. Original music: StreamLingo.** These are video-production tools, not added application runtime requirements.

## Capture / 录制

Run `node scripts/record-social-demo.mjs`, then open the loopback recording page in Chrome. It uses Chrome's own tab picker and MediaRecorder. Select the intended YouTube tab with tab audio, start the real extension, and verify captions are running before recording. The original WebM is saved under the ignored `output/social-video/capture` directory.

录制工具只记录选中的标签页；Chrome 工具栏与扩展弹窗不在录制范围内。不能用重绘弹窗假装录到了真实点击，也不能用连续截图冒充稳定帧率的视频。录制前核验真实字幕已运行；录制后检查视频、音轨和字幕三项。

Keep source audio and captured captions synchronized. Cropping, reframing, title cards, narration and music are allowed editorial changes; retyping a better translation over a failed live result is not. A draft without extension captions must not replace the public usage demo.

保持录制的音画与字幕时间关系。允许裁切、重新构图、片头片尾、旁白与配乐；不把真实输出替换成预写的正确译文。未录到扩展字幕的草稿不能作为产品效果成片。

## Footage attribution / 片段署名

The capture uses a dialogue scene from [Tears of Steel on the official Blender YouTube channel](https://www.youtube.com/watch?v=R6MlUcmOul8), starting around 3:09. It is a **recorded-video demonstration**, not a livestream. The product's primary use case remains livestream captions. Label the excerpt **YouTube playback demo / YouTube 回放实录**.

Tears of Steel — Blender Foundation | mango.blender.org. [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Excerpt cropped and shown with StreamLingo-generated captions. Source and license information: [official film page](https://mango.blender.org/about/). No endorsement is implied.

Only retain the excerpt's synchronized original film mix; it is not the separately added backing track for this promotion. Include the full attribution and source link in upload descriptions, with a short readable credit in the video.

使用短片段原有的同步音画，独立发行的电影原声专辑不作为宣传片背景音乐。视频内放简短署名，发布说明保留完整来源、许可与裁切/增加字幕说明。

## Completion checks / 交付检查

- Opening hook is readable within three seconds in each language; English copy has English narration.
- Actual recorded captions remain readable on a phone; neither the page UI nor translations are simulated.
- Original speech can be heard during the six-second narration gap; the final mix does not clip.
- Output dimensions, decoded duration, audio streams and several representative frames are checked.
- Keep the original capture and production metadata locally; attach finished MP4s to Releases instead of storing them in Git.
- Update README covers and Release assets only after the complete video passes these checks.

## Rebuild production assets / 重新生成制作素材

Use a separate environment; these dependencies are not required to use StreamLingo. The verified production environment uses Python 3.11, FFmpeg 8.0.1, sherpa-onnx 1.13.8 and soundfile 0.14.0.

```powershell
py -3.11 -m venv output/social-video-tools
& output/social-video-tools/Scripts/python.exe -m pip install sherpa-onnx==1.13.8 soundfile==0.14.0 numpy==2.4.6 cffi==2.1.1 pycparser==3.11
```

Extract the official [MeloTTS archive](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2) and [Piper LJ archive](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-ljspeech-medium.tar.bz2) under `output/social-video-tools/models/`, retaining each archive's top-level directory and license files. Then generate narration and original music:

```powershell
& output/social-video-tools/Scripts/python.exe scripts/social-video-audio.py --engine local
```

Generate a three-second title preview independently of the real recording:

```powershell
py scripts/render-social-video.py --intro-preview --language zh-CN --layout vertical --narration output/social-video/neural-local/voice-stereo-zh.wav --music output/social-video/music-original.wav
```

For the full edit, use `--video` with an original recorded WebM, `--start` with the reviewed source offset, `--screen-crop x:y:width:height` to remove recommendations/comments, and `--caption-crop x:y:width:height` with the actual subtitle bounds in the original recording. Change `--language` to `en` and `--layout` to `horizontal` for the other deliverables. Run `--dry-run` to inspect the plan first. Rendering cannot establish that a capture contains genuine extension output; verify the recording visually before using it.

The reviewed take is `youtube-zh-CN-take-02.webm` (1920 × 888, Chrome tab audio). The edit uses source timestamps 18–42.5 seconds at original speed, with main crop `0:0:1360:480` and vertical caption crop `488:216:408:208`. Recommendations, comments, channel controls, and browser toolbar are excluded. Promotional copy and narration are localized; the actual English-to-Chinese caption output is preserved in both versions. The movie is a playback demonstration, not evidence from a livestream.

The four H.264/AAC exports are 32 seconds, 30 fps, with 48 kHz stereo audio. Full decoding and sampled-frame checks passed; decoded sample peaks are below 0 dBFS. This verifies production integrity, not speech-recognition accuracy. Original captions include imperfect recognition and visible reading delay; no translation was rewritten in post-production.

Models, recordings, narration, render plans and finished videos stay inside the ignored `output/` directory. The rendering tool refuses to replace existing outputs without `--overwrite`.
