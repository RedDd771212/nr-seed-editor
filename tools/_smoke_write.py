# -*- coding: utf-8 -*-
"""端到端冒烟：打开 bin → 造草稿 → 写入测试 bin → 对账。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.project import Project
from app.core import draft as D
from app.core.writeback import write_back

BASE = Path(r'work\reg\base_sot.bin')
p = Project(BASE)
print('params:', p.param_count())
print('bosses:', [(b['id'], b['name']) for b in p.bosses()][:12])

d = D.new_draft(p, 2)
print('draft: set', d.new_set, 'pid', d.new_pid, 'template', d.template_set, d.template_pid)

# 借 pid 80 的地点当草稿内容
info = p.pattern_info(80)
for sp in info['spots'][:4]:
    d.spots.append({'attachId': sp['attachId'], 'tile': sp['tile'],
                    'mapIndex': 0, 'variationId': 0})
print('validate:', D.validate(p, d))

rep = write_back(p, d, target_bin=Path(r'work\test_out.bin'))
print('write ok:', rep['ok'], rep.get('error', ''))
for n, ok in rep['checks']:
    print('  ', n, 'OK' if ok else 'FAIL')
print('out:', rep['out'], rep['target'])
