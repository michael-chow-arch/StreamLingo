"""Build the Windows starter ZIP using an explicit allowlist; never publish it."""
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
extension = ROOT / 'dist/extension'
manifest = json.loads((extension / 'manifest.json').read_text(encoding='utf-8'))
if manifest['version'] != version or 'key' not in manifest:
    raise SystemExit('Run npm run build first: Windows manual installation requires the development extension and its stable ID.')
files = [ROOT / name for name in (
    'package.json', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md', 'README.zh-CN.md',
    'SECURITY.md', 'CONTRIBUTING.md', 'CHANGELOG.md',
    'Setup-StreamLingo.cmd', 'Start-StreamLingo.cmd', 'Stop-StreamLingo.cmd', 'Doctor-StreamLingo.cmd',
    'scripts/setup.ps1', 'scripts/start.ps1', 'scripts/stop.ps1', 'scripts/doctor.ps1', 'scripts/download-model.py',
    'backend/pyproject.toml', 'backend/README.md', 'docs/getting-started.md', 'docs/privacy-policy.md',
)]
files += list((ROOT / 'backend/src').rglob('*.py'))
files += list((ROOT / 'docs').glob('*.md'))
files += [p for p in extension.rglob('*') if p.is_file()]
files += [p for p in (ROOT / 'docs/assets').glob('*') if p.suffix in {'.png', '.jpg', '.svg', '.md'}]
for path in files:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f'Missing or unsafe release file: {path}')
output = ROOT / 'dist' / f'streamlingo-windows-{version}.zip'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

build_info = {
    'version': version,
    'source_commit': git('rev-parse', 'HEAD'),
    'source_tree': git('rev-parse', 'HEAD^{tree}'),
    'tracked_changes': bool(git('status', '--porcelain', '--untracked-files=no')),
    'built_at_utc': datetime.now(timezone.utc).isoformat(),
    'packaging_python': platform.python_version(),
    'note': 'Source provenance; this archive is not claimed to be byte-for-byte reproducible.',
}
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, f'StreamLingo/{path.relative_to(ROOT).as_posix()}')
    archive.writestr('StreamLingo/BUILD-INFO.json', json.dumps(build_info, indent=2) + '\n')
    archive.writestr('StreamLingo/START-HERE.txt',
        'StreamLingo for Windows - existing Ollama users\n\n'
        'Requirements: NVIDIA GPU, CUDA 12 cuBLAS, complete cuDNN 9 for CUDA 12,\n'
        'compatible driver and x64 Visual C++ runtime. See docs/runtime-requirements.md.\n'
        'Verified runtime combination: CUDA 12.4.1 + cuDNN 9.3. No automatic CPU fallback.\n\n'
        '1. Extract this entire folder to a permanent location.\n'
        '2. Start Ollama with an installed chat model.\n'
        '3. Double-click Setup-StreamLingo.cmd once (Internet required).\n'
        '4. In chrome://extensions enable Developer mode and Load unpacked: dist/extension.\n'
        '5. Double-click Start-StreamLingo.cmd. Open YouTube and click Start subtitles.\n\n'
        'Daily use: Start. Troubleshooting: Doctor. Exit: Stop.\n'
        '64-bit Python 3.11-3.13 is required; Setup can offer Python 3.12 through winget.\n'
        'Node.js is not required for this prebuilt bundle. Models are downloaded during Setup.\n'
        'Not a signed installer. Not yet published in the Chrome Web Store.\n'
        'Chinese instructions: README.zh-CN.md\n')
checksum = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix('.zip.sha256').write_text(f'{checksum}  {output.name}\n', encoding='ascii')
print(f'Windows bundle: {output} ({output.stat().st_size:,} bytes)')
