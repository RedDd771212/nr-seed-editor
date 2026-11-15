import glob,struct,collections,os
c=collections.Counter(); dims=collections.Counter()
for p in glob.glob(r'D:\项目\app\NR地图种子编辑器\work\menu_h\*.dds')[:99999]:
    h=open(p,'rb').read(148)
    if h[:4]!=b'DDS ': print('bad',p); continue
    size,flags,hh,ww=struct.unpack_from('<IIII',h,4)
    fourcc=h[84:88].decode('latin1')
    dxgi=struct.unpack_from('<I',h,128)[0] if fourcc=='DX10' else 0
    c[(fourcc,dxgi)]+=1; dims[(ww,hh)]+=1
print('formats:',c.most_common())
print('dims:',dims.most_common(8))
print('total',sum(c.values()))
