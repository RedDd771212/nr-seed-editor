# -*- coding: utf-8 -*-
"""黑夜君临「地图种子」信息层：把散落在 8 张 param 表里的东西拼成一个可查询的模型。

只读。不改任何文件。

链条（2026-11-09 实测得出 + 实测校准）：

    MapPatternSet(id)
        └─ patternCount（容量，严格前缀和）→ patternId 区间
              └─ LotResultMapPatternFlag(patternId)  一个 patternId 有多行 = 多套 eventFlag/modifier 变体
                    ├─ targetBoss / rareMap / patternSetId：归属（set 级唯一）
                    └─ eventFlag：事件（入侵时机、宝箱…）
              ├─ LotResultPlayAreaParam(patternId)   1:1，缩圈 + 夜晚 BOSS
              └─ LotResultSmallBaseAndSpot(patternId) 每行一个「地点」
                    ├─ smallBaseMapId → SmallBaseMapVariationParam[smallBaseMapId]（变体表）
                    │                 → SmallBaseAndSpotDefine 里 mapIdN 含它的行（遭遇/敌人预设 + 地图图标）
                    ├─ attachId       → SmallBaseAndSpotAttachPoint[attachId]（坐标：grid*256 + pos）
                    └─ mapIndex / variationId / modifier
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .paramdir import ParamDir

TILE_UNITS = 256.0  # attach point / world map point 的格宽（实测 4×4 格 ≈ 1024 世界单位）
TILE_CENTER = 128.0  # posX/posZ 以格中心为原点（m01075 实测：411/562 个点至少一项为负）

# define 行本身没填 worldMapPointIconId 时，按行名兜底到最接近的 pin 图标。
# ⚠ 小营地（Minor Base / Small Camp）本身没有 pin，绝不兜底成大营地图标（m00832）。
NAME_ICON_FALLBACK = [
    ("castle", 42010), ("large encampment", 42009), ("main encampment", 42009),
    ("ruins", 42002), ("evergaol", 42004),
    ("church", 42023), ("cathedral", 42023), ("sorcerer", 42005), ("tower", 42042),
    ("fort", 42006), ("township", 42003), ("tunnel", 42022), ("cave", 42026),
    ("field boss", 42015), ("encounter:", 42015), ("npc", 42020),
]

# attach 点名字前缀 → attach 大小（大/小），来自 SmallBaseAndSpotAttachPoint._name
ATTACH_SIZE_BY_PREFIX = {
    "major base": "大", "starter major base": "大", "castle": "大",
    "minor base": "小", "starter minor base": "小",
    "field boss": "小",
    "evergaol": "未知",
}

SEED_TABLES = [
    "MapPatternSet",
    "LotResultMapPatternFlag",
    "LotResultPlayAreaParam",
    "LotResultSmallBaseAndSpot",
    "SmallBaseAndSpotDefine",
    "SmallBaseAndSpotAttachPoint",
    "SmallBaseMapVariationParam",
    "NightBossMenuParam",
    "WorldMapPointIconParam",
]


class SeedModel:
    def __init__(self, paramdir: ParamDir):
        self.p = paramdir
        self.sets = paramdir.rows("MapPatternSet")
        self.pattern_rows = list(paramdir.rows("LotResultMapPatternFlag").values())
        self.playarea = {r["patternId"]: r for r in paramdir.rows("LotResultPlayAreaParam").values()}
        self.spots = list(paramdir.rows("LotResultSmallBaseAndSpot").values())
        self.attach = paramdir.rows("SmallBaseAndSpotAttachPoint")
        self.define = paramdir.rows("SmallBaseAndSpotDefine")
        self.variation = paramdir.rows("SmallBaseMapVariationParam")
        self.bosses = paramdir.rows("NightBossMenuParam")
        self.wm_icons = paramdir.rows("WorldMapPointIconParam")

        self.rows_by_set = defaultdict(list)
        self.rows_by_pid = defaultdict(list)
        for r in self.pattern_rows:
            self.rows_by_set[r["patternSetId"]].append(r)
            self.rows_by_pid[r["patternId"]].append(r)
        self.pids_by_set = {sid: sorted({r["patternId"] for r in rows}) for sid, rows in self.rows_by_set.items()}

        self.spots_by_pid = defaultdict(list)
        for r in self.spots:
            self.spots_by_pid[r["patternId"]].append(r)

        # smallBaseMapId -> define 行（mapIdN 里含它）
        self.define_of_tile = defaultdict(list)
        for did, d in self.define.items():
            for k in range(1, 19):
                v = d.get(f"mapId{k}", -1)
                if v and v > 0:
                    self.define_of_tile[v].append(did)

        self.ranges = self._build_ranges()

    # ---------------- 结构 ----------------
    def _build_ranges(self):
        """setId -> dict(start, end, declared, pids, block)。按 patternId 分段（0 段 / 1000 段）分块累加。"""
        out = {}
        # 按实际出现的最小 patternId 把 set 分块：块基址 = 该块第一个 set 的首个 pid
        ordered = sorted(self.sets)
        blocks = []
        cur = None
        for sid in ordered:
            n = self.sets[sid].get("patternCount", 0)
            pids = self.pids_by_set.get(sid, [])
            if cur is None or (pids and cur["next"] != pids[0]):
                cur = {"next": pids[0] if pids else 0, "sets": []}
                blocks.append(cur)
            cur["sets"].append((sid, n))
            cur["next"] += n
        for b in blocks:
            start = self.pids_by_set.get(b["sets"][0][0], [0])[0]
            for sid, n in b["sets"]:
                pids = self.pids_by_set.get(sid, [])
                out[sid] = {
                    "start": start,
                    "end": start + n - 1,
                    "declared": n,
                    "pids": pids,
                    "actual": len(pids),
                    "block": start // 1000,
                }
                start += n
        return out

    def set_of_pid(self, pid: int):
        for sid, r in self.ranges.items():
            if r["start"] <= pid <= r["end"]:
                return sid
        return None

    # ---------------- 查询 ----------------
    def describe_set(self, sid: int) -> dict:
        s = self.sets.get(sid, {})
        rng = self.ranges.get(sid, {})
        rows = self.rows_by_set.get(sid, [])
        boss = rows[0]["targetBoss"] if rows else None
        rare = rows[0]["rareMap"] if rows else None
        return {
            "set": sid,
            "patternCount": s.get("patternCount"),
            "weight": s.get("weight"),
            "chaosWeight": s.get("chaosMatchWeight"),
            "targetBoss": boss,
            "rareMap": rare,
            "range": (rng.get("start"), rng.get("end")),
            "actual": rng.get("actual"),
            "boss_name_id": self.bosses.get(boss, {}).get("bossNameId") if boss is not None else None,
            "boss_icon": self.bosses.get(boss, {}).get("bossIconId") if boss is not None else None,
        }

    def attach_size(self, attach_name: str) -> str | None:
        nm = (attach_name or "").strip().lower()
        if nm.startswith("["):                     # [Great Hollow] ... 先剥壳
            nm = nm.split("]", 1)[-1].strip()
        for pre, size in ATTACH_SIZE_BY_PREFIX.items():
            if nm.startswith(pre):
                return size
        return None

    def describe_spot(self, row: dict) -> dict:
        """把一行 LotResultSmallBaseAndSpot 补全成人能看懂的东西。"""
        ap = self.attach.get(row.get("attachId"), {})
        tile = row.get("smallBaseMapId")          # attach-only 行没有这一列
        parents = self.define_of_tile.get(tile, []) if tile is not None else []
        var = self.variation.get(tile, {})
        icon_id = None
        for did in parents:
            ic = self.define[did].get("worldMapPointIconId1")
            if ic:
                icon_id = self.wm_icons.get(ic, {}).get("iconId", ic)
                break
        if icon_id is None:
            # 2026-11-16：大空洞的堡垒 tile（Western/Eastern Underground Fort）define 里
            # icon1 全是 0，行名/组名也是空的 —— 得把 **变体名**（tile 名）也算进来才认得出 "fort"
            nm = " ".join(
                [row.get("_name", ""), (var.get("_name") or "")]
                + [self.define[d].get("_name", "") for d in parents]
            ).lower()
            for kw, iid in NAME_ICON_FALLBACK:
                if kw == "encounter:" and "setup" in nm:
                    continue          # "Encounter Setup: Ruins" 不是野外 BOSS
                if kw == "fort":
                    continue          # 2026-11-16：大空洞堡垒没有配图标，兜底出来的效果不好 → 不兜底
                if kw in nm:
                    icon_id = iid
                    break

        # 小营地 / 车队 / 夜之军团 / 夜王 本身没有 pin，绝不借用大营地图标（m00832）
        # 注意：这里只认「行名 + define 组名」，不认 tile 变体名 —— 否则夜王塔的
        # "Night Boss - xxx" 也会被误伤成无图标。
        nm_all = " ".join(
            [row.get("_name", "")] + [self.define[d].get("_name", "") for d in parents]
        ).lower()
        if any(k in nm_all for k in ("small camp", "caravans", "night horde", "night boss")):
            icon_id = None
        return {
            "row": row,
            "realName": (var.get("_name") if var else ""),
            # 属性变体（m04368）：variationId 是 0 基，0 = 第 1 号变体 → 槽位号 = variationId + 1；
            # 槽位存不存在看 variationValue_x ≠ 0，图标为 0 就是「无属性」。
            "attrIcon": (var.get("variationIconId_%d" % ((row.get("variationId") or 0) + 1))
                         if var and var.get("variationValue_%d" % ((row.get("variationId") or 0) + 1))
                         else None) or None,
            "name": row.get("_name", "") or (self.define[parents[0]].get("_name") if parents else ""),
            "tile": tile,
            "attachId": row.get("attachId"),
            "grid": (ap.get("gridXNo"), ap.get("gridZNo")),
            "pos": (ap.get("posX"), ap.get("posY"), ap.get("posZ")),
            "world": (
                None if "posX" not in ap
                else ap["gridXNo"] * TILE_UNITS + TILE_CENTER + ap["posX"],
                None if "posZ" not in ap
                else ap["gridZNo"] * TILE_UNITS + TILE_CENTER + ap["posZ"],
            ),
            "define": parents,
            "define_names": [self.define[d].get("_name", "") for d in parents],
            "icon": icon_id,
            "realName": (var.get("_name") if var else ""),
            # 属性变体（m04368）：variationId 是 0 基，0 = 第 1 号变体 → 槽位号 = variationId + 1；
            # 槽位存不存在看 variationValue_x ≠ 0，图标为 0 就是「无属性」。
            "attrIcon": (var.get("variationIconId_%d" % ((row.get("variationId") or 0) + 1))
                         if var and var.get("variationValue_%d" % ((row.get("variationId") or 0) + 1))
                         else None) or None,
            "attachName": ap.get("_name", ""),
            "attachSize": self.attach_size(ap.get("_name", "")),
            "variation": var,
            "mapIndex": row.get("mapIndex"),
            "variationId": row.get("variationId"),
        }

    def pattern_info(self, pid: int) -> dict:
        rows = self.rows_by_pid.get(pid, [])
        sid = rows[0]["patternSetId"] if rows else None
        info = {
            "patternId": pid,
            "set": self.describe_set(sid) if sid is not None else None,
            "variants": [
                {"eventFlag": r["eventFlag"], "modifier": r["modifier"], "modifierSet": r["modifierSet"],
                 "row": r["_id"]}
                for r in sorted(rows, key=lambda r: r["_id"])
            ],
            "playArea": self.playarea.get(pid),
            "spots": [self.describe_spot(r) for r in self.spots_by_pid.get(pid, [])],
        }
        return info

    # ---------------- 校验 ----------------
    def validate(self) -> list[dict]:
        issues = []

        # 1) 区间与 declared 对账
        for sid, rng in sorted(self.ranges.items()):
            want = rng["end"] - rng["start"] + 1
            got = rng["actual"]
            if got != rng["declared"]:
                issues.append({
                    "level": "error", "table": "MapPatternSet", "set": sid,
                    "msg": f"set {sid} 声明 patternCount={rng['declared']}，实际只有 {got} 个 patternId"
                           f"（区间 {rng['start']}..{rng['end']}）",
                })
            if got and rng["pids"] != list(range(rng["pids"][0], rng["pids"][0] + got)):
                issues.append({"level": "error", "table": "MapPatternSet", "set": sid,
                               "msg": f"set {sid} 的 patternId 不连续"})
            if want and got != want:
                missing = sorted(set(range(rng["start"], rng["end"] + 1)) - set(rng["pids"]))
                issues.append({"level": "error", "table": "LotResultMapPatternFlag", "set": sid,
                               "msg": f"区间内缺 patternId：{missing[:12]}{'…' if len(missing) > 12 else ''}"})

        # 2) 有 pattern 但没有缩圈
        for pid in self.rows_by_pid:
            if pid not in self.playarea:
                issues.append({"level": "error", "table": "LotResultPlayAreaParam", "patternId": pid,
                               "msg": f"patternId {pid} 有种子行，但 LotResultPlayAreaParam 没有对应行"})

        # 3) 悬空引用
        bad_attach = Counter()
        bad_var = Counter()
        no_define = Counter()
        for r in self.spots:
            if r["attachId"] not in self.attach:
                bad_attach[r["attachId"]] += 1
            if r["smallBaseMapId"] not in self.variation:
                bad_var[r["smallBaseMapId"]] += 1
            if not self.define_of_tile.get(r["smallBaseMapId"]):
                no_define[r["smallBaseMapId"]] += 1
        for k, v in sorted(bad_attach.items()):
            issues.append({"level": "error", "table": "SmallBaseAndSpotAttachPoint",
                           "msg": f"attachId {k} 在 spot 表被引用 {v} 次，但坐标表里没有"})
        for k, v in sorted(bad_var.items()):
            issues.append({"level": "warn", "table": "SmallBaseMapVariationParam",
                           "msg": f"smallBaseMapId {k} 没有变体行（被引用 {v} 次）"})
        for k, v in sorted(no_define.items()):
            issues.append({"level": "warn", "table": "SmallBaseAndSpotDefine",
                           "msg": f"smallBaseMapId {k} 找不到 define 行（被引用 {v} 次）"})

        # 4) 建筑类别 vs attach 大小（铁律：不对应会出大问题）
        issues += self.check_attach_size()
        return issues

    def check_attach_size(self) -> list[dict]:
        """把小营地/大营地、小据点/大据点跟 attach 点的 Major/Minor 对一遍。"""
        import json
        from pathlib import Path
        table_path = Path(__file__).resolve().parent.parent / "data" / "pin_icons.json"
        size_of_icon = {}
        if table_path.exists():
            icons = json.loads(table_path.read_text(encoding="utf-8"))["icons"]
            size_of_icon = {int(k): v.get("attachSize") for k, v in icons.items()}

        bad = Counter()
        for r in self.spots:
            ap = self.attach.get(r.get("attachId"), {})
            anm = (ap.get("_name") or "").lower()
            if not anm.startswith(("major base", "starter major base", "minor base", "starter minor base")):
                continue               # 只管大/小营地，屋顶/地下室 BOSS 等特例不参与
            got = self.attach_size(ap.get("_name", ""))
            info = self.describe_spot(r)
            want = size_of_icon.get(info["icon"]) if info["icon"] else None
            if not got or not want or want in ("待定", "未知"):
                continue
            if got != want:
                bad[(info["tile"], got, want, ap.get("_name", ""))] += 1
        out = []
        for (tile, got, want, nm), v in sorted(bad.items()):
            out.append({"level": "error", "table": "SmallBaseAndSpotAttachPoint",
                        "msg": f"tile {tile} 的建筑要「{want}」attach，却落在「{got}」点「{nm}」上（{v} 次）"})
        return out
