# -*- coding: utf-8 -*-
"""复验两个验证 bin：把封包后再解包的结果当独立 bin 检查。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel, T_FLAG, T_AREA, T_SPOT
from app.core.project import DEF_DIR

def latest(tag: str) -> Path:
    cands = sorted((ROOT / 'work' / 'verify_work' / 'sessions').glob(f'*_{tag}'))
    if not cands:
        raise SystemExit(f'找不到 {tag} 的会话目录')
    return cands[-1] / 'cur' / 'verify'


CASES = [
    ('V1（set 0 插 1 个）', latest('v1')),
    ('V3（新建 set 1097）', latest('v3')),
]

for title, d in CASES:
    print('=' * 70)
    print(title, '→', d)
    pd = ParamDir(str(d), str(DEF_DIR))
    m = PatternModel(pd)
    print(f'  set={len(m.sets)} pattern={len(m.patterns)}  分配错误={len(m.assignment_errors())}')
    errs = [i for i in m.validate() if i.level == 'error']
    print(f'  error={len(errs)}: {[i.msg for i in errs][:3]}')
    for grp, sets in sorted(m.groups().items()):
        pids = [p.pid for st in sets for p in st.patterns]
        print(f'  {grp} 组：set={len(sets)} pid={len(pids)} 区间={min(pids)}..{max(pids)}')
    for sid in (0, 1097):
        if sid in m.sets:
            st = m.sets[sid]
            rng = m.pid_range(sid)
            print(f'  set {sid}: 数量={st.count} 声明={st.declared_count} 区间={rng} 组合={m.combo_text(st.combo)}')
            for p in st.patterns[:3]:
                print(f'      pid {p.pid} 夜Boss={p.boss_modifier} 地点={p.spot_count} flag={len(p.flags)}')

    # ---- 行序：patternId 是否从头到尾递增（新种子行应插在它该在的位置） ----
    print('  行序检查（表内 patternId 是否递增）：')
    for t in (T_FLAG, T_AREA, T_SPOT):
        pids = [pd.rows(t)[rid]['patternId'] for rid in pd.order(t)]
        ok = all(a <= b for a, b in zip(pids, pids[1:]))
        print(f'    {t:<32} {"✓ 递增" if ok else "✗ 乱序"}')
        if t == T_FLAG and 20 in m.patterns:
            pos20 = [i for i, x in enumerate(pids) if x == 20]
            pos21 = [i for i, x in enumerate(pids) if x == 21]
            if pos20 and pos21:
                print(f'      pid 20 的行位置 {pos20[0]}..{pos20[-1]}，pid 21 从 {pos21[0]} 开始 '
                      f'→ {"✓ 20 在 21 前面" if pos20[-1] < pos21[0] else "✗ 顺序不对"}')
    print()
