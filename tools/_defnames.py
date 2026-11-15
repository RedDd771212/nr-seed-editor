import re

D = r'E:\ERtools\Smithbox_2_2_5_2026_08_29_a\Assets\PARAM\NR\Defs'
for tbl in ('LotResultSmallBaseAndSpot', 'MapPatternSet', 'LotResultMapPatternFlag',
            'SmallBaseMapVariationParam', 'WorldMapPointParam'):
    s = open(D + '\\' + tbl + '.xml', encoding='utf-8').read()
    defs = re.findall(r'<Field Def="([^"]+)"', s)
    pad = [d for d in defs if 'pad' in d]
    print(tbl, '->', pad if pad else '(no pad)')
