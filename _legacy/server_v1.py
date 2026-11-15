# -*- coding: utf-8 -*-
"""本地网页服务：只绑 127.0.0.1，不联网。"""
from __future__ import annotations

import json
import copy
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.project import Project
from app.core import draft as D
from app.core.writeback import write_back

WEB = ROOT / 'app' / 'web'
ASSETS = ROOT / 'assets'

TILE = 256.0
CENTER = 128.0
# m06466：地图档案 —— 特殊地形只是换底图，世界坐标/网格完全共用（已核对 4 张图）
MAPS_PATH = ROOT / 'src' / 'data' / 'maps.json'


def _maps() -> dict:
    if not MAPS_PATH.exists():
        return {'limveld': {'name': '宁姆韦德', 'bg': 'limveld.png'}}
    return json.loads(MAPS_PATH.read_text(encoding='utf-8'))['maps']


OX, OZ = 10504.44, 10491.71     # 与 render_overlay 一致（监牢平均标定）

STATE: dict = {'project': None, 'draft': None, 'template': None, 'rev': 0, 'map': 'limveld',
               'history': []}
LOCK = threading.Lock()

HISTORY_MAX = 60      # m06840：撤销栈上限（一份草稿很小，够用就行）


def _push_history():
    """改草稿之前先存一份快照（撤销用）。"""
    d = STATE.get('draft')
    if not d:
        return
    hist = STATE.setdefault('history', [])
    hist.append(copy.deepcopy(d))
    del hist[:-HISTORY_MAX]


def _pop_history() -> bool:
    d = STATE.get('draft')
    hist = STATE.get('history') or []
    if not d or not hist:
        return False
    STATE['draft'] = hist.pop()
    STATE['rev'] += 1
    return True


def _json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _file(handler, path: Path, ctype: str):
    data = path.read_bytes()
    handler.send_response(200)
    handler.send_header('Content-Type', ctype)
    handler.send_header('Content-Length', str(len(data)))
    # 本地小工具：永不缓存，改完 F5 立刻生效
    handler.send_header('Cache-Control', 'no-store, must-revalidate')
    handler.end_headers()
    handler.wfile.write(data)


def _spot_payload(sp):
    return {
        'attachId': sp['attachId'],
        'tile': sp['tile'],
        'icon': sp['icon'],
        'attrIcon': sp.get('attrIcon'),
        'attrName': sp.get('attrName') or '',
        'realName': sp.get('realName') or '',
        'name': sp['name'],
        'attachName': sp['attachName'],
        'attachSize': sp['attachSize'],
        'grid': list(sp['grid']),
        'world': list(sp['world']),
    }


def _draft_state() -> dict:
    from app.core import render

    p: Project = STATE['project']
    d: D.Draft = STATE['draft']
    if not p:
        return {'ok': False, 'error': '还没有打开 bin'}
    out = {
        'ok': True,
        'bin': str(p.bin_path),
        'mapId': STATE['map'],
        'maps': [{'id': k, 'name': v['name']} for k, v in _maps().items()],
        'params': p.param_count(),
        'bosses': [{'id': b['id'], 'name': b['name']} for b in p.bosses()],
        'map': {'ox': OX, 'oz': OZ, 'tile': TILE, 'center': CENTER},
    }
    if not d:
        return {**out, 'draft': None, 'issues': [], 'template': None, 'rev': STATE['rev'],
                'canUndo': False}
    issues = D.validate(p, d)
    draft_spots = [p.spot_view(s['attachId'], s['tile'], s.get('variationId') or 0) for s in d.spots]
    # m06209：同一 smallBaseMapId 多次出现时 mapIndex 从 0 累加，界面也标出来
    for sp, row in zip(draft_spots, d.spot_rows()):
        sp['mapIndex'] = row['mapIndex']
    tpl = STATE['template'] or {}
    tpl_spots = tpl.get('spots') or []
    # 判「这个点本种子用没用过」必须用**未过滤**的全量模板点；
    # 画面上只画有 icon 的，否则会把用过的点当成空闲点画成灰圈（m04900）。
    tpl_all_ids = {int(s['attachId']) for s in tpl_spots}
    tpl_draw = [s for s in tpl_spots if s.get('icon')]

    # 画面上点的位置由服务器算（含 313/116 换位 + 去重叠），前端直接用 px/py，
    # 免得两边各算一遍画出「红点和圈脱开」（m04411）。
    for spots, src in ((draft_spots, draft_spots), (tpl_draw, tpl_spots)):
        for sp, xy in zip(spots, render.layout(src)):
            if xy:
                sp['px'], sp['py'] = xy[0], xy[1]

    return {
        **out,
        'rev': STATE['rev'],
        'canUndo': bool(STATE.get('history')),   # m06840：撤销按钮置灰用
        'draft': {**d.as_dict(), 'spots': draft_spots},
        'issues': issues,
        'template': {**tpl, 'spots': tpl_draw},
        'extra': _anchors(p),
        'playarea': _playarea_state(p, d),
        'events': _events_state(p, d),
    }


def _export_state(p: Project, d) -> dict:
    """m06840：把这次改动导成一份 JSON —— 别人拿到能照着复现，也能直接对账。"""
    from app.core.draft import payload as make_payload

    rows = d.spot_rows()
    spots = []
    for sp, row in zip(d.spots, rows):
        spots.append({
            'attachId': int(sp['attachId']),
            'tile': int(sp['tile']),
            'variationId': int(sp.get('variationId') or 0),
            'mapIndex': int(row['mapIndex']),
        })
    return {
        'version': 1,
        'madeAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'sourceBin': str(p.bin_path),
        'mapId': STATE['map'],
        'bossId': d.boss_id,
        'templatePid': d.template_pid,
        'templateSet': d.template_set,
        'newSet': d.new_set,
        'newPid': d.new_pid,
        'spots': spots,
        'playarea': {'pa1': d.pa1, 'pa2': d.pa2, 'nb1': d.nb1, 'nb2': d.nb2},
        'events': [{'modifierSet': e.get('modifierSet'), 'eventFlag': e.get('eventFlag'),
                    'modifier': e.get('modifier'), 'name': e.get('name') or ''}
                   for e in (d.events or [])],
        'rows': make_payload(p, d),   # 真正会写进那四张表的行
    }


def _flag_tests() -> list:
    """work/flag_tests.json：每次写回留下的 flag 对照记录（m06079）。"""
    path = ROOT / 'work' / 'flag_tests.json'
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []


def _events_state(p: Project, d) -> list:
    """事件 / flag 行：每行给出同 modifierSet 的其它选项（m05915）。"""
    out = []
    combos = p.base_combos()
    for i, ev in enumerate(d.events or []):
        opts = []
        for c in combos.get(int(ev['modifierSet']), []):
            opts.append({'eventFlag': c['eventFlag'], 'modifier': c['modifier'],
                         'name': c['name'] or '', 'weight': c['weight']})
        # 去重（base 里同一三元组会重复出现）
        seen = set()
        uniq = []
        for o in opts:
            k = (o['eventFlag'], o['modifier'])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(o)
        out.append({
            'i': i,
            'eventFlag': ev['eventFlag'],
            'modifier': ev['modifier'],
            'modifierSet': ev['modifierSet'],
            'name': ev.get('name') or '',
            'options': uniq,
        })
    return out


def _playarea_state(p: Project, d) -> dict:
    """四块：1缩 / 2缩（PlayAreaCreateParam）、1夜 / 2夜（Night Boss 变体）。"""
    tpl = p.model.playarea.get(d.template_pid) or {}
    areas = []
    prof = p.map_profiles().get(STATE.get('map')) or {}
    terrain = prof.get('terrain') or '[Standard]'
    allow = ('[Standard]', terrain)   # m06792：普通 + 当前地形
    seen_pos = set()
    for k, r in p.params.rows('PlayAreaCreateParam').items():
        nm = (r.get('_name') or '').strip()
        if not nm or int(k) >= 20000:   # 2xxxx / 3xxxx 是副本（无名或异地网格）
            continue
        m = re.match(r'\[[^\]]+\]', nm)
        pre = m.group(0) if m else ''
        if pre and pre not in allow:
            continue
        sig = (r.get('gridXNo'), r.get('gridZNo'), r.get('posX'), r.get('posZ'))
        if sig in seen_pos:            # 2xxxx / 3xxxx 是副本
            continue
        seen_pos.add(sig)
        areas.append({'id': int(k), 'name': nm,
                      'grid': [r.get('gridXNo'), r.get('gridZNo')],
                      'pos': [r.get('posX'), r.get('posZ')]})
    areas.sort(key=lambda x: x['id'])
    nights = []
    for k, r in p.params.rows('SmallBaseMapVariationParam').items():
        nm = (r.get('_name') or '').strip()
        if nm.startswith('Night Boss'):
            nights.append({'id': int(k), 'name': nm})
    nights.sort(key=lambda x: x['name'])
    cur = {
        'pa1': d.pa1 if d.pa1 is not None else tpl.get('playArea1'),
        'pa2': d.pa2 if d.pa2 is not None else tpl.get('playArea2'),
        'nb1': d.nb1 if d.nb1 is not None else tpl.get('bossId1'),
        'nb2': d.nb2 if d.nb2 is not None else tpl.get('bossId2'),
    }
    name_of = {a['id']: a['name'] for a in areas}
    boss_of = {n['id']: n['name'] for n in nights}
    return {
        'cur': cur,
        'curText': {
            'pa1': name_of.get(cur['pa1'], ''),
            'pa2': name_of.get(cur['pa2'], ''),
            'nb1': boss_of.get(cur['nb1'], ''),
            'nb2': boss_of.get(cur['nb2'], ''),
        },
        'areas': areas,
        'nights': nights,
        'isTemplate': d.pa1 is None and d.pa2 is None and d.nb1 is None and d.nb2 is None,
    }


def _anchors(p: Project) -> list:
    """校准过的建筑位（m05283）：按当前地图档案取，全部显示、全部可点。"""
    return p.attach_points(STATE.get('map'))


def _empty_slots(p: Project, tpl_all: list, tpl_draw: list) -> list:
    """空闲点 = 官方 attach 里本种子没用到的建筑位。

    三道过滤（m04640 / m04741 / m04900）：
      1. 只要大/小尺寸、名字不是 野外BOSS/监牢/商队/夜晚 的槽；
      2. pad != 0 的是特殊地形，不算普通地图；
      3. 和模板点**位置重合**的（Starter X 与 X 是同一个点，官方两个 attachId）
         不算空闲，否则灰圈会正好压在红点上，看着像「Major Base 变灰了」。
    """
    used_ids = {int(s['attachId']) for s in tpl_all}
    skip = ('field boss', 'evergaol', 'caravan', 'night')
    # 用**原始**世界坐标比，别用画面坐标：模板点被去重叠挪过，位置会差出几十像素
    pts = [(s['world'][0] - OX, OZ - s['world'][1]) for s in tpl_all if s.get('world')]
    out = []
    for x in p.attach_points():
        if x['attachSize'] not in ('大', '小'):
            continue
        if x['attachId'] in used_ids:
            continue
        if any(k in (x['attachName'] or '').lower() for k in skip):
            continue
        px = x['world'][0] - OX
        py = OZ - x['world'][1]
        if any(abs(px - tx) < 24 and abs(py - ty) < 24 for tx, ty in pts):
            continue
        x = {**x, 'px': px, 'py': py}
        out.append(x)
    return out


def _map_png() -> bytes:
    from app.core import render
    p: Project = STATE['project']
    tpl = (STATE['template'] or {}).get('spots') or []
    draft = []
    if p and STATE['draft']:
        draft = [p.spot_view(s['attachId'], s['tile'], s.get('variationId') or 0) for s in STATE['draft'].spots]
    bg = ASSETS / 'map' / _maps().get(STATE['map'], {}).get('bg', 'limveld.png')
    # 特殊地形：主人校掉的监牢别画（m06679）
    allowed = {ap['attachId'] for ap in p.attach_points(STATE['map'])}
    return render.png_bytes(tpl, draft, rev=str(STATE['rev']), bg=bg, allowed=allowed)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ('/', '/index.html'):
            return _file(self, WEB / 'index.html', 'text/html; charset=utf-8')
        if u.path == '/_clicktest.html':
            return _file(self, WEB / '_clicktest.html', 'text/html; charset=utf-8')
        if u.path == '/app.js':
            return _file(self, WEB / 'app.js', 'application/javascript; charset=utf-8')
        if u.path == '/style.css':
            return _file(self, WEB / 'style.css', 'text/css; charset=utf-8')
        if u.path == '/map/limveld.png':
            return _file(self, ASSETS / 'map' / 'limveld.png', 'image/png')
        if u.path.startswith('/pin/'):
            iid = u.path.rsplit('/', 1)[-1].replace('.png', '')
            f = ASSETS / 'icon' / 'pin' / f'{iid}.png'
            if f.exists():
                return _file(self, f, 'image/png')
            return _json(self, {'error': 'no pin'}, 404)
        if u.path == '/api/params':
            if not STATE['project']:
                return _json(self, {'ok': False, 'error': '先打开 bin'})
            aid = int(q.get('attach', ['0'])[0])
            tile = int(q.get('tile', ['0'])[0])
            return _json(self, {'ok': True,
                                'attachId': aid, 'tile': tile,
                                'fields': STATE['project'].raw_fields(aid, tile)})
        if u.path == '/api/cell':
            if not STATE['project']:
                return _json(self, {'ok': False, 'error': '先打开 bin'})
            gx = int(q.get('gx', ['0'])[0])
            gz = int(q.get('gz', ['0'])[0])
            return _json(self, {'ok': True, **STATE['project'].cell_candidates(gx, gz)})
        if u.path == '/api/attach':
            if not STATE['project']:
                return _json(self, {'ok': False, 'error': '先打开 bin'})
            aid = int(q.get('id', ['0'])[0])
            return _json(self, {'ok': True, 'candidate': STATE['project'].attach_candidates(aid)})
        if u.path == '/api/tile':
            # m06316：手输一个 smallBaseMapId，查它是什么建筑
            if not STATE['project']:
                return _json(self, {'ok': False, 'error': '先打开 bin'})
            try:
                aid = int(q.get('attach', ['0'])[0])
                tile = int(q.get('id', ['0'])[0])
            except ValueError:
                return _json(self, {'ok': False, 'error': 'id 必须是数字'})
            if tile <= 0:
                return _json(self, {'ok': False, 'error': 'id 必须大于 0'})
            return _json(self, {'ok': True, 'info': STATE['project'].tile_probe(aid, tile)})
        if u.path == '/api/variant':
            # m06850：手输 variationId（0 基）→ 查它对应哪一档、存不存在
            if not STATE['project']:
                return _json(self, {'ok': False, 'error': '先打开 bin'})
            try:
                tile = int(q.get('tile', ['0'])[0])
                vid = int(q.get('v', ['0'])[0])
            except ValueError:
                return _json(self, {'ok': False, 'error': 'tile / v 必须是数字'})
            if tile <= 0:
                return _json(self, {'ok': False, 'error': 'tile 必须大于 0'})
            if vid < 0:
                return _json(self, {'ok': False, 'error': 'variationId 是 0 基，不能是负数'})
            return _json(self, {'ok': True, 'info': STATE['project'].variant_probe(tile, vid)})
        if u.path == '/api/state':
            return _json(self, _draft_state())
        if u.path == '/api/export':
            # m06840：导出这次改动（可直接对账）
            if not STATE['project'] or not STATE['draft']:
                return _json(self, {'ok': False, 'error': '先建草稿'})
            d = STATE['draft']
            return _json(self, {'ok': True, 'file': f'nrseed_{d.new_pid}.json',
                                'json': _export_state(STATE['project'], d)})
        if u.path == '/api/tests':
            return _json(self, {'ok': True, 'tests': _flag_tests()})
        if u.path == '/api/map.png':
            if not STATE['project']:
                return _file(self, ASSETS / 'map' / 'limveld.png', 'image/png')
            data = _map_png()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        return _json(self, {'error': 'not found'}, 404)

    # ---------- POST ----------
    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except json.JSONDecodeError:
            return _json(self, {'ok': False, 'error': 'bad json'}, 400)

        with LOCK:
            try:
                if self.path == '/api/open':
                    return self._open(body)
                if self.path == '/api/draft':
                    return self._draft(body)
                if self.path == '/api/add':
                    return self._add(body)
                if self.path == '/api/remove':
                    return self._remove(body)
                if self.path == '/api/move':
                    return self._move(body)
                if self.path == '/api/undo':
                    return self._undo(body)
                if self.path == '/api/playarea':
                    return self._playarea(body)
                if self.path == '/api/event':
                    return self._event(body)
                if self.path == '/api/map':
                    return self._set_map(body)
                if self.path == '/api/write':
                    return self._write(body)
            except Exception as e:  # noqa: BLE001
                return _json(self, {'ok': False, 'error': f'{type(e).__name__}: {e}'})
        return _json(self, {'error': 'not found'}, 404)

    # ---------- 动作 ----------
    def _open(self, body):
        raw = str(body['path']).strip().strip('"')
        p_in = Path(raw)
        # m02740-1：支持只给一个文件夹，自动找里面的 regulation*.bin
        if p_in.is_dir():
            bins = sorted([x for x in p_in.glob('*.bin') if x.is_file()])
            # 收一层子目录（Game\SOT 那种）
            if not bins:
                bins = sorted(p_in.glob('*/*.bin'))
            if not bins:
                return _json(self, {'ok': False, 'error': f'这个文件夹里没有 .bin：{p_in}'})
            if len(bins) > 1:
                return _json(self, {'ok': False, 'needChoose': True,
                                    'dir': str(p_in),
                                    'bins': [str(x) for x in bins]})
            p_in = bins[0]
        if not p_in.exists():
            return _json(self, {'ok': False, 'error': f'找不到：{p_in}'})
        p = Project(str(p_in))
        STATE['project'] = p
        STATE['draft'] = None
        STATE['template'] = None
        STATE['history'] = []          # m06840：换 bin = 旧草稿的撤销栈作废
        STATE['rev'] += 1
        # 给校准工具留个「最近打开的 bin」
        try:
            (ROOT.parent if False else Path(__file__).resolve().parents[1]).joinpath(
                'work', 'last_bin.json').write_text(
                json.dumps({'path': str(p.bin_path)}, ensure_ascii=False), encoding='utf-8')
        except Exception:
            pass
        return _json(self, {
            'ok': True,
            'bin': str(p.bin_path),
            'params': p.param_count(),
            'bosses': [{'id': b['id'], 'name': b['name']} for b in p.bosses()],
        })

    def _draft(self, body):
        p: Project = STATE['project']
        if not p:
            return _json(self, {'ok': False, 'error': '先打开 bin'})
        d = D.new_draft(p, int(body['boss']))
        STATE['draft'] = d
        STATE['history'] = []          # m06840：新草稿 = 撤销栈清空
        STATE['rev'] += 1
        info = p.pattern_info(d.template_pid)
        STATE['template'] = {
            'pid': d.template_pid,
            'set': d.template_set,
            'setName': info.get('setName'),
            'range': info.get('range'),
            'spots': [_spot_payload(s) for s in info['spots']
                      if int(s['attachId']) < 1000],
        }
        return _json(self, _draft_state())

    def _add(self, body):
        p: Project = STATE['project']
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        tile = int(body['tile'])
        _push_history()
        STATE['rev'] += 1
        d.spots.append({
            'attachId': int(body['attachId']),
            'tile': tile,
            'mapIndex': int(body.get('mapIndex', 0)),
            'variationId': int(body.get('variationId', 0)),
        })
        return _json(self, _draft_state())

    def _set_map(self, body):
        """m06466：换地图 = 只换底图，坐标体系不动。"""
        mid = str(body.get('id') or 'limveld')
        maps = _maps()
        if mid not in maps:
            return _json(self, {'ok': False, 'error': f'没有这张图：{mid}'})
        STATE['map'] = mid
        STATE['rev'] += 1
        return _json(self, _draft_state())

    def _playarea(self, body):
        """m05590：四块各自换 —— 1缩 / 2缩（PlayAreaCreateParam）、1夜 / 2夜（Night Boss 变体）。"""
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        # 四块一起改时只存一份快照，撤销一次回退全部（m06840）
        nv = {}
        for k in ('pa1', 'pa2', 'nb1', 'nb2'):
            if k in body:
                v = body[k]
                nv[k] = None if v in (None, '', 0, '0') else int(v)
        if any(getattr(d, k) != v for k, v in nv.items()):
            _push_history()
            for k, v in nv.items():
                setattr(d, k, v)
            STATE['rev'] += 1
        return _json(self, _draft_state())

    def _event(self, body):
        """m05915：换某一行的 flag 档（同 modifierSet 内选）。"""
        p: Project = STATE['project']
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        i = int(body['index'])
        if not (0 <= i < len(d.events)):
            return _json(self, {'ok': False, 'error': '行号越界'})
        ev = d.events[i]
        flag, mod = int(body.get('eventFlag') or 0), int(body.get('modifier') or 0)
        if (ev['eventFlag'], ev['modifier']) != (flag, mod):
            _push_history()
            ev['eventFlag'] = flag
            ev['modifier'] = mod
            ev['name'] = p.flag_name(flag, mod, ev['modifierSet'])
            STATE['rev'] += 1
        return _json(self, _draft_state())

    def _move(self, body):
        """m06840：草稿排序。顺序决定同一建筑第几次出现（mapIndex），拖动即改。"""
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        try:
            a = int(body['from'])
            b = int(body['to'])
        except (KeyError, TypeError, ValueError):
            return _json(self, {'ok': False, 'error': 'from/to 必须是数字'})
        n = len(d.spots)
        if not (0 <= a < n):
            return _json(self, {'ok': False, 'error': 'from 越界'})
        b = max(0, min(n - 1, b))
        if a != b:
            _push_history()
            d.spots.insert(b, d.spots.pop(a))
            STATE['rev'] += 1
        return _json(self, _draft_state())

    def _undo(self, body):
        """m06840：撤销上一步（加/删/排序/缩圈/事件）。"""
        ok = _pop_history()
        st = _draft_state()
        st['undone'] = ok
        return _json(self, st)

    def _remove(self, body):
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        i = int(body['index'])
        if 0 <= i < len(d.spots):
            _push_history()
            d.spots.pop(i)
            STATE['rev'] += 1
        return _json(self, _draft_state())

    def _write(self, body):
        p: Project = STATE['project']
        d: D.Draft = STATE['draft']
        if not d:
            return _json(self, {'ok': False, 'error': '先建草稿'})
        rep = write_back(p, d, target_bin=Path(body.get('target') or p.bin_path))
        out = {'ok': rep['ok'], 'checks': rep['checks'],
               'out': rep['out'], 'target': rep['target'],
               'patternId': d.new_pid, 'set': d.new_set,
               'test': rep.get('test')}
        if rep.get('error'):
            out['error'] = rep['error']
        return _json(self, out)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8777
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'http://127.0.0.1:{port}/')
    srv.serve_forever()


if __name__ == '__main__':
    main()










