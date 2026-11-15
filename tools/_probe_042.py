"""调查：冻伤遗迹 / 759 野外BOSS / 756-757 楼顶楼底 / 占位 BOSS。"""
import sys
from collections import Counter

sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir  # noqa: E402
from nrseed.model import SeedModel     # noqa: E402

pd = ParamDir('work/reg/params')
m = SeedModel(pd)

var = pd.rows('SmallBaseMapVariationParam')
print('== variation 总数', len(var))

# 1) 找名字里带 frost / frozen / ice 的建筑
hits = []
for vid, r in var.items():
    nm = (r.get('_name') or '')
    low = nm.lower()
    if any(k in low for k in ('frost', 'frozen', 'ice', 'snow', 'rime')):
        hits.append((vid, nm))
print('== 冰/冻 相关 variation:', len(hits))
for vid, nm in hits[:40]:
    print('  ', vid, nm)

# 2) 遗迹类里有没有「带属性」的
ruins = [(vid, r.get('_name')) for vid, r in var.items()
         if 'ruin' in (r.get('_name') or '').lower()]
print('== Ruins 类 variation:', len(ruins))
for vid, nm in ruins:
    icons = [r.get(f'variationIconId_{i}') for i in range(1, 11)]
    print('  ', vid, nm, 'icons', [i for i in icons if i])
