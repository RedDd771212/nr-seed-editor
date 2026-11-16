"""把校准工具导出的 corrections_<map>.json 固化进 src/data/maps.json。

- limveld：沿用原来的 attach_deleted.json / attach_overrides.json（不动）
- 其它地图：给 maps.json 的这张图写
    attachPool : [attachId, ...]        这张图上存在的建筑位（基准 47 个减去标删的）
    overrides  : {attachId: [x, z]}     这张图上手动挪过的坐标
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402

CALIB = ROOT / "calib"
MAPS = ROOT / "src" / "data" / "maps.json"
EXTRA = ("mountaintop", "crater", "rotted", "shroud")
BIN = r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin"

# 腐败森林专属的点（Limveld 的 47 个建筑位里没有）
ROTTED_EXTRA = [309, 315, 316, 317, 318, 319, 320, 321, 322,
                531, 532, 551, 552, 591, 592]


def main() -> None:
    bin_path = ROOT / "work" / "reg" / "base_sot.bin"
    if not bin_path.exists():
        bin_path = Path(BIN)
    p = Project(str(bin_path))
    base = {ap["attachId"]: ap["world"] for ap in p.attach_points()}

    data = json.loads(MAPS.read_text(encoding="utf-8"))
    maps = data.get("maps") or {}

    for mid in EXTRA:
        f = CALIB / f"corrections_{mid}.json"
        if not f.exists():
            print(f"{mid}: no export file, skip")
            continue
        base_mid = dict(base)
        if mid == "rotted":
            for aid in ROTTED_EXTRA:
                ap = p.model.attach.get(aid)
                if not ap:
                    continue
                gx, gz = ap.get("gridXNo"), ap.get("gridZNo")
                base_mid[aid] = [gx * 256 + 128 + (ap.get("posX") or 0),
                                 gz * 256 + 128 + (ap.get("posZ") or 0)]
        items = json.loads(f.read_text(encoding="utf-8")).get("items") or []
        gone = {int(i["id"]) for i in items if i.get("deleted")}
        over = {}
        for it in items:
            aid = int(it["id"])
            if it.get("deleted"):
                continue
            w = it.get("world")
            if w and aid in base_mid:
                b = base_mid[aid]
                if abs(w[0] - b[0]) > 0.5 or abs(w[1] - b[1]) > 0.5:
                    over[aid] = [round(float(w[0]), 3), round(float(w[1]), 3)]
        pool = sorted(a for a in base_mid if a not in gone)
        m = maps.setdefault(mid, {})
        m["attachPool"] = pool
        m["overrides"] = over
        print(f"{mid}: keep {len(pool)} / {len(base_mid)}, moved {len(over)}")

    MAPS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("written", MAPS)


if __name__ == "__main__":
    main()
