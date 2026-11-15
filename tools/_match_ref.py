import sys
sys.path.insert(0, r'src')
import numpy as np
from PIL import Image
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

REF = r'C:\Users\19803\.dsh\attachments\v1\objects\da\daadf4878ce5b89ab93a8eb5b7dcdf3270a7499792c82637773ea59af8f9c4d6'
ref = Image.open(REF).convert('RGB')
scale = 0.5
ref_s = ref.resize((int(ref.width * scale), int(ref.height * scale), ), Image.LANCZOS)
G = np.array(ref_s.convert('L')).astype(np.float32)
H, W = G.shape

m = SeedModel(ParamDir('work/reg/params'))
pins = []
for s in m.spots_by_pid[0]:
    i = m.describe_spot(s)
    if not i['icon']:
        continue
    ap = m.attach.get(i['attachId'], {})
    if not ap:
        continue
    pins.append((round(ap['gridXNo'] * 256 + ap['posX'] - 10377.7),
                 round(10368.66 - (ap['gridZNo'] * 256 + ap['posZ'])),
                 i['icon'], (m.variation.get(s['smallBaseMapId']) or {}).get('_name')))

results = []
for px, py, icon, vname in pins:
    try:
        ic = Image.open(rf'assets\icon\pin\{icon}.png').convert('RGBA')
    except FileNotFoundError:
        continue
    bg = Image.new('RGBA', ic.size, (0, 0, 0, 0))
    bg.alpha_composite(ic)
    tw = max(10, int(ic.width * scale * 88 / 88))
    th = max(10, int(ic.height * scale))
    T = np.array(bg.convert('L').resize((tw, th), Image.LANCZOS)).astype(np.float32)
    mask = np.array(bg.split()[3].resize((tw, th), Image.LANCZOS)).astype(np.float32) / 255.0
    if mask.sum() < 20:
        continue
    win = np.lib.stride_tricks.sliding_window_view(G, (th, tw))
    wmean = win.mean(axis=(2, 3), keepdims=True)
    wstd = win.std(axis=(2, 3), keepdims=True) + 1e-3
    Tm = (T * mask).sum() / mask.sum()
    Tn = (T - Tm) * mask
    tn = np.sqrt((Tn * Tn).sum()) + 1e-6
    num = (win * Tn).sum(axis=(2, 3)) - wmean[:, :, 0, 0] * Tn.sum()
    den = wstd[:, :, 0, 0] * tn
    corr = num / den
    idx = np.unravel_index(np.argmax(corr), corr.shape)
    best = float(corr[idx])
    results.append((icon, vname, px, py, idx[1], idx[0], round(best, 3)))

print('icon  var  our(px,py)  ref(px,py)  score')
for r in sorted(results, key=lambda r: -r[6]):
    print(r)
