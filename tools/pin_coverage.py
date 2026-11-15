# -*- coding: utf-8 -*-
"""统计参数里用到的 worldMapPointIconId / iconId 覆盖情况，顺便导出 pin 图标。"""
import sys, os, shutil
from pathlib import Path

ROOT = Path(r'D:\项目\app\NR地图种子编辑器')
sys.path.insert(0, str(ROOT / 'src'))
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir(str(ROOT / 'work' / 'reg' / 'params')))

have = {int(f.stem.replace('MENU_MenuIcon_', '')) for f in (ROOT / 'work' / 'menuicon_42').glob('*.png') if f.stem.split('_')[-1].isdigit()}

used_def = {}
for r in m.define.values():
    for i in range(1, 19):
        v = r.get(f'worldMapPointIconId{i}')
        if v:
            used_def.setdefault(v, 0)
            used_def[v] += 1

missing_def = {k: v for k, v in used_def.items() if k not in have}
print('define 引用 iconId 数:', len(used_def), '缺图:', len(missing_def))
print('  缺:', dict(sorted(missing_def.items())))

used_wm = {}
for r in m.wm_points.values() if hasattr(m, 'wm_points') else []:
    pass

ids = sorted(used_def)
print('引用到的 iconId:', ids)
print('已有图片:', len(have))

out = ROOT / 'assets' / 'icon' / 'pin'
out.mkdir(parents=True, exist_ok=True)
n = 0
for f in (ROOT / 'work' / 'menuicon_42').glob('*.png'):
    num = f.stem.split('_')[-1]
    if num.isdigit():
        shutil.copy2(f, out / f'{num}.png')
        n += 1
print('导出 pin 图标', n, '->', out)
