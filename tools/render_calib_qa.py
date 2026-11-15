"""把「保留 / 删除」画成一张对照图，方便一眼看完。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402

OX, OZ = 10504.44, 10491.71
PIN = 8


def main() -> None:
    p = Project(str(ROOT / 'work' / 'reg' / 'base_sot.bin'))
    pad = p.attach_pad()
    deleted = set(json.loads((ROOT / 'src' / 'data' / 'attach_deleted.json')
                             .read_text(encoding='utf-8'))['ids'])

    im = Image.open(ROOT / 'assets' / 'map' / 'limveld.png').convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    font = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 26)

    keep = dell = 0
    for aid, r in p.model.attach.items():
        aid = int(aid)
        if aid >= 1000 or pad.get(aid, 0) != 0:
            continue
        x = r['gridXNo'] * 256 + 128 + r['posX'] - OX
        y = OZ - (r['gridZNo'] * 256 + 128 + r['posZ'])
        if aid in deleted:
            dell += 1
            d.line([x - 7, y - 7, x + 7, y + 7], fill=(255, 40, 40, 235), width=3)
            d.line([x - 7, y + 7, x + 7, y - 7], fill=(255, 40, 40, 235), width=3)
        else:
            keep += 1
            col = (90, 200, 255, 235) if (r.get('_name') or '').startswith('Major') else (110, 230, 160, 235)
            d.ellipse([x - PIN, y - PIN, x + PIN, y + PIN], outline=col, width=3)

    d.rectangle([0, 0, 520, 92], fill=(12, 14, 18, 210))
    d.text((16, 12), f'保留 {keep}（蓝=大据点 绿=小据点）', font=font, fill=(215, 225, 240))
    d.text((16, 50), f'删除 {dell}（红叉）', font=font, fill=(255, 120, 120))
    im.save(ROOT / 'work' / 'calib_qa.png')
    print('keep', keep, 'del', dell, '->', ROOT / 'work' / 'calib_qa.png')


if __name__ == '__main__':
    main()
