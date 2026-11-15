# -*- coding: utf-8 -*-
"""从所有(含DLC)图集里按 layout 坐标切 MENU_*42xxx / 42xxx 地图 pin 图标。"""
import re, os, glob
from PIL import Image

ROOT = r'D:\项目\app\NR地图种子编辑器'
OUT = os.path.join(ROOT, 'work', 'pin_all')
os.makedirs(OUT, exist_ok=True)

pairs = []
for lay in glob.glob(os.path.join(ROOT, 'work', 'sblyt_h', '*.layout.bin')) + \
        glob.glob(os.path.join(ROOT, 'work', 'sblyt_l', '*.layout.bin')) + \
        glob.glob(os.path.join(ROOT, 'work', 'sblyt_dlc', '*.layout.bin')):
    base = os.path.basename(lay)
    m = re.search(r'(SB_[A-Za-z0-9_]+?)\.layout\.bin$', base)
    if not m:
        continue
    atlas_name = m.group(1)
    for d in ('atlas_png', 'atlas_png_dlc', 'atlas_h', 'atlas_dlc'):
        p = os.path.join(ROOT, 'work', d, atlas_name + '.png')
        if os.path.exists(p):
            pairs.append((lay, p))
            break

seen = set()
total = 0
for lay, png in pairs:
    txt = open(lay, 'rb').read().decode('utf-8', 'replace')
    m = re.search(r'width="(\d+)"\s+height="(\d+)"', txt)
    if not m:
        continue
    lw, lh = int(m.group(1)), int(m.group(2))
    sprites = re.findall(r'<SubTexture\s+name="([^"]+)"\s+x="(-?\d+)"\s+width="(\d+)"\s+y="(-?\d+)"\s+height="(\d+)"', txt)
    img = Image.open(png).convert('RGBA')
    sx = img.width / lw
    sy = img.height / lh
    n = 0
    for nm, x, w, y, h in sprites:
        num = re.search(r'(\d{4,5})', nm)
        if not num:
            continue
        num = num.group(1)
        if not (num.startswith('42') or num.startswith('40')):
            continue
        if num in seen:
            continue
        seen.add(num)
        box = (round(int(x) * sx), round(int(y) * sy), round((int(x) + int(w)) * sx), round((int(y) + int(h)) * sy))
        img.crop(box).save(os.path.join(OUT, num + '.png'))
        n += 1
    if n:
        print(f'{os.path.basename(png):<32} layout {lw}x{lh} -> atlas {img.size} +{n}')
    total += n
print('total', total, '->', OUT)
