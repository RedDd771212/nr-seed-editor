# -*- coding: utf-8 -*-
"""大空洞「点位校准器」：62 个建筑位摊在上下两层底图上。

三件事一次做完：
  1. 层      —— 单击圆点在地表 / 地底之间切换
  2. 位置    —— 按住拖动即可挪（只影响显示与摆点，不写回 bin）
  3. 删除    —— 右键点一下标记不要（灰色 ✕），编辑器里就不列它

启动：python calib/layer_server.py [端口]     默认 8780
产物：src/data/great_hollow_layers.json
"""
import json
import math
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / 'src'))

from app.core.project import Project  # noqa: E402
from app.core.patternset import PatternModel  # noqa: E402

OX, OZ = 10504.44, 10491.71
TILE, CENTER = 256.0, 128.0
SIZE = 1536
SPREAD = 30          # 同坐标点的错开半径（地图像素）

SAVE = PROJ / 'src' / 'data' / 'great_hollow_layers.json'
BIN = PROJ / 'work' / 'demo' / 'demo_regulation.bin'
BG0 = PROJ / 'assets' / 'map' / 'great_hollow.png'
BG1 = PROJ / 'assets' / 'map' / 'great_hollow_b1.png'

HINT_UNDER = [1107, 1110, 1145, 1146, 1147, 1159, 1160, 1164]

STATE = {'bin': str(BIN), 'points': [], 'orig': {}}


def load_points():
    p = Project(str(BIN))
    rows = p.params.rows('SmallBaseAndSpotAttachPoint')
    # 大空洞种子（rareMap=4）里每个 attach 被哪些建筑 tile 用到
    pm = PatternModel(p.params)
    pids4 = {pt.pid for s in pm.sets.values() if s.rare_map == 4 for pt in s.patterns}
    tiles_of = {}
    for r in p.params.rows('LotResultSmallBaseAndSpot').values():
        if r.get('patternId') in pids4:
            tiles_of.setdefault(r.get('attachId'), set()).add(r.get('smallBaseMapId'))

    def used_by(aid):
        out = []
        for t in sorted(tiles_of.get(aid) or []):
            nm = (p.model.variation.get(t, {}).get('_name') or '').strip()
            out.append(f'{t} {nm}'.strip())
        return out

    saved = {}
    if SAVE.exists():
        try:
            data = json.loads(SAVE.read_text(encoding='utf-8'))
            for aid in data.get('under') or []:
                saved[int(aid)] = 'under'
            for aid in data.get('surface') or []:
                saved[int(aid)] = 'surface'
            saved['__deleted'] = {int(x) for x in (data.get('deleted') or [])}
            saved['__moved'] = {int(k): v for k, v in (data.get('moved') or {}).items()}
        except Exception:  # noqa: BLE001
            saved = {}

    deleted = saved.get('__deleted') or set()
    moved = saved.get('__moved') or {}
    pts = []
    for aid in sorted(k for k in rows if 1000 <= k < 2000):
        r = rows[aid]
        if aid in moved:
            wx, wz = moved[aid]
        else:
            wx = r['gridXNo'] * TILE + CENTER + (r['posX'] or 0)
            wz = r['gridZNo'] * TILE + CENTER + (r['posZ'] or 0)
        rx, ry = round(wx - OX, 1), round(OZ - wz, 1)
        # 真实原始坐标（不含 moved）：保存时拿它做基准，否则重新加载后
        # 会把「已挪过的位置」当成基线，导致没再拖动的点被判定成「没挪过」而丢失 moved
        raw_rx = round(r['gridXNo'] * TILE + CENTER + (r['posX'] or 0) - OX, 1)
        raw_ry = round(OZ - (r['gridZNo'] * TILE + CENTER + (r['posZ'] or 0)), 1)
        pts.append({
            'id': aid,
            'name': (r.get('_name') or '').strip(),
            'posY': round(r['posY'] or 0, 1),
            'rx': rx, 'ry': ry,          # 真实坐标（可拖动）
            'px': rx, 'py': ry,          # 显示坐标（同点会被错开）
            'layer': saved.get(aid) or ('under' if aid in HINT_UNDER else 'surface'),
            'deleted': aid in deleted,
            'usedBy': used_by(aid),
            '_raw': (raw_rx, raw_ry),
        })
    STATE['orig'] = {q['id']: q['_raw'] for q in pts}
    # 同坐标点绕圈错开，免得叠在一起点不到
    groups = {}
    for q in pts:
        groups.setdefault((round(q['rx'] / 3), round(q['ry'] / 3)), []).append(q)
    for grp in groups.values():
        if len(grp) < 2:
            continue
        for n, q in enumerate(grp):
            ang = -math.pi / 2 + 2 * math.pi * n / len(grp)
            q['px'] = round(q['rx'] + SPREAD * math.cos(ang), 1)
            q['py'] = round(q['ry'] + SPREAD * math.sin(ang), 1)
    STATE['points'] = pts
    return pts


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, data, ctype='application/json'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode('utf-8'))

    def _file(self, path: Path, ctype: str):
        self._send(200, path.read_bytes(), ctype)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/':
            return self._file(ROOT / 'layer.html', 'text/html; charset=utf-8')
        if path == '/bg0.png':
            return self._file(BG0, 'image/png')
        if path == '/bg1.png':
            return self._file(BG1, 'image/png')
        if path == '/api/state':
            return self._json({
                'ok': True, 'bin': STATE['bin'], 'size': SIZE,
                'points': STATE['points'],
                'saved': SAVE.exists(), 'savePath': str(SAVE),
            })
        return self._json({'ok': False, 'error': 'not found'}, 404)

    def do_POST(self):
        path = self.path.split('?')[0]
        n = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except json.JSONDecodeError:
            return self._json({'ok': False, 'error': 'bad json'}, 400)

        if path == '/api/save':
            # 前端把当前状态整份传回来，以它为准
            incoming = {int(q['id']): q for q in (body.get('points') or [])}
            if incoming:
                for q in STATE['points']:
                    src = incoming.get(q['id'])
                    if not src:
                        continue
                    q['layer'] = src.get('layer') or q['layer']
                    q['deleted'] = bool(src.get('deleted'))
                    q['rx'] = float(src.get('rx', q['rx']))
                    q['ry'] = float(src.get('ry', q['ry']))
                    q['px'] = float(src.get('px', q['px']))
                    q['py'] = float(src.get('py', q['py']))

            under, surface, deleted, moved = [], [], [], {}
            for q in STATE['points']:
                if q['deleted']:
                    deleted.append(q['id'])
                    continue
                (under if q['layer'] == 'under' else surface).append(q['id'])
                ox, oy = STATE['orig'].get(q['id'], (q['rx'], q['ry']))
                if abs(q['rx'] - ox) > 0.5 or abs(q['ry'] - oy) > 0.5:
                    moved[str(q['id'])] = [round(q['rx'] + OX, 1), round(OZ - q['ry'], 1)]

            data = {
                'map': 'great_hollow',
                'savedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'bin': STATE['bin'],
                'count': len(STATE['points']),
                'under': sorted(under),
                'surface': sorted(surface),
                'deleted': sorted(deleted),
                'moved': moved,
                'note': 'attachId 列表就是最终规则；moved 是 [world_x, world_z] 覆盖；名字只用于生成初值',
            }
            SAVE.parent.mkdir(parents=True, exist_ok=True)
            SAVE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            hist = ROOT / 'history'
            hist.mkdir(exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            (hist / f'layers_{ts}.json').write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            # 顺手把校准结果同步进 maps.json，编辑器刷新就能看到（不用再手动跑脚本）
            synced = None
            try:
                import importlib
                import io
                import contextlib
                sys.path.insert(0, str(PROJ / 'tools'))
                mod = importlib.import_module('apply_great_hollow')
                importlib.reload(mod)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    mod.main()
                synced = buf.getvalue().strip().splitlines()[-1] if buf.getvalue().strip() else 'ok'
            except Exception as e:  # noqa: BLE001
                synced = f'同步到 maps.json 失败：{type(e).__name__}: {e}'
            return self._json({'ok': True, 'file': str(SAVE), 'under': len(under),
                               'surface': len(surface), 'deleted': len(deleted),
                               'moved': len(moved), 'synced': synced})

        if path == '/api/reload':
            load_points()
            return self._json({'ok': True, 'points': STATE['points']})

        if path == '/api/reset':
            if SAVE.exists():
                SAVE.unlink()
            return self._json({'ok': True})

        return self._json({'ok': False, 'error': 'not found'}, 404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8780
    load_points()
    print(f'点位校准器 → http://127.0.0.1:{port}/   ({STATE["bin"]})')
    ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever()


if __name__ == '__main__':
    main()
