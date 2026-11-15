import sys, os
sys.path.insert(0, r'D:\项目\app\NR地图种子编辑器\src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

ROOT = r'D:\项目\app\NR地图种子编辑器'
m = SeedModel(ParamDir(ROOT + r'\work\reg\params'))
have = {int(os.path.splitext(f)[0]) for f in os.listdir(ROOT + r'\work\pin_all') if os.path.splitext(f)[0].isdigit()}

ids = sorted({v['iconId'] for v in m.wm_icons.values()})
print('wm 表 iconId 数', len(ids))
miss = [i for i in ids if i not in have]
print('缺图', len(miss), miss)

# define 里实际用到的
used = {}
for r in m.define.values():
    for i in range(1, 4):
        v = r.get(f'worldMapPointIconId{i}')
        if v:
            row = m.wm_icons.get(v)
            if row:
                used[row['iconId']] = used.get(row['iconId'], 0) + 1
print('define 实际用到', len(used), sorted(used))
print('其中缺图', [i for i in used if i not in have])
