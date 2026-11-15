import sys, os, re, glob
from PIL import Image

# usage: cut_atlas.py <layout.xml> <atlas.png> <outdir> [prefix1,prefix2]
layout_path, atlas_path, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
prefixes = sys.argv[4].split(',') if len(sys.argv) > 4 else ['KG_MENU', 'KG_TEX']
os.makedirs(outdir, exist_ok=True)

xml = open(layout_path, encoding='utf-8-sig').read()
atlas = Image.open(atlas_path).convert('RGBA')
print('atlas', atlas.size, os.path.basename(atlas_path))

subs = re.findall(r'<SubTexture ([^>]*)/>', xml)
rows = []
for s in subs:
    d = dict(re.findall(r'(\w+)="([^"]*)"', s))
    name = d.get('name', '')
    if not any(name.startswith(p) for p in prefixes):
        continue
    x, y = int(d['x']), int(d['y'])
    w, h = int(d['width']), int(d['height'])
    ow, oh = int(d.get('originalWidth', w)), int(d.get('originalHeight', h))
    img = atlas.crop((x, y, x + w, y + h))
    bbox = img.split()[3].getbbox()
    if bbox:
        img = img.crop(bbox)
    stem = os.path.splitext(name)[0]
    out = os.path.join(outdir, stem + '.png')
    img.save(out)
    rows.append((stem, x, y, w, h, ow, oh, img.size))

print(f'cut {len(rows)} sprites -> {outdir}')
for r in rows:
    print('  %-22s rect=(%4d,%4d %3dx%3d) orig=%dx%d out=%dx%d' % r)
