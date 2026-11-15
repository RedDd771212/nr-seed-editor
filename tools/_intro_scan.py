# 找出哪个 pid 还有"空建筑位"（前端 nearestCircle 半径口径：地点圈 44 / 建筑位 15 canvas px）
import json
import math
import sys
import urllib.request

BASE = 'http://127.0.0.1:8779'


def get(u):
    return json.load(urllib.request.urlopen(BASE + u))


def post(u, d):
    req = urllib.request.Request(BASE + u, data=json.dumps(d).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req))


def circles_of(tt):
    an = tt['anchors']
    by = {a['attachId']: a for a in an}
    ox, oz = tt['map']['ox'], tt['map']['oz']
    out = []
    for sp in (tt['pidInfo']['spotView'] or []):
        cx = cy = None
        aid = sp['attachId']
        for k in (aid, aid - 1000, aid - 2000, aid - 3000, aid + 1000, aid + 2000):
            if k > 0 and k in by:
                a = by[k]
                cx, cy = a['world'][0] - ox, oz - a['world'][1]
                break
        if cx is None and sp.get('world'):
            for a in an:
                if abs(a['world'][0] - sp['world'][0]) < 14 and abs(a['world'][1] - sp['world'][1]) < 14:
                    cx, cy = a['world'][0] - ox, oz - a['world'][1]
                    break
        if cx is None and sp.get('px') is not None:
            cx, cy = sp['px'], sp['py']
        if cx is not None:
            out.append((cx, cy))
    return an, ox, oz, out


def main():
    t = get('/api3/tree')
    if not t.get('ok'):
        print('bin not open')
        return
    only_std = '--std' in sys.argv
    items = [(s, p) for s in t['sets'] for p in s['patterns']]
    if only_std:
        items = [(s, p) for s, p in items if s.get('rare') == 0]
    res = []
    for s, p in items:
        tt = post('/api3/select', {'pid': p['pid']})
        an, ox, oz, sc = circles_of(tt)
        free = [a for a in an
                if all(math.hypot(x - (a['world'][0] - ox), y - (oz - a['world'][1])) > 46 for x, y in sc)]
        if free:
            res.append((p['pid'], (s.get('name') or '')[:30], len(sc), len(free),
                        [a['attachId'] for a in free][:8], free[0]['attachName'][:32]))
    res.sort(key=lambda r: -r[3])
    print('pids with free anchors:', len(res))
    for r in res[:15]:
        print(r)
    if res:
        print('BEST', res[0][0])


if __name__ == '__main__':
    main()
