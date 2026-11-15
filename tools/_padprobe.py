import sys
from collections import Counter

sys.path.insert(0, r'.')
from app.core.project import Project

p = Project(r'D:\nrtest\base.bin')
pd = p.params
b = open(str(p.param_dir / 'SmallBaseAndSpotAttachPoint.param'), 'rb').read()
_, ents, rowsize = pd._read_table(b)

m = p.model
used = set()
for pid in (0, 80):
    for s in m.spots_by_pid.get(pid, []):
        used.add(int(s['attachId']))

rows = m.attach
c = Counter()
for rid, doff, noff in ents:
    pad = b[doff + 8]
    ap = rows.get(rid) or {}
    dsb = ap.get('defaultSmallBase')
    special = isinstance(dsb, int) and 2000 <= dsb < 2200
    c[(pad, app := ('used' if rid in used else 'unused'), special)] += 1

for k in sorted(c):
    print(k, c[k])
