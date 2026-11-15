# -*- coding: utf-8 -*-
"""查 define 里填了图标号、但最终没图标的 tile：WorldMapPointIconParam 里到底有没有。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel
from app.core.project import DEF_DIR

work = sorted((ROOT / 'work' / 'edit').glob('*_ui'))[-1] / 'cur' / 'params'
pd = ParamDir(str(work), str(DEF_DIR))
sm = SeedModel(pd)
wm = pd.rows('WorldMapPointIconParam')
print('WorldMapPointIconParam 行数 =', len(wm))
for k, r in list(wm.items())[:5]:
    print('  row', k, {kk: vv for kk, vv in r.items() if not kk.startswith('_') and vv})
print()
PINS = {p.stem for p in (ROOT / 'assets' / 'icon' / 'pin').glob('*.png')}
tiles = {}
for st in sm.sets.values():
    pass
# 用 spot 表扫一遍更直接
rows = pd.rows('LotResultSmallBaseAndSpot')
used = {}
for r in rows.values():
    t = int(r.get('smallBaseMapId') or 0)
    if t:
        used[t] = used.get(t, 0) + 1

miss = []
for t in sorted(used):
    dids = sm.define_of_tile.get(t, [])
    ic = None
    for d in dids:
        v = sm.define[d].get('worldMapPointIconId1')
        if v:
            ic = v
            break
    if not ic:
        continue
    mapped = wm.get(ic, {}).get('iconId', ic)
    if str(mapped) not in PINS:
        miss.append((t, ic, mapped, pd.rows('SmallBaseMapVariationParam').get(t, {}).get('_name')))
print(f'define 有图标号但最终 pin 不存在的 tile：{len(miss)} 个')
for m in miss[:30]:
    print('   tile', m[0], 'iconId', m[1], '→', m[2], m[3])
