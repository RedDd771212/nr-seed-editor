import re,glob
for p in glob.glob(r'D:\项目\app\NR地图种子编辑器\work\sblyt_h\*MainMenu_02*.layout.bin'):
    s=open(p,encoding='utf-8-sig').read()
    print(re.search(r'imagePath="([^"]*)"',s).group(1))
    for x in re.findall(r'<SubTexture ([^>]*)/>',s):
        d=dict(re.findall(r'(\w+)="([^"]*)"',x))
        print('  %-24s x=%-5s y=%-5s w=%-5s h=%-5s ow=%s oh=%s half=%s'%(d['name'],d['x'],d['y'],d['width'],d['height'],d.get('originalWidth'),d.get('originalHeight'),d.get('half')))
