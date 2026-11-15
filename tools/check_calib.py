"""核对 calib/corrections.json —— 人工改过的坐标不直接采信。

用法：
    python tools/check_calib.py [corrections.json] [regulation.bin]

检查项：
  1. id 是否存在、名字是否对得上
  2. 移动距离（>80 世界单位 提示、>200 报警）
  3. 移动后是否跑出自己那一格（pos 超出 ±128）
  4. 是否和别的 attach 点撞在一起（<16 单位）
  5. 删除的点是否被官方种子用过（used > 0 → 高危）
  6. 删除的点是否 pad=0（特殊地形删了没影响）
输出：逐条 OK / 注意 / 危险 + 汇总。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402

TILE, CENTER = 256.0, 128.0
OK, WARN, BAD = "ok", "注意", "危险"


def main():
    args = sys.argv[1:]
    cf = Path(args[0]) if args else ROOT / "calib" / "corrections.json"
    bin_path = args[1] if len(args) > 1 else None
    data = json.loads(cf.read_text(encoding="utf-8"))
    if not bin_path:
        bin_path = data.get("bin")
    p = Project(bin_path)

    pad = p.attach_pad()
    used = {}
    seen = set()
    for s in p.model.spots:
        key = (int(s["attachId"]), int(s["patternId"]))
        if key in seen:
            continue
        seen.add(key)
        used[key[0]] = used.get(key[0], 0) + 1

    ap = p.model.attach
    rows, counts = [], {OK: 0, WARN: 0, BAD: 0}

    # 全部点的世界坐标（用来查撞点）
    worlds = {}
    for aid, a in ap.items():
        gx, gz = a.get("gridXNo"), a.get("gridZNo")
        if gx is None or gz is None:
            continue
        worlds[aid] = (gx * TILE + CENTER + (a.get("posX") or 0),
                       gz * TILE + CENTER + (a.get("posZ") or 0))

    for it in data.get("items", []):
        aid = int(it["id"])
        a = ap.get(aid)
        lvl, why = OK, []
        if a is None:
            lvl, why = BAD, ["bin 里没有这个 attachId"]
        else:
            name = a.get("_name") or ""
            if it.get("name") and name and name != it["name"]:
                lvl = max(lvl, WARN, key=[OK, WARN, BAD].index)
                why.append(f"名字对不上：文件写「{it['name']}」，bin 里是「{name}」")
            if it.get("deleted"):
                if used.get(aid, 0) > 0:
                    lvl, why = BAD, why + [f"被 {used[aid]} 个官方种子用到，删了会缺建筑"]
                elif pad.get(aid, 0) != 0:
                    why.append("特殊地形点（pad≠0），删掉没影响")
                else:
                    why.append("没被任何官方种子用过，删除安全")
            else:
                w = it.get("world") or []
                if len(w) != 2:
                    lvl, why = BAD, why + ["world 字段坏了"]
                else:
                    gx, gz = a.get("gridXNo"), a.get("gridZNo")
                    px = w[0] - (gx * TILE + CENTER)
                    pz = w[1] - (gz * TILE + CENTER)
                    d = it.get("moved")
                    if d is None:
                        ox, oz = worlds[aid]
                        d = ((w[0] - ox) ** 2 + (w[1] - oz) ** 2) ** 0.5
                    if d > 200:
                        lvl = BAD
                        why.append(f"移动了 {d:.0f} 单位，太远")
                    elif d > 80:
                        lvl = WARN
                        why.append(f"移动了 {d:.0f} 单位（偏大，确认不是拖错）")
                    if abs(px) > 128 or abs(pz) > 128:
                        lvl = BAD if lvl == OK else lvl
                        why.append(f"跑出自己那一格：pos=({px:.1f}, {pz:.1f})，应在 ±128 内")
                    # 撞点（原本就同位置的「孪生点」不算，比如 100/122 都是 Gatefront）
                    ox0, oz0 = worlds[aid]
                    for oid, (ox, oz) in worlds.items():
                        if oid == aid:
                            continue
                        if abs(ox0 - ox) < 16 and abs(oz0 - oz) < 16:
                            continue
                        if abs(ox - w[0]) < 16 and abs(oz - w[1]) < 16:
                            lvl = BAD if lvl == OK else lvl
                            why.append(f"和 #{oid} 重合（<16 单位）")
                            break
        counts[lvl] += 1
        rows.append((lvl, aid, (a or {}).get("_name") or "", it.get("deleted"), why))

    print(f"校对文件：{cf}")
    print(f"bin     ：{bin_path}")
    print(f"改动    ：{len(rows)} 条  （危险 {counts[BAD]} / 注意 {counts[WARN]} / 正常 {counts[OK]}）\n")
    for lvl, aid, name, deleted, why in rows:
        mark = {"ok": "  ", "注意": "！", "危险": "×"}[lvl]
        act = "删除" if deleted else "移动"
        print(f"{mark} #{aid:<5} {act}  {name}")
        for w in why:
            print(f"      - {w}")
    if counts[BAD]:
        print("\n有危险项：这些不会自动采用，需要人工确认。")


if __name__ == "__main__":
    main()
