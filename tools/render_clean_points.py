"""把删完剩下的 47 个建筑位画成一张干净的图。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402

OX, OZ = 10504.44, 10491.71
COLOR = {
    'Major Base': (77, 163, 255),
    'Minor Base': (65, 209, 138),
    'Field Boss': (176, 107, 216),
    'Evergaol': (224, 163, 60),
    'Castle': (226, 85, 91),
}


def main() -> None:
    p = Project(str(ROOT / 'work' / 'reg' / 'base_sot.bin'))
    pad = p.attach_pad()
    drop = p.deleted_attach()

    rows = []
    for ap in p.attach_points():          # 已应用的校准坐标
        nm = (ap['attachName'] or '').strip()
        kind = re.split(r'\s*-\s*', nm)[0].strip()
        rows.append((ap['attachId'], nm, kind,
                     ap['world'][0] - OX, OZ - ap['world'][1]))

    im = Image.open(ROOT / 'assets' / 'map' / 'limveld.png').convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    f_name = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 17)
    f_leg = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 22)

    i = 0
    for aid, nm, kind, x, y in rows:
        col = COLOR.get(kind, (200, 200, 200))
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(10, 12, 16, 220), width=5)
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=col + (255,), width=3)
        d.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=col + (255,))
        parts = re.split(r'\s*-\s*', nm, maxsplit=1)
        short = parts[1] if len(parts) > 1 else nm
        if len(short) > 24:
            short = short[:23] + '…'
        dy = -24 if (i % 2) else 8
        d.text((x + 13, y + dy + 1), short, font=f_name, fill=(18, 20, 24, 235))
        d.text((x + 12, y + dy), short, font=f_name, fill=(245, 246, 250, 240))
        i += 1

    # 图例
    lx, ly = 26, 26
    d.rectangle([lx - 12, ly - 12, lx + 330, ly + 34 * len(COLOR) + 12], fill=(10, 12, 16, 200))
    for i, (kind, col) in enumerate(COLOR.items()):
        yy = ly + i * 34
        d.ellipse([lx, yy, lx + 16, yy + 16], outline=col, width=3)
        n = sum(1 for r in rows if r[2] == kind)
        d.text((lx + 26, yy - 3), f'{kind}  ×{n}', font=f_leg, fill=(225, 231, 240))

    out = ROOT / 'work' / 'attach_clean.png'
    im.save(out)
    print(len(rows), 'points ->', out)


if __name__ == '__main__':
    main()


