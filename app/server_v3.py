# -*- coding: utf-8 -*-
"""Step 3：三栏界面（左 set 面板 / 中地图 / 右详情）的后端。

跟老 server.py 并存，跑在另一个端口（默认 8779）：
  python app\\server_v3.py 8779  →  http://127.0.0.1:8779/

所有改动都落在 Session 的工作副本上（work\\edit\\...），点「保存」才封包写 bin。
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from app.core.project import Project, DEF_DIR                 # noqa: E402
from app.core.patternset import (                             # noqa: E402
    PatternModel, RAREMAP_NAMES, T_FLAG, T_AREA, T_SPOT,
)
from app.core.pswriter import Session, save_to_bin            # noqa: E402
from app.core import render                                   # noqa: E402

WEB = ROOT / 'app' / 'web3'
ASSETS = ROOT / 'assets'
MAPS_FILE = ROOT / 'src' / 'data' / 'maps.json'
NAMES_FILE = ROOT / 'src' / 'data' / 'tile_names.json'
NIGHT_FILE = ROOT / 'src' / 'data' / 'night_boss_names.json'
_MAPS_CACHE = {'mtime': None, 'data': {}}
_NAMES_CACHE = {'mtime': None, 'data': {}}
_NIGHT_CACHE = {'mtime': None, 'data': {}}


def _json_file(path: Path, cache: dict, key: str) -> dict:
    try:
        mt = path.stat().st_mtime
    except OSError:
        return cache['data'] or {}
    if mt != cache['mtime']:
        try:
            cache['data'] = json.loads(path.read_text(encoding='utf-8')).get(key) or {}
            cache['mtime'] = mt
        except Exception:  # noqa: BLE001
            pass
    return cache['data']


def TILE_NAMES() -> dict:
    """tile 名称表（smallBaseMapId → {en, cn}）。改完立即生效。"""
    return _json_file(NAMES_FILE, _NAMES_CACHE, 'tiles')


def NIGHT_NAMES() -> dict:
    """夜晚 BOSS 名称表（playarea 的 bossId → {en, cn}）。"""
    return _json_file(NIGHT_FILE, _NIGHT_CACHE, 'bosses')


def tile_label(t) -> str:
    """tile 的显示名：中文名 > 英文名 > 空。"""
    d = TILE_NAMES().get(str(t)) or {}
    return d.get('cn') or d.get('en') or ''


def boss_label(b) -> str:
    d = NIGHT_NAMES().get(str(b)) or {}
    return d.get('cn') or d.get('en') or ''


def tile_variants(p, tile) -> list:
    """这个 tile 有哪些属性变体（variationId 0 基 → 名字）。
    名字优先用名称表里手工填的（有的变体不代表属性，图标推出来的不准）。"""
    v = p.model.variation.get(tile) or {}
    custom = (TILE_NAMES().get(str(tile)) or {}).get('variants') or {}
    out = []
    for slot in range(1, 11):
        if not v.get(f'variationValue_{slot}'):
            continue
        icon = v.get(f'variationIconId_{slot}') or 0
        vid = slot - 1
        auto = p.attr_name(icon) or '无属性'
        mine = (custom.get(str(vid)) or '').strip()
        out.append({'v': vid, 'name': mine or auto, 'auto': auto,
                    'icon': icon, 'custom': bool(mine)})
    return out


def MAPS() -> dict:
    """地图档案（按文件 mtime 自动重读 —— 校准器保存后会直接改它，不许重启）。"""
    try:
        mt = MAPS_FILE.stat().st_mtime
    except OSError:
        return _MAPS_CACHE['data'] or {}
    if mt != _MAPS_CACHE['mtime']:
        try:
            _MAPS_CACHE['data'] = json.loads(MAPS_FILE.read_text(encoding='utf-8'))['maps']
            _MAPS_CACHE['mtime'] = mt
        except Exception:  # noqa: BLE001
            pass
    return _MAPS_CACHE['data']

# rareMap → 地图档案 id
TERRAIN_OF_RARE = {0: 'limveld', 1: 'mountaintop', 2: 'crater', 3: 'rotted',
                   4: 'great_hollow', 5: 'shroud'}
OX, OZ = 10504.44, 10491.71
TILE, CENTER = 256.0, 128.0

STATE: dict = {'project': None, 'session': None, 'model': None,
               'sel_set': None, 'sel_pid': None, 'dirty': False, 'rev': 0,
               'last_save': None, 'layer': 'surface'}
LOCK = threading.Lock()


def _cur_layer() -> str:
    """当前看的地图层（只有 Great Hollow 这类多层的图有意义）。"""
    return STATE.get('layer') if STATE.get('layer') in ('surface', 'under') else 'surface'


def _json(h, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    h.send_response(code)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    h.send_header('Content-Length', str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def _file(h, path: Path, ctype: str):
    data = path.read_bytes()
    h.send_response(200)
    h.send_header('Content-Type', ctype)
    h.send_header('Content-Length', str(len(data)))
    h.send_header('Cache-Control', 'no-store')
    h.end_headers()
    h.wfile.write(data)


# ---------------------------------------------------------------- 状态

CUSTOM_SETS_FILE = ROOT / 'work' / 'custom_sets.json'
RANDOM_SEL_FILE = ROOT / 'work' / 'random_sel.json'
_SEL_CACHE = {'mtime': None, 'data': {}}


def _random_sel_all() -> dict:
    return _json_file(RANDOM_SEL_FILE, _SEL_CACHE, 'sels')


def _random_sel() -> dict:
    """当前 bin 的随机勾选：{attach: [...], playarea: [...], night: [...]}。没记录就返回空（=全选）。"""
    return _random_sel_all().get(_bin_key()) or {}


def _save_random_sel(sel: dict):
    data = _random_sel_all()
    data[_bin_key()] = sel
    RANDOM_SEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    RANDOM_SEL_FILE.write_text(
        json.dumps({'sels': data}, ensure_ascii=False, indent=2), encoding='utf-8')
    _SEL_CACHE['mtime'] = None


def _random_pool() -> dict:
    """随机表候选池。表1 = 点位（校准/未校准）+ 建筑（全局，带权重）；
    表2 = 夜王 / 缩圈。"""
    p: Project = STATE['project']
    m: PatternModel = STATE['model']
    if not p or not m:
        return {'calibrated': [], 'uncalibrated': [], 'playarea': [], 'night': [],
                'night1': [], 'night2': [], 'tiles': []}
    prof = MAPS().get(_terrain_id(STATE['sel_set'])) or {}
    # 已校准 = 主人删完后留下的点；未校准 = 显示用的白圈点（删过的，默认不参与随机）
    calibrated = [int(a) for a in (prof.get('calibrated') or prof.get('attachPool') or [])]
    if not calibrated:
        calibrated = sorted(int(a) for a in _anchor_map())
    show = [int(a) for a in (prof.get('attachPool') or [])] or calibrated
    cal_set = set(calibrated)
    uncal = sorted(a for a in show if a not in cal_set)
    try:
        areas = [int(x['id']) for x in _playarea_options()]
    except Exception:  # noqa: BLE001
        areas = []
    bosses = sorted(int(b) for b in p.boss_modifier())
    try:
        n1, n2, _mods = m._night_sets()
    except Exception:  # noqa: BLE001
        n1, n2 = [], []
    # 建筑池：所有校准点用过的 tile 并集（含 ±2000 孪生），每个带变体槽
    try:
        at = m._attach_tiles()
        tids = set()
        for a in calibrated:
            tids |= set(at.get(int(a)) or set())
        tiles = []
        for t in sorted(int(x) for x in tids if x):
            vrows = p.model.variation.get(t) or {}
            vs = []
            for slot in range(1, 11):
                if vrows.get(f'variationValue_{slot}'):
                    vs.append({'v': slot - 1,
                               'name': p.attr_name(vrows.get(f'variationIconId_{slot}')) or '无属性'})
            tiles.append({'id': t, 'name': tile_label(t), 'variants': vs})
    except Exception:  # noqa: BLE001
        tiles = []
    return {'calibrated': calibrated, 'uncalibrated': uncal, 'playarea': areas,
            'night': bosses, 'night1': n1, 'night2': n2, 'tiles': tiles}


def _custom_sets() -> dict:
    """{bin 路径: {sid: [boss, rare]}} —— 空 set 创建时选的夜王/地图类型没处存，
    记在这里，插入种子时按它来，避免被源种子的组合覆盖。"""
    try:
        return json.loads(CUSTOM_SETS_FILE.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}


def _save_custom_sets(data: dict):
    CUSTOM_SETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_SETS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _bin_key() -> str:
    p = STATE.get('project')
    return str(p.bin_path) if p else ''


def _remember_combo(sid, combo):
    if not combo:
        return
    data = _custom_sets()
    data.setdefault(_bin_key(), {})[str(sid)] = [int(combo[0]), int(combo[1])]
    _save_custom_sets(data)


def _forget_combo(sid):
    data = _custom_sets()
    data.get(_bin_key(), {}).pop(str(sid), None)
    _save_custom_sets(data)


def _inject_combos():
    m = STATE.get('model')
    if m is None:
        return
    raw = _custom_sets().get(_bin_key()) or {}
    m.set_combos = {int(k): (int(v[0]), int(v[1])) for k, v in raw.items() if len(v) >= 2}


def _refresh_groups():
    """把当前地形的「成组点」规则注入模型（大空洞：4 组各只显示代表点，改一个带动整组）。"""
    m = STATE.get('model')
    if m is None:
        return
    prof = MAPS().get(_terrain_id(STATE['sel_set'])) or {}
    m.groups = {int(k): v for k, v in (prof.get('groups') or {}).items()}
    m.attach_pool = [int(a) for a in (prof.get('attachPool') or [])]
    # 校准点：大空洞有单独的 calibrated（删完后留下的），其它地图就是 attachPool，
    # 都没有（limveld）→ 用这张图自动算出来的建筑位
    m.calib_points = [int(a) for a in (prof.get('calibrated') or prof.get('attachPool') or [])]
    if not m.calib_points:
        m.calib_points = sorted(int(a) for a in _anchor_map())
    sel = _random_sel()
    m.random_sel = {
        'attach': [int(a) for a in (sel.get('attach') or [])],
        'playarea': [int(a) for a in (sel.get('playarea') or [])],
        'night': [int(a) for a in (sel.get('night') or [])],
        'tiles': {int(k): int(v) for k, v in (sel.get('tiles') or {}).items()},
        'variants': {int(k): {int(v): int(w) for v, w in (vv or {}).items()}
                     for k, vv in (sel.get('variants') or {}).items()},
    }
    _inject_combos()


def _reload_model():
    s = STATE['session']
    STATE['model'] = s.model() if s else None
    _refresh_groups()
    STATE['rev'] += 1


def _terrain_id(sid) -> str:
    m = STATE['model']
    if m is None or sid is None:
        return 'limveld'
    st = m.sets.get(sid)
    rare = st.rare_map if st else None
    return TERRAIN_OF_RARE.get(rare, 'limveld')


def _playarea_options() -> list:
    """1缩/2缩可选点：只留[Standard]和当前地形的（老界面同款规则）。

    2026-11-16：游戏原始 bin（moremap）里 PlayAreaCreateParam 的 `_name` 可能整列为空，
    所以地图档案给了 `playareaIds` 白名单时直接按 id 列，不再依赖名字。
    """
    p: Project = STATE['project']
    if not p:
        return []
    prof = MAPS().get(_terrain_id(STATE['sel_set'])) or {}
    want = prof.get('playareaIds')
    terrain = prof.get('terrain') or '[Standard]'
    allow = ('[Standard]', terrain)
    rows = p.params.rows('PlayAreaCreateParam')
    named = any((r.get('_name') or '').strip() for r in rows.values())
    if not want and not named:
        # 游戏原始 bin 整列名字都是空的 → 只能反过来用「当前地形种子实际用过的缩圈点」
        want = _playarea_ids_from_seeds()
    seen = set()
    out = []
    for k, r in rows.items():
        nm = (r.get('_name') or '').strip()
        if want:
            if int(k) not in want:
                continue
        else:
            if not nm or int(k) >= 20000:
                continue
            mt = re.match(r'\[[^\]]+\]', nm)
            pre = mt.group(0) if mt else ''
            if pre and pre not in allow:
                continue
            # 只有走名字筛时才去重（2xxxx 是 1000 段的无名副本）；白名单模式全保留
            sig = (r.get('gridXNo'), r.get('gridZNo'), r.get('posX'), r.get('posZ'))
            if sig in seen:
                continue
            seen.add(sig)
        out.append({'id': int(k), 'name': nm or f'{k}',
                    'grid': [r.get('gridXNo'), r.get('gridZNo')],
                    'pos': [r.get('posX'), r.get('posZ')]})
    out.sort(key=lambda x: x['id'])
    return out


def _playarea_ids_from_seeds():
    """当前地形（rareMap）的种子实际用过的 playArea1/2 集合（名字不可用时的兜底）。"""
    m = STATE.get('model')
    p: Project = STATE['project']
    if not m or not p:
        return None
    st = m.sets.get(STATE['sel_set'])
    rare = st.rare_map if st else None
    if rare is None:
        return None
    pids = {pt.pid for s in m.sets.values() if s.rare_map == rare for pt in s.patterns}
    ids = set()
    for r in p.params.rows('LotResultPlayAreaParam').values():
        if r.get('patternId') in pids:
            for k in ('playArea1', 'playArea2'):
                v = r.get(k)
                if v:
                    ids.add(int(v))
    return ids or None


TWIN_OFFSETS = (0, -1000, -2000, -3000, 1000, 2000)


def _anchor_map() -> dict:
    """当前地形的建筑位（校准坐标）：attachId → world。"""
    p: Project = STATE['project']
    if not p:
        return {}
    key = _terrain_id(STATE['sel_set'])
    cache = STATE.setdefault('_anchor_cache', {})
    if key not in cache:
        cache[key] = {a['attachId']: list(a['world']) for a in p.attach_points(key)}
    return cache[key]


def _resolve_anchor(aid: int):
    """地点 attachId → 对应的建筑位（原号或孪生号）。返回 (anchorId, world) 或 (None, None)。"""
    amap = _anchor_map()
    for k in TWIN_OFFSETS:
        c = aid + k
        if c > 0 and c in amap:
            return c, amap[c]
    return None, None


def _layer_attach_set():
    """当前层能显示的 attachId 集合；None = 这张图不分层（全都显示）。"""
    prof = MAPS().get(_terrain_id(STATE['sel_set'])) or {}
    ids = (prof.get('layers') or {}).get(_cur_layer())
    return set(ids) if ids else None


def _spot_payload(row) -> dict:
    """spot 行 → 画图用（借 project.model 的 describe_spot 算图标/坐标）。

    能认到建筑位时，**位置直接用建筑位的校准坐标**（2026-11-15：大圈要跟着小圈走）；
    认不到才退回原始坐标 / 人工校准表。
    """
    p: Project = STATE['project']
    sp = p.model.describe_spot(row)
    _aid, w = _resolve_anchor(int(sp['attachId'] or 0))
    if w:
        sp['world'] = list(w)
    else:
        ov = p.attach_overrides().get(sp['attachId'])
        if ov:
            sp['world'] = list(ov)
    sp['attrName'] = p.attr_name(sp.get('attrIcon'))     # 426xx → 中文属性名
    sp['tileName'] = tile_label(sp.get('tile'))         # tile 名称表
    tid = sp.get('tile')
    vid = int(row.get('variationId') or 0)
    if tid:
        sp['variantName'] = next((x['name'] for x in tile_variants(p, tid) if x['v'] == vid), '')
    return sp


def _tree() -> dict:
    p: Project = STATE['project']
    m: PatternModel = STATE['model']
    s: Session = STATE['session']
    if not p or not m:
        return {'ok': False, 'error': '还没有打开 bin'}
    _refresh_groups()
    bosses = [{'id': b['id'], 'name': b['name']} for b in p.bosses() if b['id'] <= 9]
    sets = []
    for sid, st in sorted(m.sets.items()):
        combo = st.combo
        sets.append({
            'sid': sid, 'name': st.name,
            'boss': combo[0] if combo else None,
            'rare': combo[1] if combo else None,
            'rareName': RAREMAP_NAMES.get(combo[1]) if combo else None,
            'bossName': m.boss_name(combo[0]) if combo else None,
            'count': st.count, 'declared': st.declared_count,
            'weight': st.row.get('weight'), 'chaosW': st.row.get('chaosMatchWeight'),
            'range': m.pid_range(sid),
            'status': 'custom' if st.name.startswith('[Custom]') else 'official',
            'patterns': [{'pid': pt.pid, 'spots': pt.spot_count,
                          'night': list(pt.boss_modifier)} for pt in st.patterns],
        })

    terrain = _terrain_id(STATE['sel_set'])
    prof = MAPS().get(terrain) or {}
    lay = _cur_layer()
    anchors = p.attach_points(terrain)
    anchors = [a for a in anchors if not a.get('layer') or a['layer'] == lay]
    type_map = {}
    for tname, ids in (prof.get('types') or {}).items():
        for a in ids or []:
            type_map[int(a)] = tname
    for a in anchors:
        a['type'] = type_map.get(a['attachId'], 'white')
    out = {
        'ok': True,
        'bin': str(p.bin_path),
        'maps': [{'id': k, 'name': v['name']} for k, v in MAPS().items()],
        'bosses': bosses,
        'rares': [{'id': k, 'name': v} for k, v in sorted(RAREMAP_NAMES.items())],
        'sets': sets,
        'selSet': STATE['sel_set'], 'selPid': STATE['sel_pid'],
        'dirty': STATE['dirty'], 'rev': STATE['rev'],
        'history': s.history if s else [],
        'work': str(s.dir) if s else None,
        'lastSave': STATE['last_save'],
        'map': {'ox': OX, 'oz': OZ, 'tile': TILE, 'center': CENTER},
        'terrain': terrain,
        'layer': lay,
        'layers': ['surface', 'under'] if prof.get('bgUnder') else ['surface'],
        'groups': prof.get('groups') or {},
        # 夜晚 BOSS 候选：bossId → 它固定的 bossModifier（2026-11-16 实测 36 个）
        'nightBosses': [{'id': int(b), 'modifier': int(m), 'name': boss_label(b)}
                        for b, m in sorted(p.boss_modifier().items())],
        'anchors': anchors,
        'playareas': _playarea_options(),
    }
    pid = STATE['sel_pid']
    if pid is not None and pid in m.patterns:
        pt = m.patterns[pid]
        lay_ids = _layer_attach_set()
        keep = [r for r in pt.spots
                if lay_ids is None or int(r.get('attachId') or 0) in lay_ids]
        spots = [_spot_payload(r) for r in keep]
        for sp, xy in zip(spots, render.layout(spots)):
            if xy:
                sp['px'], sp['py'] = xy
        out['pidInfo'] = {
            'pid': pid,
            'set': STATE['sel_set'],
            'spots': [{'row': int(r['_id']), 'attachId': r.get('attachId'),
                       'tile': r.get('smallBaseMapId'), 'variationId': r.get('variationId'),
                       'mapIndex': r.get('mapIndex')} for r in keep],
            'spotView': [{**{k: sp.get(k) for k in ('attachId', 'tile', 'tileName', 'icon', 'attrIcon',
                                                    'attrName', 'variantName', 'realName', 'name',
                                                    'attachName', 'world', 'px', 'py')},
                          'row': int(keep[i]['_id']), 'mapIndex': keep[i].get('mapIndex'),
                          'variationId': keep[i].get('variationId')}
                         for i, sp in enumerate(spots)],
            'playarea': pt.playarea,
            'flags': [{'row': int(r['_id']), 'eventFlag': r.get('eventFlag'),
                       'modifier': r.get('modifier'), 'modifierSet': r.get('modifierSet'),
                       'name': (r.get('_name') or '')} for r in pt.flags],
            'night': list(pt.boss_modifier),
            'combo': list(pt.combo) if pt.combo else None,
        }
    return out


# ---------------------------------------------------------------- 计划

def _plan(op: str, args: dict):
    m: PatternModel = STATE['model']
    if m is None:
        raise ValueError('先打开 bin')
    _refresh_groups()
    if op == 'create_set':
        return m.plan_create_set(int(args['boss']), int(args['rare']),
                                 fields=args.get('fields'), copy_pools=bool(args.get('copy_pools')))
    if op == 'insert_pattern':
        return m.plan_insert_pattern(int(args['set']), source_pid=args.get('source'),
                                     night=tuple(args['night']) if args.get('night') else None,
                                     recompute_pools=not bool(args.get('keep_pools')))
    if op == 'delete_pattern':
        return m.plan_delete_pattern(int(args['pid']))
    if op == 'random_pattern':
        # 随机内容由「随机表」决定（表1 点位/建筑、表2 夜王/缩圈）
        # 随机表还没配置过（全空）→ 默认三类都随机，否则第一次用会「什么都不随机」
        sel = m.random_sel or {}
        has_any = bool(sel.get('attach')) or bool(sel.get('playarea')) or bool(sel.get('night'))
        opts = {
            'attach': True if not has_any else bool(sel.get('attach')),
            'playarea': True if not has_any else bool(sel.get('playarea')),
            'night': True if not has_any else bool(sel.get('night')),
        }
        return m.plan_random_pattern(int(args['set']), opts=opts)
    if op == 'delete_set':
        return m.plan_delete_set(int(args['sid']))
    if op == 'set_fields':
        return m.plan_set_fields(int(args['sid']), args['fields'])
    if op == 'change_combo':
        return m.plan_change_combo(int(args['sid']), int(args['boss']), int(args['rare']),
                                   recopy_pools=bool(args.get('recopy')))
    if op == 'recompute_pools':
        return m.plan_recompute_pools(int(args['sid']))
    if op == 'spot_add':
        return m.plan_spot_add(int(args['pid']), int(args['attachId']),
                               int(args['tile']), int(args.get('variationId') or 0))
    if op == 'spot_remove':
        return m.plan_spot_remove(int(args['pid']), int(args['row']))
    if op == 'spot_field':
        return m.plan_spot_field(int(args['pid']), int(args['row']),
                                 str(args['field']), args['value'])
    if op == 'spot_tile':
        return m.plan_spot_tile(int(args['pid']), int(args['row']), int(args['tile']),
                                None if args.get('variationId') is None else int(args['variationId']))
    if op == 'playarea':
        return m.plan_playarea(int(args['pid']), args['fields'])
    raise ValueError(f'未知操作：{op}')


RANDOM_LOG_FILE = ROOT / 'work' / 'random_log.jsonl'


def _log_random(entry: dict):
    """把一次随机的结果追加进开发者日志（jsonl，一行一条）。"""
    try:
        RANDOM_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RANDOM_LOG_FILE, 'a', encoding='utf-8') as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:  # noqa: BLE001
        pass


def _random_entry(plan, pid: int, sid: int) -> dict:
    """从 plan 里抽出一条随机记录。"""
    import time as _t
    np_ = (plan.new_pids or [{}])[0]
    ov = np_.get('spot_overrides') or {}
    tiles = {}
    varis = {}
    for o in ov.values():
        t = int(o.get('tile') or 0)
        tiles[t] = tiles.get(t, 0) + 1
        if t:
            varis[f'{t}:{o.get("variationId") or 0}'] = varis.get(f'{t}:{o.get("variationId") or 0}', 0) + 1
    return {
        'time': _t.strftime('%Y-%m-%d %H:%M:%S'),
        'pid': pid, 'set': sid,
        'template_pid': np_.get('source_pid'),
        'combo': list(np_.get('combo') or ()),
        'spots_total': np_.get('spots'),
        'spots_randomized': len(ov),
        'tile_hist': {str(k): v for k, v in sorted(tiles.items())},
        'variant_hist': varis,
        'playarea': np_.get('playarea_overrides') or {},
        'night': list(np_.get('night') or ()),
        'notes': plan.notes,
        'warnings': plan.warnings,
    }


def _export_random_log() -> dict:
    """把 work\\random_log.jsonl 汇总导出成带时间戳的 JSON，返回路径。"""
    import time as _t
    if not RANDOM_LOG_FILE.exists():
        return {'ok': False, 'error': '还没有随机日志（先随机几张）'}
    entries = []
    for line in RANDOM_LOG_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    out = ROOT / 'work' / f'random_log_{_t.strftime("%Y%m%d_%H%M%S")}.json'
    out.write_text(json.dumps({
        'exported_at': _t.strftime('%Y-%m-%d %H:%M:%S'),
        'bin': str(STATE['project'].bin_path) if STATE.get('project') else '',
        'count': len(entries),
        'entries': entries,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'ok': True, 'path': str(out), 'count': len(entries)}


def _apply_random_batch(args: dict) -> dict:
    """一次生成 N 个随机种子（每张都重新挑模板/随机内容）。"""
    sid = int(args['set'])
    n = max(1, min(50, int(args.get('count') or 1)))
    pids = []
    for i in range(n):
        plan = _plan('random_pattern', {'set': sid})
        if not plan.ok:
            return {'ok': False, 'error': f'第 {i + 1} 张失败：' + '；'.join(plan.errors),
                    'done': len(pids), 'pids': pids}
        rep = STATE['session'].apply(plan)
        if not rep.ok:
            return {'ok': False, 'error': f'第 {i + 1} 张失败：' + '；'.join(rep.errors),
                    'done': len(pids), 'pids': pids}
        _reload_model()
        pids.append(plan.new_pids[0]['pid'])
        _log_random(_random_entry(plan, pids[-1], sid))
    STATE['dirty'] = True
    STATE['sel_set'] = sid
    STATE['sel_pid'] = pids[-1] if pids else STATE.get('sel_pid')
    return {'ok': True, 'pids': pids, 'count': len(pids), 'tree': _tree()}


def _apply(op: str, args: dict) -> dict:
    if op == 'random_batch':
        return _apply_random_batch(args)
    plan = _plan(op, args)
    if not plan.ok:
        return {'ok': False, 'error': '；'.join(plan.errors), 'plan': plan.summary()}
    s: Session = STATE['session']
    rep = s.apply(plan)
    if rep.ok:
        # 空 set 的身份要记下来（创建/改组合），删 set 时清掉
        if plan.op == 'create_set':
            for ns in plan.new_sets:
                _remember_combo(ns['sid'], ns.get('combo'))
        elif plan.op == 'change_combo':
            _remember_combo(int(args['sid']), (int(args['boss']), int(args['rare'])))
        elif plan.op == 'delete_set':
            _forget_combo(int(args['sid']))
        STATE['dirty'] = True
        _reload_model()
        # 选择跟着走
        if plan.new_sets:
            STATE['sel_set'] = max(STATE['model'].sets)
            STATE['sel_pid'] = None
        if plan.new_pids:
            STATE['sel_set'] = plan.new_pids[0]['set']
            STATE['sel_pid'] = plan.new_pids[0]['pid']
            if plan.op == 'random_pattern':
                _log_random(_random_entry(plan, plan.new_pids[0]['pid'], plan.new_pids[0]['set']))
        if plan.removed_sets:
            STATE['sel_set'] = None
            STATE['sel_pid'] = None
        m = STATE['model']
        if STATE['sel_pid'] is not None and STATE['sel_pid'] not in m.patterns:
            STATE['sel_pid'] = None
        if STATE['sel_set'] is not None and STATE['sel_set'] not in m.sets:
            STATE['sel_set'] = None
    return {'ok': rep.ok, 'error': '；'.join(rep.errors) if rep.errors else None,
            'checks': rep.checks, 'changes': rep.changes,
            'warnings': rep.warnings, 'plan': plan.summary()}


def _map_png() -> bytes:
    p: Project = STATE['project']
    m: PatternModel = STATE['model']
    pid = STATE['sel_pid']
    if not m:
        return b''
    spots = []
    if pid is not None and pid in m.patterns:
        lay_ids = _layer_attach_set()
        spots = [_spot_payload(r) for r in m.patterns[pid].spots
                 if lay_ids is None or int(r.get('attachId') or 0) in lay_ids]
    terrain = _terrain_id(STATE['sel_set'])
    prof = MAPS().get(terrain) or {}
    bgname = prof.get('bg') or 'limveld.png'
    if _cur_layer() == 'under' and prof.get('bgUnder'):
        bgname = prof['bgUnder']
    bg = ASSETS / 'map' / bgname
    allowed = {a['attachId'] for a in p.attach_points(terrain)}
    return render.png_bytes([], spots, rev=str(STATE['rev']), bg=bg, allowed=allowed, rings=False)


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = u.path
        if path in ('/', '/index.html'):
            return _file(self, WEB / 'index.html', 'text/html; charset=utf-8')
        if path == '/app.js':
            return _file(self, WEB / 'app.js', 'application/javascript; charset=utf-8')
        if path == '/style.css':
            return _file(self, WEB / 'style.css', 'text/css; charset=utf-8')
        if path.startswith('/pin/'):
            iid = path.rsplit('/', 1)[-1].replace('.png', '')
            f = ASSETS / 'icon' / 'pin' / f'{iid}.png'
            if f.exists():
                return _file(self, f, 'image/png')
            return _json(self, {'error': 'no pin'}, 404)
        if path == '/api3/tree':
            return _json(self, _tree())
        if path == '/api3/map.png':
            data = _map_png()
            if not data:
                return _json(self, {'error': 'no pid'}, 404)
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        if path == '/api3/attach':
            p = STATE['project']
            aid = int(q.get('id', ['0'])[0])
            cand = p.attach_candidates(aid)
            tiles = cand.get('tiles') or []
            cand['names'] = {str(t): tile_label(t) for t in tiles}
            for it in (cand.get('tileInfo') or []):
                it['name'] = tile_label(it.get('tile'))
            return _json(self, {'ok': True, 'candidate': cand})
        if path == '/api3/names':
            p = STATE['project']
            tiles = TILE_NAMES()
            bosses = NIGHT_NAMES()
            if p and not bosses:
                bosses = {str(b): {'en': '', 'cn': ''} for b in sorted(p.boss_modifier())}
            variants = {}
            if p:
                for t in tiles:
                    vs = tile_variants(p, int(t))
                    if vs:
                        variants[str(t)] = vs
            return _json(self, {'ok': True, 'tiles': tiles, 'bosses': bosses,
                                'variants': variants})
        if path == '/api3/random':
            return _json(self, {'ok': True, 'pool': _random_pool(), 'sel': _random_sel()})
        if path == '/api3/randomlog':
            try:
                return _json(self, _export_random_log())
            except Exception as e:  # noqa: BLE001
                return _json(self, {'ok': False, 'error': f'{type(e).__name__}: {e}'})
        if path == '/api3/cell':
            p = STATE['project']
            gx = int(q.get('gx', ['0'])[0])
            gz = int(q.get('gz', ['0'])[0])
            return _json(self, {'ok': True, **p.cell_candidates(gx, gz)})
        if path == '/api3/raw':
            p = STATE['project']
            aid = int(q.get('attach', ['0'])[0])
            tile = int(q.get('tile', ['0'])[0])
            return _json(self, {'ok': True, 'fields': p.raw_fields(aid, tile)})
        return _json(self, {'error': 'not found'}, 404)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except Exception:  # noqa: BLE001  （含 UnicodeDecodeError：非 UTF-8 请求体）
            return _json(self, {'ok': False, 'error': 'bad json'}, 400)

        with LOCK:
            try:
                if self.path == '/api3/open':
                    return self._open(body)
                if self.path == '/api3/select':
                    if 'set' in body:
                        STATE['sel_set'] = int(body['set']) if body['set'] is not None else None
                        STATE['sel_pid'] = None
                    if 'pid' in body:
                        STATE['sel_pid'] = int(body['pid']) if body['pid'] is not None else None
                        if STATE['sel_pid'] is not None:
                            pt = STATE['model'].patterns.get(STATE['sel_pid'])
                            if pt and pt.flags:
                                STATE['sel_set'] = int(pt.flags[0]['patternSetId'])
                    STATE['rev'] += 1
                    return _json(self, _tree())
                if self.path == '/api3/random':
                    sel = {
                        'attach': [int(x) for x in (body.get('attach') or [])],
                        'playarea': [int(x) for x in (body.get('playarea') or [])],
                        'night': [int(x) for x in (body.get('night') or [])],
                        'tiles': {int(k): int(v) for k, v in (body.get('tiles') or {}).items()},
                        'variants': {int(k): {int(v): int(w) for v, w in (vv or {}).items()}
                                     for k, vv in (body.get('variants') or {}).items()},
                    }
                    _save_random_sel(sel)
                    return _json(self, {'ok': True,
                                        'count': len(sel['attach']) + len(sel['playarea'])
                                        + len(sel['night']) + len(sel['tiles'])})
                if self.path == '/api3/names':
                    tiles = body.get('tiles') or {}
                    bosses = body.get('bosses')
                    data = {
                        '_note': 'tile（smallBaseMapId）名称表。en 来自 Smithbox 社区命名，cn 可手工补；'
                                 '编辑器的「名称表」界面会改这个文件，改完立即生效。',
                        'tiles': tiles,
                    }
                    NAMES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    _NAMES_CACHE['mtime'] = None
                    if bosses is not None:
                        bdata = {
                            '_note': '夜晚 BOSS（playarea 的 bossId，47xx/52xx）名称表；'
                                     '编辑器的「名称表 → 夜晚 BOSS」会改这个文件。',
                            'bosses': bosses,
                        }
                        NIGHT_FILE.write_text(json.dumps(bdata, ensure_ascii=False, indent=2), encoding='utf-8')
                        _NIGHT_CACHE['mtime'] = None
                    return _json(self, {'ok': True, 'count': len(tiles),
                                        'bossCount': len(bosses or {})})
                if self.path == '/api3/layer':
                    lay = str(body.get('layer') or 'surface')
                    if lay not in ('surface', 'under'):
                        return _json(self, {'ok': False, 'error': 'layer 只能是 surface / under'})
                    STATE['layer'] = lay
                    STATE['rev'] += 1
                    return _json(self, _tree())
                if self.path == '/api3/plan':
                    plan = _plan(str(body.get('op')), body.get('args') or {})
                    return _json(self, {'ok': plan.ok, 'plan': plan.summary(),
                                        'errors': plan.errors, 'warnings': plan.warnings})
                if self.path == '/api3/apply':
                    out = _apply(str(body.get('op')), body.get('args') or {})
                    out['tree'] = _tree()
                    return _json(self, out)
                if self.path == '/api3/save':
                    return self._save(body)
                if self.path == '/api3/rollback':
                    return self._rollback(body)
            except Exception as e:  # noqa: BLE001
                return _json(self, {'ok': False, 'error': f'{type(e).__name__}: {e}'})
        return _json(self, {'error': 'not found'}, 404)

    # ---- 动作 ----
    def _open(self, body):
        raw = str(body['path']).strip().strip('"')
        p_in = Path(raw)
        if p_in.is_dir():
            bins = sorted(x for x in p_in.glob('*.bin') if x.is_file()) or sorted(p_in.glob('*/*.bin'))
            if not bins:
                return _json(self, {'ok': False, 'error': f'这个文件夹里没有 .bin：{p_in}'})
            if len(bins) > 1:
                return _json(self, {'ok': False, 'needChoose': True,
                                    'bins': [str(x) for x in bins]})
            p_in = bins[0]
        if not p_in.exists():
            return _json(self, {'ok': False, 'error': f'找不到：{p_in}'})
        p = Project(str(p_in))
        STATE['project'] = p
        STATE['session'] = Session(p, work_root=ROOT / 'work' / 'edit', name='ui')
        STATE['_anchor_cache'] = {}
        STATE['sel_set'] = None
        STATE['sel_pid'] = None
        STATE['dirty'] = False
        STATE['last_save'] = None
        _reload_model()
        m = STATE['model']
        if m.sets:
            prefer = next((sid for sid in sorted(m.sets) if m.sets[sid].patterns), min(m.sets))
            STATE['sel_set'] = prefer
            if m.sets[prefer].patterns:
                STATE['sel_pid'] = m.sets[prefer].patterns[0].pid
        return _json(self, _tree())

    def _save(self, body):
        s: Session = STATE['session']
        p: Project = STATE['project']
        if not s:
            return _json(self, {'ok': False, 'error': '先打开 bin'})
        target = Path(str(body.get('target') or p.bin_path))
        rep = save_to_bin(p, s.params_dir, target_bin=target, base_bin=p.bin_path)
        if rep.get('ok'):
            STATE['dirty'] = False
            STATE['last_save'] = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
                                  'target': str(target), 'backup': rep.get('backup')}
        return _json(self, {'ok': bool(rep.get('ok')), 'error': rep.get('error'),
                            'checks': rep.get('checks'), 'backup': rep.get('backup'),
                            'target': str(target)})

    def _rollback(self, body):
        s: Session = STATE['session']
        if not s:
            return _json(self, {'ok': False, 'error': '先打开 bin'})
        rep = s.rollback(int(body.get('n') or 0))
        STATE['dirty'] = True
        _reload_model()
        m = STATE['model']
        if STATE['sel_pid'] is not None and STATE['sel_pid'] not in m.patterns:
            STATE['sel_pid'] = None
        if STATE['sel_set'] is not None and STATE['sel_set'] not in m.sets:
            STATE['sel_set'] = None
        return _json(self, {'ok': rep.ok, 'error': '；'.join(rep.errors) if rep.errors else None,
                            'tree': _tree()})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8779
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'http://127.0.0.1:{port}/')
    srv.serve_forever()


if __name__ == '__main__':
    main()
