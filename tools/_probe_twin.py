# -*- coding: utf-8 -*-
"""验证：DLC 种子用的 2xxx attach 是否 = 1xx 的孪生编号（减 2000 能对上池子）。"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'src'))
from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel
from app.core.project import DEF_DIR

work = sorted((ROOT / 'work' / 'edit').glob('*_ui'))[-1] / 'cur' / 'params'
m = PatternModel(ParamDir(str(work), str(DEF_DIR)))
maps = json.loads((ROOT / 'src' / 'data' / 'maps.json').read_text(encoding='utf-8'))['maps']
POOL = {k: (set(v['attachPool']) if v.get('attachPool') else None) for k, v in maps.items()}
T = {0: 'limveld', 1: 'mountaintop', 2: 'crater', 3: 'rotted', 4: 'limveld', 5: 'shroud'}

def match_ids(a, pool):
    for cand in (a, a - 1000, a - 2000, a - 3000, a + 1000, a + 2000):
        if cand > 0 and cand in pool:
            return cand
    return None

for pid in (1105, 1106, 1135, 120, 0):
    pt = m.patterns.get(pid)
    if not pt:
        continue
    t = T[pt.rare_map]
    pool = POOL.get(t)
    ids = {int(r['attachId']) for r in pt.spots}
    if pool is None:
        print(f'pid {pid} rare={pt.rare_map}({t}) 无池子（全部锚点）  attach={len(ids)}')
        continue
    direct = sum(1 for a in ids if a in pool)
    twin = sum(1 for a in ids if match_ids(a, pool) is not None)
    free_direct = len(pool) - direct
    free_twin = len(pool) - twin
    print(f'pid {pid} rare={pt.rare_map}({t}) 池={len(pool)} 地点 attach={len(ids)}'
          f'  直接命中={direct}  含孪生={twin}  空闲锚点 {free_direct} → {free_twin}')
    if pid == 1105:
        print('   前 12 个 attach 的孪生:', [(a, match_ids(a, pool)) for a in sorted(ids)[:12]])
