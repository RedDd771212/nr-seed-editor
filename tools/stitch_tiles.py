import sys, os, glob
from PIL import Image

src = sys.argv[1]
out = sys.argv[2]
# mode: 'row_col' => first index = row (top->bottom), second = col (left->right)
#       'col_row' => first index = col (left->right), second = row (top->bottom)
mode = sys.argv[3] if len(sys.argv) > 3 else 'row_col'
flip_y = (len(sys.argv) > 4 and sys.argv[4] == 'flip')

files = sorted(glob.glob(os.path.join(src, '*.png')))
tiles = {}
for p in files:
    name = os.path.splitext(os.path.basename(p))[0]
    parts = name.split('_')
    a, b = int(parts[-2]), int(parts[-1])
    tiles[(a, b)] = Image.open(p).convert('RGBA')

w, h = next(iter(tiles.values())).size
na = max(k[0] for k in tiles) + 1
nb = max(k[1] for k in tiles) + 1
if mode == 'col_row':
    W, H = nb * w, na * h
else:
    W, H = na * w, nb * h

sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
for (a, b), im in tiles.items():
    if mode == 'col_row':
        x, y = a * w, b * h
    else:
        x, y = b * w, a * h
    if flip_y:
        y = H - h - y
    sheet.paste(im, (x, y))
sheet.save(out)
print(f'{len(tiles)} tiles -> {out} {sheet.size} mode={mode} flip={flip_y}')
