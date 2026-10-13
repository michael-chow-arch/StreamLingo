"""Collect local draft store artwork and copy; does not upload anything."""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
version = json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
names = [
    'docs/assets/streamlingo-overview-en.jpg', 'docs/assets/streamlingo-overview-zh-CN.jpg',
    'docs/assets/store-promo-440x280.png', 'docs/assets/README.md',
    'extension/icons/icon128.png', 'docs/chrome-web-store.md', 'docs/privacy-policy.md',
    'docs/promotion.md',
]
output = root/'dist'/f'streamlingo-{version}-store-materials.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for name in names:
        archive.write(root/name, name)
    archive.writestr('READ-ME.txt',
        'Draft Chrome Web Store materials. Not a published listing.\n'
        'Artwork uses the built UI with original sample content and simulated state.\n'
        'Use the English 1280x800 JPEG for the English listing and the Chinese JPEG for Chinese.\n'
        'Use the 440x280 PNG as the small promo tile.\n'
        'Follow docs/chrome-web-store.md for required manual verification and store-assigned extension ID.\n'
        'Host privacy-policy.md at a public URL before submitting.\n')
print(f'Store materials (not uploaded): {output}')
