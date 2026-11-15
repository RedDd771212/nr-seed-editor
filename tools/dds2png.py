import sys, os, glob
from PIL import Image

src = sys.argv[1]
out = sys.argv[2]
maxpx = int(sys.argv[3]) if len(sys.argv) > 3 else 256
os.makedirs(out, exist_ok=True)
files = sorted(glob.glob(os.path.join(src, '*.dds')))
done = 0
for p in files:
    base = os.path.splitext(os.path.basename(p))[0]
    dst = os.path.join(out, base + '.png')
    if os.path.exists(dst):
        done += 1
        continue
    try:
        im = Image.open(p)
        im.load()
        im = im.convert('RGBA')
        w, h = im.size
        if max(w, h) > maxpx:
            r = maxpx / max(w, h)
            im = im.resize((max(1, round(w * r)), max(1, round(h * r))), Image.LANCZOS)
        im.save(dst)
        done += 1
    except Exception as e:
        print('FAIL', base, type(e).__name__, e)
print(f'converted {done}/{len(files)} -> {out}')
