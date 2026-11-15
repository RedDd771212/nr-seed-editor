# -*- coding: utf-8 -*-
"""Step 2：把 patternset.Plan 落到 param 目录（字段级 patch + 增删行 + 封包对账）。

设计原则：
  - 所有改动先在**副本**上做（work\\edit\\<bin>_<时间戳>\\params）
  - 每张表只在内存里重建一次（rebuild），改完再写盘
  - 改完立刻用 PatternModel 重新加载副本做「预期 vs 实际」对账
  - 封包 / 解包 / 备份 / 覆盖在 save_to_bin() 里，跟老的 writeback 同一套纪律

字段改写用 paramtool（regtool 配套脚本），不序列化 XML。
"""
from __future__ import annotations

import json
import shutil
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from app.core.paths import SCRIPTS, DEF_DIR

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import paramtool as pt  # noqa: E402

pt.DEF_DIR = str(DEF_DIR)      # 统一用随包携带的 paramdef

from app.core.patternset import (  # noqa: E402
    T_SET, T_FLAG, T_AREA, T_SPOT, PatternModel, maptype_flag, maptype_mod,
)

FMT = {'s8': 'b', 'u8': 'B', 's16': 'h', 'u16': 'H',
       's32': 'i', 'u32': 'I', 'f32': 'f', 'f64': 'd'}


def _i(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 单表编辑

def _field_map(d) -> dict:
    """字段名 → (offset, size, bit, fmt)"""
    out, off = {}, 0
    for f in d['fields']:
        if f['bitlist'] is not None:
            for nm, sh in f['bitlist']:
                out[nm] = (off, f['size'], sh, None)
            off += f['total']
            continue
        for nm in f['name'].split('|'):
            out[nm] = (off, f['total'], None, FMT.get(f['type']))
        off += f['total']
    return out


class Table:
    """一张 param 表的内存副本：按行 id 存 bytearray，改完一次性 rebuild。

    order_by：
      'id'  —— set 表：按行 id 排（set id 被 flag 行的 patternSetId 引用，**绝不重编号**）
      'pid' —— flag / area / spot：按 patternId 从上往下排，行 id 重编成 1..N
               （这些行 id 没有任何表引用，重编是安全的；这样新种子的行会插到
                它该在的位置，而不是永远甩在表尾）
    """

    def __init__(self, param_dir: Path, table: str, order_by: str = 'id', renumber: bool = False):
        self.name = table
        self.order_by = order_by
        self.renumber = renumber
        self.path = param_dir / f'{table}.param'
        self.buf = bytearray(self.path.read_bytes())
        self.n, self.strings_off, self.ents, self.row_size = pt.parse_table(self.buf)
        self.old_off = {rid: noff for rid, _doff, noff in self.ents}
        self.data: dict[int, bytearray] = {}
        for rid, doff, _noff in self.ents:
            self.data[rid] = bytearray(self.buf[doff:doff + self.row_size])
        self.defs = pt.load_def(table)
        self.fm = _field_map(self.defs)
        self.names: dict[int, str] = {}
        self.dirty = False

    # ---- 读 ----
    def exists(self, rid: int) -> bool:
        return rid in self.data

    def max_id(self) -> int:
        return max(self.data) if self.data else 0

    def new_id(self) -> int:
        rid = self.max_id() + 1
        while rid in self.data:
            rid += 1
        return rid

    # ---- 改 ----
    def field(self, rid: int, name: str) -> int:
        off, size, bit, fmt = self.fm[name]
        data = self.data[rid]
        if bit is not None:
            raw = int.from_bytes(data[off:off + size], 'little')
            return (raw >> bit) & 1
        return struct.unpack_from('<' + fmt, data, off)[0]

    def set_field(self, rid: int, name: str, value) -> bool:
        if name not in self.fm:
            raise KeyError(f'{self.name} 没有字段 {name}')
        off, size, bit, fmt = self.fm[name]
        old = self.field(rid, name)
        if old == value:
            return False
        data = self.data[rid]
        if bit is not None:
            pt.set_value(data, 0, off, size, bit, int(value), None)
        else:
            pt.set_value(data, 0, off, size, None, value, fmt)
        self.dirty = True
        return True

    def add(self, rid: int, data: bytes | bytearray, name: str = ''):
        if rid in self.data:
            raise ValueError(f'{self.name} 已有 id={rid}')
        self.data[rid] = bytearray(data)
        if name:
            self.names[rid] = name
        self.dirty = True

    def remove(self, rid: int):
        if rid in self.data:
            del self.data[rid]
            self.dirty = True

    # ---- 写 ----
    def flush(self):
        if not self.dirty:
            return 0
        if self.order_by == 'pid':
            off, _size, _bit, fmt = self.fm['patternId']
            keyed = []
            for rid, data in self.data.items():
                pid = struct.unpack_from('<' + fmt, data, off)[0]
                keyed.append((pid, rid, data))
            keyed.sort(key=lambda x: (x[0], x[1]))
            items = [(rid, data) for _pid, rid, data in keyed]
        else:
            items = sorted(self.data.items(), key=lambda kv: kv[0])

        rows = []
        names: dict[int, str] = {}
        for i, (rid, data) in enumerate(items):
            new_id = (i + 1) if self.renumber else rid
            rows.append((new_id, bytes(data), self.old_off.get(rid, 0)))
            if rid in self.names:
                names[i] = self.names[rid]     # rebuild 里 new_names 按“索引”记

        out = pt.rebuild(self.buf, rows, self.row_size, names or None)
        self.path.write_bytes(out)
        self.dirty = False
        return len(rows)


# ---------------------------------------------------------------- 应用计划

@dataclass
class ApplyReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changes: dict[str, int] = field(default_factory=dict)   # 表 → 变更行数
    checks: list[tuple[str, bool]] = field(default_factory=list)
    params_dir: str = ''
    detail: dict = field(default_factory=dict)

    def fail(self, msg: str) -> 'ApplyReport':
        self.ok = False
        self.errors.append(msg)
        return self

    def summary(self) -> list[str]:
        out = [f'应用结果：{"成功" if self.ok else "失败"}']
        for e in self.errors:
            out.append(f'   ✗ {e}')
        for w in self.warnings:
            out.append(f'   ! {w}')
        for k, v in self.changes.items():
            out.append(f'   {k}: {v} 行')
        for name, ok in self.checks:
            out.append(f'   {"✓" if ok else "✗"} {name}')
        return out


def _pid_rows(model: PatternModel, pid: int) -> dict[str, list[int]]:
    p = model.patterns.get(pid)
    if not p:
        return {'flag': [], 'area': [], 'spot': []}
    out = {
        'flag': [int(r['_id']) for r in p.flags],
        'area': [int(p.playarea['_id'])] if p.playarea else [],
        'spot': [int(r['_id']) for r in p.spots],
    }
    return out


def _apply_core(plan, params_dir: Path, def_dir, model: PatternModel) -> ApplyReport:
    """在给定 param 目录里就地应用 plan（调用方负责备份/回滚）。"""
    rep = ApplyReport(params_dir=str(params_dir))
    tables = {
        'set': Table(params_dir, T_SET, order_by='id', renumber=False),
        'flag': Table(params_dir, T_FLAG, order_by='pid', renumber=True),
        'area': Table(params_dir, T_AREA, order_by='pid', renumber=True),
        'spot': Table(params_dir, T_SPOT, order_by='pid', renumber=True),
    }

    try:
        _apply_set_edits(plan, tables)
        _apply_flag_row_edits(plan, tables)
        _apply_spot_edits(plan, tables)
        _apply_renumber(plan, model, tables)
        _apply_new_pids(plan, model, tables)
        _apply_removed_pids(plan, model, tables)
        _apply_new_sets(plan, tables)
        _apply_removed_sets(plan, tables)
        _apply_counts(plan, tables)
    except Exception as e:  # noqa: BLE001
        return rep.fail(f'应用时出错：{type(e).__name__}: {e}')

    for key, t in tables.items():
        n = t.flush()
        if n:
            rep.changes[key] = n

    # ---- 对账：重新加载 ----
    from nrseed.paramdir import ParamDir
    pd2 = ParamDir(str(params_dir), str(def_dir))
    m2 = PatternModel(pd2)
    rep.checks.append(('重新加载成功', True))
    for c in plan.count_edits:
        st = m2.sets.get(c['sid'])
        rep.checks.append((f"set {c['sid']} patternCount = {c['new']}",
                           bool(st) and st.declared_count == c['new']))
    for np in plan.new_pids:
        p = m2.patterns.get(np['pid'])
        rep.checks.append((f"新 pid {np['pid']} 存在（flag {np['flags']} / 地点 {np['spots']}）",
                           bool(p) and len(p.flags) == np['flags'] and len(p.spots) == np['spots']))
        if p and p.flags:
            rep.checks.append((f"新 pid {np['pid']} 组合正确",
                               p.combo == tuple(np['combo'])))
    removed_tables = {'flag': pd2.rows(T_FLAG), 'area': pd2.rows(T_AREA), 'spot': pd2.rows(T_SPOT)}
    for pid in plan.removed_pids:
        rows = _pid_rows(model, pid)
        gone = not any(rid in removed_tables[k] for k in ('flag', 'area', 'spot') for rid in rows[k])
        rep.checks.append((f'pid {pid} 的原始记录已删除', gone))
    for ns in plan.new_sets:
        rep.checks.append((f"新 set {ns['sid']} 存在", ns['sid'] in m2.sets))
    for add in plan.spot_adds:
        pt = m2.patterns.get(add['pid'])
        ok = bool(pt) and any(_i(r.get('smallBaseMapId')) == add['tile']
                              and _i(r.get('attachId')) == add['attachId'] for r in pt.spots)
        rep.checks.append((f"pid {add['pid']} 新地点已写入", ok))
    spot_rows = pd2.rows(T_SPOT)
    for rid in plan.spot_removes:
        rep.checks.append((f'地点行 {rid} 已删除', rid not in spot_rows))
    for e in plan.area_field_edits:
        pt = m2.patterns.get(e['pid'])
        got = _i(pt.playarea.get(e['field'])) if pt and pt.playarea else None
        rep.checks.append((f"pid {e['pid']} playarea.{e['field']} = {e['new']}", got == _i(e['new'])))
    for sid in plan.removed_sets:
        rep.checks.append((f'set {sid} 已删除', sid not in m2.sets))
    if plan.moves:
        missing = [mv['new_pid'] for mv in plan.moves if mv['new_pid'] not in m2.patterns]
        rep.checks.append((f"pid 平移 {len(plan.moves)} 个全部生效", not missing))
        rep.detail['moves_missing'] = missing[:10]
    bad = m2.assignment_errors()
    rep.checks.append(('组内前缀和规则仍成立', not bad))
    rep.detail['assignment_errors'] = bad[:10]

    rep.ok = rep.ok and all(ok for _n, ok in rep.checks)
    return rep


def apply_plan(project, plan, work_root: Path | None = None, tag: str = '') -> ApplyReport:
    """一次性：复制一份 params → 应用 → 返回报告（不碰原目录、不碰 bin）。"""
    rep = ApplyReport()
    if not plan.ok:
        return rep.fail('计划本身有错，拒绝执行：' + '；'.join(plan.errors))
    model: PatternModel = getattr(project, 'pset_model', None) or PatternModel(project.params)
    ts = time.strftime('%Y%m%d_%H%M%S')
    stem = Path(project.bin_path).stem
    work = (work_root or (ROOT / 'work' / 'edit')) / f'{stem}_{ts}{("_" + tag) if tag else ""}'
    params_dir = work / 'params'
    if params_dir.exists():
        return rep.fail(f'工作目录已存在：{params_dir}')
    shutil.copytree(project.param_dir, params_dir)

    out = _apply_core(plan, params_dir, project.params.def_dir, model)
    _record_history(work.parent / f'{stem}_history.json', ts, plan, out)
    return out


def _record_history(path: Path, ts: str, plan, rep: ApplyReport):
    try:
        data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
        data.append({'ts': ts, 'op': plan.op, 'title': plan.title,
                     'params': rep.params_dir, 'ok': rep.ok, 'changes': rep.changes})
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:  # noqa: BLE001
        pass


class Session:
    """编辑会话：一份基线 + 一份工作副本 + 每步快照（可回滚）。

    目录：
      work\\edit\\<bin>_<时间戳>\\
        base\\params        打开时的基线
        cur\\params         当前工作副本
        snap\\0001_create_set\\params
        session.json        历史
    """

    MAX_SNAPS = 8

    def __init__(self, project, work_root: Path | None = None, name: str = ''):
        self.project = project
        self.def_dir = project.params.def_dir
        self.stem = Path(project.bin_path).stem
        ts = time.strftime('%Y%m%d_%H%M%S')
        root = work_root or (ROOT / 'work' / 'edit')
        root.mkdir(parents=True, exist_ok=True)
        self.dir = root / f'{self.stem}_{ts}{("_" + name) if name else ""}'
        self.base = self.dir / 'base'
        self.cur = self.dir / 'cur'
        self.snap_root = self.dir / 'snap'
        self.dir.mkdir(parents=True, exist_ok=False)
        # 只留最近 4 个会话（每份约 120MB，别把 work 撑爆）
        olds = sorted((d for d in root.iterdir()
                       if d.is_dir() and d.name.startswith(self.stem + '_')), key=lambda d: d.name)
        for d in olds[:-4]:
            shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(project.param_dir, self.base / 'params')
        shutil.copytree(self.base / 'params', self.cur / 'params')
        self.history: list[dict] = []
        self._save()

    # ---- 状态 ----
    @property
    def params_dir(self) -> Path:
        return self.cur / 'params'

    def model(self) -> PatternModel:
        return PatternModel(self._pd(self.params_dir))

    def _pd(self, d: Path):
        from nrseed.paramdir import ParamDir
        return ParamDir(str(d), str(self.def_dir))

    def _save(self):
        (self.dir / 'session.json').write_text(
            json.dumps({'bin': str(self.project.bin_path), 'history': self.history},
                       ensure_ascii=False, indent=2), encoding='utf-8')

    # ---- 操作 ----
    def snapshot(self, tag: str) -> Path:
        seq = len(self.history) + 1
        d = self.snap_root / f'{seq:04d}_{tag}'
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(self.cur / 'params', d / 'params')
        snaps = sorted(self.snap_root.glob('*'))
        while len(snaps) > self.MAX_SNAPS:
            shutil.rmtree(snaps.pop(0))
        return d

    def apply(self, plan) -> ApplyReport:
        """就地应用；失败自动回滚到执行前。"""
        rep = ApplyReport()
        if not plan.ok:
            return rep.fail('计划本身有错，拒绝执行：' + '；'.join(plan.errors))
        model = self.model()
        snap = self.snapshot(plan.op)
        out = _apply_core(plan, self.params_dir, self.def_dir, model)
        if not out.ok:
            self.rollback_dir(snap)
            out.warnings.append('已自动回滚到执行前')
            return out
        self.history.append({'n': len(self.history) + 1, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                             'op': plan.op, 'title': plan.title, 'snap': snap.name,
                             'changes': out.changes, 'ok': True})
        self._save()
        return out

    def rollback(self, n: int) -> ApplyReport:
        """回滚到第 n 步执行前（n=0 表示回到会话基线）。"""
        rep = ApplyReport()
        if n == 0:
            src = self.base / 'params'
            tag = 'base'
        else:
            rec = next((h for h in self.history if h['n'] == n), None)
            if not rec:
                return rep.fail(f'没有第 {n} 步的记录')
            src = self.snap_root / rec['snap'] / 'params'
            tag = rec['snap']
        if not src.exists():
            return rep.fail(f'快照不存在：{src}')
        self.rollback_dir(src.parent)
        # 截断历史
        self.history = self.history[:max(0, n - 1)]
        self._save()
        rep.checks.append((f'已回滚到 {tag}', True))
        rep.params_dir = str(self.params_dir)
        return rep

    def rollback_dir(self, snap_dir: Path):
        """用某个快照目录覆盖工作副本（快照目录下应有 params/）。"""
        src = snap_dir / 'params' if (snap_dir / 'params').exists() else snap_dir
        dst = self.params_dir
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)


# ---- 各个子步骤 ----

def _apply_set_edits(plan, tables: dict):
    t = tables['set']
    for e in plan.set_edits:
        if not t.exists(e['sid']):
            raise KeyError(f"MapPatternSet 没有 set {e['sid']}")
        t.set_field(e['sid'], e['field'], e['new'])


def _apply_flag_row_edits(plan, tables: dict):
    t = tables['flag']
    for e in plan.flag_row_edits:
        if not t.exists(e['row_id']):
            raise KeyError(f'flag 行 {e["row_id"]} 不存在')
        t.set_field(e['row_id'], e['field'], e['new'])


def _apply_spot_edits(plan, tables: dict):
    """地点行：改字段 / 删行 / 加行；以及 playarea 的字段改动。"""
    t = tables['spot']
    for e in plan.spot_field_edits:
        if not t.exists(e['row_id']):
            raise KeyError(f'spot 行 {e["row_id"]} 不存在')
        t.set_field(e['row_id'], e['field'], e['new'])
    for rid in plan.spot_removes:
        t.remove(rid)
    for add in plan.spot_adds:
        src = add.get('source_row')
        if src is None or src not in t.data:
            src = next(iter(t.data))          # 兜底：拿表里第一行当模板
        nid = t.new_id()
        t.add(nid, bytearray(t.data[src]), f"p{add['pid']}_add")
        t.set_field(nid, 'patternId', add['pid'])
        t.set_field(nid, 'attachId', add['attachId'])
        t.set_field(nid, 'smallBaseMapId', add['tile'])
        t.set_field(nid, 'variationId', add['variationId'])
        t.set_field(nid, 'mapIndex', add['mapIndex'])

    a = tables['area']
    for e in plan.area_field_edits:
        rows = [rid for rid in a.data if a.field(rid, 'patternId') == e['pid']]
        if not rows:
            raise KeyError(f"pid {e['pid']} 没有 playarea 行")
        a.set_field(rows[0], e['field'], e['new'])


def _apply_renumber(plan, model: PatternModel, tables: dict):
    """把 move 里的 old_pid → new_pid 改到三张表上。"""
    for mv in plan.moves:
        rows = _pid_rows(model, mv['old_pid'])
        for rid in rows['flag']:
            tables['flag'].set_field(rid, 'patternId', mv['new_pid'])
        for rid in rows['area']:
            tables['area'].set_field(rid, 'patternId', mv['new_pid'])
        for rid in rows['spot']:
            tables['spot'].set_field(rid, 'patternId', mv['new_pid'])


def _apply_new_pids(plan, model: PatternModel, tables: dict):
    for np in plan.new_pids:
        src = model.patterns.get(np['source_pid'])
        if not src:
            raise KeyError(f"源 pid {np['source_pid']} 不存在")
        pid = np['pid']
        combo = tuple(np['combo'])

        # --- flag 行：克隆 + 改 patternId/patternSetId/组合/地图类型旗标 ---
        if not src.flags:
            raise ValueError(f'源 pid {src.pid} 没有 flag 行')
        for i, r in enumerate(src.flags):
            src_id = int(r['_id'])
            data = bytearray(tables['flag'].data[src_id])
            tgt = tables['flag'].new_id()
            tables['flag'].add(tgt, data, f'p{pid}_{i:02d}')
            f = tables['flag']
            f.set_field(tgt, 'patternId', pid)
            f.set_field(tgt, 'patternSetId', np['set'])
            f.set_field(tgt, 'targetBoss', combo[0])
            f.set_field(tgt, 'rareMap', combo[1])
            # 地图类型行（modifierSet=0 且 eventFlag=76xx）
            if (int(f.field(tgt, 'modifierSet')) == 0
                    and 7600 <= int(f.field(tgt, 'eventFlag')) <= 7699):
                f.set_field(tgt, 'eventFlag', maptype_flag(combo[1]))
                f.set_field(tgt, 'modifier', maptype_mod(combo[1]))

        # --- playarea 行 ---
        if not src.playarea:
            raise ValueError(f'源 pid {src.pid} 没有 playarea 行')
        data = bytearray(tables['area'].data[int(src.playarea['_id'])])
        aid = tables['area'].new_id()
        tables['area'].add(aid, data, f'p{pid}')
        a = tables['area']
        a.set_field(aid, 'patternId', pid)
        n1, n2 = np.get('night') or (None, None)
        if n1 is not None:
            a.set_field(aid, 'bossId1', _boss_id_of(model, n1))
            a.set_field(aid, 'bossModifier1', n1)
        if n2 is not None:
            a.set_field(aid, 'bossId2', _boss_id_of(model, n2))
            a.set_field(aid, 'bossModifier2', n2)

        # --- spot 行 ---
        for i, r in enumerate(src.spots):
            data = bytearray(tables['spot'].data[int(r['_id'])])
            sid = tables['spot'].new_id()
            tables['spot'].add(sid, data, f'p{pid}_{i:02d}')
            tables['spot'].set_field(sid, 'patternId', pid)


def _boss_id_of(model: PatternModel, boss_modifier: int) -> int:
    """bossModifier → 对应 playarea 行里的 bossId（从模型里查一份对照）。"""
    for p in model.patterns.values():
        if not p.playarea:
            continue
        pa = p.playarea
        if int(pa.get('bossModifier1') or -1) == boss_modifier:
            return int(pa.get('bossId1') or 0)
        if int(pa.get('bossModifier2') or -1) == boss_modifier:
            return int(pa.get('bossId2') or 0)
    return 0


def _apply_removed_pids(plan, model: PatternModel, tables: dict):
    for pid in plan.removed_pids:
        rows = _pid_rows(model, pid)
        for rid in rows['flag']:
            tables['flag'].remove(rid)
        for rid in rows['area']:
            tables['area'].remove(rid)
        for rid in rows['spot']:
            tables['spot'].remove(rid)


def _apply_new_sets(plan, tables: dict):
    for ns in plan.new_sets:
        t = tables['set']
        rid = t.new_id()
        d = pt.default_row(str(Path(pt.DEF_DIR) / f'{T_SET}.xml'), t.row_size)
        t.add(rid, d, ns['name'])
        for k, v in ns['row'].items():
            if k in t.fm:
                t.set_field(rid, k, v)
        ns['applied_id'] = rid


def _apply_removed_sets(plan, tables: dict):
    for sid in plan.removed_sets:
        tables['set'].remove(sid)


def _apply_counts(plan, tables: dict):
    for c in plan.count_edits:
        tables['set'].set_field(c['sid'], 'patternCount', c['new'])


# ---------------------------------------------------------------- 封包保存

def save_to_bin(project, params_dir: Path, target_bin: Path | None = None,
                base_bin: Path | None = None) -> dict:
    """副本 params → pack → unpack 对账 → 备份 → 覆盖目标 bin。"""
    from app.core.project import REGROOL, _run

    base = Path(base_bin or project.bin_path)
    target = Path(target_bin or base)
    ts = time.strftime('%Y%m%d_%H%M%S')
    out_bin = params_dir.parent / f'{base.stem}.new.bin'
    _run(['dotnet', 'exec', str(REGROOL), 'pack', str(base), str(params_dir), str(out_bin)])

    vdir = params_dir.parent / 'verify'
    _run(['dotnet', 'exec', str(REGROOL), 'unpack', str(out_bin), str(vdir)])

    report = {'ok': True, 'out': str(out_bin), 'target': str(target), 'checks': []}
    checks = report['checks']

    touched = {T_SET, T_FLAG, T_AREA, T_SPOT}
    diff = []
    for f in sorted(params_dir.glob('*.param')):
        g = vdir / f.name
        if not g.exists() or g.read_bytes() != f.read_bytes():
            diff.append(f.stem)
    checks.append(('封包后逐表字节一致', not diff))
    report['diff_tables'] = diff

    if not all(ok for _n, ok in checks):
        report['ok'] = False
        report['error'] = '对账失败：' + '；'.join(f'{n}={"OK" if ok else "FAIL"}' for n, ok in checks)
        return report

    if target.exists():
        shutil.copy2(target, target.with_suffix(target.suffix + f'.prev_{ts}'))
    shutil.copy2(out_bin, target)
    report['backup'] = str(target.with_suffix(target.suffix + f'.prev_{ts}'))
    return report
