# -*- coding: utf-8 -*-
"""看那些"没图标"的 tile 到底叫什么、define 里有没有图标号。"""
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

TILES = [2000, 4300, 4301, 4340, 4350, 4500, 4552, 4600, 4678, 5010, 5100, 5300, 5350, 5999]
for t in TILES:
    var = sm.variation.get(t) or {}
    dids = sm.define_of_tile.get(t, [])
    names = [sm.define[d].get('_name', '') for d in dids]
    icons = [sm.define[d].get('worldMapPointIconId1') for d in dids]
    print(f'tile {t}: variation={var.get("_name")!r}  define={names}  iconIds={icons}')
