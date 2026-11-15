import re,glob,os
for key in ['SB_MapCursor_0','SB_MenuIcon_0','SB_StatusIcon_0']:
    for p in glob.glob(r'D:\项目\app\NR地图种子编辑器\work\sblyt_l\*'+key+'*.layout.bin'):
        s=open(p,encoding='utf-8-sig').read()
        subs=re.findall(r'<SubTexture ([^>]*)/>',s)
        names=[dict(re.findall(r'(\w+)="([^"]*)"',x))['name'] for x in subs]
        print(f'== {key} n={len(names)}')
        print('  ', names[:12])
