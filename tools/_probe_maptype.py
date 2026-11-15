# -*- coding: utf-8 -*-
"""查 rareMap 与地图类型旗标(76xx) 的对应关系。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel
from app.core.project import DEF_DIR

pd = ParamDir(str(ROOT / 'work' / 'open' / 'regulation_198c55de' / 'params'), str(DEF_DIR))
m = PatternModel(pd)

print('== rareMap -> 地图类型旗标(76xx) ==')
seen = {}
for st in sorted(m.sets.values(), key=lambda s: s.sid):
    if not st.patterns:
        continue
    rows = [r for p in st.patterns for r in p.flags
            if int(r.get('modifierSet') or 0) == 0 and 7600 <= int(r.get('eventFlag') or 0) <= 7699]
    if not rows:
        print('  set %-5s rareMap=%s  没有 76xx 行  %s' % (st.sid, st.rare_map, st.name))
        continue
    flags = tuple(sorted({int(r['eventFlag']) for r in rows}))
    key = (st.rare_map, flags)
    seen.setdefault(key, []).append(st.sid)

for (rare, flags), sids in sorted(seen.items(), key=lambda x: (x[0][0] if x[0][0] is not None else -1)):
    print('  rareMap=%-4s -> %s   例 set %s%s（共 %d 个 set）'
          % (rare, list(flags), sids[:6], ' …' if len(sids) > 6 else '', len(sids)))

print()
print('== 各 set 的 76xx 行里 modifier 是什么 ==')
for st in [m.sets[s] for s in (0, 13, 35, 1004, 1084)]:
    rows = [r for p in st.patterns for r in p.flags
            if int(r.get('modifierSet') or 0) == 0 and 7600 <= int(r.get('eventFlag') or 0) <= 7699]
    print('  set %-5s rareMap=%s  %s -> %s'
          % (st.sid, st.rare_map, st.name,
             sorted({(int(r['eventFlag']), int(r.get('modifier') or 0)) for r in rows})))
