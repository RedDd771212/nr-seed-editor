"""按的思路，把该删的 attach 点标成 deleted。

人工校准的做法：不要的点直接拖到地图外面。按这个思路归纳成规则，
再逐条核对（用过的点会被标出来），最后写进 calib/corrections.json，
并额外导出 src/data/attach_deleted.json 给编辑器用。
"""
from __future__ import annotations

import json
import sys
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project  # noqa: E402

BIN = str(ROOT / 'work' / 'reg' / 'base_sot.bin')

# 拖到图外的那批，按「名字前缀」归纳（m05074）
DEL_PREFIX = (
    'Night Horde -',        # 夜之军团：不是建筑
    'Event -',              # 事件点：由 eventFlag 决定
    'Night Boss',           # 夜晚 BOSS 槽：固定
    'Starter Major Base',   # 出生点同位置孪生（正式点已存在）
    'Starter Minor Base',
)


def main() -> None:
    p = Project(BIN)
    pad = p.attach_pad()
    used = collections.Counter(int(s['attachId']) for s in p.model.spots)

    corr_path = ROOT / 'calib' / 'corrections.json'
    corr = json.loads(corr_path.read_text(encoding='utf-8'))

    attach = {int(k): v for k, v in p.model.attach.items()}

    def name_of(aid: int) -> str:
        return (attach.get(aid, {}).get('_name') or '').strip()

    # ① 亲手拖出去的
    mine = {int(it['id']) for it in corr['items']
            if it.get('deleted') or not (-64 <= (it.get('world') or [0])[0] <= 0 or True)}

    def outside(it) -> bool:
        w = it.get('world') or [0, 0]
        return not (10752 - 32 <= w[0] <= 11776 + 32 and 9216 - 32 <= w[1] <= 10240 + 32)

    mine = {int(it['id']) for it in corr['items'] if it.get('deleted') or outside(it)}

    # ② 按名字前缀扩充
    by_prefix = set()
    for aid in attach:
        nm = name_of(aid)
        if nm.startswith(DEL_PREFIX):
            by_prefix.add(aid)

    # ③ 没名字的野外BOSS槽（Field Boss - 且没被任何官方种子用到）
    fb_empty = {aid for aid in attach
                if name_of(aid) == 'Field Boss -' and used.get(aid, 0) == 0}

    # ④ 所有「没名字、也没被任何官方种子用过」的点（m05138：要删）
    junk_unnamed = {aid for aid in attach
                    if not name_of(aid) and used.get(aid, 0) == 0}

    delete = mine | by_prefix | fb_empty | junk_unnamed

    # 已经在他文件里的，改 flag；不在文件里的，补一条（保留原坐标）
    have = {int(it['id']) for it in corr['items']}
    for aid in sorted(delete - have):
        r = attach.get(aid) or {}
        corr['items'].append({
            'id': aid,
            'name': (r.get('_name') or '').strip(),
            'deleted': True,
            'world': [r.get('gridXNo', 0) * 256 + 128 + r.get('posX', 0),
                      r.get('gridZNo', 0) * 256 + 128 + r.get('posZ', 0)],
            'moved': 0.0,
            'reason': 'blue-whale-rule',
        })
    for it in corr['items']:
        if int(it['id']) in delete:
            it['deleted'] = True

    corr_path.write_text(json.dumps(corr, ensure_ascii=False, indent=2), encoding='utf-8')

    # 导出给编辑器
    out = ROOT / 'src' / 'data' / 'attach_deleted.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        'note': '这些 attach 点按m05074 的思路不参与编辑（删除标记，不是改 bin）',
        'ids': sorted(delete),
        'rules': [
            'Night Horde - / Event - / Night Boss / Starter Major Base / Starter Minor Base 全部删',
            'Field Boss - 且没有被任何官方种子用到 → 删',
            '700~899 的无名点 → 删',
            '其余按手工拖到图外',
        ],
        'byCategory': {
            'NightHorde': sum(1 for a in delete if name_of(a).startswith('Night Horde -')),
            'Event': sum(1 for a in delete if name_of(a).startswith('Event -')),
            'NightBoss': sum(1 for a in delete if name_of(a).startswith('Night Boss')),
            'Starter': sum(1 for a in delete if name_of(a).startswith('Starter ')),
            'FieldBossUnused': len(fb_empty & delete),
            'UnnamedJunk': len(junk_unnamed & delete),
        },
        'usedByOfficial': sorted(a for a in delete if used.get(a, 0) > 0),
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'手标 {len(mine)}')
    print(f'按名字前缀 {len(by_prefix)}')
    print(f'没被用过的野外BOSS槽 {len(fb_empty)}')
    print(f'700/800 无名点 {len(junk_unnamed)}')
    print(f'合计删除 {len(delete)} 个 attach 点')
    print('其中被官方种子用过的：', len([a for a in delete if used.get(a, 0) > 0]))
    print('导出 →', out)


if __name__ == '__main__':
    main()

