# -*- coding: utf-8 -*-
"""MapPatternSet / Pattern 的可写模型（Step 1：只读解析 + 规划 dry-run + 校验）。

**本模块没有任何写盘动作**：只从 ParamDir 读，产出 Plan / Issue。
真正的写入在 Step 2 的 pswriter 里做。

核心规则（2026-11-15 实测，两份 bin 101/101 验证）：

    patternId = ⌊setId / 1000⌋ * 1000 + 组内前缀和
    组内顺序 = set id 升序；组与组互不影响

    set 的身份（夜王 targetBoss / 地图类型 rareMap）不在 set 行里，
    而在它每条 LotResultMapPatternFlag 行上。

    set 级池子（eventModifier*、night*BossModifier* 的 _Count 字段）：按 2026-11-15 的决定
    **当「个数」用**（派生值，不手填）：
      - 事件池取值：按 pid 取「modifierSet==0 且 eventFlag 不是地图类型(7600..7605)」那一行的 modifier
      - 夜间池：按 pid 取 playarea 的 bossModifier1 / bossModifier2
      - 加/删 pattern 后由模型自动重算；官方数据自己也有 28 处对不上（DLC 组写成 1/1），
        所以我们自己的 set 永远自洽，官方 set 只做 info 提示。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

T_SET = 'MapPatternSet'
T_FLAG = 'LotResultMapPatternFlag'
T_AREA = 'LotResultPlayAreaParam'
T_SPOT = 'LotResultSmallBaseAndSpot'
T_BASE = 'LotBaseMapPatternFlag'
T_ATTACH = 'SmallBaseAndSpotAttachPoint'
T_VAR = 'SmallBaseMapVariationParam'
T_BOSS = 'NightBossMenuParam'

GROUP_SIZE = 1000
MAPTYPE_FLAGS = {7600, 7601, 7602, 7603, 7604, 7605}   # 地图类型行（7600 + rareMap）
MAPTYPE_FLAG_BASE = 7600
MAPTYPE_MOD_BASE = 10                                  # 地图类型行的 modifier = 10 + rareMap
RAREMAP_NAMES = {0: '普通', 1: '山顶', 2: '火山', 3: '腐败森林', 4: 'Great Hollow', 5: '隐城'}


def maptype_flag(rare: int) -> int:
    """rareMap → 地图类型旗标（实测：0..5 → 7600..7605）。"""
    return MAPTYPE_FLAG_BASE + int(rare)


def maptype_mod(rare: int) -> int:
    """rareMap → 地图类型行的 modifier（实测：0..5 → 10..15）。"""
    return MAPTYPE_MOD_BASE + int(rare)


# 池子里被忽略的"脏数据"白名单（docs/eventFlag规律.md 里的结论）
FLAG_WHITELIST = {7535, 1046400230, 1038400230}


def _i(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 数据对象

@dataclass
class Pattern:
    """一个种子（patternId）及其三张表的行。"""
    pid: int
    flags: list[dict] = field(default_factory=list)
    playarea: dict | None = None
    spots: list[dict] = field(default_factory=list)

    # ---- 身份 ----
    @property
    def boss_id(self) -> int | None:
        for r in self.flags:
            if r.get('targetBoss') is not None:
                return _i(r['targetBoss'])
        return None

    @property
    def rare_map(self) -> int | None:
        for r in self.flags:
            if r.get('rareMap') is not None:
                return _i(r['rareMap'])
        return None

    @property
    def combo(self) -> tuple[int, int] | None:
        if self.flags and self.boss_id is not None and self.rare_map is not None:
            return (self.boss_id, self.rare_map)
        return None

    @property
    def event_modifier(self) -> int | None:
        """这个 pid 在地图类型行之外的那条 modifierSet=0 行里填的 modifier。"""
        cand = [r for r in self.flags
                if _i(r.get('modifierSet')) == 0 and _i(r.get('eventFlag')) not in MAPTYPE_FLAGS]
        return _i(cand[-1].get('modifier')) if cand else None

    @property
    def boss_modifier(self) -> tuple[int | None, int | None]:
        pa = self.playarea or {}
        return (_i(pa.get('bossModifier1')) if pa else None,
                _i(pa.get('bossModifier2')) if pa else None)

    @property
    def spot_count(self) -> int:
        return len(self.spots)


@dataclass
class PatternSet:
    """一个 MapPatternSet 行 + 它名下的 pattern。"""
    sid: int
    name: str
    row: dict = field(default_factory=dict)
    patterns: list[Pattern] = field(default_factory=list)

    @property
    def group(self) -> int:
        return self.sid // GROUP_SIZE

    @property
    def count(self) -> int:
        return len(self.patterns)

    @property
    def declared_count(self) -> int:
        return _i(self.row.get('patternCount'))

    @property
    def combo(self) -> tuple[int, int] | None:
        for p in self.patterns:
            c = p.combo
            if c:
                return c
        return None

    @property
    def boss_id(self) -> int | None:
        c = self.combo
        return c[0] if c else None

    @property
    def rare_map(self) -> int | None:
        c = self.combo
        return c[1] if c else None


# ---------------------------------------------------------------- 规划对象

@dataclass
class Plan:
    """一次结构/字段改动的预演结果。dry-run 只产出它，不落盘。"""
    op: str
    title: str
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    set_edits: list[dict] = field(default_factory=list)      # {sid, field, old, new}
    count_edits: list[dict] = field(default_factory=list)    # {sid, old, new}
    new_sets: list[dict] = field(default_factory=list)       # {sid, name, combo, copy_from}
    removed_sets: list[int] = field(default_factory=list)
    new_pids: list[dict] = field(default_factory=list)       # {pid, set, source_pid, flags, spots}
    removed_pids: list[int] = field(default_factory=list)
    moves: list[dict] = field(default_factory=list)          # {set, old_pid, new_pid}

    flag_row_edits: list[dict] = field(default_factory=list)  # {pid, row_id, field, old, new}
    area_edits: list[dict] = field(default_factory=list)
    spot_edits: list[dict] = field(default_factory=list)

    # 地点行级操作（Step 3：载入 pattern 改地点）
    spot_adds: list[dict] = field(default_factory=list)       # {pid, source_row, attachId, tile, variationId, mapIndex}
    spot_removes: list[int] = field(default_factory=list)     # 行 id
    spot_field_edits: list[dict] = field(default_factory=list)  # {row_id, field, old, new}
    area_field_edits: list[dict] = field(default_factory=list)  # {pid, field, old, new}

    # 影响面统计（给报表用）
    added_rows: dict[str, int] = field(default_factory=dict)
    touched_rows: dict[str, int] = field(default_factory=dict)

    def fail(self, msg: str) -> 'Plan':
        self.ok = False
        self.errors.append(msg)
        return self

    def summary(self) -> list[str]:
        out = [f'[{self.op}] {self.title}  → {"可以执行" if self.ok else "不能执行"}']
        for e in self.errors:
            out.append(f'   ✗ {e}')
        for w in self.warnings:
            out.append(f'   ! {w}')
        for n in self.notes:
            out.append(f'   · {n}')
        for c in self.count_edits:
            out.append(f"   patternCount: set {c['sid']}  {c['old']} → {c['new']}")
        for s in self.new_sets:
            out.append(f"   新建 set {s['sid']}（{s['name']}）照着 {s['copy_from']} 抄")
        if self.new_pids:
            for p in self.new_pids:
                out.append(f"   新增 pid {p['pid']}（set {p['set']}，抄自 pid {p['source_pid']}："
                           f"{p['flags']} 条 flag + 1 条 playarea + {p['spots']} 个地点）")
        if self.removed_pids:
            out.append(f"   删除 pid {sorted(self.removed_pids)}")
        if self.removed_sets:
            out.append(f"   删除 set {sorted(self.removed_sets)}")
        if self.moves:
            head = ', '.join(f"{m['old_pid']}→{m['new_pid']}" for m in self.moves[:8])
            more = ' …' if len(self.moves) > 8 else ''
            out.append(f"   pid 平移 {len(self.moves)} 个：{head}{more}")
        if self.set_edits:
            head = ', '.join(f"{e['field']}: {e['old']}→{e['new']}" for e in self.set_edits[:8])
            more = ' …' if len(self.set_edits) > 8 else ''
            out.append(f"   set 行改 {len(self.set_edits)} 个字段：{head}{more}")
        if self.flag_row_edits:
            out.append(f"   flag 行改 {len(self.flag_row_edits)} 个字段")
        for k, v in self.added_rows.items():
            out.append(f'   新增行 {k}: {v}')
        if self.spot_adds:
            out.append(f"   加地点：{len(self.spot_adds)} 个")
        if self.spot_removes:
            out.append(f"   删地点：{len(self.spot_removes)} 个")
        if self.spot_field_edits:
            out.append(f"   改地点字段：{len(self.spot_field_edits)} 处")
        if self.area_field_edits:
            out.append(f"   改缩圈/夜王字段：{len(self.area_field_edits)} 处")
        for k, v in self.touched_rows.items():
            out.append(f'   改 patternId 行 {k}: {v}')
        return out


@dataclass
class Issue:
    level: str          # error / warn / ok
    msg: str
    table: str = ''
    sid: int | None = None
    pid: int | None = None


# ---------------------------------------------------------------- 模型

class PatternModel:
    """一个 param 目录里的 set / pattern 全量模型（只读）。"""

    def __init__(self, params):
        self.p = params
        self.sets: dict[int, PatternSet] = {}
        self.patterns: dict[int, Pattern] = {}
        self.base_combos = self._load_base_combos()
        self.boss_names = self._load_boss_names()
        self._load()

    # ---- 载入 ----
    def _load(self):
        set_rows = self.p.rows(T_SET)
        flag_rows = self.p.rows(T_FLAG)
        area_rows = self.p.rows(T_AREA)
        spot_rows = self.p.rows(T_SPOT)

        for sid, row in set_rows.items():
            self.sets[sid] = PatternSet(sid=sid, name=(row.get('_name') or '').strip(), row=dict(row))

        by_pid: dict[int, Pattern] = {}
        for r in flag_rows.values():
            pid = _i(r.get('patternId'))
            pt = by_pid.get(pid)
            if pt is None:
                pt = by_pid[pid] = Pattern(pid=pid)
            pt.flags.append(dict(r))
        for r in area_rows.values():
            pid = _i(r.get('patternId'))
            pt = by_pid.get(pid)
            if pt is None:
                pt = by_pid[pid] = Pattern(pid=pid)
            pt.playarea = dict(r)
        for r in spot_rows.values():
            pid = _i(r.get('patternId'))
            pt = by_pid.get(pid)
            if pt is None:
                pt = by_pid[pid] = Pattern(pid=pid)
            pt.spots.append(dict(r))

        for pid, pt in by_pid.items():
            pt.flags.sort(key=lambda r: _i(r.get('_id')))
            pt.spots.sort(key=lambda r: _i(r.get('_id')))
            self.patterns[pid] = pt
            sid = None
            if pt.flags:
                sid = _i(pt.flags[0].get('patternSetId'), -1)
            if sid is not None and sid in self.sets:
                self.sets[sid].patterns.append(pt)

        for st in self.sets.values():
            st.patterns.sort(key=lambda p: p.pid)

    def _load_base_combos(self) -> set[tuple[int, int, int]]:
        out = set()
        if not self.p.has(T_BASE):
            return out
        for r in self.p.rows(T_BASE).values():
            out.add((_i(r.get('eventFlag')), _i(r.get('modifier')), _i(r.get('modifierSet'))))
        return out

    def _load_boss_names(self) -> dict[int, str]:
        out = {}
        if self.p.has(T_BOSS):
            for rid, r in self.p.rows(T_BOSS).items():
                nm = (r.get('_name') or '').strip()
                if nm:
                    out[rid] = nm
        return out

    # ---- 分组与编号 ----
    def groups(self) -> dict[int, list[PatternSet]]:
        out: dict[int, list[PatternSet]] = {}
        for st in self.sets.values():
            out.setdefault(st.group, []).append(st)
        for v in out.values():
            v.sort(key=lambda s: s.sid)
        return out

    def group_of(self, sid: int) -> int:
        return sid // GROUP_SIZE

    def expected_pid(self, sid: int, index: int) -> int:
        """这个 set 的第 index 个 pattern 按规则应该拿到的 pid。"""
        grp = self.group_of(sid)
        base = grp * GROUP_SIZE
        off = 0
        for st in sorted(self.sets.values(), key=lambda s: s.sid):
            if self.group_of(st.sid) != grp:
                continue
            if st.sid == sid:
                return base + off + index
            off += st.count
        return base + off + index

    def pid_range(self, sid: int) -> tuple[int, int] | None:
        st = self.sets.get(sid)
        if not st or not st.patterns:
            return None
        return (self.expected_pid(sid, 0), self.expected_pid(sid, st.count - 1))

    def assignment_errors(self) -> list[dict]:
        """实测 pid 与「分组前缀和」规则是否一致。"""
        bad = []
        for st in self.sets.values():
            for i, p in enumerate(st.patterns):
                want = self.expected_pid(st.sid, i)
                if p.pid != want:
                    bad.append({'set': st.sid, 'expected': want, 'actual': p.pid, 'index': i})
        return bad

    # ---- 查询辅助 ----
    def set(self, sid: int) -> PatternSet | None:
        return self.sets.get(sid)

    def pattern(self, pid: int) -> Pattern | None:
        return self.patterns.get(pid)

    def boss_name(self, bid) -> str:
        if bid is None:
            return '—'
        return self.boss_names.get(bid) or f'Boss {bid}'

    def combo_text(self, combo) -> str:
        if not combo:
            return '—'
        return f'{self.boss_name(combo[0])} · {RAREMAP_NAMES.get(combo[1], combo[1])}'

    def find_official_set(self, boss: int, rare: int) -> int | None:
        """找官方里 (夜王, 地图类型) 对得上的 set；优先非自建、非 DLC 块。"""
        cands = []
        for st in self.sets.values():
            if st.combo != (boss, rare):
                continue
            cands.append(st)
        if not cands:
            return None
        cands.sort(key=lambda s: (s.name.startswith('[Custom]'), s.group, s.sid))
        return cands[0].sid

    # ---- 池子 ----
    def pool_of(self, sid: int) -> dict:
        st = self.sets.get(sid)
        if not st:
            return {}
        ev = Counter(p.event_modifier for p in st.patterns if p.event_modifier is not None)
        b1 = Counter(p.boss_modifier[0] for p in st.patterns if p.boss_modifier[0] is not None)
        b2 = Counter(p.boss_modifier[1] for p in st.patterns if p.boss_modifier[1] is not None)
        return {'event': dict(ev), 'night1': dict(b1), 'night2': dict(b2)}

    def declared_pool(self, sid: int) -> dict:
        st = self.sets.get(sid)
        if not st:
            return {}
        row = st.row
        ev = {}
        for i in range(1, 9):
            c = _i(row.get(f'eventModifier{i}_Count'))
            if c:
                ev[_i(row.get(f'eventModifier{i}'))] = c
        n1 = {}
        for i in range(1, 17):
            c = _i(row.get(f'night1BossModifier{i}_Count'))
            if c:
                n1[_i(row.get(f'night1BossModifier{i}'))] = c
        n2 = {}
        for i in range(1, 17):
            c = _i(row.get(f'night2BossModifier{i}_Count'))
            if c:
                n2[_i(row.get(f'night2BossModifier{i}'))] = c
        return {'event': ev, 'night1': n1, 'night2': n2}

    def pool_mismatch(self, sid: int) -> bool:
        return self.pool_of(sid) != self.declared_pool(sid)

    # ---- 校验 ----
    def validate(self) -> list[Issue]:
        out: list[Issue] = []
        attach = self.p.rows(T_ATTACH) if self.p.has(T_ATTACH) else {}
        var = self.p.rows(T_VAR) if self.p.has(T_VAR) else {}

        # 1) patternCount == 实际
        for st in self.sets.values():
            if st.declared_count != st.count:
                out.append(Issue('error', f'set {st.sid} 声明 patternCount={st.declared_count}，'
                                         f'实际 {st.count} 个 pattern', T_SET, st.sid))

        # 2) 组内 pid 连续 + 不重复
        seen = set()
        for grp, sets in self.groups().items():
            pids = []
            for st in sets:
                pids += [p.pid for p in st.patterns]
            if len(set(pids)) != len(pids):
                dup = [x for x, n in Counter(pids).items() if n > 1]
                out.append(Issue('error', f'{grp} 组有重复 pid：{sorted(dup)[:10]}', T_FLAG))
            if pids:
                want = set(range(pids[0], pids[0] + len(pids)))
                miss = sorted(want - set(pids))
                extra = sorted(set(pids) - want)
                if miss:
                    out.append(Issue('error', f'{grp} 组 pid 断档：{miss[:10]}', T_FLAG))
                if extra:
                    out.append(Issue('error', f'{grp} 组 pid 越界：{extra[:10]}', T_FLAG))

        # 3) 每个 pid 至少 1 条 flag、恰好 1 条 playarea
        for p in self.patterns.values():
            if not p.flags:
                out.append(Issue('error', f'pid {p.pid} 没有 flag 行', T_FLAG, None, p.pid))
            if p.playarea is None:
                out.append(Issue('error', f'pid {p.pid} 没有 playarea 行', T_AREA, None, p.pid))

        # 4) 同一 set 内 targetBoss / rareMap 一致
        for st in self.sets.values():
            combos = {p.combo for p in st.patterns if p.combo}
            if len(combos) > 1:
                out.append(Issue('error', f'set {st.sid} 内 pattern 的组合不一致：{sorted(map(str, combos))}',
                                 T_FLAG, st.sid))

        # 5) flag 三元组必须在 base 表里（只 warn 一次，官方自己也有 10 来条跨族借用）
        if self.base_combos:
            for p in self.patterns.values():
                for r in p.flags:
                    key = (_i(r.get('eventFlag')), _i(r.get('modifier')), _i(r.get('modifierSet')))
                    if key[0] == 0 and key[1] == 0:
                        continue
                    if key in self.base_combos or key[0] in FLAG_WHITELIST:
                        continue
                    out.append(Issue('info', f'pid {p.pid} 三元组 {key} 不在 LotBaseMapPatternFlag 里',
                                     T_FLAG, None, p.pid))

        # 6) spots 引用存在
        #   2xxx 是官方"空壳 tile"（只有 define、没有变体行），官方大量在用 → 不报
        for p in self.patterns.values():
            for r in p.spots:
                aid = _i(r.get('attachId'))
                if attach and aid and aid not in attach:
                    out.append(Issue('error', f'pid {p.pid} 的 attachId {aid} 不存在', T_SPOT, None, p.pid))

        # 7) mapIndex：官方并不按文件顺序编号（会先 1 后 0），所以只查「同一 pid 同一 tile 内重复」
        for p in self.patterns.values():
            seen: dict[int, set] = {}
            for r in p.spots:
                t = _i(r.get('smallBaseMapId'))
                idx = _i(r.get('mapIndex'))
                s = seen.setdefault(t, set())
                if idx in s:
                    out.append(Issue('error', f'pid {p.pid} tile {t} 的 mapIndex {idx} 重复', T_SPOT, None, p.pid))
                    break
                s.add(idx)

        # 8) variationId：只在这个 tile 真有变体档位时才查
        #    （4xxx 里有一批 tile 有行但全 0，官方照样填 variationId；2xxx 干脆没有行）
        for p in self.patterns.values():
            for r in p.spots:
                vid = _i(r.get('variationId'))
                if not vid:
                    continue
                tile = _i(r.get('smallBaseMapId'))
                row = var.get(tile) or {}
                if not any(row.get(f'variationValue_{i}') for i in range(1, 11)):
                    continue
                if not row.get(f'variationValue_{vid + 1}'):
                    out.append(Issue('warn', f'pid {p.pid} tile {tile} 的 variationId={vid} 没有这一档',
                                     T_SPOT, None, p.pid))

        # 9) 池子字段 vs 实际 pattern：**官方自己就有 28 处对不上**，所以只作提示
        for st in self.sets.values():
            if st.patterns and self.pool_mismatch(st.sid):
                out.append(Issue('info', f'set {st.sid} 的池子字段与实际 pattern 对不上'
                                         f'（官方也有这种情况；可一键重算）', T_SET, st.sid))

        if not out:
            out.append(Issue('ok', '全部检查通过'))
        return out

    # ---------------------------------------------------------------- 规划

    def _shift_map(self, grp: int, from_pid: int, delta: int, skip: set[int] | None = None) -> list[dict]:
        """同组里 pid >= from_pid 的 pattern 平移 delta。"""
        skip = skip or set()
        out = []
        for p in sorted(self.patterns.values(), key=lambda x: x.pid):
            if p.pid in skip:
                continue
            if self._group_of_pid(p.pid) != grp:
                continue
            if p.pid >= from_pid:
                out.append({'old_pid': p.pid, 'new_pid': p.pid + delta})
        return out

    def _group_of_pid(self, pid: int) -> int:
        # pid 的组 = 它所属 set 的组（用 flag 行的 patternSetId 反查）
        p = self.patterns.get(pid)
        if p and p.flags:
            return _i(p.flags[0].get('patternSetId')) // GROUP_SIZE
        return pid // GROUP_SIZE

    def _row_counts_for_moves(self, moves: list[dict]) -> dict[str, int]:
        old = {m['old_pid'] for m in moves}
        c = {T_FLAG: 0, T_AREA: 0, T_SPOT: 0}
        for pid in old:
            p = self.patterns.get(pid)
            if not p:
                continue
            c[T_FLAG] += len(p.flags)
            c[T_AREA] += 1 if p.playarea else 0
            c[T_SPOT] += len(p.spots)
        return c

    def plan_create_set(self, boss: int, rare: int, name: str | None = None,
                        fields: dict | None = None, copy_pools: bool = False) -> Plan:
        sid = max(self.sets) + 1 if self.sets else 0
        src = self.find_official_set(boss, rare)
        plan = Plan(op='create_set', title=f'新建 set：{self.combo_text((boss, rare))}')
        if src is None:
            return plan.fail(f'官方没有 (夜王 {boss}, 地图类型 {rare}) 这个组合的 set，没法照抄')
        src_set = self.sets.get(src)
        row = {k: v for k, v in src_set.row.items() if not k.startswith('_')}
        row['patternCount'] = 0
        # 池子（modifier 字段）：默认清 0（空 set 就是 0 个）；
        # 需要「照抄官方」池子时传 copy_pools=True —— 整段池子连同计数一起抄过来
        if not copy_pools:
            for i in range(1, 9):
                row[f'eventModifier{i}'] = 0
                row[f'eventModifier{i}_Count'] = 0
            for grp in ('night1BossModifier', 'night2BossModifier'):
                for i in range(1, 17):
                    row[f'{grp}{i}'] = 0
                    row[f'{grp}{i}_Count'] = 0
        if fields:
            row.update(fields)
        nm = name or f'{src_set.name} (Custom)'
        plan.new_sets.append({'sid': sid, 'name': nm, 'combo': (boss, rare),
                              'copy_from': src, 'row': row})
        plan.notes.append(f'set id = {sid}（表尾），落 {sid // GROUP_SIZE} 组')
        first_pid = self.expected_pid(sid, 0)
        plan.notes.append(f'它第一个 pattern 的 pid 会是 {first_pid}')
        pool_txt = '池子照抄官方' if copy_pools else '池子清 0（空 set）'
        plan.notes.append(f'其余字段照抄 set {src}（{src_set.name}），patternCount=0，{pool_txt}')
        return plan

    def plan_insert_pattern(self, sid: int, source_pid: int | None = None,
                            at: int | None = None, combo: tuple[int, int] | None = None,
                            night: tuple[int, int] | None = None,
                            recompute_pools: bool = True) -> Plan:
        st = self.sets.get(sid)
        plan = Plan(op='insert_pattern', title=f'在 set {sid} 插入一个 pattern')
        if not st:
            return plan.fail(f'set {sid} 不存在')
        src_pid = source_pid if source_pid is not None else (st.patterns[0].pid if st.patterns else None)
        if src_pid is None:
            return plan.fail('这个 set 里没有可照抄的 pattern，请指定源 pid')
        src = self.patterns.get(src_pid)
        if not src:
            return plan.fail(f'源 pid {src_pid} 不存在')
        if src.playarea is None:
            return plan.fail(f'源 pid {src_pid} 没有 playarea 行')

        idx = st.count if at is None else max(0, min(at, st.count))
        grp = st.group
        base = grp * GROUP_SIZE
        off = 0
        for s2 in sorted(self.sets.values(), key=lambda s: s.sid):
            if s2.group != grp:
                continue
            if s2.sid == sid:
                break
            off += s2.count
        new_pid = base + off + idx

        # 组合：默认沿用这个 set 的身份；set 是空的就用传进来的
        target_combo = combo or st.combo or src.combo
        if target_combo is None:
            return plan.fail('这个 set 没有身份（空 set），请指定 combo=(夜王, 地图类型)')
        if src.combo and src.combo != target_combo:
            plan.warnings.append(f'源 pid {src_pid} 的组合是 {self.combo_text(src.combo)}，'
                                 f'插入后会改写成 {self.combo_text(target_combo)}')

        # 归一化参照：新 set 用官方同组合 set 的第一个 pattern；已有 pattern 的 set 用它自己的第一个
        ref = None
        if st.patterns:
            ref = st.patterns[0]
        else:
            off_sid = self.find_official_set(*target_combo)
            if off_sid is not None and self.sets[off_sid].patterns:
                ref = self.sets[off_sid].patterns[0]

        ev_v = src.event_modifier
        n1_v, n2_v = (ref.boss_modifier if ref else src.boss_modifier)
        if night is not None:           # 验证用：强制指定夜晚 BOSS 修饰（做识别标记）
            n1_v, n2_v = night
            plan.notes.append(f'夜晚 BOSS 被强制指定为 {n1_v} / {n2_v}（验证标记）')

        moves = self._shift_map(grp, new_pid, +1)
        plan.moves = moves
        plan.new_pids.append({
            'pid': new_pid, 'set': sid, 'source_pid': src_pid,
            'combo': target_combo,
            'maptype_flag': maptype_flag(target_combo[1]),
            'maptype_mod': maptype_mod(target_combo[1]),
            'night': (n1_v, n2_v),
            'ref_pid': ref.pid if ref else None,
            'flags': len(src.flags), 'spots': src.spot_count,
        })
        plan.count_edits.append({'sid': sid, 'old': st.declared_count, 'new': st.declared_count + 1})
        plan.added_rows = {T_FLAG: len(src.flags), T_AREA: 1, T_SPOT: len(src.spots)}
        plan.touched_rows = self._row_counts_for_moves(moves)

        # 池子（个数）跟着 +1（验证/照抄场景可以关掉）
        if recompute_pools:
            pools = self.pool_of(sid)
            ev, n1, n2 = dict(pools['event']), dict(pools['night1']), dict(pools['night2'])
            if ev_v is not None:
                ev[ev_v] = ev.get(ev_v, 0) + 1
            if n1_v is not None:
                n1[n1_v] = n1.get(n1_v, 0) + 1
            if n2_v is not None:
                n2[n2_v] = n2.get(n2_v, 0) + 1
            plan.set_edits.extend(self._pool_field_edits(sid, ev, n1, n2))
        else:
            plan.notes.append('池子字段保持原样（照抄），不随本次插入重算')

        plan.notes.append(f'插在第 {idx + 1} 个（set 内顺序），新 pid = {new_pid}')
        plan.notes.append(f'同组平移 {len(moves)} 个 pid（{grp} 组），其它组不受影响')
        plan.notes.append(f'克隆内容：{len(src.flags)} 条 flag + 1 条 playarea + {src.spot_count} 个地点；'
                          f'flag 的 targetBoss/rareMap/地图类型旗标会改成 {self.combo_text(target_combo)}'
                          + (f'，夜间 BOSS 参照 pid {ref.pid}' if ref else ''))
        return plan

    def plan_delete_pattern(self, pid: int) -> Plan:
        p = self.patterns.get(pid)
        plan = Plan(op='delete_pattern', title=f'删除 pid {pid}')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        sid = _i(p.flags[0].get('patternSetId'), -1) if p.flags else -1
        st = self.sets.get(sid)
        if not st:
            return plan.fail(f'pid {pid} 找不到所属 set')
        if st.count <= 1:
            plan.warnings.append('这是这个 set 里唯一的 pattern，删完它就是一个空 set（合法，官方也有）')
        grp = st.group
        moves = self._shift_map(grp, pid + 1, -1, skip={pid})
        plan.moves = moves
        plan.removed_pids.append(pid)
        plan.count_edits.append({'sid': sid, 'old': st.declared_count, 'new': st.declared_count - 1})
        plan.added_rows = {}
        plan.touched_rows = self._row_counts_for_moves(moves)

        # 池子（个数）跟着 -1
        pools = self.pool_of(sid)
        ev, n1, n2 = dict(pools['event']), dict(pools['night1']), dict(pools['night2'])
        ev_v = p.event_modifier
        n1_v, n2_v = p.boss_modifier
        for d, v in ((ev, ev_v), (n1, n1_v), (n2, n2_v)):
            if v is not None:
                d[v] = max(0, d.get(v, 0) - 1)
        plan.set_edits.extend(self._pool_field_edits(sid, ev, n1, n2))

        plan.notes.append(f'删除 {len(p.flags)} 条 flag + 1 条 playarea + {len(p.spots)} 个地点')
        plan.notes.append(f'同组平移 {len(moves)} 个 pid（{grp} 组）')
        return plan

    def plan_delete_set(self, sid: int) -> Plan:
        st = self.sets.get(sid)
        plan = Plan(op='delete_set', title=f'删除 set {sid}')
        if not st:
            return plan.fail(f'set {sid} 不存在')
        grp = st.group
        start = self.expected_pid(sid, 0) if st.patterns else None
        pids = [p.pid for p in st.patterns]
        plan.removed_sets.append(sid)
        plan.removed_pids.extend(pids)
        if start is not None:
            plan.moves = self._shift_map(grp, start + len(pids), -len(pids), skip=set(pids))
        plan.touched_rows = self._row_counts_for_moves(plan.moves)
        plan.added_rows = {}
        plan.notes.append(f'连带删除 {len(pids)} 个 pattern')
        return plan

    def plan_set_fields(self, sid: int, fields: dict) -> Plan:
        st = self.sets.get(sid)
        plan = Plan(op='set_fields', title=f'改 set {sid} 的字段')
        if not st:
            return plan.fail(f'set {sid} 不存在')
        for k, v in fields.items():
            old = st.row.get(k)
            if k == 'patternCount':
                plan.fail('patternCount 是派生值，不能直接改')
                continue
            if old == v:
                continue
            plan.set_edits.append({'sid': sid, 'field': k, 'old': old, 'new': v})
        if plan.ok and not plan.set_edits:
            plan.notes.append('没有实际变化')
        return plan

    def plan_change_combo(self, sid: int, boss: int, rare: int, recopy_pools: bool = False) -> Plan:
        st = self.sets.get(sid)
        plan = Plan(op='change_combo', title=f'改 set {sid} 的组合 → {self.combo_text((boss, rare))}')
        if not st:
            return plan.fail(f'set {sid} 不存在')
        src = self.find_official_set(boss, rare)
        if src is None:
            plan.warnings.append('官方没有这个组合的 set 可抄，池子不会改')
        changed = 0
        for p in st.patterns:
            for r in p.flags:
                if _i(r.get('targetBoss')) != boss:
                    plan.flag_row_edits.append({'pid': p.pid, 'row_id': _i(r.get('_id')),
                                                'field': 'targetBoss',
                                                'old': _i(r.get('targetBoss')), 'new': boss})
                    changed += 1
                if _i(r.get('rareMap')) != rare:
                    plan.flag_row_edits.append({'pid': p.pid, 'row_id': _i(r.get('_id')),
                                                'field': 'rareMap',
                                                'old': _i(r.get('rareMap')), 'new': rare})
                    changed += 1
                # 地图类型行（modifierSet=0 且 eventFlag=76xx）要一起换：旗标 7600+rare、modifier 10+rare
                if (_i(r.get('modifierSet')) == 0 and _i(r.get('eventFlag')) in MAPTYPE_FLAGS):
                    if _i(r.get('eventFlag')) != maptype_flag(rare):
                        plan.flag_row_edits.append({'pid': p.pid, 'row_id': _i(r.get('_id')),
                                                    'field': 'eventFlag',
                                                    'old': _i(r.get('eventFlag')),
                                                    'new': maptype_flag(rare)})
                        changed += 1
                    if _i(r.get('modifier')) != maptype_mod(rare):
                        plan.flag_row_edits.append({'pid': p.pid, 'row_id': _i(r.get('_id')),
                                                    'field': 'modifier',
                                                    'old': _i(r.get('modifier')),
                                                    'new': maptype_mod(rare)})
                        changed += 1
        if not st.patterns:
            plan.notes.append('空 set：没有 flag 行要改，只改工具侧记录 + 名字')
        if recopy_pools and src is not None:
            src_set = self.sets[src]
            for i in range(1, 9):
                plan.set_edits.append({'sid': sid, 'field': f'eventModifier{i}',
                                       'old': st.row.get(f'eventModifier{i}'),
                                       'new': src_set.row.get(f'eventModifier{i}')})
                plan.set_edits.append({'sid': sid, 'field': f'eventModifier{i}_Count',
                                       'old': st.row.get(f'eventModifier{i}_Count'),
                                       'new': src_set.row.get(f'eventModifier{i}_Count')})
            for grp in ('night1BossModifier', 'night2BossModifier'):
                for i in range(1, 17):
                    plan.set_edits.append({'sid': sid, 'field': f'{grp}{i}',
                                           'old': st.row.get(f'{grp}{i}'),
                                           'new': src_set.row.get(f'{grp}{i}')})
                    plan.set_edits.append({'sid': sid, 'field': f'{grp}{i}_Count',
                                           'old': st.row.get(f'{grp}{i}_Count'),
                                           'new': src_set.row.get(f'{grp}{i}_Count')})
        plan.touched_rows = {T_FLAG: changed}
        plan.notes.append(f'要改 {changed} 个 flag 行字段')
        return plan

    def plan_recompute_pools(self, sid: int) -> Plan:
        st = self.sets.get(sid)
        plan = Plan(op='recompute_pools', title=f'按实际 pattern 重算 set {sid} 的池子')
        if not st:
            return plan.fail(f'set {sid} 不存在')
        actual = self.pool_of(sid)
        if not actual['event'] and not actual['night1']:
            plan.notes.append('空 set：池子会全部清 0')
        plan.set_edits.extend(self._pool_field_edits(sid, actual['event'], actual['night1'], actual['night2']))
        plan.notes.append(f'实际：事件 {actual["event"]} / 夜1 {actual["night1"]} / 夜2 {actual["night2"]}')
        return plan

    def _pool_field_edits(self, sid: int, ev: dict, n1: dict, n2: dict) -> list[dict]:
        """按计数更新池子：**值留在原槽位**，只改计数；新值优先塞空槽。

        之前按 merge 重新排槽，会把 210/180/601 这些值互相搬家，校对时看着像乱改。
        """
        st = self.sets.get(sid)
        if not st:
            return []
        row = st.row
        out: list[dict] = []
        for prefix, slots, counts in (('eventModifier', 8, ev),
                                      ('night1BossModifier', 16, n1),
                                      ('night2BossModifier', 16, n2)):
            vals = [_i(row.get(f'{prefix}{i}')) for i in range(1, slots + 1)]
            cnts = [_i(row.get(f'{prefix}{i}_Count')) for i in range(1, slots + 1)]
            val2slot: dict[int, int] = {}
            for i, v in enumerate(vals):
                if v:
                    val2slot.setdefault(v, i)
            new_vals, new_cnts = list(vals), list(cnts)
            # 1) 已有值：计数跟着走（不再出现的写 0，值保留）
            for v, slot in val2slot.items():
                new_cnts[slot] = counts.get(v, 0)
            # 2) 计数里出现的新值：先塞 value=0 的空槽，再塞计数为 0 的槽
            free = [i for i in range(slots) if not new_vals[i]]
            for v, c in counts.items():
                if v in val2slot:
                    continue
                if free:
                    s = free.pop(0)
                else:
                    cand = [i for i in range(slots) if new_cnts[i] == 0]
                    if not cand:
                        break          # 槽位满了，丢弃（8/16 个槽一般够用）
                    s = cand[0]
                new_vals[s], new_cnts[s] = v, c
            # 3) 输出差异
            for i in range(slots):
                self._pool_pair(out, sid, row, f'{prefix}{i + 1}', new_vals[i], new_cnts[i])
        return out

    @staticmethod
    def _pool_pair(out: list, sid: int, row: dict, base: str, val, cnt):
        o1, o2 = row.get(base), row.get(base + '_Count')
        if o1 != val:
            out.append({'sid': sid, 'field': base, 'old': o1, 'new': val})
        if o2 != cnt:
            out.append({'sid': sid, 'field': base + '_Count', 'old': o2, 'new': cnt})

    # ---------------- 地点 / 缩圈（Step 3：载入 pattern 改内容） ----------------

    def plan_spot_add(self, pid: int, attach_id: int, tile: int,
                      variation_id: int = 0) -> Plan:
        p = self.patterns.get(pid)
        plan = Plan(op='spot_add', title=f'给 pid {pid} 加一个地点')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        tile = int(tile)
        used = [_i(r.get('mapIndex')) for r in p.spots if _i(r.get('smallBaseMapId')) == tile]
        mi = (max(used) + 1) if used else 0
        src = int(p.spots[0]['_id']) if p.spots else None
        plan.spot_adds.append({'pid': pid, 'source_row': src, 'attachId': int(attach_id),
                               'tile': tile, 'variationId': int(variation_id or 0), 'mapIndex': mi})
        plan.notes.append(f'新地点的 mapIndex = {mi}（该 tile 已有 {len(used)} 个）')
        return plan

    def plan_spot_remove(self, pid: int, row_id: int) -> Plan:
        p = self.patterns.get(pid)
        plan = Plan(op='spot_remove', title=f'删掉 pid {pid} 的一个地点')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        row = next((r for r in p.spots if int(r['_id']) == int(row_id)), None)
        if not row:
            return plan.fail(f'pid {pid} 里没有这一行（row {row_id}）')
        if len(p.spots) <= 1:
            plan.warnings.append('这是这个种子最后一个地点，删完就是一个空种子（游戏里可能异常）')
        plan.spot_removes.append(int(row_id))
        plan.notes.append(f'删掉 tile {_i(row.get("smallBaseMapId"))} / attach {_i(row.get("attachId"))}')
        return plan

    def plan_spot_field(self, pid: int, row_id: int, field: str, value) -> Plan:
        p = self.patterns.get(pid)
        plan = Plan(op='spot_field', title=f'改 pid {pid} 地点行的 {field}')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        row = next((r for r in p.spots if int(r['_id']) == int(row_id)), None)
        if not row:
            return plan.fail(f'pid {pid} 里没有这一行（row {row_id}）')
        old = row.get(field)
        if old == value:
            plan.notes.append('没有实际变化')
            return plan
        plan.spot_field_edits.append({'row_id': int(row_id), 'field': field, 'old': old, 'new': value})
        return plan

    def plan_spot_tile(self, pid: int, row_id: int, tile: int,
                       variation_id: int | None = None) -> Plan:
        """把某个地点换成另一种建筑（改 smallBaseMapId）；mapIndex 按新 tile 重排。"""
        p = self.patterns.get(pid)
        plan = Plan(op='spot_tile', title=f'改 pid {pid} 地点的建筑')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        row = next((r for r in p.spots if int(r['_id']) == int(row_id)), None)
        if not row:
            return plan.fail(f'pid {pid} 里没有这一行（row {row_id}）')
        tile = int(tile)
        if tile <= 0:
            return plan.fail('tile 必须大于 0')
        old_tile = _i(row.get('smallBaseMapId'))
        vary = None if variation_id is None else int(variation_id)
        if old_tile == tile and (vary is None or _i(row.get('variationId')) == vary):
            plan.notes.append('没有实际变化')
            return plan

        if old_tile != tile:
            used = [_i(r.get('mapIndex')) for r in p.spots
                    if _i(r.get('smallBaseMapId')) == tile and int(r['_id']) != int(row_id)]
            mi = (max(used) + 1) if used else 0
            plan.spot_field_edits.append({'row_id': int(row_id), 'field': 'smallBaseMapId',
                                          'old': old_tile, 'new': tile})
            plan.spot_field_edits.append({'row_id': int(row_id), 'field': 'mapIndex',
                                          'old': _i(row.get('mapIndex')), 'new': mi})
            plan.spot_field_edits.append({'row_id': int(row_id), 'field': 'variationId',
                                          'old': _i(row.get('variationId')),
                                          'new': 0 if vary is None else vary})
            plan.notes.append(f'tile {old_tile} → {tile}，mapIndex 改成 {mi}')
        elif vary is not None:
            plan.spot_field_edits.append({'row_id': int(row_id), 'field': 'variationId',
                                          'old': _i(row.get('variationId')), 'new': vary})
            plan.notes.append(f'variationId → {vary}')
        return plan

    def plan_playarea(self, pid: int, fields: dict) -> Plan:
        """改这个种子的缩圈 / 夜晚 BOSS（直接给 playarea 行字段）。"""
        p = self.patterns.get(pid)
        plan = Plan(op='playarea', title=f'改 pid {pid} 的缩圈/夜王')
        if not p:
            return plan.fail(f'pid {pid} 不存在')
        if p.playarea is None:
            return plan.fail(f'pid {pid} 没有 playarea 行')
        for k, v in fields.items():
            old = p.playarea.get(k)
            if old == v:
                continue
            plan.area_field_edits.append({'pid': pid, 'field': k, 'old': old, 'new': v})
        if not plan.area_field_edits:
            plan.notes.append('没有实际变化')
        return plan

    @staticmethod
    def _merge_pool(order: list, counts: dict) -> list[tuple[int, int]]:
        """保留原有槽位顺序，再按首次出现补新值。"""
        out = []
        used = set()
        for v in order:
            if v in counts:
                out.append((v, counts[v]))
                used.add(v)
            else:
                out.append((v, 0))
        for v, c in counts.items():
            if v not in used:
                out.append((v, c))
        return out
