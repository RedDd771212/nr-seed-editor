# -*- coding: utf-8 -*-
"""从 SB_MenuIcon 图集按 layout 坐标切 MENU_MenuIcon_42xxx（地图 pin 图标）。"""
import re, os, sys, glob
from PIL import Image

ATLAS = r'D:\项目\app\NR地图种子编辑器\work\atlas_png'
SBLYT = r'D:\项目\app\NR地图种子编辑器\work\sblyt_l'
OUT = r'D:\项目\app\NR地图种子编辑器\work\menuicon_42'

os.makedirs(OUT, exist_ok=True)

for lay in sorted(glob.glob(os.path.join(SBLYT, '*MenuIcon*.layout.bin'))):
    txt = open(lay, 'rb').read().decode('utf-8', 'replace')
    sprites = re.findall(r'<SubTexture\s+name="([^"]+)"\s+x="(-?\d+)"\s+width="(\d+)"\s+y="(-?\d+)"\s+height="(\d+)"', txt)
    name = os.path.basename(lay)
    atlas_name = re.search(r'SB_MenuIcon_\d', name).group(0)
    img = Image.open(os.path.join(ATLAS, atlas_name + '.png')).convert('RGBA')
    hits = [s for s in sprites if '42' in s[0]]
    print(atlas_name, 'sprites', len(sprites), '42xxx', len(hits))
    for nm, x, w, y, h in hits:
        box = (int(x), int(y), int(x) + int(w), int(y) + int(h))
        img.crop(box).save(os.path.join(OUT, nm.replace('.png', '') + '.png'))
print('saved ->', OUT)
