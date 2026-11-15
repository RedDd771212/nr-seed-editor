# -*- coding: utf-8 -*-
"""paramtool.py —— 直接读写解包后的 .param 字节（不经过 XML）

配套 regtool.dll（unpack/pack）使用：
  regtool 负责把 regulation.bin 解成 252 个 .param，再把改好的封回去
  本脚本负责按 Smithbox 的 paramdef 字段名读写值，以及加行/删行

用法：
  python paramtool.py defs                              # 打印使用的 def 目录
  python paramtool.py rows   <param目录> <表名>          # 列出所有行 ID
  python paramtool.py get    <param目录> <表名> <行ID> <字段>
  python paramtool.py set    <param目录> <表名> <行ID> <字段> <值>
  python paramtool.py dump   <param目录> <表名> <行ID>    # 打印该行所有字段
  python paramtool.py add    <param目录> <表名> <新行ID> [行名]
  python paramtool.py remove <param目录> <表名> <行ID>
  python paramtool.py schema <param目录> [输出目录]      # 导出全表 schema（json + 2 个 csv）

表名不带 .param 后缀，例如 NpcParam、Magic、Bullet。

加行/删行的实现（2026-10-21 实测）：
  param 布局：
    0x00 i32 stringsOffset（0x10 同值）
    0x0A u16 行数
    0x40     行表，每项 24 字节：i64 id, i64 dataOff, i64 nameOff
    0x40+24n 数据区，每行 rowSize 字节
    stringsOffset 起为字符串区（UTF-16LE 零结尾行名）
  重建时只改 0x00/0x0A/0x10 和行表三个字段，其余 header 字节原样保留。
  重建不改动的表与原件逐字节一致（Magic/NpcParam/Bullet/EquipParamWeapon/MapGdRegionInfoParam 已验证）。
  删行不回收字符串区（文件会留一点旧名字的字节），但行数据与行数正确。

纪律：
  - 只改文件字节，不序列化 XML，不碰 WitchyBND
  - 改前备份整个 param 目录
  - 改完必须 pack 回去再 unpack 验一遍
"""
import glob
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paramdump as pd

TYPE_FMT = {
    "u8": "B", "s8": "b", "x8": "B",
    "u16": "H", "s16": "h", "x16": "H",
    "u32": "I", "s32": "i", "x32": "I",
    "f32": "f",
    "u64": "Q", "s64": "q", "x64": "Q",
    "f64": "d",
}

INT_RANGES = {
    "u8": (0, 255), "s8": (-128, 127),
    "u16": (0, 65535), "s16": (-32768, 32767),
    "u32": (0, 2**32 - 1), "s32": (-(2**31), 2**31 - 1),
    "u64": (0, 2**64 - 1), "s64": (-(2**63), 2**63 - 1),
}


def find_def_dir():
    cands = []
    env = os.environ.get("SMITHBOX_DIR")
    if env:
        cands.append(os.path.join(env, "Assets", "PARAM", "NR", "Defs"))
    root = os.environ.get("ERTOOLS_ROOT", r"E:\ERtools")
    cands += glob.glob(os.path.join(root, "Smithbox*", "Assets", "PARAM", "NR", "Defs"))
    cands = [c for c in cands if os.path.isdir(c)]
    if not cands:
        raise SystemExit("找不到 Smithbox 的 NR paramdef 目录（可设 SMITHBOX_DIR）")
    return max(cands, key=os.path.getmtime)


DEF_DIR = find_def_dir()


def load_def(table):
    path = os.path.join(DEF_DIR, table + ".xml")
    if not os.path.exists(path):
        raise SystemExit("找不到 paramdef：" + path)
    return pd.parse_def(path)


def field_offset(d, name):
    """返回 (偏移, 存储字节数, bit 位移或 None)"""
    off = 0
    for f in d["fields"]:
        names = f["name"].split("|")
        if name in names:
            if f["bitlist"] is not None:
                for n, sh in f["bitlist"]:
                    if n == name:
                        return off, f["size"], sh
                raise SystemExit(name + " 不在位域组里")
            return off, f["total"], None
        off += f["total"]
    raise SystemExit("字段不存在：" + name + "（可用 dump 查看）")


def open_param(param_dir, table):
    path = os.path.join(param_dir, table + ".param")
    if not os.path.exists(path):
        raise SystemExit("找不到 param 文件：" + path)
    return path, bytearray(open(path, "rb").read())


def find_row(ents, rowid):
    for rid, doff, noff in ents:
        if rid == rowid:
            return doff, noff
    raise SystemExit("行不存在：" + str(rowid))


def set_value(buf, doff, off, size, bit, value, fmt):
    if bit is not None:
        raw = int.from_bytes(buf[doff + off:doff + off + size], "little")
        raw = (raw & ~(1 << bit)) | ((int(value) & 1) << bit)
        buf[doff + off:doff + off + size] = raw.to_bytes(size, "little")
        return
    struct.pack_into("<" + fmt, buf, doff + off, value)


def decode_display(buf, d, doff):
    out = []
    p = doff
    for f in d["fields"]:
        if f["bitlist"] is not None:
            raw = int.from_bytes(buf[p:p + f["size"]], "little")
            bits = [(n, (raw >> sh) & 1) for n, sh in f["bitlist"]]
            out.append((f["name"], "0x%02X " % raw + " ".join("%s=%d" % (a, b) for a, b in bits)))
            p += f["size"]
            continue
        if f["type"] in ("fixstr", "fixstrW"):
            raw = bytes(buf[p:p + f["total"]])
            if f["type"] == "fixstrW":
                txt = raw.decode("utf-16-le", "backslashreplace").rstrip("\x00")
            else:
                txt = raw.rstrip(b"\x00").decode("utf-8", "backslashreplace")
            out.append((f["name"], txt))
            p += f["total"]
            continue
        if f["type"] == "dummy8" or f["type"].startswith("x"):
            p += f["total"]
            continue
        n = f["arr"] or 1
        vals = []
        for _ in range(n):
            raw = buf[p:p + f["size"]]
            if f["type"][0] == "f":
                v = struct.unpack("<f" if f["size"] == 4 else "<d", raw)[0]
            elif f["type"][0] == "u":
                v = int.from_bytes(raw, "little")
            else:
                v = int.from_bytes(raw, "little", signed=True)
            vals.append(v)
            p += f["size"]
        out.append((f["name"], vals[0] if n == 1 else vals))
    return out


# ---------------- 加行 / 删行 ----------------

def parse_table(buf):
    """返回 (行数, stringsOffset, [(id, dataOff, nameOff)], rowSize)"""
    n = struct.unpack_from("<H", buf, 0x0A)[0]
    strings_off = struct.unpack_from("<i", buf, 0x00)[0]
    table = []
    for i in range(n):
        rid, doff, noff = struct.unpack_from("<qqq", buf, 0x40 + i * 24)
        table.append((rid, doff, noff))
    if n == 0:
        return 0, strings_off, table, 0
    data_start = 0x40 + 24 * n
    row_size = (strings_off - data_start) // n
    return n, strings_off, table, row_size


def rebuild(buf, rows, row_size, new_names=None):
    """rows: [(id, data_bytes, old_name_off)]；new_names: {索引: 行名}
    返回新文件字节。"""
    n = len(rows)
    old_s = struct.unpack_from("<i", buf, 0)[0]
    old_strings = bytes(buf[old_s:])
    header = bytearray(buf[:0x40])
    data_start = 0x40 + 24 * n
    strings_start = data_start + n * row_size
    delta = strings_start - old_s

    out = bytearray()
    out += header
    out += b"\x00" * (24 * n)
    for _, data, _ in rows:
        out += data
    out += old_strings

    new_name_off = {}
    if new_names:
        for idx, nm in new_names.items():
            off = len(out)
            out += nm.encode("utf-16-le") + b"\x00\x00"
            new_name_off[idx] = off

    for i, (rid, data, old_name_off) in enumerate(rows):
        if new_names and i in new_names:
            noff = new_name_off[i]
        else:
            noff = old_name_off + delta
        struct.pack_into("<qqq", out, 0x40 + i * 24, rid, data_start + i * row_size, noff)

    struct.pack_into("<i", out, 0x00, strings_start)
    struct.pack_into("<H", out, 0x0A, n)
    struct.pack_into("<i", out, 0x10, strings_start)
    return bytes(out)


def _parse_num(txt):
    try:
        return int(txt, 0)
    except ValueError:
        return float(txt)


def default_row(defpath, row_size):
    d = pd.parse_def(defpath)
    row = bytearray(row_size)
    off = 0
    for f in d["fields"]:
        if f["bitlist"] is not None:
            off += f["size"]
            continue
        if f["type"] in ("dummy8", "fixstr", "fixstrW") or f["type"].startswith("x"):
            off += f["total"]
            continue
        arr = f["arr"] or 1
        for k in range(arr):
            v = 0
            if f["default"] is not None:
                txt = f["default"].strip()
                if txt.startswith("[") and txt.endswith("]"):
                    parts = txt[1:-1].split("|")
                    if k < len(parts):
                        v = _parse_num(parts[k])
                else:
                    v = _parse_num(txt)
            if f["type"][0] == "f":
                struct.pack_into("<f" if f["size"] == 4 else "<d", row, off, float(v))
            elif f["type"][0] == "u":
                v = int(v)
                row[off:off + f["size"]] = (v & ((1 << (8 * f["size"])) - 1)).to_bytes(f["size"], "little")
            else:
                struct.pack_into("<" + TYPE_FMT.get(f["type"], "i"), row, off, int(v))
            off += f["size"]
    return bytes(row)


def cmd_add(param_dir, table, newid, name=""):
    p = os.path.join(param_dir, table + ".param")
    buf = open(p, "rb").read()
    n, strings_off, table_rows, row_size = parse_table(buf)
    if any(r[0] == newid for r in table_rows):
        raise SystemExit("行已存在: %d" % newid)
    rows = [(rid, bytes(buf[doff:doff + row_size]), noff) for rid, doff, noff in table_rows]
    newdata = default_row(os.path.join(DEF_DIR, table + ".xml"), row_size)
    rows.append((newid, newdata, 0))
    rows.sort(key=lambda r: r[0])
    idx = next(i for i, r in enumerate(rows) if r[0] == newid)
    out = rebuild(buf, rows, row_size, {idx: name or ""})
    open(p, "wb").write(out)
    print("OK add %s[%d] name=%r rows=%d" % (table, newid, name, len(rows)))


def cmd_remove(param_dir, table, rowid):
    p = os.path.join(param_dir, table + ".param")
    buf = open(p, "rb").read()
    n, strings_off, table_rows, row_size = parse_table(buf)
    if not any(r[0] == rowid for r in table_rows):
        raise SystemExit("行不存在: %d" % rowid)
    rows = [(rid, bytes(buf[doff:doff + row_size]), noff)
            for rid, doff, noff in table_rows if rid != rowid]
    out = rebuild(buf, rows, row_size)
    open(p, "wb").write(out)
    print("OK remove %s[%d] rows=%d" % (table, rowid, len(rows)))


# ---------------- 导出全表 schema ----------------

def _def_fields(d):
    """把 paramdef 展开成带偏移的字段列表（位域拆成独立字段）"""
    out = []
    off = 0
    for f in d["fields"]:
        if f["bitlist"] is not None:
            for nm, sh in f["bitlist"]:
                out.append(dict(name=nm, type=f["type"], offset=off,
                                size=f["size"], arr=None, bit=sh, default=None))
            off += f["size"]
            continue
        out.append(dict(name=f["name"], type=f["type"], offset=off,
                        size=f["total"], arr=f["arr"], bit=None,
                        default=f["default"]))
        off += f["total"]
    return out


def _def_candidates(table):
    """缺 def 时的备选：去掉最后一段后缀（AtkParam_Npc → AtkParam）"""
    return [table.rsplit("_", 1)[0]] if "_" in table else []


def cmd_schema(param_dir, out_dir):
    import csv
    import json

    os.makedirs(out_dir, exist_ok=True)
    tables, field_rows, warns = [], [], []
    for p in sorted(glob.glob(os.path.join(param_dir, "*.param"))):
        table = os.path.splitext(os.path.basename(p))[0]
        buf = open(p, "rb").read()
        soff, ents, rs = pd.read_table(buf)
        hdr_n = struct.unpack_from("<H", buf, 0x0A)[0]
        if hdr_n != len(ents):
            warns.append("%s: headerRows=%d tableRows=%d" % (table, hdr_n, len(ents)))
        defpath = os.path.join(DEF_DIR, table + ".xml")
        defsrc = "exact"
        if not os.path.exists(defpath):
            defpath, defsrc = None, None
            for cand in _def_candidates(table):
                cp = os.path.join(DEF_DIR, cand + ".xml")
                if os.path.exists(cp):
                    defpath, defsrc = cp, "fallback:" + cand
                    break
        d = pd.parse_def(defpath) if defpath else None
        if d is not None and defsrc != "exact" and rs is not None and d["defsize"] != rs:
            warns.append("%s: %s defRowSize=%d != rowSize=%s -> 拒绝该 def"
                         % (table, defsrc, d["defsize"], rs))
            d, defsrc = None, "rejected"
        if d is None:
            warns.append("%s: 缺 paramdef（无可用 fallback，字段不可索引）" % table)
        fields = _def_fields(d) if d else []
        tables.append(dict(
            table=table,
            paramtype=(d or {}).get("paramtype"),
            defSource=defsrc,
            rows=len(ents),
            rowSize=rs,
            defRowSize=(d or {}).get("defsize"),
            fieldCount=len(fields),
            fields=fields,
        ))
        for f in fields:
            field_rows.append([table, f["offset"], f["name"], f["type"],
                               f["arr"] or "", "" if f["bit"] is None else f["bit"],
                               f["size"], f["default"] or ""])

    with open(os.path.join(out_dir, "schema.json"), "w", encoding="utf-8") as fp:
        json.dump({"tables": tables}, fp, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "schema_tables.csv"), "w",
              encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["table", "paramtype", "defSource", "rows", "rowSize",
                    "defRowSize", "fieldCount"])
        for t in tables:
            w.writerow([t["table"], t["paramtype"], t["defSource"], t["rows"],
                        t["rowSize"], t["defRowSize"], t["fieldCount"]])
    with open(os.path.join(out_dir, "schema_fields.csv"), "w",
              encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["table", "offset", "field", "type", "arr", "bit", "size", "default"])
        w.writerows(field_rows)

    print("tables=%d fields=%d -> %s" % (len(tables), len(field_rows), out_dir))
    if warns:
        print("warnings=%d" % len(warns))
        for x in warns[:20]:
            print("  " + x)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    mode = args[0]

    if mode == "defs":
        print(DEF_DIR)
        return

    if mode == "schema":
        out_dir = args[2] if len(args) > 2 else "."
        cmd_schema(args[1], out_dir)
        return

    param_dir = args[1]
    table = args[2]

    if mode == "rows":
        path, buf = open_param(param_dir, table)
        n, soff, tr, rs = parse_table(buf)
        print("# %s: rows=%d rowSize=%s" % (table, n, rs))
        for rid, doff, noff in tr:
            print(rid)
        return

    if mode == "dump":
        rowid = int(args[3], 0)
        path, buf = open_param(param_dir, table)
        d = load_def(table)
        n, soff, tr, rs = parse_table(buf)
        doff, noff = find_row(tr, rowid)
        print("# %s row=%s dataOff=%s" % (table, rowid, doff))
        for name, v in decode_display(buf, d, doff):
            print("  %s = %s" % (name, v))
        return

    if mode == "get":
        rowid = int(args[3], 0)
        fname = args[4]
        path, buf = open_param(param_dir, table)
        d = load_def(table)
        n, soff, tr, rs = parse_table(buf)
        doff, noff = find_row(tr, rowid)
        off, size, bit = field_offset(d, fname)
        f = next(x for x in d["fields"] if fname in x["name"].split("|"))
        if bit is not None:
            raw = int.from_bytes(buf[doff + off:doff + off + size], "little")
            print((raw >> bit) & 1)
        else:
            print(struct.unpack_from("<" + TYPE_FMT[f["type"]], buf, doff + off)[0])
        return

    if mode == "set":
        rowid = int(args[3], 0)
        fname = args[4]
        value = args[5]
        path, buf = open_param(param_dir, table)
        d = load_def(table)
        n, soff, tr, rs = parse_table(buf)
        doff, noff = find_row(tr, rowid)
        off, size, bit = field_offset(d, fname)
        f = next(x for x in d["fields"] if fname in x["name"].split("|"))
        if bit is not None:
            set_value(buf, doff, off, size, bit, int(value, 0), None)
        else:
            fmt = TYPE_FMT[f["type"]]
            if f["type"][0] == "f":
                val = float(value)
            else:
                val = int(value, 0)
                lo, hi = INT_RANGES[f["type"]]
                if not (lo <= val <= hi):
                    raise SystemExit("值 %s 超出 %s 范围 [%s, %s]" % (val, f["type"], lo, hi))
            set_value(buf, doff, off, size, bit, val, fmt)
        open(path, "wb").write(buf)
        print("OK %s[%s].%s = %s" % (table, rowid, fname, value))
        return

    if mode == "add":
        newid = int(args[3], 0)
        name = args[4] if len(args) > 4 else ""
        cmd_add(param_dir, table, newid, name)
        return

    if mode == "remove":
        rowid = int(args[3], 0)
        cmd_remove(param_dir, table, rowid)
        return

    print(__doc__)


if __name__ == "__main__":
    main()
