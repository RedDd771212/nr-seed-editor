import sys,collections,math
p=sys.argv[1]
b=open(p,'rb').read()
print('size',len(b))
for m in [b'TPF\0',b'DCX\0',b'KRAK',b'DFLT',b'ZSTD',b'BHF4',b'BDF4',b'DDS ']:
    print(m, b.count(m))
seg=b[0:2000000]
c=collections.Counter(seg)
ent=-sum((v/len(seg))*math.log2(v/len(seg)) for v in c.values())
print('entropy first 2MB: %.3f bits/byte'%ent)
print('first 64 bytes:', b[:64].hex(' '))
