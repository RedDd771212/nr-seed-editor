import sys, collections
sys.path.insert(0, r'.')
from app.core.project import Project

p = Project(r'D:\nrtest\base.bin')
var = p.params.rows('SmallBaseMapVariationParam')
defs = list(p.params.rows('SmallBaseAndSpotDefine').values())
wmi = p.params.rows('WorldMapPointIconParam')
rows = p.params.rows('LotResultSmallBaseAndSpot')

by_tile = {}
for d in defs:
    for i in range(1, 19):
        t = d.get('mapId%d' % i)
        if t is not None and t > 0:
            by_tile.setdefault(t, d)

print('%-6s %-30s %-12s %-8s %-8s %s' % ('sbId', 'variation name', 'defname', 'bicon', 'attr', 'variationId'))
seen = set()
for k, r in rows.items():
    sb = r['smallBaseMapId']
    key = (sb, r['variationId'])
    if key in seen:
        continue
    seen.add(key)
    v = var.get(sb)
    d = by_tile.get(sb)
    bicon = None
    if d:
        wi = d.get('worldMapPointIconId1')
        bicon = wmi[wi]['iconId'] if wi in wmi else None
    vid = r['variationId']
    attr = v.get('variationIconId_%d' % (vid + 1)) if v else None
    print('%-6s %-30s %-12s %-8s %-8s %d' % (
        sb, (v['_name'] if v else '?'), (d['_name'].replace('Encounter Setup: ', '') if d else '-'),
        bicon, attr, vid))
    if len(seen) > 26:
        break
