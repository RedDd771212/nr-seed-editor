# -*- coding: utf-8 -*-
"""把种子地点叠到 Limveld 手绘地图上（1 世界单位 = 1 像素，用主城做锚点校准）。

坐标（m01075 修正）：posX/posZ 以格中心为原点
  world_x = gridX*256 + 128 + posX
  world_z = gridZ*256 + 128 + posZ
校准（m00802）：主城 attach world (11225.7, 9662.66) 对应手绘图 (720, 834)
  → OX = 11225.7 - 720 = 10505.7，OZ = 834 + 9662.66 = 10496.66
换算：px = wx - OX，py = OZ - wz（z 越大越靠北/上）。

人工校准src/data/seed_overrides.json 里的 swap_pairs 会在这里生效（只改显示）。

用法: python tools/render_overlay.py 0 [--flip]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.model import SeedModel  # noqa: E402
from nrseed.paramdir import ParamDir  # noqa: E402

MAP = ROOT / 'assets' / 'map' / 'limveld.png'
PINS = ROOT / 'assets' / 'icon' / 'pin'
TABLE = ROOT / 'src' / 'data' / 'pin_icons.json'
OVERRIDES = ROOT / 'src' / 'data' / 'seed_overrides.json'
OX, OZ = 10504.44, 10491.71    # 以 7 个监牢圆心标定（m01308）
PIN = 74
BAR = 70
NUDGE = []  # 不再单点微调；位置偏差一律改 OX/OZ，保证主城只当参照
BOSS_ICONS = {42015, 42016, 42027, 42034, 42035, 42019}  # 野外BOSS / 粪金龟 / 强化野外BOSS 等


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


def main():
    from PIL import Image, ImageDraw, ImageFont
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    pid = int(nums[0]) if nums else 0
    flip = '--flip' in sys.argv
    m = SeedModel(ParamDir(str(ROOT / 'work' / 'reg' / 'params')))
    table = json.loads(TABLE.read_text(encoding='utf-8'))['icons']
    ov = json.loads(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}

    infos = {}
    for sp in m.spots_by_pid.get(pid, []):
        info = m.describe_spot(sp)
        infos[sp.get('_id')] = info

    swap = {}
    for a, b in (ov.get(str(pid), {}) or {}).get('swap_pairs', []):
        swap[a], swap[b] = b, a
    # 全局按 attachId 换位（同一对槽位在每个种子里都会复现同样的错位）
    by_attach = {}
    for rid, info in infos.items():
        by_attach.setdefault(info['attachId'], []).append(rid)
    for a, b in (ov.get('global') or {}).get('swap_attach', []):
        ra, rb = by_attach.get(a, [None])[0], by_attach.get(b, [None])[0]
        if ra is not None and rb is not None:
            swap[ra], swap[rb] = rb, ra

    base = Image.open(MAP).convert('RGBA')
    W, H = base.size
    canvas = Image.new('RGBA', (W, H + BAR), (22, 23, 27, 255))
    canvas.alpha_composite(base, (0, 0))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 16)

    used = {}
    drawn = 0
    placed = []      # 先算位置，再统一去重叠
    for rid, info in infos.items():
        if not info['icon']:
            continue                      # 没图的先不画
        src = infos.get(swap.get(rid)) or info   # 人工校准只用对方的坐标
        wx, wz = src['world']
        if wx is None:
            continue
        px = wx - OX
        py = (wz - (OZ - H)) if flip else (OZ - wz)
        placed.append([px, py, info['icon']])

    # 同一坐标叠了好几个 pin（如野外BOSS守着魔法师塔）→ 绕小圈错开，谁都不挡谁
    buckets = {}
    for p in placed:
        buckets.setdefault((round(p[0] / 10), round(p[1] / 10)), []).append(p)
    for grp in buckets.values():
        n = len(grp)
        if n < 2:
            continue
        # m01225：建筑在上、守着它的野外BOSS 在下 → BOSS 排到后位（后位 = 顺时针往下）
        grp.sort(key=lambda p: 1 if p[2] in BOSS_ICONS else 0)
        r = 40 + 10 * (n - 2)
        for k, p in enumerate(grp):
            ang = -math.pi / 2 + 2 * math.pi * k / n
            p[0] += r * math.cos(ang)
            p[1] += r * math.sin(ang)

    for n_icon, ndx, ndy in NUDGE:
        for p in placed:
            if p[2] == n_icon:
                p[0] += ndx
                p[1] += ndy

    for px, py, icon_id in placed:
        ic = icon_pixels(icon_id)
        used[icon_id] = used.get(icon_id, 0) + 1
        drawn += 1
        if ic:
            canvas.alpha_composite(ic, (int(px - ic.width / 2), int(py - ic.height / 2)))

    # 没有 pin 的点（m01351）：事件控制的不画；LotResultSmallBaseAndSpot 规定的用文字标出来
    lfont = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 15)
    labels = 0
    for rid, info in infos.items():
        if info['icon']:
            continue
        nm_all = ' '.join([info['name']] + info['define_names']).lower()
        if 'night horde' in nm_all or info['name'].lower().startswith('encounter:'):
            continue                      # 夜之军团等：由事件控制，不画
        wx, wz = info['world']
        if wx is None:
            continue
        px = wx - OX
        py = (wz - (OZ - H)) if flip else (OZ - wz)
        text = (info['name'] or ' / '.join(info['define_names']) or f"tile {info['tile']}")
        text = text.replace('Tile: ', '').replace(' (Cataclysm)', '')
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(250, 235, 190))
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):     # 描边，压在画上也看得清
            d.text((px + 7 + ox, py - 9 + oy), text, font=lfont, fill=(40, 40, 45))
        d.text((px + 7, py - 9), text, font=lfont, fill=(255, 245, 215))
        labels += 1

    d.rectangle([0, H, W, H + BAR], fill=(22, 23, 27, 255))
    x = 10
    for icon_id, cnt in sorted(used.items(), key=lambda kv: -kv[1])[:10]:
        ic = icon_pixels(icon_id, 30)
        if ic:
            canvas.alpha_composite(ic, (x + 2, H + 18))
        name = (table.get(str(icon_id)) or {}).get('zh') or f'#{icon_id}'
        d.text((x + 36, H + 24), f'{name} x{cnt}', fill=(225, 225, 235), font=font)
        x += 36 + int(d.textlength(f'{name} x{cnt}', font=font)) + 14

    title = f'patternId {pid}  on Limveld' + ('  [flip]' if flip else '') + \
            (f'  (calibrated {len(swap)//2})' if swap else '')
    d.text((14, 12), title, fill=(30, 30, 30),
           font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 20))
    name = f'seed_{pid}_overlay_flip.png' if flip else f'seed_{pid}_overlay.png'
    out = ROOT / 'work' / name
    canvas.convert('RGB').save(out)
    print('->', out, drawn, 'pins', labels, 'labels')


if __name__ == '__main__':
    main()









