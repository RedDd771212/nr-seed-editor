# -*- coding: utf-8 -*-
"""检查：带 variationId 的地点，attrIcon 有没有下发、地图 PNG 里有没有画徽章。"""
import json
import sys
import urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:8779'


def post(path, body):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(API + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=300).read())


def get(path):
    return urllib.request.urlopen(API + path, timeout=300).read()


tree = post('/api3/open', {'path': r'C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin'})
print('sets =', len(tree['sets']))

# 找一个带属性变体的 pid
target = None
for st in tree['sets']:
    for p in st['patterns']:
        t = post('/api3/select', {'pid': p['pid']})
        sv = (t.get('pidInfo') or {}).get('spotView') or []
        attrs = [s for s in sv if s.get('attrIcon')]
        if len(attrs) >= 2:
            target = (st['sid'], p['pid'], len(attrs), attrs[:3])
            break
    if target:
        break

if not target:
    print('没找到带属性变体的种子')
    raise SystemExit

sid, pid, n, sample = target
print(f'set {sid} pid {pid}: 有属性图标的地点 {n} 个')
for s in sample:
    print('   tile', s['tile'], 'attrIcon', s['attrIcon'], 'attrName', s['attrName'], 'px', round(s['px']), 'py', round(s['py']))

png = Path(ROOT / 'work' / '_apicheck.png')
png.write_bytes(get('/api3/map.png'))
im = Image.open(png)
print('map.png 尺寸', im.size)

# 裁一个带属性点的位置放大看
s = sample[0]
x, y = int(s['px']), int(s['py'])
box = (max(0, x - 70), max(0, y - 70), x + 70, y + 70)
crop = im.crop(box).resize((280, 280), Image.NEAREST)
out = ROOT / 'work' / '_attr_crop.png'
crop.save(out)
print('裁剪:', out, box)
