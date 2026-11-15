# -*- coding: utf-8 -*-
"""种子信息层：给人看的调研报告 + 给图用的散点预览。

用法:
  python tools/seed_report.py 0            # 一个 patternId 的完整报告
  python tools/seed_report.py 0 --map      # 顺手把散点画到 map 图上
  python tools/seed_report.py --validate   # 全表体检
  python tools/seed_report.py --sets       # 看所有种子组（set）的区间
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from nrseed.model import SeedModel  # noqa: E402
from nrseed.paramdir import ParamDir  # noqa: E402

PARAMS = ROOT / "work" / "reg" / "params"
MAP_IMG = ROOT / "assets" / "map" / "limveld.png"


def fmt_xy(v):
    return "—" if v is None else f"{v:.6f}"


def print_sets(m: SeedModel):
    print(f"{'set':>5} {'boss':>4} {'rare':>4} {'decl':>4} {'act':>3}  {'区间':>11}  {'权重':>6} {'混沌':>5}")
    for sid in sorted(m.ranges):
        d = m.describe_set(sid)
        lo, hi = d["range"]
        print(f"{sid:>5} {str(d['targetBoss']):>4} {str(d['rareMap']):>4} {d['patternCount']:>4} {d['actual']:>3}  "
              f"{lo:>5}..{hi:<5} {str(d['weight']):>6} {str(d['chaosWeight']):>5}")


def print_report(m: SeedModel, pid: int):
    info = m.pattern_info(pid)
    s = info["set"] or {}
    print("=" * 78)
    print(f"种子 patternId = {pid}")
    print("=" * 78)
    print(f"归属种子组 set {s.get('set')}   Boss {s.get('targetBoss')}   rareMap {s.get('rareMap')}   "
          f"区间 {s.get('range')}   weight={s.get('weight')} chaos={s.get('chaosWeight')}")
    print(f"Boss 名 id={s.get('boss_name_id')}  图标 id={s.get('boss_icon')}（NightBossMenuParam）")
    print()

    print(f"事件变体（{len(info['variants'])} 套，由开局抽中的那套决定 eventFlag）")
    for v in info["variants"]:
        print(f"   row={v['row']:>5}  eventFlag={v['eventFlag']:>6}  modifierSet={v['modifierSet']:>6}  modifier={v['modifier']:>6}")
    print()

    pa = info["playArea"]
    if pa:
        print("缩圈 / 夜晚 BOSS（LotResultPlayAreaParam）")
        print(f"   playArea1={pa['playArea1']}  playArea2={pa['playArea2']}")
        print(f"   bossId1={pa['bossId1']}  bossId2={pa['bossId2']}  "
              f"extra={pa['extraBossId1']}/{pa['extraBossId2']}")
        print(f"   bossModifier1={pa['bossModifier1']}  bossModifier2={pa['bossModifier2']}")
    else:
        print("缩圈：⚠ 没有对应行")
    print()

    spots = info["spots"]
    print(f"地点（LotResultSmallBaseAndSpot）：{len(spots)} 个")
    by_tile = defaultdict(list)
    for sp in spots:
        by_tile[(sp["tile"], tuple(sp["define"]))].append(sp)
    for (tile, defs), items in sorted(by_tile.items()):
        names = items[0]["define_names"]
        icon = items[0]["icon"]
        print(f"   tile {tile:>5}  ×{len(items):<3} 图标iconId={icon}  {names}")
        for sp in items[:40]:
            print(f"       attach {sp['attachId']:>4}  grid={sp['grid']}  pos=({sp['pos'][0]:.6f}, {sp['pos'][1]:.6f}, {sp['pos'][2]:.6f})"
                  f"  mapIndex={sp['mapIndex']} variation={sp['variationId']}  {sp['name']}")
        if len(items) > 40:
            print(f"       … 还有 {len(items) - 40} 个")
    print()

    issues = [i for i in m.validate() if i.get("patternId") == pid]
    if issues:
        print("本种子的问题")
        for i in issues:
            print(f"   [{i['level']}] {i['msg']}")
    else:
        print("本种子链路完整：pattern → playArea → spots → attach/define 全部对得上。")


def render_map(m: SeedModel, pid: int, out: Path):
    from PIL import Image, ImageDraw

    if not MAP_IMG.exists():
        print("没有地图底图，跳过渲染")
        return
    im = Image.open(MAP_IMG).convert("RGBA")
    W, H = im.size
    d = ImageDraw.Draw(im)
    spots = m.spots_by_pid.get(pid, [])
    if not spots:
        print("这个 patternId 没有地点，跳过渲染")
        return

    pts = []
    for r in spots:
        ap = m.attach.get(r["attachId"])
        if not ap:
            continue
        pts.append((ap["gridXNo"] * 256 + 128 + ap["posX"], ap["gridZNo"] * 256 + 128 + ap["posZ"], r))
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    print(f"世界坐标范围 x {x0:.0f}..{x1:.0f}  z {z0:.0f}..{z1:.0f}")

    def to_px(x, z):
        return ((x - x0) / (x1 - x0) * (W - 1), (z - z0) / (z1 - z0) * (H - 1))

    palette = [(230, 90, 80), (240, 170, 70), (110, 200, 130), (110, 165, 235), (200, 120, 230), (235, 235, 120)]
    tiles = sorted({r["smallBaseMapId"] for r in spots})
    color = {t: palette[i % len(palette)] for i, t in enumerate(tiles)}
    for x, z, r in pts:
        px, py = to_px(x, z)
        c = color[r["smallBaseMapId"]]
        d.ellipse([px - 6, py - 6, px + 6, py + 6], outline=c, width=3)
        d.ellipse([px - 1.5, py - 1.5, px + 1.5, py + 1.5], fill=c)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out)
    print(f"预览图 -> {out}")


def main():
    args = [a for a in sys.argv[1:]]
    flags = {a for a in args if a.startswith("--")}
    nums = [a for a in args if not a.startswith("--")]
    m = SeedModel(ParamDir(str(PARAMS)))

    if "--validate" in flags:
        issues = m.validate()
        errs = [i for i in issues if i["level"] == "error"]
        print(f"体检：{len(issues)} 条（error {len(errs)}）")
        for i in issues:
            print(f"  [{i['level']}] {i['table']}: {i['msg']}")
        return
    if "--sets" in flags:
        print_sets(m)
        return

    pid = int(nums[0]) if nums else 0
    print_report(m, pid)
    if "--map" in flags:
        render_map(m, pid, ROOT / "work" / f"seed_{pid}_map.png")


if __name__ == "__main__":
    main()

