"""把「已删除」的点统一搬到地图画布外面（主人 m05175 的约定：拖出去 = 不要）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OX, OZ = 10504.44, 10491.71

corr_path = ROOT / 'calib' / 'corrections.json'
corr = json.loads(corr_path.read_text(encoding='utf-8'))
deleted = set(json.loads((ROOT / 'src' / 'data' / 'attach_deleted.json')
                         .read_text(encoding='utf-8'))['ids'])

have = {int(it['id']) for it in corr['items']}
n = 0
for it in corr['items']:
    aid = int(it['id'])
    if aid not in deleted:
        continue
    i = n
    n += 1
    # 画布外左侧：px 从 -640 起，每 50 一行往下排
    px = -640 - (i % 8) * 40
    py = 60 + (i // 8) * 40
    it['deleted'] = True
    it['world'] = [round(OX + px, 3), round(OZ - py, 3)]
    it['moved'] = 0.0
    it['reason'] = it.get('reason') or 'parked-outside'

# 还没在文件里的（理论上不该有）
for aid in sorted(deleted - have):
    i = n
    n += 1
    it = {'id': aid, 'name': '', 'deleted': True, 'moved': 0.0,
          'reason': 'parked-outside',
          'world': [round(OX - 640 - (i % 8) * 40, 3), round(OZ - (60 + (i // 8) * 40), 3)]}
    corr['items'].append(it)

corr_path.write_text(json.dumps(corr, ensure_ascii=False, indent=2), encoding='utf-8')
print('parked', n, 'deleted points outside the canvas')
