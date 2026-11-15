import re,sys,collections
p=r'D:\项目\app\NR地图种子编辑器\work\sblyt_h\W__CL_data_Target_INTERROOT_win64_menu_ScaleForm_Tif_01_Common_High_SB_KG_0.layout.bin'
s=open(p,encoding='utf-8').read()
subs=re.findall(r'<SubTexture ([^>]*)/>',s)
print('subtextures:',len(subs))
names=[dict(re.findall(r'(\w+)="([^"]*)"',x))['name'] for x in subs]
print('first 10:',names[:10])
pref=collections.Counter(n.split('_')[0]+'_'+n.split('_')[1] for n in names)
print(pref)
# print all names grouped
for n in names: print(n)
