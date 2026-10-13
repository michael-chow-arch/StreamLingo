# StreamLingo release artwork

Current README covers combine original project typography with a real Chrome recording of the open film Tears of Steel. Older UI fixtures listed below use original garden artwork and simulated controls. Their provenance is different; keep the distinctions when reusing them.

## Current real-recording covers

`real-demo-cover-en.jpg` and `real-demo-cover-zh-CN.jpg` are 1600 × 1000 JPEG browser exports of `scripts/social-cover-preview.mjs`. They show real English-to-Chinese captions from the recorded take, with localized promotional copy. The crop excludes recommendations, comments and channel controls. No popup or translation is reconstructed. Rebuild from the reviewed local frame described in [video-production.md](../video-production.md), open port 8902 in the browser, and export the full 1600 × 1000 page after images load. Preserve the original screenshot bytes and use the filename extension that matches their actual encoding.

Footage: Tears of Steel — Blender Foundation, [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). [Source](https://www.youtube.com/watch?v=R6MlUcmOul8), [official license information](https://mango.blender.org/about/). Changes: cropped frame, actual StreamLingo-generated captions, and added promotional layout. No endorsement is implied. The scene is YouTube playback, not a livestream.

## Historical UI demonstration assets

| File | Purpose | Size |
| --- | --- | --- |
| `streamlingo-overview-en.jpg` | English interface and copy; Chinese-to-English demo; English README / store | 1280 × 800 |
| `streamlingo-overview-zh-CN.jpg` | Chinese interface and copy; English-to-Chinese demo; Chinese README / store | 1280 × 800 |
| `popup-en.jpg` | English popup; Chinese-to-English selected; English README | 380 × 579 |
| `popup-zh-CN.jpg` | Chinese popup; English-to-Chinese selected; Chinese README | 380 × 545 |
| `store-promo-440x280.png` | Small promotional tile | 440 × 280 |
| `promo-cover-en.jpg` | English usage-video opening hook; English README | 1280 × 800 |
| `promo-cover-zh-CN.jpg` | Chinese usage-video opening hook; Chinese README | 1280 × 800 |

Earlier mixed-language `streamlingo-overview.jpg`, `store-chinese-to-english.jpg`, and `popup.jpg` remain as historical assets. Current READMEs use the new real-recording covers plus the locale-specific popup close-ups. Source-language text inside a bilingual caption is intentionally retained.

The JPEGs are browser screenshots of `scripts/demo-preview.mjs`, using the built `popup.js`, `popup.css`, and `content.js`. Chrome messages, connection state, and subtitle text are simulated. The garden scene and sentences are original. These pictures show interface behavior and are **not evidence of recognition accuracy, a real livestream, or Chrome Web Store approval**. The overview explicitly labels this as a UI demonstration.

To preview after a build: `node scripts/demo-preview.mjs`. Use `http://127.0.0.1:8899/?lang=en&mode=zh-en` for the English overview and `/?lang=zh-CN&mode=en-zh` for Chinese. For popup close-ups, use `/popup` with the same parameters. Explicit parameters override saved fixture settings so a previous Chinese session cannot leak into an English screenshot.

The `/capture` page saves original browser-captured JPEG/PNG bytes locally to an allowlisted filename with a matching format; it never uploads to an external service. Overview screenshots use the 1280 × 800 page region. Popup screenshots use the actual 380-pixel-wide body and its measured height. Stop the preview server when finished. UI fixtures are excluded from both shipped extension builds.

`scripts/generate-brand-assets.py` draws the original logo and promotional tile with Pillow. Logo sources and raster icons are in `extension/icons/`. Model verification is recorded separately in [validation.md](../validation.md).

## Record the 30-second usage videos

`node scripts/promo-preview.mjs` serves a separate loopback fixture at `http://127.0.0.1:8900`. Build the extension first. The fixture does not connect to the speech backend, capture a real Chrome tab, or run a model. The silent walkthrough opens with bilingual subtitles, then shows opening a livestream, selecting a direction, starting subtitles, reading the results, stopping, and visiting the project. It does not demonstrate installation.

Open `/?lang=en&frame=0` or `/?lang=zh-CN&frame=0`. Capture the **1280 × 800 `#promo-frame` element** as an original JPEG after the page's `html` element has `data-ready="true"`. Capture these frozen frame numbers for each language: **0, 6, 12, 16, 18, 24, 30, 36, 44, 48, 54**. Their timeline positions equal the frame number divided by 2, and the holds total exactly 30 seconds. `/?lang=en&t=12` is equivalent to frame 24. `&play=1` plays the keyframe walkthrough; frozen URLs are recommended for reproducible screenshots. `/plan.json?lang=en` exposes the timing plan.

The fixture uses the built popup and content-script UI with simulated session controls. If available, subtitle segments 3 and 4 come unchanged from `output/release-acceptance/20261013/restored-smoke-en.json` (Chinese interface) or `restored-smoke-zh.json` (English interface). The screen clearly labels these as **recorded result excerpts, not live inference or an accuracy benchmark**. A clone without those local files uses explicitly labelled original scripted subtitles instead. Timings are edited for the silent demonstration; do not add the original sample audio as if it were synchronized. No third-party livestream is replayed.

Open `/capture?lang=en&frame=0`, select the locale and frame number, and paste the browser screenshot's original JPEG base64. The form remains open and shows the saved filename. It accepts only complete JPEG headers with a 1280 × 800 frame size, fixed locale/frame filenames, same-origin requests, and at most an 8 MiB request body. Frames go to gitignored `output/promo-video/<locale>/frame-00000.jpg`. An optional evidence selector accepts only `live-en-running.jpg` and `release-published.jpg` in `output/promo-video/evidence`; evidence images are excluded from video inputs.

With an existing FFmpeg installation on PATH (no extra Python dependencies), render the captures:

```powershell
python scripts/render-promo-video.py --lang en --keyframes --no-fade
python scripts/render-promo-video.py --lang zh-CN --keyframes --no-fade
```

Outputs are silent H.264 MP4s at `dist/streamlingo-demo-en.mp4` and `dist/streamlingo-demo-zh-CN.mp4`. `--no-fade` makes the opening hook visible immediately; omitting it adds short opening/closing fades. Use `--dry-run` to validate captures and `--overwrite` only to intentionally replace a video. The renderer also supports `--all-frames --input-fps 2` for 60 sequential frames, or `--timestamps plan.json` for explicit frame/time entries. It checks dimensions and ordering before FFmpeg runs, and uses CPU encoding rather than the inference GPU.

Copy a chosen captured frame's **unchanged original JPEG bytes** to `docs/assets/promo-cover-en.jpg` or `docs/assets/promo-cover-zh-CN.jpg` for the README covers. MP4s belong in GitHub Release attachments; do not commit large videos to Git. Stop the preview server when finished. Neither the fixture nor capture endpoints ship in the extension.
