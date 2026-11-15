import sys
sys.path.insert(0, r'src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

m = SeedModel(ParamDir('work/reg/params'))
for aid in (116, 313, 302, 300):
    ap = m.attach[aid]
    print(aid, repr(ap.get('_name')))
    print('   gridX', ap['gridXNo'], 'posX', round(ap['posX'], 2),
          'gridZ', ap['gridZNo'], 'posZ', round(ap['posZ'], 2))
print()
for s in m.spots_by_pid[0]:
    if s.get('attachId') in (116, 313):
        ap = m.attach[s['attachId']]
        print(s['attachId'], 'sbMapId', s['smallBaseMapId'], 'var', repr((m.variation.get(s['smallBaseMapId']) or {}).get('_name')),
              'mapIndex', s.get('mapIndex'), 'variationId', s.get('variationId'))
