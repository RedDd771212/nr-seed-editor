# -*- coding: utf-8 -*-
"""合并 WorldMapPointIconParam 的英文名 + 主人的中文分类，产出 src\\data\\pin_icons.json。"""
import sys, os, json
sys.path.insert(0, r'D:\项目\app\NR地图种子编辑器\src')
from nrseed.paramdir import ParamDir
from nrseed.model import SeedModel

ROOT = r'D:\项目\app\NR地图种子编辑器'
m = SeedModel(ParamDir(os.path.join(ROOT, 'work', 'reg', 'params')))

# iconId: (中文, 类别, attach大小, 可加, 可视, 备注)
ZH = {
    42000: ('赐福', '系统点', None, False, True, '一般不加，只需要知道'),
    42001: ('圣杯教堂', '据点', '小', True, True, '小据点 attach'),
    42002: ('遗迹', '据点', '大', True, True, ''),
    42003: ('大商店', '据点', '小', True, True, ''),
    42004: ('监牢（未开启）', '据点', '未知', False, True, '未知大小，先不加；可视用这个'),
    42005: ('魔法师塔', '据点', '小', True, True, ''),
    42006: ('要塞', '据点', '大', True, True, ''),
    42009: ('营地', '据点', '大', True, True, ''),
    42010: ('主城', '属性容器', '大', False, True, '只规定属性，不摆 attach'),
    42012: ('灵魂鹰', '系统点', None, False, True, '小树上停鹰，可快速穿梭'),
    42015: ('野外BOSS', '据点', '小', True, True, ''),
    42016: ('粪金龟', '据点', '待定', False, True, '添加逻辑未知，挂起'),
    42019: ('未命名 42019', '未使用', None, False, False, ''),
    42020: ('商人', '系统点', None, False, True, 'Merchant'),
    42021: ('魔法师塔·二型', '据点', '小', True, True, 'Sorcerer\'s Rise 2'),
    42022: ('矿坑', '系统点', None, False, True, 'Tunnel Entrance；同赐福'),
    42023: ('教堂', '据点', '大', True, True, 'Great Church'),
    42024: ('商人（鳞片）', '系统点', None, False, True, 'Scale-bearing Merchant'),
    42026: ('洞窟入口', '系统点', None, False, True, 'Cave Entrance'),
    42027: ('野外BOSS（强）', '据点', '小', True, True, 'Field Boss [Hard]'),
    42029: ('监牢（开启）', '据点', '未知', False, False, 'Evergaol [Open]'),
    42030: ('魔法师塔（已解锁）', '标记', None, False, True, ''),
    42031: ('魔法师塔（已清）', '标记', None, False, True, ''),
    42032: ('魔法师塔2（已解锁）', '标记', None, False, True, ''),
    42033: ('魔法师塔2（已清）', '标记', None, False, True, ''),
    42034: ('突变野外BOSS', '据点', '小', True, True, 'Mutated Field Boss'),
    42035: ('突变野外BOSS（强）', '据点', '小', True, True, 'Mutated Field Boss [Hard]'),
    42036: ('监牢（开启·圆形）', '据点', '未知', False, False, ''),
    42040: ('水晶', '事件点', None, False, True, '由 eventFlag 决定'),
    42041: ('水晶簇', '事件点', None, False, True, ''),
    42042: ('神授塔', '系统点', None, False, True, '同赐福'),
    42043: ('大空洞下城', '属性容器', '大', False, True, '只动属性'),
    42044: ('大空洞上城', '属性容器', '大', False, True, '只动属性'),
    42045: ('城塞（小）', '据点', '大', True, True, ''),
    42046: ('圆形遗迹', '据点', '大', True, True, ''),
    42047: ('毒池', '据点', '大', True, True, ''),
    42048: ('锻造村', '据点', '大', True, True, ''),
    42049: ('商人（地下）', '系统点', None, False, True, ''),
    42200: ('任务目标', '系统点', None, False, True, 'Mission Objective'),
    42201: ('地变目标', '系统点', None, False, True, 'Shifting Earth Objective'),
    42202: ('埋藏宝箱', '事件点', None, False, True, 'Buried Treasure；由 eventFlag 决定'),
    42220: ('第二夜树', '系统点', None, False, True, 'Second day tree'),
    42407: ('灵魂气流', '系统点', None, False, True, 'Spiritstream；同赐福'),
}

out = {'version': 1, 'source': 'WorldMapPointIconParam + 主人 m00388/m00403 口授', 'icons': {}}
for cid in sorted({v['iconId'] for v in m.wm_icons.values()} | set(ZH)):
    wm = next((v for v in m.wm_icons.values() if v['iconId'] == cid), None)
    zh = ZH.get(cid)
    if not zh and not wm:
        continue
    entry = {
        'iconId': cid,
        'en': (wm or {}).get('_name') or '',
        'png': f'{cid}.png' if os.path.exists(os.path.join(ROOT, 'assets', 'icon', 'pin', f'{cid}.png')) else None,
    }
    if zh:
        entry.update({'zh': zh[0], 'category': zh[1], 'attachSize': zh[2], 'placeable': zh[3], 'visible': zh[4], 'note': zh[5]})
    else:
        entry.update({'zh': entry['en'], 'category': '未分类', 'attachSize': None, 'placeable': False, 'visible': True, 'note': ''})
    out['icons'][str(cid)] = entry

dst = os.path.join(ROOT, 'src', 'data', 'pin_icons.json')
os.makedirs(os.path.dirname(dst), exist_ok=True)
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print('写入', dst, len(out['icons']), '条；有图', sum(1 for v in out['icons'].values() if v['png']))
