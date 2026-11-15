# -*- coding: utf-8 -*-
"""只读 PARAM 目录访问层。

依赖 fs-bin-modding 技能里的 paramdump.py（读 param 二进制 + Smithbox 的 paramdef XML）。
本模块只做「按表名取行、按字段名取值」，绝不写文件。
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

# 优先用项目自带的 src\vendor（发布包），找不到再退回开发机的技能目录
_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_CANDS = [_ROOT / 'src' / 'vendor',
                 Path.home() / '.dsh' / 'skills' / 'fs-bin-modding' / 'scripts']
_SCRIPTS = next((p for p in _SCRIPT_CANDS if p.exists()), None)
if _SCRIPTS is None:
    raise SystemExit('缺少 paramtool/paramdump：请检查 src\\vendor\\')
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import paramdump as pd  # noqa: E402


def find_def_dir() -> str:
    env = os.environ.get("SMITHBOX_DIR")
    cands = []
    if env:
        cands.append(os.path.join(env, "Assets", "PARAM", "NR", "Defs"))
    cands.append(str(_ROOT / "vendor" / "NRDefs"))
    for root in (r"E:\ERtools", r"D:\ERtools", r"C:\ERtools"):
        cands += glob.glob(os.path.join(root, "Smithbox*", "Assets", "PARAM", "NR", "Defs"))
    for c in cands:
        if os.path.isdir(c):
            return c
    raise SystemExit("找不到 NR paramdef 目录（发布包里应该在 vendor\\NRDefs）")


class ParamDir:
    """一个解包后的 param 目录（regtool unpack 的产物）。"""

    MAX_ROWS = 200000

    def __init__(self, path: str, def_dir: str | None = None):
        self.path = path
        self.def_dir = def_dir or find_def_dir()
        self._defs: dict[str, dict] = {}
        self._rows: dict[str, dict[int, dict]] = {}
        self._order: dict[str, list[int]] = {}
        self._meta: dict[str, dict] = {}

    # ---------- 基础 ----------
    def has(self, table: str) -> bool:
        return os.path.isfile(os.path.join(self.path, table + ".param"))

    def definition(self, table: str) -> dict:
        if table not in self._defs:
            self._defs[table] = pd.parse_def(os.path.join(self.def_dir, table + ".xml"))
        return self._defs[table]

    def meta(self, table: str) -> dict:
        if table not in self._meta:
            self._load(table)
        return self._meta[table]

    def rows(self, table: str) -> dict[int, dict]:
        """行 id -> {字段名: 值}（位域会展开成 a=1 b=0）。"""
        if table not in self._rows:
            self._load(table)
        return self._rows[table]

    def order(self, table: str) -> list[int]:
        if table not in self._order:
            self._load(table)
        return self._order[table]

    # ---------- 内部 ----------
    def _load(self, table: str):
        path = os.path.join(self.path, table + ".param")
        if not os.path.isfile(path):
            raise KeyError(f"没有这张表：{path}")
        d = self.definition(table)
        with open(path, "rb") as f:
            b = f.read()
        soff, ents, rowsize = self._read_table(b)
        rows, order = {}, []
        for rid, doff, noff in ents:
            row: dict = {"_id": rid, "_name": pd.str_at(b, noff)}
            for name, v, bits in pd.decode_row(b, doff, d["fields"]):
                if bits is not None:
                    row["_bits_" + name] = v
                    for bn, bv in bits:
                        row[bn] = bv
                else:
                    row[name] = v
            rows[rid] = row
            order.append(rid)
        self._rows[table] = rows
        self._order[table] = order
        self._meta[table] = {
            "rows": len(ents),
            "rowSize": rowsize,
            "defRowSize": d["defsize"],
            "paramType": d["paramtype"],
            "dataVersion": d["dataversion"],
        }

    def _read_table(self, b: bytes):
        """与 paramdump.read_table 同算法，但不设 20000 行上限（大表要全读）。"""
        import struct

        strings_off = struct.unpack_from("<i", b, 0)[0]
        ents = []
        o = 0x40
        while o + 24 <= len(b):
            rid, doff, noff = struct.unpack_from("<qqq", b, o)
            if ents and doff < ents[-1][1]:
                break
            ents.append((rid, doff, noff))
            o += 24
            if len(ents) > self.MAX_ROWS:
                break
        if ents and ents[0][1] >= 0x40:
            n = (ents[0][1] - 0x40) // 24
            if 0 < n <= len(ents):
                ents = ents[:n]
        rowsize = (ents[1][1] - ents[0][1]) if len(ents) > 1 else None
        return strings_off, ents, rowsize
