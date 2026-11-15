from PIL import Image
import glob
for p in glob.glob(r'D:\项目\app\NR地图种子编辑器\work\menu_h\*.dds')[:3]:
    try:
        im=Image.open(p); im.load(); print(p.split('\\')[-1], im.mode, im.size, 'OK')
    except Exception as e: print(p.split('\\')[-1], type(e).__name__, e)
