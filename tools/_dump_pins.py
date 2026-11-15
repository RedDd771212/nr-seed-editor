import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir('work/reg/params'))
rows = []
for s in m.spots_by_pid[0]:
    i = m.describe_spot(s)
    if not i['icon']:
        continue
    ap = m.attach.get(i['attachId'], {})
    wx = ap['gridXNo'] * 256 + ap['posX']
    wz = ap['gridZNo'] * 256 + ap['posZ']
    rows.append((round(wx - 10377.7), round(10368.66 - wz), i['icon'],
                 i['attachName'][:38], ap['gridXNo'], ap['gridZNo']))
for r in sorted(rows, key=lambda r: -r[0]):
    print('%5d %5d %s %-40s gx=%s gz=%s' % r)
