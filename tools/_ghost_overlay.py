import sys
sys.path.insert(0, r'src')
from PIL import Image
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

ROOT = '.'
m = SeedModel(ParamDir('work/reg/params'))
base = Image.open(r'assets\map\limveld.png').convert('RGBA')
W, H = base.size
OX, OZ = 10377.7, 10368.66
PIN = 88
GHOST = 0.45

pins = []
for s in m.spots_by_pid[0]:
    i = m.describe_spot(s)
    if not i['icon']:
        continue
    ap = m.attach.get(i['attachId'], {})
    if not ap:
        continue
    wx = ap['gridXNo'] * 256 + ap['posX']
    wz = ap['gridZNo'] * 256 + ap['posZ']
    pins.append((wx - OX, OZ - wz, i['icon']))

for x, y, icon in pins:
    try:
        ic = Image.open(rf'assets\icon\pin\{icon}.png').convert('RGBA')
    except FileNotFoundError:
        continue
    ic.thumbnail((PIN, PIN))
    a = ic.split()[3].point(lambda v: int(v * GHOST))
    ic.putalpha(a)
    base.alpha_composite(ic, (int(x - ic.width / 2), int(y - ic.height / 2)))

base.convert('RGB').save(r'work\seed_0_ghost.png')
base.convert('RGB').crop((1000, 380, 1400, 760)).resize((1200, 1140)).save(r'work\z_ghost_camp.png')
print('ok', len(pins))
