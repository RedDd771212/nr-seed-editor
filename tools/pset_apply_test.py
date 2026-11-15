# -*- coding: utf-8 -*-
"""Step 2 自测：在副本上做「新建 set → 插 pattern → 插到中间 set → 删 pattern → 改字段」，
每步都用 PatternModel 重新加载对账，最后 pack/unpack 验一遍。

只写 work\\step2\\ 下的副本，不碰游戏 bin、不碰原解包目录。
用法：python tools/pset_apply_test.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel
from app.core.pswriter import apply_plan, save_to_bin
from app.core.project import DEF_DIR

SRC_PARAMS = ROOT / 'work' / 'open' / 'regulation_198c55de' / 'params'
BASE_BIN = Path(r'C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin')
WORK = ROOT / 'work' / 'step2'


class Shim:
    """apply_plan 需要的最小 project：bin 路径 + 解包目录 + ParamDir。"""

    def __init__(self, params_dir: Path, bin_path: Path):
        self.param_dir = Path(params_dir)
        self.bin_path = Path(bin_path)
        self.params = ParamDir(str(self.param_dir), str(DEF_DIR))
        self.pset_model = PatternModel(self.params)


def hr(t):
    print()
    print('=' * 70)
    print(t)
    print('=' * 70)


def pd_rows(shim, key: str):
    from app.core.patternset import T_FLAG, T_AREA, T_SPOT
    table = {'flag': T_FLAG, 'area': T_AREA, 'spot': T_SPOT}[key]
    return shim.params.rows(table)


def build(tag: str) -> Shim:
    d = WORK / tag / 'params'
    if d.parent.exists():
        shutil.rmtree(d.parent)
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC_PARAMS, d)
    return Shim(d, BASE_BIN)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    hr('准备：复制一份 params 到副本')
    cur = build('t0')
    m = cur.pset_model
    print(f'  set={len(m.sets)} pattern={len(m.patterns)} 分配规则错误={len(m.assignment_errors())}')

    # ---------- 1) 新建 set ----------
    hr('1) 新建 set：Maris + 隐城')
    plan = m.plan_create_set(3, 5)
    for line in plan.summary():
        print('  ' + line)
    rep = apply_plan(cur, plan, work_root=WORK / 'run', tag='create')
    for line in rep.summary():
        print('  ' + line)
    if not rep.ok:
        return 1
    cur = Shim(Path(rep.params_dir), BASE_BIN)
    m = cur.pset_model
    new_sid = max(m.sets)
    st = m.sets[new_sid]
    print(f'  验证：set {new_sid} 名字={st.name!r} 数量={st.count} 声明={st.declared_count} 组合={m.combo_text(st.combo)}')

    # ---------- 2) 往新 set 插一个 pattern ----------
    hr(f'2) 往 set {new_sid} 插一个 pattern（源 = pid 155）')
    plan = m.plan_insert_pattern(new_sid, source_pid=155)
    for line in plan.summary():
        print('  ' + line)
    rep = apply_plan(cur, plan, work_root=WORK / 'run', tag='insert_new')
    for line in rep.summary():
        print('  ' + line)
    if not rep.ok:
        return 1
    cur = Shim(Path(rep.params_dir), BASE_BIN)
    m = cur.pset_model
    st = m.sets[new_sid]
    print(f'  验证：set {new_sid} 数量={st.count} pid={[p.pid for p in st.patterns]}')
    for p in st.patterns:
        print(f'        pid {p.pid}: 组合={m.combo_text(p.combo)} flag={len(p.flags)} 地点={p.spot_count} '
              f'夜1={p.boss_modifier[0]} 夜2={p.boss_modifier[1]}')
    print(f'  池子：声明={m.declared_pool(new_sid)} 实际={m.pool_of(new_sid)}')
    print(f'  池子一致={not m.pool_mismatch(new_sid)}')

    # ---------- 3) 往中间的 set 0 插一个（考验重编号） ----------
    hr('3) 往 set 0（Gladius 普通）插一个 pattern（源 = pid 0）')
    before = {p.pid: p.spot_count for p in m.sets[0].patterns}
    plan = m.plan_insert_pattern(0, source_pid=0)
    for line in plan.summary()[:6]:
        print('  ' + line)
    rep = apply_plan(cur, plan, work_root=WORK / 'run', tag='insert_mid')
    for line in rep.summary():
        print('  ' + line)
    if not rep.ok:
        return 1
    cur = Shim(Path(rep.params_dir), BASE_BIN)
    m = cur.pset_model
    st = m.sets[0]
    print(f'  验证：set 0 数量={st.count}（原 {len(before)}）pid 区间={m.pid_range(0)}')
    old_first = m.patterns.get(21)      # 原来 pid 20（set 1 的第一个）现在应变成 21
    print(f'        原 pid 20 现在在 21：{bool(old_first)}（组合 {m.combo_text(old_first.combo) if old_first else "-"}）')
    print(f'        新 pid 20 在 set 0：{m.patterns[20].flags[0]["patternSetId"] if 20 in m.patterns else "-"}')
    print(f'        1000 组首个 pid：{m.pid_range(1000)}  ← 应仍是 1000..1004')
    print(f'  池子一致={not m.pool_mismatch(0)}')

    # ---------- 4) 删一个 pattern ----------
    hr('4) 删除刚插进去的 pid 20（克隆件）')
    clone_rows = [int(r['_id']) for r in m.patterns[20].flags]
    plan = m.plan_delete_pattern(20)
    for line in plan.summary()[:6]:
        print('  ' + line)
    rep = apply_plan(cur, plan, work_root=WORK / 'run', tag='delete')
    for line in rep.summary():
        print('  ' + line)
    if not rep.ok:
        return 1
    cur = Shim(Path(rep.params_dir), BASE_BIN)
    m = cur.pset_model
    print(f'  验证：set 0 数量={m.sets[0].count}（应回到 20）')
    print(f'        克隆件的 flag 行还在吗={any(rid in pd_rows(cur, "flag") for rid in clone_rows)}（应 False）')
    print(f'        p 号 20 现在归属 set={m.patterns[20].flags[0]["patternSetId"] if 20 in m.patterns else "-"}'
          f'（应 1，即后面的 set 补上了这个号）')

    # ---------- 5) 改字段 ----------
    hr(f'5) 改 set {new_sid} 的 weight / chaosMatchWeight')
    plan = m.plan_set_fields(new_sid, {'weight': 5000, 'chaosMatchWeight': 600})
    rep = apply_plan(cur, plan, work_root=WORK / 'run', tag='fields')
    for line in rep.summary():
        print('  ' + line)
    if not rep.ok:
        return 1
    cur = Shim(Path(rep.params_dir), BASE_BIN)
    m = cur.pset_model
    print(f'  验证：weight={m.sets[new_sid].row.get("weight")} '
          f'chaosW={m.sets[new_sid].row.get("chaosMatchWeight")}')

    # ---------- 6) 整体再校验 ----------
    hr('6) 整体校验（9 条不变式）')
    issues = m.validate()
    n = {'error': 0, 'warn': 0, 'info': 0}
    for it in issues:
        n[it.level] = n.get(it.level, 0) + 1
    print(f'  error={n["error"]} warn={n["warn"]} info={n["info"]}')
    for it in issues:
        if it.level == 'error':
            print('  ✗', it.msg)
    print(f'  分配规则错误={len(m.assignment_errors())}')

    # ---------- 8) 会话模式：连续操作 + 回滚 ----------
    hr('8) 会话模式：创建会话 → 新建 set → 插 pattern → 回滚')
    from app.core.pswriter import Session
    sess = Session(cur, work_root=WORK / 'sessions', name='atest')
    m = sess.model()
    base_n = len(m.sets)
    r = sess.apply(m.plan_create_set(3, 5))
    print(f'  操作1 新建 set：{r.ok}  {dict(r.changes)}')
    m = sess.model()
    sid = max(m.sets)
    r = sess.apply(m.plan_insert_pattern(sid, source_pid=155))
    print(f'  操作2 插入 pattern：{r.ok}  {dict(r.changes)}')
    m = sess.model()
    print(f'  当前：set 数={len(m.sets)} set {sid} 数量={m.sets[sid].count} '
          f'pid={[p.pid for p in m.sets[sid].patterns]}')
    r = sess.rollback(2)
    m = sess.model()
    print(f'  回滚到第2步前：set {sid} 数量={m.sets[sid].count}（应 0）  历史剩 {len(sess.history)} 条')
    r = sess.rollback(0)
    m = sess.model()
    print(f'  回滚到基线：set 数={len(m.sets)}（应 {base_n}）  set {sid} 存在={sid in m.sets}')
    print(f'  会话目录：{sess.dir}')

    # ---------- 7) 封包 / 解包对账 ----------
    hr('7) 封包 → 解包 → 逐表对账（目标写 work\\step2\\out.bin，不碰游戏 bin）')
    out_target = WORK / 'out.bin'
    report = save_to_bin(cur, Path(cur.param_dir), target_bin=out_target, base_bin=BASE_BIN)
    for name, ok in report['checks']:
        print(f'  {"✓" if ok else "✗"} {name}')
    print(f'  输出：{report.get("out")}')
    if report.get('diff_tables'):
        print('  不一致的表：', report['diff_tables'][:10])
    print(f'  整体：{"成功" if report["ok"] else "失败 " + report.get("error", "")}')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
