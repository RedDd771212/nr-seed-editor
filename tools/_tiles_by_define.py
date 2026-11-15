import sys, collections
sys.path.insert(0, r'.')
from app.core.project import Project

p = Project(r'D:\nrtest\base.bin')
rows = list(p.params.rows('LotResultSmallBaseAndSpot').values())
att = p.model.attach
by = collections.defaultdict(lambda: {'tiles': set(), 'attaches': set(), 'sizes': collections.Counter()})
for r in rows:
    a = int(r['attachId'])
    t = int(r['smallBaseMapId'])
    nm = p._define_name(t) or '(no define)'
    d = by[nm]
    d['tiles'].add(t)
    d['attaches'].add(a)
    if a in att:
        d['sizes'][p.model.attach_size(att[a].get('_name', ''))] += 1

for nm, d in sorted(by.items(), key=lambda kv: -len(kv[1]['attaches'])):
    print(f"{nm[:42]:44s} tiles={len(d['tiles']):3d} attaches={len(d['attaches']):3d} sizes={dict(d['sizes'])}")

print('---- 103 的候选类型（全表）----')
for r in rows:
    if int(r['attachId']) == 103:
        print(' ', int(r['smallBaseMapId']), p._define_name(int(r['smallBaseMapId'])))
