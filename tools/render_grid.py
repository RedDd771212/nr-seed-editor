# -*- coding: utf-8 -*-
"""把一个种子的地点画成 4x4 世界格子示意图（不依赖底图对齐，坐标是精确的）。

用法: python tools/render_grid.py 0
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.model import SeedModel  # noqa: E402
from nrseed.paramdir import ParamDir  # noqa: E402

TABLE = ROOT / 'src' / 'data' / 'pin_icons.json'
PINS = ROOT / 'assets' / 'icon' / 'pin'
TILE = 256
GX0, GX1 = 42, 46      # gridXNo 42..45
GZ0, GZ1 = 36, 40      # gridZNo 36..39
CELL = 220
MARGIN = 40
PIN = 40


def icon_pixels(icon_id, px=PIN):
    from PIL import Image
    if icon_id is None:
        return None
    p = PINS / f'{icon_id}.png'
    if not p.exists():
        return None
    im = Image.open(p).convert('RGBA')
    im.thumbnail((px, px))
    return im


def render(m, pid, out: Path):
    from PIL import Image, ImageDraw, ImageFont
    table = json.loads(TABLE.read_text(encoding='utf-8'))['icons']
    cols, rows = GX1 - GX0, GZ1 - GZ0
    W = MARGIN * 2 + cols * CELL
    H = MARGIN * 2 + rows * CELL + 70
    im = Image.new('RGBA', (W, H), (24, 25, 30, 255))
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 15)
    font_s = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 12)

    # 格子
    for i in range(cols):
        for j in range(rows):
            x0 = MARGIN + i * CELL
            y0 = MARGIN + j * CELL
            d.rectangle([x0, y0, x0 + CELL, y0 + CELL], outline=(70, 72, 84), width=1)
    d.text((MARGIN, 12), f'patternId {pid} · 4x4 世界格（X {GX0}..{GX1-1} / Z {GZ0}..{GZ1-1}）',
           fill=(230, 230, 240), font=font)

    used = {}
    for sp in m.spots_by_pid.get(pid, []):
        info = m.describe_spot(sp)
        ap = m.attach.get(info['attachId'])
        if not ap:
            continue
        gx, gz = ap['gridXNo'], ap['gridZNo']
        px = MARGIN + (gx - GX0) * CELL + (ap['posX'] + TILE / 2) / TILE * CELL
        py = MARGIN + (gz - GZ0) * CELL + (ap['posZ'] + TILE / 2) / TILE * CELL
        ic = icon_pixels(info['icon'])
        used[info['icon']] = used.get(info['icon'], 0) + 1
        if ic:
            im.alpha_composite(ic, (int(px - ic.width / 2), int(py - ic.height / 2)))
        else:
            d.ellipse([px - 5, py - 5, px + 5, py + 5], outline=(255, 120, 90), width=2)

    y = H - 56
    x = MARGIN
    for icon_id, cnt in sorted(used.items(), key=lambda kv: -kv[1])[:10]:
        ic = icon_pixels(icon_id, 24)
        if ic:
            im.alpha_composite(ic, (x, y))
        name = (table.get(str(icon_id)) or {}).get('zh') or f'#{icon_id}'
        d.text((x + 28, y + 4), f'{name} x{cnt}', fill=(220, 220, 230), font=font_s)
        x += 28 + int(d.textlength(f'{name} x{cnt}', font=font_s)) + 14

    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert('RGB').save(out)
    print('->', out)


def main():
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    pid = int(nums[0]) if nums else 0
    m = SeedModel(ParamDir(str(ROOT / 'work' / 'reg' / 'params')))
    render(m, pid, ROOT / 'work' / f'seed_{pid}_grid.png')


if __name__ == '__main__':
    main()
