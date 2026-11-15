import sys, struct, collections
import numpy as np

path = sys.argv[1]
data = np.fromfile(path, dtype=np.uint8)
sig = np.frombuffer(b'DDS ', dtype=np.uint8)
# find candidate offsets via a simple sliding search on first 4 bytes
matches = []
n = len(data)
# vectorised search: compare each position window (memory heavy); do chunked
chunk = 64 * 1024 * 1024
start = 0
while start < n:
    end = min(n, start + chunk + 3)
    seg = data[start:end]
    if len(seg) < 4:
        break
    idx = np.flatnonzero((seg[:-3] == sig[0]) & (seg[1:-2] == sig[1]) & (seg[2:-1] == sig[2]) & (seg[3:] == sig[3]))
    for i in idx:
        o = start + int(i)
        if o + 148 > n:
            continue
        hdr = data[o:o + 148].tobytes()
        size, flags, h, w = struct.unpack_from('<IIII', hdr, 4)
        if size != 124 or not (1 <= h <= 8192) or not (1 <= w <= 8192):
            continue
        fourcc = hdr[84:88].decode('latin1')
        dxgi = struct.unpack_from('<I', hdr, 128)[0] if fourcc == 'DX10' else 0
        matches.append((o, w, h, fourcc, dxgi))
    start += chunk

print(f'valid DDS: {len(matches)}')
fmt = collections.Counter((m[3], m[4]) for m in matches)
for k, v in fmt.most_common(20):
    print('  fmt', k, v)
for m in matches[:15]:
    print('  off=0x%X %dx%d fourcc=%r dxgi=%d' % (m[0], m[1], m[2], m[3], m[4]))
