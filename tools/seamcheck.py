import glob,os,sys,numpy as np
from PIL import Image
from pathlib import Path
d=sys.argv[1] if len(sys.argv)>1 else str(Path.home()/'Desktop'/'普通地图')
T={}
for p in glob.glob(d+r'\*.png'):
    n=os.path.splitext(os.path.basename(p))[0].split('_')
    T[(int(n[-2]),int(n[-1]))]=np.asarray(Image.open(p).convert('RGB'),dtype=np.int16)
N=6
print('tiles',len(T))
# in assembled orientation: col=a, row=b, y flipped
def tile(a,b): return T[(a,b)]
dx=[];dy=[]
for a in range(N-1):
    for b in range(N):
        l=tile(a,b)[:,-1,:]; r=tile(a+1,b)[:,0,:]
        dx.append(np.abs(l-r).mean())
for a in range(N):
    for b in range(N-1):
        top=tile(a,b)[0,:,:]      # b=0 is bottom row after flip -> its top edge touches b=1 bottom edge
        bot=tile(a,b+1)[-1,:,:]
        dy.append(np.abs(top-bot).mean())
print('vertical seam diff  mean=%.2f max=%.2f'%(np.mean(dx),np.max(dx)))
print('horizontal seam diff mean=%.2f max=%.2f'%(np.mean(dy),np.max(dy)))
# corner continuity: check if a/b swapped gives better
dx2=[];dy2=[]
for a in range(N-1):
    for b in range(N):
        l=tile(b,a)[:,-1,:]; r=tile(b,a+1)[:,0,:]
        dx2.append(np.abs(l-r).mean())
for a in range(N):
    for b in range(N-1):
        dx2.append(0)
print('swapped mean=%.2f'%np.mean([v for v in dx2]))
