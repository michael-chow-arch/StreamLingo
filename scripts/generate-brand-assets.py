"""Render original code-defined StreamLingo branding (requires Pillow)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
icons = ROOT / 'extension/icons'
assets = ROOT / 'docs/assets'
icons.mkdir(parents=True, exist_ok=True)
assets.mkdir(parents=True, exist_ok=True)
svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128"><rect x="4" y="4" width="120" height="120" rx="32" fill="#2563eb"/><g fill="#fff"><rect x="29" y="47" width="10" height="34" rx="5"/><rect x="49" y="28" width="10" height="72" rx="5"/><rect x="69" y="38" width="10" height="52" rx="5"/><rect x="89" y="51" width="10" height="26" rx="5"/></g></svg>'''
(icons / 'logo.svg').write_text(svg, encoding='utf-8')
master = Image.new('RGBA', (512, 512))
draw = ImageDraw.Draw(master)
draw.rounded_rectangle((16, 16, 496, 496), radius=128, fill='#2563eb')
for x, y, h in [(29, 47, 34), (49, 28, 72), (69, 38, 52), (89, 51, 26)]:
    draw.rounded_rectangle((x*4, y*4, (x+10)*4, (y+h)*4), radius=20, fill='white')
for size in (16, 32, 48, 128):
    master.resize((size, size), Image.Resampling.LANCZOS).save(icons / f'icon{size}.png')

# Chrome Web Store small promotional tile. Original artwork, not a screenshot.
tile = Image.new('RGB', (880, 560), '#eef4ff')
d = ImageDraw.Draw(tile)
tile.paste(master.resize((128,128), Image.Resampling.LANCZOS), (54,52), master.resize((128,128), Image.Resampling.LANCZOS))
font_root = Path('C:/Windows/Fonts')
regular = font_root/'segoeui.ttf'
bold = font_root/'segoeuib.ttf'
def text(x, y, value, size, color='#10213b', strong=False):
    d.text((x,y), value, fill=color, font=ImageFont.truetype(str(bold if strong else regular),size))
text(202, 62, 'StreamLingo', 65, strong=True)
text(58, 221, 'Live streams.', 65, strong=True)
text(58, 298, 'AI-translated.', 65, strong=True)
d.text((60, 400), 'YouTube 直播 AI 翻译字幕', fill='#244f87', font=ImageFont.truetype(str(font_root/'msyh.ttc'), 35))
text(60, 458, 'Setup once. Start daily.', 28, '#244f87')
text(60, 501, 'Requires Ollama + local companion service', 22, '#435b79')
tile.resize((440,280), Image.Resampling.LANCZOS).save(assets/'store-promo-440x280.png')
print('Created original logo, four icons, and 440x280 promotional tile.')
