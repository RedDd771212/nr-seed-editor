# -*- coding: utf-8 -*-
"""DLC 种子的 attachId / 坐标 与建筑位池子的关系。"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel
from app.core.patternset import PatternModel
from app.core.project import DEF_DIR

work = sorted((ROOT / 'work' / 'edit').glob('*_ui'))[-1] / 'cur' / 'params'
pd = ParamDir(str(work), str(DEF_DIR))
m = PatternModel(pd)
sm = SeedModel(pd)

maps = json.loads((ROOT / 'src' / 'data' / 'maps.json').read_text(encoding='utf-8'))['maps']
POOL = {k: (set(v['attachPool']) if v.get('attachPool') else None) for k, v in maps.items()}

for pid in (1105, 1106, 0, 120, 155):
    pt = m.patterns.get(pid)
    if not pt:
        continue
    rare = pt.rare_map
    t = {0: 'limveld', 1: 'mountaintop', 2: 'crater', 3: 'rotted', 4: 'limveld', 5: 'shroud'}[rare]
    pool = POOL.get(t)
    ids = sorted({int(r['attachId']) for r in pt.spots})
    hit = len([i for i in ids if pool and i in pool])
    print(f'pid {pid} rare={rare}({t}) 地点={len(pt.spots)} 不同 attach={len(ids)} 命中池子={hit}')
    print('   attach 样本:', ids[:12])
    if pool:
        print('   池子样本:', sorted(pool)[:12])
    # 坐标是否落在锚点范围里（用几条样本）
    for r in pt.spots[:3]:
        sp = sm.describe_spot(r)
        print('   world:', [round(v, 1) if v is not None else None for v in sp['world']],
              ' attach', sp['attachId'], 'name', sp['attachName'])
    print()
