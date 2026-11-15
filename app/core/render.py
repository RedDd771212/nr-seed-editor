# -*- coding: utf-8 -*-
"""把地点画到手绘地图上 —— 与 tools/render_overlay.py 同一套标准。

标准（主人验收过的版本）：
  world = grid*256 + 128 + pos
  px = wx - OX, py = OZ - wz
  OX/OZ 用 7 个监牢圆心平均标定
  pin = 74px，同坐标成组的绕圈错开，BOSS 排后位
  attach 116 / 313 显示换位（固定槽位错位）

分层（m01831）：
  模板层 = 小红圈只标位置；监牢不动（逻辑未定），照旧画图标
  草稿层 = 图标 + 白圈；没图标用文字标注
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / 'assets' / 'map' / 'limveld.png'
PINS = ROOT / 'assets' / 'icon' / 'pin'

OX, OZ = 10504.44, 10491.71
PIN = 74
BOSS_ICONS = {42015, 42016, 42027, 42034, 42035, 42019}
SWAP_ATTACH = []   # m05210：313/116 的位置已由主人校准进 attach_overrides.json，这里不再二次换位

C_TPL = (232, 78, 78)
_preview_cache: dict = {}


def _icon(icon_id, px=PIN, alpha=255):
    if icon_id is None:
        return None
    p = PINS / f'{icon_id}.png'
    if not p.exists():
        return None
    im = Image.open(p).convert('RGBA')
    im.thumbnail((px, px))
    if alpha < 255:
        a = im.getchannel('A').point(lambda v: v * alpha // 255)
        im.putalpha(a)
    return im


def _to_px(world):
    if not world:
        return None
    return world[0] - OX, OZ - world[1]


def _swap_coords(spots):
    """视觉纠正（m02852）：313 和 116 的显示位置整体对调——数据不动，只换画在哪。

    原始坐标里 313（教堂）落在 116（大营地）下方，游戏里是教堂在上方，
    所以这两个点的画面位置互换，写回时仍用各自原始坐标。
    """
    by_attach = {}
    for i, sp in enumerate(spots):
        by_attach.setdefault(sp.get('attachId'), []).append(i)
    for a, b in SWAP_ATTACH:
        ia = by_attach.get(a) or []
        ib = by_attach.get(b) or []
        for x, y in zip(ia, ib):
            wa, wb = spots[x].get('world'), spots[y].get('world')
            spots[x]['world'], spots[y]['world'] = wb, wa


def _place(spots):
    """→ [(x, y, icon_id, 原始下标)]，含同坐标去重叠。"""
    pts = []
    for i, sp in enumerate(spots):
        p = _to_px(sp.get('world'))
        if not p:
            continue
        pts.append([p[0], p[1], sp.get('icon'), i])
    buckets = {}
    for k, p in enumerate(pts):
        buckets.setdefault((round(p[0] / 10), round(p[1] / 10)), []).append(k)
    for grp in buckets.values():
        if len(grp) < 2:
            continue
        grp.sort(key=lambda k: 1 if pts[k][2] in BOSS_ICONS else 0)
        r = 40 + 10 * (len(grp) - 2)
        for n, k in enumerate(grp):
            ang = -math.pi / 2 + 2 * math.pi * n / len(grp)
            pts[k][0] += r * math.cos(ang)
            pts[k][1] += r * math.sin(ang)
    return [tuple(p) for p in pts]


def layout(spots):
    """给前端用：返回与输入等长的 [(px, py)]，与地图上画的完全一致。

    这里必须先做视觉纠正（313/116 换位）再去重叠 —— 前端如果自己算，
    过滤过的列表分组不同，就会跟服务器画的对不上（m04411「红点和圈脱开了」）。
    """
    tpl = [dict(s) for s in spots]
    _swap_coords(tpl)
    pos = {i: (x, y) for (x, y, _icon, i) in _place(tpl)}
    return [pos.get(i) for i in range(len(spots))]


def _label_point(d, x, y, text, font, dx=8):
    text = (text or '').replace('Tile: ', '').replace(' (Cataclysm)', '')
    d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(250, 235, 190), outline=(40, 40, 45))
    for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.text((x + dx + ox, y - 9 + oy), text, font=font, fill=(30, 30, 34))
    d.text((x + dx, y - 9), text, font=font, fill=(255, 245, 215))


def render(template_spots, draft_spots, labels=True, bg=None, allowed=None, rings=True) -> Image.Image:
    """rings=False：不画地点白圈（v3 界面由前端统一画圆圈，好按建筑位类型上色/高亮）。"""
    base = Image.open(bg or MAP).convert('RGBA')
    canvas = base.copy()
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 15)

    tpl = [dict(s) for s in template_spots]
    drf = [dict(s) for s in draft_spots]
    _swap_coords(tpl)

    # 模板层（m05283）：不再画种子里那堆红点 —— 可放建筑的位置改由前端画 47 个校准锚点。
    # 监牢仍画图标当参照（不可改）。
    for x, y, icon, i in _place(tpl):
        sp = tpl[i]
        if ('evergaol' in (sp.get('attachName') or '').lower()
                and (allowed is None or sp.get('attachId') in allowed)):
            ic = _icon(icon, PIN)
            if ic:
                canvas.alpha_composite(ic, (int(x - ic.width / 2), int(y - ic.height / 2)))

    # 草稿层：建筑图标 + 白圈 + 右下角属性小图标（主人 m02119）
    for x, y, icon, i in _place(drf):
        ic = _icon(icon, PIN)
        if rings:
            d.ellipse([x - PIN * 0.42, y - PIN * 0.42, x + PIN * 0.42, y + PIN * 0.42],
                      outline=(255, 255, 255, 235), width=3)
        if ic:
            canvas.alpha_composite(ic, (int(x - ic.width / 2), int(y - ic.height / 2)))
        attr = _icon(drf[i].get('attrIcon'), 38)
        if attr:
            ax = int(x + PIN * 0.26)
            ay = int(y + PIN * 0.26)
            d.rectangle([ax - 2, ay - 2, ax + attr.width + 1, ay + attr.height + 1], outline=(20, 20, 24, 220), width=2)
            canvas.alpha_composite(attr, (ax, ay))
        # 楼顶 / 楼底 角标（m04153：756 Rooftop、757 Basement 坐标相同，得看得出是哪层）
        nm = (drf[i].get('attachName') or '').lower()
        mark = '↑' if 'rooftop' in nm else ('↓' if 'basement' in nm else None)
        if mark:
            bx, by = int(x + PIN * 0.30), int(y - PIN * 0.52)
            d.rounded_rectangle([bx, by, bx + 24, by + 24], radius=6,
                                fill=(16, 18, 22), outline=(255, 255, 255), width=2)
            d.text((bx + 6, by + 1), mark, font=font, fill=(255, 255, 255))

    if labels:
        for sp in drf:
            if sp.get('icon'):
                continue
            p = _to_px(sp.get('world'))
            if not p:
                continue
            nm = ' '.join(filter(None, [sp.get('name'), sp.get('attachName')])).lower()
            if 'night horde' in nm or 'night boss' in nm or 'caravans' in nm:
                continue
            _label_point(d, p[0], p[1],
                         sp.get('name') or sp.get('attachName') or f"tile {sp.get('tile')}",
                         font, dx=34)
    return canvas


def png_bytes(template_spots, draft_spots, rev='', bg=None, allowed=None, rings=True) -> bytes:
    from io import BytesIO
    im = render(template_spots, draft_spots, bg=bg, allowed=allowed, rings=rings)
    buf = BytesIO()
    im.convert('RGB').save(buf, format='PNG')
    return buf.getvalue()




