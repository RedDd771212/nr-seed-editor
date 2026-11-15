# -*- coding: utf-8 -*-
"""草稿：基于模板种子造一个新种子（新增 set + flag + playArea + spots）。"""
from __future__ import annotations

from dataclasses import dataclass, field

from .project import T_SET, T_FLAG, T_AREA, T_SPOT


@dataclass
class Draft:
    boss_id: int
    template_pid: int
    template_set: int
    new_set: int
    new_pid: int
    spots: list[dict] = field(default_factory=list)   # {attachId, tile, mapIndex, variationId}
    events: list[dict] = field(default_factory=list)  # flag 行（照抄模板，可换档）
    pa1: int | None = None      # 1缩 → PlayAreaCreateParam.id（None=跟着模板）
    pa2: int | None = None      # 2缩
    nb1: int | None = None      # 1夜 → SmallBaseMapVariationParam 里的 Night Boss
    nb2: int | None = None      # 2夜
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            'bossId': self.boss_id,
            'templatePid': self.template_pid,
            'templateSet': self.template_set,
            'newSet': self.new_set,
            'newPid': self.new_pid,
            'spots': self.spots,
            'events': self.events,
            'pa1': self.pa1, 'pa2': self.pa2, 'nb1': self.nb1, 'nb2': self.nb2,
            'warnings': self.warnings,
        }

    def spot_rows(self) -> list:
        """生成 LotResultSmallBaseAndSpot 的行。

        m06209：同一个 smallBaseMapId 在一个种子里出现多次时，mapIndex 必须
        从 0 开始逐个累加（0,1,2…），否则游戏里那处地点没有 BGM。
        """
        cnt: dict[int, int] = {}
        rows = []
        for sp in self.spots:
            t = int(sp['tile'])
            idx = cnt.get(t, 0)
            cnt[t] = idx + 1
            rows.append({
                'patternId': self.new_pid,
                'attachId': sp['attachId'],
                'smallBaseMapId': t,
                'mapIndex': idx,
                'variationId': sp.get('variationId', 0),
                'modifier': 0,
            })
        return rows


def _max_set(model) -> int:
    ids = list(model.sets.keys())
    return max(ids) if ids else 0


def _max_pid(model) -> int:
    pids = [r.get('patternId') for r in model.pattern_rows if r.get('patternId') is not None]
    return max(pids) if pids else 0


def _next_pid(model) -> int:
    """按「声明容量」算下一个可用 patternId（游戏按 patternCount 累加分区）。

    set 1096 声明 5 个但只有 1200 一行，所以下一个必须是 1205，不能占 1201。
    """
    end = 0
    for sid, rng in model.ranges.items():
        start = rng[0] if isinstance(rng, (list, tuple)) else rng.get('start')
        cnt = (model.sets.get(sid) or {}).get('patternCount') or 0
        if start is not None:
            end = max(end, start + cnt - 1)
    return max(end + 1, _max_pid(model) + 1)


def new_draft(project, boss_id: int) -> Draft:
    """夜王 → 取 boss*10 的第一个 set 的 patternId 当模板。"""
    model = project.model
    base = boss_id * 10
    cand = [s for s in (base, base + 1) if s in model.sets]
    if not cand:
        raise ValueError(f'夜王 {boss_id} 没有找到基础 set（{base}）')
    tset = cand[0]
    pids = sorted(model.pids_by_set.get(tset, []))
    if not pids:
        raise ValueError(f'set {tset} 里没有 patternId')
    tpid = pids[0]

    d = Draft(boss_id=boss_id, template_pid=tpid, template_set=tset,
              new_set=_max_set(model) + 1, new_pid=_next_pid(model))
    if d.new_pid > _max_pid(model) + 1:
        d.warnings.append(f'新 pid {d.new_pid} 跳过了 {_max_pid(model)} 之后的空位（原因是 set 声明容量大于实际行数）')

    # 照抄模板 pid 的 flag 行（m05915：三元组天然合法；之后可在界面上换档）
    d.events = []
    for r in model.rows_by_set.get(tset, []):
        if r.get('patternId') != tpid:
            continue
        d.events.append({
            'row': r.get('_id'),
            'eventFlag': int(r.get('eventFlag') or 0),
            'modifier': int(r.get('modifier') or 0),
            'modifierSet': int(r.get('modifierSet') or 0),
            'name': project.flag_name(r.get('eventFlag') or 0, r.get('modifier') or 0,
                                      r.get('modifierSet') or 0),
        })
    return d


def validate(project, d: Draft) -> list[dict]:
    """返回 [{level, msg}]，level ∈ ok/warn/error。"""
    model = project.model
    out = []
    if not d.spots:
        out.append({'level': 'warn', 'msg': '还没有放任何地点'})

    seen = set()
    for sp in d.spots:
        aid, tile = sp['attachId'], sp['tile']
        key = (aid, tile)
        if key in seen:
            out.append({'level': 'warn', 'msg': f'重复：attach {aid} + tile {tile}'})
        seen.add(key)
        ap = model.attach.get(aid)
        if not ap:
            out.append({'level': 'error', 'msg': f'attach {aid} 在 AttachPoint 里不存在'})
            continue
        if not model.define_of_tile.get(tile):
            out.append({'level': 'warn',
                        'msg': f'tile {tile} 没有 define 名（2xxx 系缺口）'})
        size = model.attach_size(ap.get('_name', ''))
        if size == '未知':
            out.append({'level': 'warn',
                        'msg': f'attach {aid}（{ap.get("_name", "")}）大小未知，先别放'})
        try:
            # m05400：候选只来自「官方在这个 attach 用过的 tile」，
            # 所以这里只对「官方从没在这个位置用过」的情况给个黄灯，不拦。
            off = project.official_tiles().get(int(aid)) if hasattr(project, 'official_tiles') else None
            if off and int(tile) not in off:
                out.append({'level': 'warn',
                            'msg': f'attach {aid} 没见官方放过 smallBaseMapId {tile}（仍可写，游戏里可能不对）'})
        except Exception:  # noqa: BLE001
            pass
        # m05452：属性变体必须落在真实存在的槽位上（variationId 0 基）
        try:
            var_id = int(sp.get('variationId') or 0)
            slots = [v['variationId'] for v in project.tile_variants(tile)]
            if var_id and var_id not in slots:
                out.append({'level': 'warn',
                            'msg': f'tile {tile} 没有 variationId={var_id} 这一档（有 {slots}）'})
        except Exception:  # noqa: BLE001
            pass

    tset = model.sets.get(d.template_set) or {}
    if not tset:
        out.append({'level': 'error', 'msg': f'模板 set {d.template_set} 不存在'})
    if d.new_pid in {r.get('patternId') for r in model.pattern_rows}:
        out.append({'level': 'error', 'msg': f'patternId {d.new_pid} 已被占用'})

    if not out:
        out.append({'level': 'ok', 'msg': f'可以写回：set {d.new_set} / patternId {d.new_pid}'})
    return out


def _copy_fields(project, table: str, row: dict, skip=()) -> dict:
    """只保留 def 里存在、且不是 _id/_name 的字段。"""
    from .writer import _field_map
    import paramtool as pt
    fm = _field_map(pt.load_def(table))
    out = {}
    for k, v in row.items():
        if k.startswith('_') or k in skip or k not in fm:
            continue
        out[k] = v
    return out


def payload(project, d: Draft) -> dict:
    """生成要写入四张表的行。"""
    model = project.model
    tset_row = model.sets[d.template_set]
    set_row = _copy_fields(project, T_SET, tset_row, skip={'patternCount'})
    set_row['patternCount'] = 1

    flag_rows = []
    # 用草稿里的 events（默认照抄模板），保留模板行的其它字段（unknown_0 等）
    tpl_by_id = {r.get('_id'): r for r in model.rows_by_set.get(d.template_set, [])}
    events = d.events or [{'row': r.get('_id'),
                           'eventFlag': int(r.get('eventFlag') or 0),
                           'modifier': int(r.get('modifier') or 0),
                           'modifierSet': int(r.get('modifierSet') or 0)}
                          for r in model.rows_by_set.get(d.template_set, [])
                          if r.get('patternId') == d.template_pid]
    for ev in events:
        src = tpl_by_id.get(ev.get('row'))
        if not src:
            continue
        f = _copy_fields(project, T_FLAG, src)
        f['eventFlag'] = ev['eventFlag']
        f['modifier'] = ev['modifier']
        f['modifierSet'] = ev['modifierSet']
        f['patternId'] = d.new_pid
        f['patternSetId'] = d.new_set
        flag_rows.append(f)

    area_row = None
    for r in model.pattern_rows:
        if r.get('patternId') == d.template_pid:
            break
    area = model.playarea.get(d.template_pid)
    if area:
        area_row = _copy_fields(project, T_AREA, area)
        area_row['patternId'] = d.new_pid
        # 四块各自可换（m05590）：1缩 / 2缩 / 1夜 / 2夜
        if d.pa1 is not None:
            area_row['playArea1'] = d.pa1
        if d.pa2 is not None:
            area_row['playArea2'] = d.pa2
        if d.nb1 is not None:
            area_row['bossId1'] = d.nb1
            # m05801：bossModifierx 与 bossId x 一一对应，换 boss 必须一起换
            mod = project.boss_modifier().get(d.nb1)
            if mod is not None:
                area_row['bossModifier1'] = mod
        if d.nb2 is not None:
            area_row['bossId2'] = d.nb2
            mod = project.boss_modifier().get(d.nb2)
            if mod is not None:
                area_row['bossModifier2'] = mod

    spots = d.spot_rows()
    return {'set': set_row, 'flags': flag_rows, 'area': area_row, 'spots': spots}

