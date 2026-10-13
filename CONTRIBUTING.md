# Contributing to StreamLingo

Thanks for helping make local subtitles easier to use. Reports and contributions in English or Simplified Chinese are welcome.

## Find the right place

- For installation questions, start with [Getting started](docs/getting-started.md), then open an [issue](https://github.com/michael-chow-arch/StreamLingo/issues) with the relevant environment details.
- For bugs, give a small reproduction, expected behavior, actual behavior, and redacted errors. A short original or synthetic audio fixture is more useful than a long third-party stream.
- For larger changes, describe the problem and proposed scope in an issue before investing in a substantial implementation.
- For security vulnerabilities, follow [SECURITY.md](SECURITY.md) and report privately.

## Set up without speech models

Prerequisites: Node.js 22+ and Python 3.11–3.13. A GPU and Ollama are not needed for the automated suite.

From the repository root on Windows:

```powershell
npm ci
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -e '.\backend[test]'
npm run check
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

On a POSIX shell, the environment's Python is `backend/.venv/bin/python`; install with `backend/.venv/bin/python -m pip install -e './backend[test]'`. This is a development command, not a claim that live capture or the speech stack has been validated on every OS.

`npm run check` checks TypeScript, runs extension/protocol tests, and builds `dist/extension`. Backend tests use demo providers, fakes, and local test transports. Do not add real model downloads or calls to a developer's Ollama service to the default suite.

GitHub Actions runs the JavaScript checks with Node 22 and backend tests with Python 3.11 and 3.12. Model integration checks are separate, opt-in work. The optional `[asr]` dependency group is not installed by CI.

## Make a focused change

Read the [architecture](docs/architecture.md) and [protocol](docs/protocol.md). Keep Chrome capture in the extension, orchestration in the application layer, and upstream/model-specific behavior in adapters.

- Keep start, stop, disconnect, and resource cleanup correct. Audio capture starts only after a user action.
- Validate messages at context and network boundaries. Preserve session IDs, revisions, and immutable finalized source segments.
- Keep completed translation pages in order and readable. Do not replace lossless reading with silent dropping, clipping, or global text deduplication; real speakers can repeat words.
- Keep interface language independent of translation direction. Update English and Simplified Chinese UI text together.
- Reuse browser APIs and suitable upstream libraries before implementing another audio stack or speech decoder. Attribute incorporated code and preserve its license notices.

Add meaningful tests for changed behavior, especially timing, cleanup, language negotiation, and protocol errors. Small documentation or styling changes do not need artificial tests. Describe what was checked and what was not.

## Verify browser or model changes

Build, load `dist/extension` in Chrome, and verify the affected flow. After rebuilding, reload the extension and refresh the YouTube page so it gets the new content script. Use the [demo mode](docs/getting-started.md#lightweight-demo-and-developer-setup) when testing transport or rendering alone.

For real-model checks, identify the hardware, model, language direction, audio source, and configuration. Use original, synthetic, or permission-cleared audio. Report demo results separately from actual ASR/translation results. Do not turn a single fixture's word match rate into a general accuracy claim.

## Submit a pull request

Keep changes focused and explain the user-visible problem, resulting behavior, and validation. Include screenshots for visible UI changes and note any model-dependent behavior that has not been exercised. Update both READMEs when setup steps or product capabilities change.

Do not commit model weights, virtual environments, build output, private recordings, transcripts, credentials, or personal diagnostic logs. The repository's ignored `output/` folder is suitable for local regression artifacts. Public screenshots and videos must use original or licensed content and must not expose someone else's contact or account details.

Contributions are made under the project's [MIT License](LICENSE). Dependencies, copied portions, and model weights retain their own terms; update [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) when necessary. Be respectful and specific when discussing changes.
