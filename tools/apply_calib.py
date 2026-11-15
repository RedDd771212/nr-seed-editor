"""把校准好的坐标固化成 src/data/attach_overrides.json。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402


def main() -> None:
    p = Project(str(ROOT / 'work' / 'reg' / 'base_sot.bin'))
    corr = json.loads((ROOT / 'calib' / 'corrections.json').read_text(encoding='utf-8'))
    deleted = set(json.loads((ROOT / 'src' / 'data' / 'attach_deleted.json')
                             .read_text(encoding='utf-8'))['ids'])

    points = {}
    for it in corr['items']:
        aid = int(it['id'])
        if aid in deleted or it.get('deleted'):
            continue
        w = it.get('world')
        o = it.get('orig')
        if not w or not o:
            continue
        if abs(w[0] - o[0]) < 0.5 and abs(w[1] - o[1]) < 0.5:
            continue          # 没动过
        name = (p.model.attach.get(aid) or {}).get('_name') or it.get('name') or ''
        points[str(aid)] = {
            'world': [round(float(w[0]), 3), round(float(w[1]), 3)],
            'orig': [round(float(o[0]), 3), round(float(o[1]), 3)],
            'name': name.strip(),
        }

    out = {
        'source': 'calib/corrections.json（人工校准，m05210 采纳）',
        'note': 'world 是画布上的世界坐标，只影响显示与摆点，不写回 bin',
        'points': points,
    }
    path = ROOT / 'src' / 'data' / 'attach_overrides.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(len(points), 'overrides ->', path)


if __name__ == '__main__':
    main()
