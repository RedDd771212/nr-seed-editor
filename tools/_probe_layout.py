from PIL import Image
import re, glob, os

ATLAS = r'D:\项目\app\NR地图种子编辑器\work\atlas_png'
SBLYT = r'D:\项目\app\NR地图种子编辑器\work\sblyt_l'

for f in ['SB_MenuIcon_0', 'SB_MenuIcon_1', 'SB_KG_0', 'SB_MapCursor_0', 'SB_MapCursor_02_0']:
    im = Image.open(os.path.join(ATLAS, f + '.png'))
    print(f, im.size, im.mode)

for p in glob.glob(os.path.join(SBLYT, '*MenuIcon*.layout.bin')) + glob.glob(os.path.join(SBLYT, '*MapCursor*.layout.bin')):
    head = open(p, 'rb').read(400).decode('utf-8', 'replace')
    m = re.search(r'width="(\d+)"\s+height="(\d+)"', head)
    name = os.path.basename(p)
    print(name[-40:], m.groups() if m else head[:200])
