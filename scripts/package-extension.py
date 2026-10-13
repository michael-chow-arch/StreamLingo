"""Create a reviewed-layout ZIP from a fresh store build; never publish it."""
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
subprocess.run(["node", str(ROOT / "scripts" / "build.mjs"), "--store"], cwd=ROOT, check=True)
source = ROOT / "dist" / "store-extension"
manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
if "key" in manifest:
    raise ValueError("A store release must not contain the development key")
allowed = {"manifest.json", "popup.html", "offscreen.html", "popup.css", "background.js", "popup.js", "offscreen.js",
           "pcm-worklet.js", "content.js", "THIRD_PARTY_NOTICES.md", "AUDIO_SOURCE_NOTICES.md", "LICENSE", "LICENSE.apache-2.0.txt", "LICENSE.zod.txt",
           "_locales/en/messages.json", "_locales/zh_CN/messages.json"}
allowed.update(f"icons/icon{size}.png" for size in (16, 32, 48, 128))
files = {path.relative_to(source).as_posix(): path for path in source.rglob("*") if path.is_file()}
if set(files) != allowed:
    raise ValueError(f"Unexpected/missing release files: {set(files) ^ allowed}")
for name, path in files.items():
    if name.endswith(".js"):
        if "sourceMappingURL=" in path.read_text(encoding="utf-8"):
            raise ValueError(f"Source map reference in {name}")
output = ROOT / "dist" / f"streamlingo-{manifest['version']}-chrome-web-store.zip"
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(files):
        info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, files[name].read_bytes())
with zipfile.ZipFile(output) as archive:
    if archive.testzip() is not None or "manifest.json" not in archive.namelist():
        raise ValueError("ZIP integrity check failed")
print(f"Release ZIP (not uploaded): {output}")
