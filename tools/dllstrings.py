import re,sys
p=r'E:\ERtools\Smithbox_2_2_5_2026_08_29_a\Andre.SoulsFormats.dll'
b=open(p,'rb').read()
s=set(re.findall(rb'[ -~]{4,}', b))
s={x.decode('latin1') for x in s}
pat=re.compile(r'SBLYT|Sprite|SPRITE|Sblyt|Layout', re.I)
hits=sorted([x for x in s if pat.search(x)])
for h in hits[:80]: print(h)
print('total hits', len(hits))
