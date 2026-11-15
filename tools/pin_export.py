# -*- coding: utf-8 -*-
"""导出 pin 图标到 assets，并画两张对照表（wm 表 51 个 + 未命名 42xxx）。"""
import sys, os, shutil
sys.path.insert(0, r'D:\项目\app\NR地图种子编辑器\src')
from PIL import Image, ImageDraw, ImageFont
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

ROOT = r'D:\项目\app\NR地图种子编辑器'
PIN_SRC = os.path.join(ROOT, 'work', 'pin_all')
PIN_OUT = os.path.join(ROOT, 'assets', 'icon', 'pin')
SHEETS = os.path.join(ROOT, 'work', 'sheets')
os.makedirs(PIN_OUT, exist_ok=True)
os.makedirs(SHEETS, exist_ok=True)

m = SeedModel(ParamDir(os.path.join(ROOT, 'work', 'reg', 'params')))
wm = {v['iconId']: v for v in m.wm_icons.values()}

for f in os.listdir(PIN_SRC):
    shutil.copy2(os.path.join(PIN_SRC, f), os.path.join(PIN_OUT, f))

font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 14)
font_s = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 11)


def sheet(ids, out, cols=9, cell=132):
    rows = (len(ids) + cols - 1) // cols
    img = Image.new('RGB', (cols * cell, rows * (cell + 26) + 10), (24, 24, 28))
    d = ImageDraw.Draw(img)
    for i, cid in enumerate(ids):
        p = os.path.join(PIN_SRC, f'{cid}.png')
        x, y = (i % cols) * cell, (i // cols) * (cell + 26)
        if os.path.exists(p):
            ic = Image.open(p).convert('RGBA')
            ic.thumbnail((cell - 12, cell - 12))
            bg = Image.new('RGBA', (cell - 4, cell - 4), (40, 40, 46, 255))
            bg.alpha_composite(ic, ((cell - 4 - ic.width) // 2, (cell - 4 - ic.height) // 2))
            img.paste(bg.convert('RGB'), (x + 2, y + 2))
        d.text((x + 6, y + cell - 2), f'#{cid}', fill=(240, 200, 90), font=font)
        nm = (wm.get(cid) or {}).get('_name') or ''
        if nm:
            d.text((x + 6, y + cell + 12), nm[:20], fill=(190, 190, 200), font=font_s)
    img.save(out)
    print(len(ids), '->', out, img.size)


named = sorted(wm)
sheet(named, os.path.join(SHEETS, 'pin_named.png'))
unnamed = sorted({int(os.path.splitext(f)[0]) for f in os.listdir(PIN_SRC) if os.path.splitext(f)[0].isdigit()} - set(named))
sheet(unnamed, os.path.join(SHEETS, 'pin_unnamed.png'), cols=12, cell=110)
print('copied', len(os.listdir(PIN_OUT)), 'pins ->', PIN_OUT)
