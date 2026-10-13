# Security policy

## Report a vulnerability privately

Email [michael.chow.tech@gmail.com](mailto:michael.chow.tech@gmail.com) with the subject **StreamLingo security report**. Please do not post exploit details, sensitive audio, or personal data in a public issue.

Include the affected version or commit, component, impact, and a minimal reproduction. Use synthetic data where possible. If sensitive material is necessary, first describe what it contains and arrange an appropriate way to share it. The maintainer will coordinate investigation and disclosure; this volunteer project does not promise a fixed response time or a bug bounty.

## Supported versions

StreamLingo is in early development. Security fixes target the latest source revision; older preview builds do not have a separate maintenance branch. Update the source, backend environment, and unpacked extension together.

## Local service boundary

The default installation listens on loopback and allows only explicitly configured Chrome extension origins. It is intended for one user and one active capture session on the same machine.

The origin allowlist is not authentication against other local programs. The development extension public key is not a secret. Do not expose the service to a LAN or the internet, proxy it publicly, or replace the allowlist with a wildcard. A remotely exposed, multi-user deployment needs a separate security design.

## Audio, text, and logs

The [privacy policy](docs/privacy-policy.md) describes user-facing data handling in English and Simplified Chinese.

Capture starts through a user action in the extension. Tab audio goes to the configured local StreamLingo service, recognized text goes to the configured Ollama endpoint, and subtitles return to the page. Closing the popup or switching tabs does not stop capture; use the stop button to stop it.

The default configuration uses local services for both recognition and translation. Configuring a remote Ollama URL sends recognized text and limited context to that endpoint. Its operator and data practices then matter. Dependency/model downloads and YouTube playback involve their respective external services.

StreamLingo has no built-in analytics or hosted transcription service. The normal subtitle pipeline does not write an audio recording or transcript archive. Completed cues are retained in page memory for the current session and cleared when it ends. Diagnostic output and upstream dependencies can nevertheless contain recognized text, errors, model names, paths, or other sensitive details. Review and redact logs before sharing them. Explicitly run regression scripts may also write local fixtures and reports under `output/`.

## Useful report areas

Reports about unauthorized capture, origin or host validation bypass, remote code execution, unsafe message handling, or unintended data disclosure are especially helpful. Inaccurate transcription, slow translation, and ordinary installation failures belong in the [public issue tracker](https://github.com/michael-chow-arch/StreamLingo/issues) when they do not expose a security vulnerability.
