import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel
from PIL import Image

OX, OZ = 10505.7, 10496.66
m = SeedModel(ParamDir('work/reg/params'))
art = Image.open(r'assets\map\limveld.png').convert('RGB')
n = 0
for s in m.spots_by_pid[80]:
    i = m.describe_spot(s)
    if i['icon'] != 42004:
        continue
    wx, wz = i['world']
    px, py = wx - OX, OZ - wz
    print('row', s['_id'], 'px', round(px, 1), 'py', round(py, 1), i['attachName'])
    art.crop((px - 45, py - 45, px + 45, py + 45)).resize((270, 270)).save(
        r'work\eg_%d.png' % n)
    n += 1
