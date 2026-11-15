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
MAPS = json.loads((ROOT / 'src' / 'data' / 'maps.json').read_text(encoding='utf-8'))['maps']

# rareMap → 地图档案 id（4 Great Hollow 没有专门底图，借普通图）
TERRAIN_OF_RARE = {0: 'limveld', 1: 'mountaintop', 2: 'crater', 3: 'rotted', 4: 'limveld', 5: 'shroud'}
OX, OZ = 10504.44, 10491.71
TILE, CENTER = 256.0, 128.0

STATE: dict = {'project': None, 'session': None, 'model': None,
               'sel_set': None, 'sel_pid': None, 'dirty': False, 'rev': 0,
               'last_save': None}
LOCK = threading.Lock()


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

def _reload_model():
    s = STATE['session']
    STATE['model'] = s.model() if s else None
    STATE['rev'] += 1


def _terrain_id(sid) -> str:
    m = STATE['model']
    if m is None or sid is None:
        return 'limveld'
    st = m.sets.get(sid)
    rare = st.rare_map if st else None
    return TERRAIN_OF_RARE.get(rare, 'limveld')


def _playarea_options() -> list:
    """1缩/2缩可选点：只留[Standard]和当前地形的（老界面同款规则）。"""
    p: Project = STATE['project']
    if not p:
        return []
    prof = MAPS.get(_terrain_id(STATE['sel_set'])) or {}
    terrain = prof.get('terrain') or '[Standard]'
    allow = ('[Standard]', terrain)
    seen = set()
    out = []
    for k, r in p.params.rows('PlayAreaCreateParam').items():
        nm = (r.get('_name') or '').strip()
        if not nm or int(k) >= 20000:
            continue
        mt = re.match(r'\[[^\]]+\]', nm)
        pre = mt.group(0) if mt else ''
        if pre and pre not in allow:
            continue
        sig = (r.get('gridXNo'), r.get('gridZNo'), r.get('posX'), r.get('posZ'))
        if sig in seen:
            continue
        seen.add(sig)
        out.append({'id': int(k), 'name': nm,
                    'grid': [r.get('gridXNo'), r.get('gridZNo')],
                    'pos': [r.get('posX'), r.get('posZ')]})
    out.sort(key=lambda x: x['id'])
    return out


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


def _spot_payload(row) -> dict:
    """spot 行 → 画图用（借 project.model 的 describe_spot 算图标/坐标）。

    能认到建筑位时，**位置直接用建筑位的校准坐标**（主人 2026-11-15：大圈要跟着小圈走）；
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
    return sp


def _tree() -> dict:
    p: Project = STATE['project']
    m: PatternModel = STATE['model']
    s: Session = STATE['session']
    if not p or not m:
        return {'ok': False, 'error': '还没有打开 bin'}
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

    out = {
        'ok': True,
        'bin': str(p.bin_path),
        'maps': [{'id': k, 'name': v['name']} for k, v in MAPS.items()],
        'bosses': bosses,
        'rares': [{'id': k, 'name': v} for k, v in sorted(RAREMAP_NAMES.items())],
        'sets': sets,
        'selSet': STATE['sel_set'], 'selPid': STATE['sel_pid'],
        'dirty': STATE['dirty'], 'rev': STATE['rev'],
        'history': s.history if s else [],
        'work': str(s.dir) if s else None,
        'lastSave': STATE['last_save'],
        'map': {'ox': OX, 'oz': OZ, 'tile': TILE, 'center': CENTER},
        'terrain': _terrain_id(STATE['sel_set']),
        'anchors': p.attach_points(_terrain_id(STATE['sel_set'])),
        'playareas': _playarea_options(),
    }
    pid = STATE['sel_pid']
    if pid is not None and pid in m.patterns:
        pt = m.patterns[pid]
        spots = [_spot_payload(r) for r in pt.spots]
        for sp, xy in zip(spots, render.layout(spots)):
            if xy:
                sp['px'], sp['py'] = xy
        out['pidInfo'] = {
            'pid': pid,
            'set': STATE['sel_set'],
            'spots': [{'row': int(r['_id']), 'attachId': r.get('attachId'),
                       'tile': r.get('smallBaseMapId'), 'variationId': r.get('variationId'),
                       'mapIndex': r.get('mapIndex')} for r in pt.spots],
            'spotView': [{**{k: sp.get(k) for k in ('attachId', 'tile', 'icon', 'attrIcon',
                                                    'attrName', 'realName', 'name',
                                                    'attachName', 'world', 'px', 'py')},
                          'row': int(pt.spots[i]['_id']), 'mapIndex': pt.spots[i].get('mapIndex'),
                          'variationId': pt.spots[i].get('variationId')}
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
    if op == 'create_set':
        return m.plan_create_set(int(args['boss']), int(args['rare']),
                                 fields=args.get('fields'), copy_pools=bool(args.get('copy_pools')))
    if op == 'insert_pattern':
        return m.plan_insert_pattern(int(args['set']), source_pid=args.get('source'),
                                     night=tuple(args['night']) if args.get('night') else None,
                                     recompute_pools=not bool(args.get('keep_pools')))
    if op == 'delete_pattern':
        return m.plan_delete_pattern(int(args['pid']))
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


def _apply(op: str, args: dict) -> dict:
    plan = _plan(op, args)
    if not plan.ok:
        return {'ok': False, 'error': '；'.join(plan.errors), 'plan': plan.summary()}
    s: Session = STATE['session']
    rep = s.apply(plan)
    if rep.ok:
        STATE['dirty'] = True
        _reload_model()
        # 选择跟着走
        if plan.new_sets:
            STATE['sel_set'] = max(STATE['model'].sets)
            STATE['sel_pid'] = None
        if plan.new_pids:
            STATE['sel_set'] = plan.new_pids[0]['set']
            STATE['sel_pid'] = plan.new_pids[0]['pid']
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
        spots = [_spot_payload(r) for r in m.patterns[pid].spots]
    bg = ASSETS / 'map' / (MAPS.get(_terrain_id(STATE['sel_set']), {}) or {}).get('bg', 'limveld.png')
    allowed = {a['attachId'] for a in p.attach_points(_terrain_id(STATE['sel_set']))}
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
            return _json(self, {'ok': True, 'candidate': p.attach_candidates(aid)})
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
        except json.JSONDecodeError:
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
