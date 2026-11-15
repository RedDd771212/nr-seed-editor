import glob,os,numpy as np
from PIL import Image
d=r'C:\Users\19803\Desktop\普通地图'
T={}
for p in glob.glob(d+r'\*.png'):
    n=os.path.splitext(os.path.basename(p))[0].split('_')
    T[(int(n[-2]),int(n[-1]))]=np.asarray(Image.open(p).convert('RGB'),dtype=np.int16)
N=6
def score(dy_off, dx_off):
    vals=[]
    for a in range(N-1):
        for b in range(N):
            A=T[(a,b)]; B=T[(a+1,b)]
            # compare column pairs with vertical offset dy_off of B
            y0=max(0,dy_off); y1=256+min(0,dy_off)
            l=A[y0:y1,-1,:]; r=B[y0-dy_off:y1-dy_off,0,:]
            vals.append(np.abs(l-r).mean())
    return np.mean(vals)
best=[]
for dy in range(-4,5):
    best.append((score(dy,0),dy))
best.sort()
print('best vertical offsets (score, dy):', best[:5])
def scoreh(dx_off):
    vals=[]
    for a in range(N):
        for b in range(N-1):
            A=T[(a,b)]; B=T[(a,b+1)]
            x0=max(0,dx_off); x1=256+min(0,dx_off)
            t=A[0,x0:x1,:]; bot=B[-1,x0-dx_off:x1-dx_off,:]
            vals.append(np.abs(t-bot).mean())
    return np.mean(vals)
bh=[(scoreh(dx),dx) for dx in range(-4,5)]
bh.sort()
print('best horizontal offsets (score, dx):', bh[:5])
