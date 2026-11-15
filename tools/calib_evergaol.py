import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel
from PIL import Image
import numpy as np

OX, OZ = 10505.7, 10496.66
m = SeedModel(ParamDir('work/reg/params'))
art = Image.open(r'assets\map\limveld.png').convert('L')
A = np.asarray(art, dtype=np.float32)

offs = []
for s in m.spots_by_pid[80]:
    i = m.describe_spot(s)
    if i['icon'] != 42004:
        continue
    wx, wz = i['world']
    px, py = wx - OX, OZ - wz
    x0, y0 = int(px) - 35, int(py) - 35
    win = A[y0:y0 + 70, x0:x0 + 70]
    if win.size == 0:
        continue
    dark = win < np.percentile(win, 12)          # 最暗的 12% = 圆环
    ys, xs = np.nonzero(dark)
    if len(xs) < 20:
        print('skip', i['attachName'])
        continue
    cx, cy = x0 + xs.mean(), y0 + ys.mean()
    dx, dy = cx - px, cy - py
    offs.append((dx, dy))
    print('%-32s pin=(%7.1f,%7.1f) circle=(%7.1f,%7.1f) d=(%+5.2f,%+5.2f)'
          % (i['attachName'], px, py, cx, cy, dx, dy))

if offs:
    ax = sum(o[0] for o in offs) / len(offs)
    ay = sum(o[1] for o in offs) / len(offs)
    print('median/mean offset dx=%+.2f dy=%+.2f  (n=%d)' % (ax, ay, len(offs)))
    print('=> OX = %.2f, OZ = %.2f' % (OX - ax, OZ + ay))
