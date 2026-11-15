# -*- coding: utf-8 -*-
"""把一个种子的散点画到 Limveld 地图上，带真实的游戏 pin 图标。

用法:
  python tools/render_seed.py 0                 # 单个种子
  python tools/render_seed.py 0 --flip-z        # z 轴翻转
  python tools/render_seed.py --attach-all      # 只画全部 attach 点（校准用）
  python tools/render_seed.py --all             # 所有种子
  ... --box x0,x1,z0,z1                          # 自定义世界坐标范围
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.model import SeedModel  # noqa: E402
from nrseed.paramdir import ParamDir  # noqa: E402

MAP = ROOT / 'assets' / 'map' / 'limveld.png'
PINS = ROOT / 'assets' / 'icon' / 'pin'
TABLE = ROOT / 'src' / 'data' / 'pin_icons.json'
BAR = 64
TILE = 256
PIN_PX = 44


def load_model():
    return SeedModel(ParamDir(str(ROOT / 'work' / 'reg' / 'params')))


def load_table():
    return json.loads(TABLE.read_text(encoding='utf-8'))['icons']


def icon_pixels(icon_id, px=PIN_PX):
    from PIL import Image
    if icon_id is None:
        return None
    p = PINS / f'{icon_id}.png'
    if not p.exists():
        return None
    im = Image.open(p).convert('RGBA')
    im.thumbnail((px, px))
    return im


def render(m, spots, out: Path, box=None, flip_z=False, title=''):
    from PIL import Image, ImageDraw, ImageFont

    base = Image.open(MAP).convert('RGBA')
    W, H = base.size
    canvas = Image.new('RGBA', (W, H + BAR), (20, 20, 24, 255))
    canvas.alpha_composite(base, (0, 0))
    d = ImageDraw.Draw(canvas)
    table = load_table()

    pts = []
    for sp in spots:
        info = m.describe_spot(sp)
        wx, wz = info['world']
        if wx is None:
            continue
        pts.append((wx, wz, info))

    if box:
        x0, x1, z0, z1 = box
    else:
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)

    def to_px(x, z):
        px = (x - x0) / (x1 - x0) * W
        t = (z - z0) / (z1 - z0)
        py = (t if flip_z else 1 - t) * H
        return px, py

    used = {}
    for wx, wz, info in pts:
        px, py = to_px(wx, wz)
        ic = icon_pixels(info['icon'])
        used[info['icon']] = used.get(info['icon'], 0) + 1
        if ic:
            canvas.alpha_composite(ic, (int(px - ic.width / 2), int(py - ic.height / 2)))
        else:
            d.ellipse([px - 5, py - 5, px + 5, py + 5], outline=(255, 120, 90), width=2)

    items = sorted(used.items(), key=lambda kv: -kv[1])[:9]
    d.rectangle([0, H, W, H + BAR], fill=(20, 20, 24, 255))
    x = 10
    font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 16)
    for icon_id, cnt in items:
        ic = icon_pixels(icon_id, 28)
        if ic:
            canvas.alpha_composite(ic, (x + 2, H + 16))
        name = (table.get(str(icon_id)) or {}).get('zh') or f'#{icon_id}'
        d.text((x + 34, H + 20), f'{name} x{cnt}', fill=(225, 225, 235), font=font)
        x += 34 + int(d.textlength(f'{name} x{cnt}', font=font)) + 16

    d.text((12, 10), f'{title}  spots {len(pts)}  icons {len(used)}',
           fill=(30, 30, 30), font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 20))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(out)
    print(f'-> {out}  ({len(pts)} points)')


def main():
    args = sys.argv[1:]
    flip = '--flip-z' in args
    box = None
    for i, a in enumerate(args):
        if a == '--box' and i + 1 < len(args):
            box = tuple(float(v) for v in args[i + 1].split(','))
    m = load_model()

    if '--attach-all' in args:
        spots = [{'attachId': k} for k in sorted(m.attach)]
        render(m, spots, ROOT / 'work' / 'attach_points.png', box=box, flip_z=flip, title='all attach points')
        return
    if '--all' in args:
        spots = [s for pid in sorted(m.spots_by_pid) for s in m.spots_by_pid[pid]]
        render(m, spots, ROOT / 'work' / 'seed_all_map.png', box=box, flip_z=flip, title='all seeds')
        return
    nums = [a for a in args if a.isdigit()]
    pid = int(nums[0]) if nums else 0
    render(m, m.spots_by_pid.get(pid, []), ROOT / 'work' / f'seed_{pid}_map.png', box=box, flip_z=flip, title=f'patternId {pid}')


if __name__ == '__main__':
    main()
