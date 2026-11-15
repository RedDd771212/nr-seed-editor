# -*- coding: utf-8 -*-
"""往 param 目录里追加行（只碰目标表，不改其他表）。"""
from __future__ import annotations

import sys
from pathlib import Path

from app.core.paths import SCRIPTS, DEF_DIR

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import paramtool as pt  # noqa: E402

pt.DEF_DIR = str(DEF_DIR)      # 统一用随包携带的 paramdef

FMT = {'s8': 'b', 'u8': 'B', 's16': 'h', 'u16': 'H',
       's32': 'i', 'u32': 'I', 'f32': 'f', 'f64': 'd'}


def _field_map(d) -> dict:
    """name -> (offset, size, bit, fmt)"""
    out, off = {}, 0
    for f in d['fields']:
        if f['bitlist'] is not None:
            for nm, sh in f['bitlist']:
                out[nm] = (off, f['size'], sh, None)
            off += f['total']
            continue
        for nm in f['name'].split('|'):
            out[nm] = (off, f['total'], None, FMT.get(f['type']))
        off += f['total']
    return out


def read_table(param_dir: Path, table: str):
    _, buf = pt.open_param(str(param_dir), table)
    n, strings_off, tbl, row_size = pt.parse_table(buf)
    rows = [{'id': rid, 'data': bytes(buf[doff:doff + row_size]), 'noff': noff, 'name': None}
            for rid, doff, noff in tbl]
    return bytearray(buf), rows, row_size


def append_rows(param_dir: Path, table: str, new_rows: list[tuple]) -> list[int]:
    """new_rows: [(id, name, {field: value})] → 追加并落盘，返回所有行 id。"""
    buf, rows, row_size = read_table(param_dir, table)
    d = pt.load_def(table)
    fm = _field_map(d)
    defpath = str(Path(pt.DEF_DIR) / (table + '.xml'))

    for rid, name, values in new_rows:
        if any(r['id'] == rid for r in rows):
            raise ValueError(f'{table} 已有 id={rid}')
        data = bytearray(pt.default_row(defpath, row_size))
        for k, v in values.items():
            if k not in fm:
                raise KeyError(f'{table} 没有字段 {k}')
            off, size, bit, fmt = fm[k]
            if bit is not None:
                pt.set_value(data, 0, off, size, bit, int(v), None)
            elif fmt is None:
                raise KeyError(f'{table}.{k} 字段类型不支持')
            else:
                pt.set_value(data, 0, off, size, None, v, fmt)
        rows.append({'id': rid, 'data': bytes(data), 'noff': -1, 'name': name or str(rid)})

    rows.sort(key=lambda r: r['id'])
    new_names = {i: r['name'] for i, r in enumerate(rows) if r['name']}
    packed = [(r['id'], r['data'], r['noff']) for r in rows]
    out = pt.rebuild(buf, packed, row_size, new_names)
    Path(param_dir, table + '.param').write_bytes(bytes(out))
    return [r['id'] for r in rows]
