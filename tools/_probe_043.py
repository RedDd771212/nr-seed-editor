"""列出所有带属性图标(426xx)的 variation，按图标分组。"""
import sys
from collections import defaultdict

sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir  # noqa: E402

pd = ParamDir('work/reg/params')
var = pd.rows('SmallBaseMapVariationParam')

by_icon = defaultdict(list)
for vid, r in var.items():
    for i in range(1, 11):
        ic = r.get(f'variationIconId_{i}')
        if ic:
            by_icon[ic].append((vid, r.get('_name'), i, r.get(f'variationValue_{i}')))
            break

for ic in sorted(by_icon):
    rows = by_icon[ic]
    print(f'== icon {ic}  ({len(rows)} 个)')
    for vid, nm, slot, val in rows:
        print(f'   {vid}  {nm}  slot={slot} value={val}')
