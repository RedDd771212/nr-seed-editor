"""调查 759 / 756 / 757 三个 attach。"""
import sys
from collections import Counter

sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir  # noqa: E402
from nrseed.model import SeedModel     # noqa: E402

pd = ParamDir('work/reg/params')
m = SeedModel(pd)

att = pd.rows('SmallBaseAndSpotAttachPoint')
for want in (759, 756, 757, 754, 755):
    r = att.get(want)
    if not r:
        print(want, '（没有这个 attach）')
        continue
    print(want, r.get('_name'), 'grid', r.get('gridXNo'), r.get('gridZNo'))

print()
for want in (759, 756, 757):
    pairs = Counter()
    for pid, rows in m.spots_by_pid.items():
        for s in rows:
            if s['attachId'] == want:
                pairs[s.get('smallBaseMapId')] += 1
    print(f'== attach {want} 出现在 {sum(pairs.values())} 个地点 / {len(pairs)} 种 tile')
    for t, n in pairs.most_common(30):
        nm = (m.variation.get(t) or {}).get('_name') if hasattr(m, 'variation') else ''
        print(f'   tile {t}  x{n}  var={nm}')

