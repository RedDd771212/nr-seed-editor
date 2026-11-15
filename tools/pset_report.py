# -*- coding: utf-8 -*-
"""Step 1 报表：MapPatternSet / Pattern 模型 + 校验 + dry-run 预演。

只读，不写任何 bin。
用法：
    python tools/pset_report.py <解包后的 params 目录> [--all]

--all 会把 101 个 set 全列出来（默认只列有问题的 + 分组汇总）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir                      # noqa: E402
from nrseed.model import SeedModel                        # noqa: E402
from app.core.patternset import (                          # noqa: E402
    PatternModel, RAREMAP_NAMES, T_SET, T_FLAG, T_AREA, T_SPOT, T_BASE,
)
from app.core.project import DEF_DIR                      # noqa: E402


def hr(title=''):
    print()
    print('=' * 78)
    if title:
        print(title)
        print('=' * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('params')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    pdir = Path(args.params)
    if not pdir.is_absolute():
        pdir = ROOT / pdir
    pd = ParamDir(str(pdir), str(DEF_DIR))
    model = PatternModel(pd)

    hr('一、表规模')
    for t in (T_SET, T_FLAG, T_AREA, T_SPOT, T_BASE):
        if pd.has(t):
            print(f'  {t:<32} {len(pd.rows(t)):>7} 行   rowSize={pd.meta(t)["rowSize"]}')
    print(f'  set 数 = {len(model.sets)}   pattern 数 = {len(model.patterns)}')

    hr('二、分组（千位）与 pid 区间')
    for grp, sets in sorted(model.groups().items()):
        pids = [p.pid for st in sets for p in st.patterns]
        print(f'  {grp} 组：{len(sets)} 个 set，{len(pids)} 个 pid，'
              f'区间 {min(pids) if pids else "-"}..{max(pids) if pids else "-"}')

    hr('三、分配一致性（实测 pid vs 分组前缀和）')
    bad = model.assignment_errors()
    if not bad:
        print('  ✓ 全部一致')
    else:
        for b in bad[:20]:
            print(f"  ✗ set {b['set']} 第 {b['index']} 个：应为 {b['expected']}，实际 {b['actual']}")

    hr('四、校验')
    issues = model.validate()
    order = {'error': 0, 'warn': 1, 'info': 2, 'ok': 3}
    mark_of = {'error': '✗', 'warn': '!', 'info': '·', 'ok': '✓'}
    # 同类问题合并成一行，避免几百条刷屏
    from collections import Counter
    import re as _re
    groups = {}
    for it in issues:
        key = it.level + '|' + _re.sub(r'\d+', 'N', it.msg)
        groups.setdefault(key, []).append(it)
    for key in sorted(groups, key=lambda k: order.get(k.split('|')[0], 9)):
        items = groups[key]
        level = items[0].level
        msg = _re.sub(r'\d+', 'N', items[0].msg)
        sample = items[0].msg
        print(f'  {mark_of.get(level, "?")} [{level}] {msg}  ×{len(items)}')
        if len(items) > 1:
            print(f'       例：{sample}')
    n = Counter(it.level for it in issues)
    print(f'  合计：error {n["error"]} / warn {n["warn"]} / info {n["info"]}')

    hr('五、set 一览（' + ('全部' if args.all else '只列自建/有问题的') + '）')
    hdr = f'{"set":>6} {"夜王":<12} {"地形":<11} {"数量":>5} {"声明":>5} {"pid 区间":>13} {"weight":>7} {"chaosW":>7}  名字'
    print('  ' + hdr)
    for st in sorted(model.sets.values(), key=lambda s: s.sid):
        show = args.all
        if not show:
            show = st.name.startswith('[Custom]') or st.declared_count != st.count
        if not show:
            continue
        rng = model.pid_range(st.sid)
        rngt = f'{rng[0]}..{rng[1]}' if rng else '—'
        combo = st.combo
        boss = model.boss_name(combo[0])[:12] if combo else '—'
        rare = RAREMAP_NAMES.get(combo[1], str(combo[1])) if combo else '—'
        flag = '  ' if st.declared_count == st.count else ' ?'
        pool = '' if not model.pool_mismatch(st.sid) else '  池子≠实际'
        print(f'  {st.sid:>6} {boss:<12} {rare:<11} {st.count:>5} {st.declared_count:>5} '
              f'{rngt:>13} {st.row.get("weight"):>7} {st.row.get("chaosMatchWeight"):>7}{flag}  {st.name}{pool}')

    # ---------------- dry-run 预演 ----------------
    hr('六、dry-run 预演（全部只算不落盘）')

    maris = 3          # 夜王 Maris
    shroud = 5         # 隐城
    print('\n[1] 新建 set：Maris + 隐城')
    for line in model.plan_create_set(maris, shroud).summary():
        print('  ' + line)

    print('\n[2] 在 set 35（Maris · 隐城）插入一个 pattern，源 = pid 155')
    for line in model.plan_insert_pattern(35, source_pid=155).summary():
        print('  ' + line)

    print('\n[3] 在 set 0（Gladius · 普通）插入一个 pattern，源 = pid 0（看跨 set 平移）')
    for line in model.plan_insert_pattern(0, source_pid=0).summary():
        print('  ' + line)

    print('\n[4] 删除 pid 159')
    for line in model.plan_delete_pattern(159).summary():
        print('  ' + line)

    print('\n[5] 删除 set 1096（自建的那个）')
    for line in model.plan_delete_set(1096).summary():
        print('  ' + line)

    print('\n[6] 改 set 1096 的 weight / chaosMatchWeight')
    for line in model.plan_set_fields(1096, {'weight': 5000, 'chaosMatchWeight': 7600}).summary():
        print('  ' + line)

    print('\n[7] 把 set 35 的组合改成 Maris + 火山（不重抄池子）')
    for line in model.plan_change_combo(35, maris, 2).summary():
        print('  ' + line)

    print('\n[8] 重算 set 0 的池子（按它现有的 20 个 pattern）')
    p = model.plan_recompute_pools(0)
    changed = [e for e in p.set_edits if e['old'] != e['new']]
    print(f'  [recompute_pools] 需要改 {len(changed)} 个字段')
    for e in changed[:12]:
        print(f"    {e['field']}: {e['old']} → {e['new']}")
    if len(changed) > 12:
        print('    …')

    print('\n[9] 重算 set 1096 的池子（自建那个：池子 20、实际 1，应该会大幅变化）')
    p = model.plan_recompute_pools(1096)
    changed = [e for e in p.set_edits if e['old'] != e['new']]
    print(f'  [recompute_pools] 需要改 {len(changed)} 个字段')
    for e in changed[:12]:
        print(f"    {e['field']}: {e['old']} → {e['new']}")

    hr('完')


if __name__ == '__main__':
    main()
