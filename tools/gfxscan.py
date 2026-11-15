import sys,glob,os
for p in sys.argv[1:]:
    b=open(p,'rb').read()
    print(os.path.basename(p), 'size', len(b), 'FWS', b[:3].decode('latin1','ignore'),
          'JPEG', b.count(b'\xff\xd8\xff'), 'PNG', b.count(b'\x89PNG'), 'DDS', b.count(b'DDS '))
