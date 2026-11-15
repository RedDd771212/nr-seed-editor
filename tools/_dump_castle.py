import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

OX, OZ = 10505.7, 10496.66
m = SeedModel(ParamDir('work/reg/params'))
for s in m.spots_by_pid[80]:
    i = m.describe_spot(s)
    if i['icon'] != 42010:
        continue
    wx, wz = i['world']
    print('row', s['_id'], 'px', round(wx - OX, 2), 'py', round(OZ - wz, 2),
          'grid', i['grid'], 'pos', i['pos'], 'tile', i['tile'], 'attach', i['attachId'],
          'name', i['attachName'])
