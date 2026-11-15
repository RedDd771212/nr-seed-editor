import re,glob,os
for p in sorted(glob.glob(r'D:\项目\app\NR地图种子编辑器\work\sblyt_h\*.layout.bin')):
    s=open(p,encoding='utf-8-sig').read()
    subs=re.findall(r'<SubTexture ([^>]*)/>',s)
    names=[dict(re.findall(r'(\w+)="([^"]*)"',x))['name'] for x in subs]
    base=os.path.basename(p).split('_SB_')[1].replace('.layout.bin','')
    print(f'{base:22s} n={len(names):3d}  {names[:6]}')
