import sys
from collections import Counter
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir('work/reg/params'))
for pid in (0, 80):
    c = Counter()
    for s in m.spots_by_pid[pid]:
        i = m.describe_spot(s)
        if i['icon']:
            continue
        nm = (i['name'] or '') + ' | ' + ' / '.join(i['define_names'])
        c[nm[:70]] += 1
    print('pid', pid, len(c), 'kinds')
    for k, v in c.most_common(8):
        print('  %2d  %s' % (v, k))
