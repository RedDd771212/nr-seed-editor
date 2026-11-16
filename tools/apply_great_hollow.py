# -*- coding: utf-8 -*-
"""把大空洞的校准结果落成编辑器数据：
   1) 往 great_hollow_layers.json 里写 4 个「组」的配套表（只留代表点）
   2) 生成 maps.json 的 great_hollow 档案（attachPool + overrides）
运行：python tools/apply_great_hollow.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LAYERS = ROOT / 'src' / 'data' / 'great_hollow_layers.json'
MAPS = ROOT / 'src' / 'data' / 'maps.json'

# 2026-11-16 实测：80 个大空洞种子里 4 组 100% 整组出现，tile 固定配套
GROUPS = [
    {
        'name': '上城属性', 'rep': 1141, 'members': [1141, 1142, 1143, 1144],
        'sets': [[5358, 5354, 5362, 5350], [5359, 5357, 5363, 5351]],
        'labels': ['Fire 一套', 'Magic 一套'],
    },
    {
        'name': '上城地下', 'rep': 1145, 'members': [1145, 1146, 1147, 1148],
        'sets': [[5360, 5364, 5352, 5355], [5360, 5364, 5352, 5356],
                 [5361, 5349, 5353, 5355], [5361, 5349, 5353, 5356]],
        'labels': ['5360/5364/5352 + 5355', '5360/5364/5352 + 5356',
                   '5361/5349/5353 + 5355', '5361/5349/5353 + 5356'],
    },
    {
        'name': '下城属性', 'rep': 1135, 'members': [1135, 1136, 1137],
        'sets': [[5367, 5380, 5381], [5368, 5382, 5383]],
        'labels': ['Rot 一套', 'Holy 一套'],
    },
    {
        'name': '下城地下', 'rep': 1138, 'members': [1138, 1139, 1140],
        'sets': [[5370, 5386, 5387], [5371, 5388, 5389], [5372, 5390, 5391]],
        'labels': ['一套', '二套', '三套'],
    },
]


def main():
    layers = json.loads(LAYERS.read_text(encoding='utf-8'))
    deleted = set(layers['deleted'])

    # 代表点 = 组内「没有被标删除」的那一个（主人在校准器里每组只留一个）
    for g in GROUPS:
        alive = [a for a in g['members'] if a not in deleted]
        if len(alive) == 1:
            g['rep'] = alive[0]
        elif not alive:
            print(f"!! 「{g['name']}」整组都被删了，跳过")
            g['rep'] = None
        else:
            print(f"!! 「{g['name']}」还剩 {alive} 个没删，暂时用 {alive[0]} 当代表")
            g['rep'] = alive[0]
    GROUPS[:] = [g for g in GROUPS if g['rep']]

    # 校验：每个 set 的 tile 个数必须等于 members 个数
    for g in GROUPS:
        for s in g['sets']:
            assert len(s) == len(g['members']), f"{g['name']} 配套表长度不对"
    layers['groups'] = GROUPS
    layers['note'] = ('attachId 列表是最终规则；deleted 不显示；moved 是 [world_x, world_z]；'
                      'groups 里只显示 rep 一个点，改它时同组按 sets 配套')
    LAYERS.write_text(json.dumps(layers, ensure_ascii=False, indent=2), encoding='utf-8')

    group_members = {a: g for g in GROUPS for a in g['members']}
    deleted = set(layers['deleted'])
    # 修复历史污染：surface / under 里如果混进了「删过」的点，踢掉
    # （之前为了“白圈显示”把恢复的点写回了 surface，导致它们进了随机池）
    fixed_s = [a for a in layers['surface'] if a not in deleted]
    fixed_u = [a for a in layers['under'] if a not in deleted]
    if len(fixed_s) != len(layers['surface']) or len(fixed_u) != len(layers['under']):
        print(f'清掉 layers 里混入的删除点：surface {len(layers["surface"])}→{len(fixed_s)}，'
              f'under {len(layers["under"])}→{len(fixed_u)}')
    layers['surface'], layers['under'] = sorted(fixed_s), sorted(fixed_u)

    # 校准留下的点（随机池只认这个）
    show = [a for a in (layers['surface'] + layers['under'])
            if a not in group_members or a == group_members[a]['rep']]
    # 显示用的池 = 留下的 + 恢复显示的白圈点
    extra = sorted(a for a in deleted if a not in group_members)
    pool = sorted(set(show) | set(extra))
    layers['calibrated'] = show
    print(f'校准留下的点 {len(show)} 个；显示池 {len(pool)} 个（含恢复显示 {len(extra)} 个）')

    # 三类颜色：蓝=城+塔，绿=野外BOSS+据点，白=其他
    BLUE = [1111, 1112, 1113, 1114, 1115, 1116,          # 双塔
            1135, 1138, 1143, 1146]                        # 上城 / 下城的组代表点
    GREEN = [1150, 1151, 1152, 1153,                       # 据点 Minor Base
             1155, 1156, 1157, 1158, 1159, 1160, 1161, 1162, 1163, 1164, 1165]  # 野外 BOSS
    types = {'blue': sorted(a for a in BLUE if a in pool),
             'green': sorted(a for a in GREEN if a in pool),
             'white': sorted(a for a in pool if a not in BLUE and a not in GREEN)}
    for g in GROUPS:
        print(f"  组「{g['name']}」代表 = {g['rep']}")

    def _keep(a):
        return a not in group_members or a == group_members[a]['rep']

    maps = json.loads(MAPS.read_text(encoding='utf-8'))
    prof = {
        'name': '大空洞（Great Hollow）',
        'bg': 'great_hollow.png',
        'bgUnder': 'great_hollow_b1.png',
        'terrain': '[Great Hollow]',
        'attachPool': pool,
        'calibrated': layers['calibrated'],      # 校准留下的点（随机池只认这个）
        'overrides': {str(k): v for k, v in (layers.get('moved') or {}).items()},
        'layers': {'surface': sorted(a for a in layers['surface'] if _keep(a)),
                   'under': sorted(a for a in layers['under'] if _keep(a))},
        'groups': {str(g['rep']): g for g in GROUPS},
        'types': types,
    }
    maps['maps']['great_hollow'] = prof
    prof['playareaIds'] = [11000, 11001, 11002, 12000, 12001]   # 缩圈点（不依赖行名，见 server_v3）
    MAPS.write_text(json.dumps(maps, ensure_ascii=False, indent=2), encoding='utf-8')
    print('maps.json 已更新 great_hollow：', pool)
    print('overrides（挪过的）:', len(prof['overrides']))
    print('层：地表', len(prof['layers']['surface']), '地底', len(prof['layers']['under']))


if __name__ == '__main__':
    main()
