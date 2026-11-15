import sys, collections
sys.path.insert(0, r'.')
from app.core.project import Project

p = Project(r'D:\nrtest\base.bin')
var = p.params.rows('SmallBaseMapVariationParam')
rows = p.params.rows('LotResultSmallBaseAndSpot')

for att in (103, 1103, 2103):
    ids = collections.Counter()
    for k, r in rows.items():
        if r['attachId'] == att:
            ids[r['smallBaseMapId']] += 1
    print('== attach', att, 'slots', len(ids))
    for sb, n in sorted(ids.items()):
        v = var.get(sb)
        if not v:
            print('   %-6s <no variation> n=%d' % (sb, n))
            continue
        icons = [v.get('variationIconId_%d' % i) for i in range(1, 7)]
        print('   %-6s %-30s n=%-3d icons=%s' % (sb, v['_name'], n, icons))
