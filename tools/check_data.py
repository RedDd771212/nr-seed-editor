# -*- coding: utf-8 -*-
"""校验 src/data 下的数据表：能解析、关键字段齐、引用对得上。

CI 里会跑；本地改完数据表也可以直接跑一遍：
    python tools/check_data.py
退出码 0 = 通过，1 = 有问题（会打印到 stdout）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'src' / 'data'

# Windows 的 CI（cp1252 控制台）打印中文会炸，统一成 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

errors: list[str] = []
warns: list[str] = []


def load(name):
    p = DATA / name
    if not p.exists():
        errors.append(f'{name}: 文件不存在')
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as e:
        errors.append(f'{name}: JSON 解析失败（{e}）')
        return None


def main() -> int:
    # 1) 所有 json 必须能解析
    jsons = sorted(DATA.glob('*.json'))
    for p in jsons:
        try:
            json.loads(p.read_text(encoding='utf-8-sig'))
        except json.JSONDecodeError as e:
            errors.append(f'{p.name}: JSON 解析失败（{e}）')
    print(f'· 解析 {len(jsons)} 个 json')

    # 2) 地图档案
    maps = load('maps.json')
    if maps:
        items = maps.get('maps')
        if not isinstance(items, dict) or not items:
            errors.append('maps.json: 缺少非空的 "maps"')
        else:
            for mid, m in items.items():
                for k in ('name', 'bg', 'terrain'):
                    if not m.get(k):
                        errors.append(f'maps.json[{mid}]: 缺字段 {k}')
            print(f'· 地图档案 {len(items)} 张')

    # 3) 建筑 / 属性 / 图标 分类表（各自的关键字段不同）
    tables = (
        ('building_types.json', 'types', 'index'),
        ('attribute_types.json', 'types', 'index'),
        ('pin_icons.json', 'icons', 'iconId'),
    )
    for name, key, must in tables:
        t = load(name)
        if t is None:
            continue
        items = t.get(key)
        if not isinstance(items, (list, dict)) or not items:
            errors.append(f'{name}: 缺少非空的 "{key}"')
        else:
            print(f'· {name}：{len(items)} 条')
            rows = items.values() if isinstance(items, dict) else items
            for i, row in enumerate(rows, 1):
                if not isinstance(row, dict):
                    errors.append(f'{name}[{i}]: 不是对象')
                elif must not in row:
                    errors.append(f'{name}[{i}]: 缺 "{must}"')

    # 4) 校准数据：坐标必须是 [x, z] 两个数
    for name in ('attach_overrides.json', 'attach_deleted.json'):
        t = load(name)
        if not isinstance(t, dict):
            continue
        for k, v in (t.get('items') or {}).items():
            if isinstance(v, dict) and 'world' in v:
                w = v['world']
                if not (isinstance(w, list) and len(w) == 2
                        and all(isinstance(x, (int, float)) for x in w)):
                    errors.append(f'{name}[{k}]: world 必须是 [x, z] 两个数字')

    # 5) 攻击面提醒：数据表里不该出现绝对路径
    for p in jsons:
        t = p.read_text(encoding='utf-8-sig', errors='replace')
        for bad in (':\\Users\\', ':/Users/'):
            if bad in t:
                warns.append(f'{p.name}: 含本机用户目录路径（{bad}），建议改成相对路径')

    print()
    for w in warns:
        print('WARN ', w)
    for e in errors:
        print('ERROR', e)
    if errors:
        print(f'\n失败：{len(errors)} 个问题')
        return 1
    print('通过' + (f'（{len(warns)} 条提醒）' if warns else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
