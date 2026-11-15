# -*- coding: utf-8 -*-
"""把 work\menuicon_42 里的图拼成编号对照表。"""
import os, re
from PIL import Image, ImageDraw, ImageFont

SRC = r'D:\项目\app\NR地图种子编辑器\work\menuicon_42'
OUT = r'D:\项目\app\NR地图种子编辑器\work\sheets\menuicon42.png'
COLS, CELL = 8, 128
files = sorted(os.listdir(SRC), key=lambda s: int(re.search(r'(\d+)', s).group(1)))
rows = (len(files) + COLS - 1) // COLS
font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 15)
sheet = Image.new('RGB', (COLS * CELL, rows * (CELL + 22) + 8), (24, 24, 28))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(os.path.join(SRC, f)).convert('RGBA')
    im.thumbnail((CELL - 10, CELL - 10))
    x = (i % COLS) * CELL
    y = (i // COLS) * (CELL + 22)
    bg = Image.new('RGBA', (CELL - 4, CELL - 4), (40, 40, 46, 255))
    bg.alpha_composite(im, ((CELL - 4 - im.width) // 2, (CELL - 4 - im.height) // 2))
    sheet.paste(bg.convert('RGB'), (x + 2, y + 2))
    d.text((x + 6, y + CELL), f.replace('.png', '').replace('MENU_MenuIcon_', '#'), fill=(240, 200, 90), font=font)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
sheet.save(OUT)
print(len(files), '->', OUT, sheet.size)
