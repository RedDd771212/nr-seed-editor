import re
from pathlib import Path

D = Path(r'E:\ERtools\Smithbox_2_2_5_2026_08_29_a\Assets\PARAM\NR\Defs')
s = (D / 'SmallBaseAndSpotAttachPoint.xml').read_text(encoding='utf-8')
defs = re.findall(r'<Field Def="([^"]+)"', s)

SIZES = {'s8': 1, 'u8': 1, 'dummy8': 1, 's16': 2, 'u16': 2,
         's32': 4, 'u32': 4, 'f32': 4, 's64': 8, 'u64': 8, 'f64': 8}
total = 0
for d in defs:
    t = d.split()[0]
    n = 1
    m = re.search(r'\[(\d+)\]', d)
    if m:
        n = int(m.group(1))
    b = re.search(r':(\d+)$', d)
    size = SIZES.get(t, 0)
    if b:
        total += 1            # bitfield 占 1 字节（未跨字节）
    else:
        total += size * n
    print(f'{t:8s} {d:60s} {size*n}')
print('rowSize', total)
