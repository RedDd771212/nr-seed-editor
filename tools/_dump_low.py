import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

OX, OZ = 10505.7, 10496.66
m = SeedModel(ParamDir('work/reg/params'))
for s in m.spots_by_pid[80]:
    i = m.describe_spot(s)
    if not i['icon']:
        continue
    wx, wz = i['world']
    px, py = wx - OX, OZ - wz
    if py > 850:
        print('row %5s icon %s px=(%.0f,%.0f) tile=%s attach=%s pos=%s name=%s' % (
            s['_id'], i['icon'], px, py, i['tile'], i['attachId'], i['pos'], i['attachName'][:40]))
