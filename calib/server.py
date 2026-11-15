"""校准工具（和编辑器分开的第二个小工具）。

用途：把 attach 点摊在图上，主人手动拖位置 / 标删除，保存成 corrections_<map>.json，
      蓝鲸再逐条核对（不直接采信）。

- limveld：摊全部 562 个点（历史流程）
- 特殊地形（山顶/火山/腐败森林/隐城）：只摊「校准好的 47 个建筑位」，主人删掉这张图上不存在的即可

启动：python calib/server.py [端口]      默认 8778
"""
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJ = ROOT.parent
sys.path.insert(0, str(PROJ))

from app.core.project import Project  # noqa: E402

OX, OZ = 10504.44, 10491.71     # 和编辑器同一套标定
TILE, CENTER = 256.0, 128.0

MAPS = {
    "limveld": ("宁姆韦德（普通）", "limveld.png", "all"),
    "mountaintop": ("山顶（Mountaintop）", "mountaintop.png", "anchors"),
    "crater": ("火山口（The Crater）", "crater.png", "anchors"),
    "rotted": ("腐败森林（Rotted Woods）", "rotted.png", "anchors"),
    "shroud": ("隐城（Shrouded City）", "shroud.png", "anchors"),
}

STATE = {"project": None, "bin": None, "used": None, "map": "limveld"}


def _load(bin_path: str):
    p = Project(bin_path)
    used = {}                     # attachId -> 用到它的 patternId 个数
    seen = set()
    for s in p.model.spots:
        key = (int(s["attachId"]), int(s["patternId"]))
        if key in seen:
            continue
        seen.add(key)
        used[key[0]] = used.get(key[0], 0) + 1
    STATE.update(project=p, bin=str(p.bin_path), used=used)


def _anchor_rows(p: Project):
    """47 个校准过的建筑位（已含 attach_overrides 的坐标）。"""
    out = []
    for ap in p.attach_points():
        out.append({
            "id": ap["attachId"],
            "name": ap.get("attachName") or "",
            "grid": list(ap.get("grid") or []),
            "pos": [0.0, 0.0, 0.0],
            "world": list(ap["world"]),
            "pad": 0,
            "size": ap.get("attachSize") or "",
            "used": (STATE["used"] or {}).get(ap["attachId"], 0),
        })
    return out


def _all_rows(p: Project):
    pad = p.attach_pad()
    used = STATE["used"] or {}
    out = []
    for aid, ap in p.model.attach.items():
        gx, gz = ap.get("gridXNo"), ap.get("gridZNo")
        if gx is None or gz is None:
            continue
        px, pz = ap.get("posX") or 0.0, ap.get("posZ") or 0.0
        out.append({
            "id": aid,
            "name": ap.get("_name") or "",
            "grid": [gx, gz],
            "pos": [px, ap.get("posY") or 0.0, pz],
            "world": [gx * TILE + CENTER + px, gz * TILE + CENTER + pz],
            "pad": pad.get(aid, 0),
            "size": p.model.attach_size(ap.get("_name") or ""),
            "used": used.get(aid, 0),
        })
    return out


def _points():
    p = STATE["project"]
    kind = MAPS[STATE["map"]][2]
    rows = _anchor_rows(p) if kind == "anchors" else _all_rows(p)
    rows.sort(key=lambda x: x["id"])
    return rows


def _corr_file(mid=None):
    mid = mid or STATE["map"]
    if mid == "limveld":
        return ROOT / "corrections.json"
    return ROOT / f"corrections_{mid}.json"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, data, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self._file(ROOT / "web" / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._file(ROOT / "web" / "app.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self._file(ROOT / "web" / "style.css", "text/css; charset=utf-8")
        if path == "/map.png":
            bg = MAPS[STATE["map"]][1]
            return self._file(PROJ / "assets" / "map" / bg, "image/png")
        if path == "/api/state":
            mid = STATE["map"]
            return self._json({
                "ok": bool(STATE["project"]),
                "bin": STATE["bin"],
                "mapId": mid,
                "mapName": MAPS[mid][0],
                "maps": [{"id": k, "name": v[0]} for k, v in MAPS.items()],
                "map": {"ox": OX, "oz": OZ, "tile": TILE, "center": CENTER},
                "points": _points() if STATE["project"] else [],
                "corrections": self._read_corrections(),
            })
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if path == "/api/load":
            _load(body["path"])
            return self._json({"ok": True})
        if path == "/api/map":
            mid = body.get("id")
            if mid not in MAPS:
                return self._json({"ok": False, "error": "没有这张图"})
            STATE["map"] = mid
            return self._json({"ok": True, "mapId": mid})
        if path == "/api/reset":
            f = _corr_file()
            if f.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                (ROOT / "history").mkdir(exist_ok=True)
                (ROOT / "history" / f"reset_{STATE['map']}_{ts}.json").write_text(
                    f.read_text(encoding="utf-8"), encoding="utf-8")
                f.unlink()
            return self._json({"ok": True, "map": STATE["map"]})
        if path == "/api/save":
            data = {
                "bin": STATE["bin"],
                "map": STATE["map"],
                "savedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "items": body.get("items") or [],
            }
            f = _corr_file()
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            (ROOT / "history").mkdir(exist_ok=True)
            (ROOT / "history" / f"corrections_{STATE['map']}_{ts}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json({"ok": True, "count": len(data["items"]), "file": str(f)})
        self._json({"ok": False, "error": "not found"}, 404)

    def _read_corrections(self):
        f = _corr_file()
        if not f.exists():
            return {"items": []}
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {"items": []}

    def _file(self, path: Path, ctype: str):
        data = path.read_bytes()
        self._send(200, data, ctype)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8778
    bin_path = sys.argv[2] if len(sys.argv) > 2 else None
    if not bin_path:
        try:
            cfg = json.loads((PROJ / "work" / "last_bin.json").read_text(encoding="utf-8"))
            bin_path = cfg["path"]
        except Exception:
            bin_path = r"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin"
    _load(bin_path)
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"校准工具 → http://127.0.0.1:{port}/  ({STATE['bin']})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
