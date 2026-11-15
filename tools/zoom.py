from PIL import Image
im=Image.open(r'D:\项目\app\NR地图种子编辑器\work\stitch_col_row_flip.png')
crop=im.crop((240,240,272,272)).resize((320,320),Image.NEAREST)
crop2=im.crop((492,492,524,524)).resize((320,320),Image.NEAREST)
crop.save(r'D:\项目\app\NR地图种子编辑器\work\seam_zoom1.png')
crop2.save(r'D:\项目\app\NR地图种子编辑器\work\seam_zoom2.png')
print('ok')
