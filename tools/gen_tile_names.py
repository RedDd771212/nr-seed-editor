# -*- coding: utf-8 -*-
"""从有名字的 bin 导出 tile（smallBaseMapId）名称表 → src/data/tile_names.json

名字来源是 Smithbox 的社区命名；moremap 那种原始 bin 里 _name 是空的，
所以编辑器统一读这份本地表，读不到才回退 bin。

运行：python tools/gen_tile_names.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from app.core.project import Project  # noqa: E402

OUT = ROOT / 'src' / 'data' / 'tile_names.json'
CANDIDATES = [
    ROOT / 'work' / 'demo' / 'demo_regulation.bin',
    Path(r'C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin'),
]


def find_bin():
    for b in CANDIDATES:
        if b.exists():
            p = Project(str(b))
            v = p.params.rows('SmallBaseMapVariationParam')
            named = sum(1 for r in v.values() if (r.get('_name') or '').strip())
            if named:
                return b, p, named
    return None, None, 0


def main():
    b, p, named = find_bin()
    if not p:
        print('找不到带名字的 bin（work/demo/demo_regulation.bin 存在吗？）')
        return
    print(f'用 {b}（{named} 行有名字）')

    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding='utf-8')).get('tiles') or {}
        except Exception:  # noqa: BLE001
            old = {}

    v = p.params.rows('SmallBaseMapVariationParam')
    tiles = {}
    for tid in sorted(v):
        nm = (v[tid].get('_name') or '').strip()
        prev = old.get(str(tid)) or {}
        entry = {}
        cn = prev.get('cn') or ''
        if cn:
            entry['cn'] = cn
        if nm:
            entry['en'] = nm
        elif prev.get('en'):
            entry['en'] = prev['en']
        if entry:
            tiles[str(tid)] = entry

    data = {
        '_note': 'tile（smallBaseMapId）名称表。en 来自 Smithbox 社区命名，cn 可手工补；'
                 '编辑器的「名称表」界面会改这个文件，改完立即生效。',
        'tiles': tiles,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'写入 {OUT}：{len(tiles)} 个 tile（保留已有中文名 {sum(1 for x in tiles.values() if x.get("cn"))} 个）')


if __name__ == '__main__':
    main()
