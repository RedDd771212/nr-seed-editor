import sys, os, glob, math
from PIL import Image, ImageDraw, ImageFont

src, pattern, out, cols = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 6
cell = int(sys.argv[5]) if len(sys.argv) > 5 else 256
files = sorted(glob.glob(os.path.join(src, pattern)))
os.makedirs(os.path.dirname(out), exist_ok=True)

try:
    font = ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf', 22)
except Exception:
    font = ImageFont.load_default()

rows = math.ceil(len(files) / cols)
sheet = Image.new('RGB', (cols * cell, rows * (cell + 26)), (28, 28, 32))
d = ImageDraw.Draw(sheet)
idx_lines = []
for i, p in enumerate(files):
    cx, cy = (i % cols) * cell, (i // cols) * (cell + 26)
    try:
        im = Image.open(p).convert('RGBA')
        im.thumbnail((cell - 8, cell - 8), Image.LANCZOS)
        bg = Image.new('RGBA', im.size, (40, 40, 46, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.convert('RGB'), (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2))
    except Exception as e:
        d.text((cx + 6, cy + 6), 'ERR', fill=(255, 80, 80), font=font)
    d.text((cx + 6, cy + cell + 2), f'#{i:04d}', fill=(255, 210, 90), font=font)
    idx_lines.append(f'{i:04d}\t{os.path.basename(p)}')
sheet.save(out)
csv = os.path.splitext(out)[0] + '.csv'
open(csv, 'w', encoding='utf-8').write('index\tfile\n' + '\n'.join(idx_lines) + '\n')
print(f'{len(files)} images -> {out} ({sheet.size[0]}x{sheet.size[1]})')
