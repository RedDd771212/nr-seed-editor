# -*- coding: utf-8 -*-
"""盘点：bin 里用到的 tile，哪些在我们的数据/图标里是"缺的"。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel
from app.core.patternset import PatternModel
from app.core.project import DEF_DIR

work = sorted((ROOT / 'work' / 'edit').glob('*_ui'))[-1] / 'cur' / 'params'
pd = ParamDir(str(work), str(DEF_DIR))
m = PatternModel(pd)
sm = SeedModel(pd)

PINS = {p.stem for p in (ROOT / 'assets' / 'icon' / 'pin').glob('*.png')}
tiles = {}
for st in m.sets.values():
    for pt in st.patterns:
        for r in pt.spots:
            t = int(r.get('smallBaseMapId') or 0)
            if t:
                tiles[t] = tiles.get(t, 0) + 1

has_var = {t: (t in m_variation) if False else (t in (sm.variation or {})) for t in tiles}
defines = sm.define_of_tile

no_var = [t for t in tiles if not has_var[t]]
no_define = [t for t in tiles if not defines.get(t)]
icon = {}
for t in tiles:
    row = {'_id': 0, 'attachId': 0, 'smallBaseMapId': t, 'variationId': 0}
    try:
        sp = sm.describe_spot(row)
        icon[t] = sp.get('icon')
    except Exception:
        icon[t] = None
no_icon = [t for t in tiles if not icon.get(t)]
no_pin = sorted({icon[t] for t in tiles if icon.get(t) and str(icon[t]) not in PINS})

print(f'tile 总数（种子里用到的）= {len(tiles)}')
print(f'没有变体行 = {len(no_var)}  没有 define 行 = {len(no_define)}  没有图标 = {len(no_icon)}')
print(f'有图标但 assets 里缺 PNG 的图标号 = {no_pin}')
print()
print('没图标的 tile（前 40 个，括号里是使用次数）:')
print('  ' + ', '.join(f'{t}({tiles[t]})' for t in sorted(no_icon)[:40]))
print()
print('5xxx tile 一览:')
print('  ' + ', '.join(f'{t}({tiles[t]})' for t in sorted(t for t in tiles if 5000 <= t < 6000)))
print()
print('4xxx tile 一览（前 30）:')
print('  ' + ', '.join(f'{t}({tiles[t]})' for t in sorted(t for t in tiles if 4000 <= t < 5000)[:30]))
