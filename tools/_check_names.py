# -*- coding: utf-8 -*-
"""抽样检查重编行 id 之后，行名与 patternId 是否对得上。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import T_FLAG, T_AREA, T_SPOT
from app.core.project import DEF_DIR

d = sorted((ROOT / 'work' / 'verify_work' / 'sessions').glob('*_v1'))[-1] / 'cur' / 'verify'
pd = ParamDir(str(d), str(DEF_DIR))

rows = pd.rows(T_FLAG)
order = pd.order(T_FLAG)
print('flag 行名抽样：')
for k, rid in enumerate(order[:3]):
    r = rows[rid]
    print('   pos%-3d id=%-6d pid=%-4d name=%r' % (k, rid, r['patternId'], r['_name']))
start = next(i for i, rid in enumerate(order) if rows[rid]['patternId'] == 20)
for k in range(start, start + 3):
    rid = order[k]
    r = rows[rid]
    print('   pos%-3d id=%-6d pid=%-4d name=%r' % (k, rid, r['patternId'], r['_name']))

a = pd.rows(T_AREA)
ao = pd.order(T_AREA)
print('playarea 行名抽样：')
for rid in ao[:3]:
    r = a[rid]
    print('   id=%-6d pid=%-4d name=%r' % (rid, r['patternId'], r['_name']))

s = pd.rows(T_SPOT)
so = pd.order(T_SPOT)
print('spot 行名抽样：', [s[rid]['_name'] for rid in so[:4]])
