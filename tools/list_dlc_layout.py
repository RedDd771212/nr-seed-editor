import re
p=r'D:\项目\app\NR地图种子编辑器\work\sblyt_dlc\W__CL_data_Target_INTERROOT_win64_menu_ScaleForm_Tif_21_Common_DLC01_High_SB_KG_DLC01_0.layout.bin'
s=open(p,encoding='utf-8-sig').read()
subs=re.findall(r'<SubTexture ([^>]*)/>',s)
print('total',len(subs))
for x in subs:
    d=dict(re.findall(r'(\w+)="([^"]*)"',x)); print(d['name'], d['x'],d['y'],d['width'],d['height'])
