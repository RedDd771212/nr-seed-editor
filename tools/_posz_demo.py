import sys
sys.path.insert(0, r'src')
from PIL import Image, ImageDraw, ImageFont

CELL = 230
GX0, GX1 = 42, 46
GZ0, GZ1 = 36, 40
W = (GX1 - GX0) * CELL
H = (GZ1 - GZ0) * CELL
img = Image.new('RGB', (W + 90, H + 110), (24, 26, 30))
d = ImageDraw.Draw(img)
f = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 22)
fs = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 17)

for gx in range(GX0, GX1):
    for gz in range(GZ0, GZ1):
        x0 = (gx - GX0) * CELL
        y0 = (GZ1 - 1 - gz) * CELL
        d.rectangle((x0, y0, x0 + CELL, y0 + CELL), outline=(70, 74, 84))
        d.text((x0 + 6, y0 + 4), 'X%d/Z%d' % (gx, gz), font=fs, fill=(90, 96, 110))
        cx = x0 + CELL / 2
        cy = y0 + CELL / 2
        d.line((cx - 5, cy, cx + 5, cy), fill=(60, 64, 74))
        d.line((cx, cy - 5, cx, cy + 5), fill=(60, 64, 74))


def put(gx, gz, posx, posz, label, color, dy=26):
    wx = gx * 256 + 128 + posx
    wz = gz * 256 + 128 + posz
    px = (wx - GX0 * 256) / 256 * CELL
    py = (GZ1 * 256 - wz) / 256 * CELL
    r = 7
    d.ellipse((px - r, py - r, px + r, py + r), fill=color)
    tw = d.textlength(label, font=f)
    tx = px + 10 if px + 10 + tw < W else px - 10 - tw
    d.text((tx, py - dy), label, font=f, fill=color)


put(43, 37, 89.7, 62.66, '主城 z=9662.7', (255, 210, 90))
put(45, 38, 44.0, 97.0, '营地 z=9953  (+290)', (120, 220, 140), 30)
put(45, 38, 39.0, -9.0, '教堂 z=9847  (+184)', (255, 140, 140), -8)

d.text((10, H + 16), 'world_z = gridZ*256 + 128 + posZ   ·   上=北', font=f, fill=(200, 205, 215))
d.text((10, H + 50), '主城 37*256+128+62.7=9662.7 / 营地 38*256+128+97=9953 / 教堂 38*256+128-9=9847', font=fs, fill=(150, 156, 170))
d.text((10, H + 76), '两个据点都在主城北侧，营地比教堂再北 106', font=fs, fill=(150, 156, 170))
img.save(r'work\posz_demo.png')
print('ok', img.size)
