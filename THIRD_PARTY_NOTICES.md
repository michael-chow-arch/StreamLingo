# Third party components and references

StreamLingo integrates existing browser and speech technologies. It does not implement a speech recognition model.

| Component | Use | Upstream license/source |
| --- | --- | --- |
| Chrome extension samples | Reference for service-worker/offscreen tab capture and audio playback | [GoogleChrome/chrome-extensions-samples](https://github.com/GoogleChrome/chrome-extensions-samples/tree/main/functional-samples/sample.tabcapture-recorder), Apache-2.0 |
| WhisperLiveKit | Optional local streaming speech recognition engine | [QuentinFuxa/WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit), Apache-2.0; speech models and transitive dependencies have their own licenses |
| Web Audio | Browser-native sample-rate conversion, mixing and audio playback | Browser API; no third-party resampling implementation vendored |
| FastAPI and Pydantic | Local HTTP/WebSocket server and Python input validation | MIT; installed as Python dependencies |
| Zod | Runtime validation of server messages in the extension | MIT; installed through npm and bundled into the extension |
| esbuild, TypeScript, tsx | Development build, type checking and tests | Upstream npm package licenses; build tools are not runtime service dependencies |

Exact installed JavaScript versions are recorded in package-lock.json; backend versions and optional speech integration are documented in backend/pyproject.toml and backend/README.md. Builds retain bundled legal comments and include LICENSE.apache-2.0.txt, LICENSE.zod.txt and the audio source notices alongside the extension.

The Chrome sample informed the API sequence. StreamLingo adds application-specific session handling, transport validation, cancellation and subtitle rendering. The audio package documents any additional source attribution next to its implementation.

Subtitle display research (2026-10-13): [Shaka Player UITextDisplayer](https://github.com/shaka-project/shaka-player/blob/main/lib/text/ui_text_displayer.js)
uses timed cues and normal wrapping with preserved whitespace (`pre-wrap`). It is an Apache-2.0 reference;
no Shaka implementation is copied or bundled. StreamLingo uses the browser's native `Intl.Segmenter` for sentence/word boundaries,
then a small reading scheduler for arriving translations. Its automatic pagination and minimum reading time are application policy,
not a feature attributed to Shaka. [Able Player](https://github.com/ableplayer/ableplayer) and
[videojs-transcript](https://github.com/walsh9/videojs-transcript) were evaluated for interactive transcripts;
their history/scroll controls were not adopted because the requested interface is automatic captions only.
No transcript widget or virtual scrolling dependency is installed.
