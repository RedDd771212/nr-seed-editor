from PIL import Image, ImageDraw

sheet = Image.new('RGB', (270 * 4, 270 * 2), (20, 20, 22))
for k in range(7):
    try:
        im = Image.open(r'work\eg_%d.png' % k).convert('RGB')
    except FileNotFoundError:
        continue
    d = ImageDraw.Draw(im)
    d.line((125, 135, 145, 135), fill=(255, 60, 60), width=2)
    d.line((135, 125, 135, 145), fill=(255, 60, 60), width=2)
    sheet.paste(im, ((k % 4) * 270, (k // 4) * 270))
sheet.save(r'work\eg_sheet.png')
print('ok')
