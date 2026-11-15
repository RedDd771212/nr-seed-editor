# -*- coding: utf-8 -*-
"""查：当前每个种子里，有多少建筑位没被地点占用（这些才是应该画小圈的）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel
from app.core.project import DEF_DIR

# 直接读当前 v3 会话的工作副本（跟界面同一份数据）
work = sorted((ROOT / 'work' / 'edit').glob('*_ui'))[-1] / 'cur' / 'params'
pd = ParamDir(str(work), str(DEF_DIR))
m = PatternModel(pd)

# 跟界面一致：锚点 = attach_points(当前地形)
import json
from app.core.project import Project
BIN = Path(r'C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin')


class Shim:
    def __init__(self):
        self.param_dir = work
        self.bin_path = BIN
        self.params = pd
        self.model = __import__('nrseed.model', fromlist=['SeedModel']).SeedModel(pd)


p = Shim()
TERRAIN = {0: 'limveld', 1: 'mountaintop', 2: 'crater', 3: 'rotted', 4: 'limveld', 5: 'shroud'}
cache = {}
for rare, t in TERRAIN.items():
    anchors = p.model and None
    pool = (json.loads((ROOT / 'src' / 'data' / 'maps.json').read_text('utf-8'))['maps']
            .get(t, {}).get('attachPool'))
    cache[rare] = set(pool) if pool else None

print('每个地形池子大小:', {k: (len(v) if v else '全部') for k, v in cache.items()})
print()
rows = []
for st in sorted(m.sets.values(), key=lambda s: s.sid):
    for pt in st.patterns:
        rare = pt.rare_map
        pool = cache.get(rare)
        used = {int(r['attachId']) for r in pt.spots}
        if pool is None:
            continue
        free = pool - used
        rows.append((st.sid, pt.pid, rare, len(pt.spots), len(pool), len(free), sorted(free)[:6]))
rows.sort(key=lambda r: -r[5])
print('占用率最低的 8 个种子（free = 该地形里有、但这个种子里没放东西的建筑位 → 会画小圈）:')
for r in rows[:8]:
    print(f'  set {r[0]:>5} pid {r[1]:>5} rare={r[2]} 地点={r[3]:>3} 池={r[4]:>3} 空闲={r[5]:>3} 例:{r[6]}')
print()
zero = [r for r in rows if r[5] == 0]
print(f'完全没有空闲建筑位的种子：{len(zero)} / {len(rows)}')
