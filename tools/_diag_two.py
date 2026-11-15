import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir('work/reg/params'))

print('=== defines ===')
for did, d in sorted(m.define.items()):
    tiles = [d.get('mapId%d' % i) for i in range(1, 19)]
    tiles = [t for t in tiles if t]
    print(did, repr(d.get('_name'))[:60], 'icon', d.get('worldMapPointIconId1'), 'tiles', tiles[:8])

print('\n=== spots on tiles 3210 / 4100 (pid0) ===')
for s in m.spots_by_pid[0]:
    if s.get('mapId') not in (3210, 4100) and s.get('smallBaseMapId') not in (3210, 4100):
        continue
    ap = m.attach.get(s.get('attachId'), {})
    i = m.describe_spot(s)
    print('tile', s.get('mapId'), 'sbMapId', s.get('smallBaseMapId'), 'attach', s.get('attachId'),
          ap.get('_name'), '-> icon', i['icon'], 'defines', i.get('define_names'))
