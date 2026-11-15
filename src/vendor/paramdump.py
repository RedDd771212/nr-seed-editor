# -*- coding: utf-8 -*-
"""
通用 PARAM 读取器（独立实现，不依赖 WitchyBND 的交互式游戏选择）。
用法:
  python paramdump.py <param文件> <paramdef.xml> <rowid ...>
  python paramdump.py --all  <param文件> <paramdef.xml>
  python paramdump.py --list <param文件> <paramdef.xml>
只读，绝不修改源文件。
行表固定在 0x40，每项 24 字节 (i64 id, i64 dataOffset, i64 nameOffset)；
行数与行宽由 dataOffset 间距经验推算（比头部字段可靠）。
"""
import sys, io, os, struct, re
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

TYPE_SIZE = {'u8': 1, 's8': 1, 'dummy8': 1, 'x8': 1,
             'u16': 2, 's16': 2, 'x16': 2,
             'u32': 4, 's32': 4, 'f32': 4, 'x32': 4,
             'u64': 8, 's64': 8, 'f64': 8, 'x64': 8,
             'fixstr': 1,   # 固定长字符串：1 字节 * arr 个数
             'fixstrW': 2}  # 固定长宽字符串：2 字节 * arr 个数

FIELD_RE = re.compile(
    r'^(\w+)\s+([A-Za-z_]\w*)(?:\[(\d+)\])?(?::(\d+))?(?:\s*=\s*(.+?))?$')


def parse_def(path):
    root = ET.parse(path).getroot()
    fields = []
    for f in root.find('Fields').findall('Field'):
        m = FIELD_RE.match(f.get('Def').strip())
        if not m:
            raise SystemExit('无法解析字段定义: ' + f.get('Def'))
        ftype, name, arr, bit, default = m.groups()
        size = TYPE_SIZE[ftype]
        total = size * int(arr) if arr else size
        fields.append(dict(type=ftype, name=name, arr=int(arr) if arr else None,
                           default=default, bit=int(bit) if bit else None,
                           size=size, total=total))
    # 合并连续位域为一个存储单元
    final, i = [], 0
    while i < len(fields):
        f = fields[i]
        # 位域：连续的 :bit 字段按「存储单元容量」累积合并（u8/dummy8 都算 1 字节单元）
        if f['bit'] is not None:
            j, bitlist, used = i, [], 0
            base = f['size']
            while j < len(fields) and fields[j]['bit'] is not None and fields[j]['size'] == base \
                    and used + fields[j]['bit'] <= base * 8:
                bitlist.append((fields[j]['name'], used))
                used += fields[j]['bit']
                j += 1
            final.append(dict(type=f['type'], name='|'.join(b[0] for b in bitlist),
                              size=base, total=base, bitlist=bitlist,
                              arr=None, default=None, bit=None))
            i = j
            continue
        final.append(dict(type=f['type'], name=f['name'], size=f['size'], total=f['total'],
                          arr=f['arr'], default=f['default'], bit=None, bitlist=None))
        i += 1
    return dict(paramtype=root.findtext('ParamType'),
                dataversion=int(root.findtext('DataVersion') or 0),
                unicode=(root.findtext('Unicode', 'False').lower() == 'true'),
                fields=final, defsize=sum(x['total'] for x in final))


def read_table(b):
    """返回 (stringsOffset, [(id,dataOff,nameOff)...], rowSize)"""
    strings_off = struct.unpack_from('<i', b, 0)[0]
    ents = []
    o = 0x40
    while o + 24 <= len(b):
        rid, doff, noff = struct.unpack_from('<qqq', b, o)
        if ents and doff < ents[-1][1]:
            break
        ents.append((rid, doff, noff))
        o += 24
        if len(ents) > 500000:
            break
    # 精确截断：行表从 0x40 起、每项 24 字节，到第一行的数据偏移为止
    if ents and ents[0][1] >= 0x40:
        n = (ents[0][1] - 0x40) // 24
        if 0 < n <= len(ents):
            ents = ents[:n]
    rowsize = (ents[1][1] - ents[0][1]) if len(ents) > 1 else None
    return strings_off, ents, rowsize


def str_at(b, off):
    if off <= 0 or off + 2 > len(b):
        return ''
    e = off
    while e + 1 < len(b) and b[e:e + 2] != b'\x00\x00':
        e += 2
    if e - off > 512:
        return ''
    try:
        return b[off:e].decode('utf-16-le')
    except Exception:
        return ''


def decode_row(b, off, fields):
    out, p = [], off
    for f in fields:
        if f['bitlist'] is not None:
            raw = int.from_bytes(b[p:p + f['size']], 'little')
            out.append((f['name'], raw, [(nm, (raw >> sh) & 1) for nm, sh in f['bitlist']]))
            p += f['size']
            continue
        if f['type'] in ('fixstr', 'fixstrW'):
            raw = b[p:p + f['total']]
            if f['type'] == 'fixstrW':
                txt = raw.decode('utf-16-le', 'backslashreplace').rstrip('\x00')
            else:
                txt = raw.rstrip(b'\x00').decode('utf-8', 'backslashreplace')
            out.append((f['name'], txt, None))
            p += f['total']
            continue
        if f['type'] in ('dummy8',) or f['type'].startswith('x'):
            p += f['total']
            continue
        n = f['arr'] or 1
        vals = []
        for _ in range(n):
            raw = b[p:p + f['size']]
            if f['type'][0] == 'f':
                v = struct.unpack('<f' if f['size'] == 4 else '<d', raw)[0]
            elif f['type'][0] == 'u':
                v = int.from_bytes(raw, 'little')
            else:
                v = int.from_bytes(raw, 'little', signed=True)
            vals.append(v)
            p += f['size']
        out.append((f['name'], vals[0] if n == 1 else vals, None))
    return out


def main():
    args = sys.argv[1:]
    mode = 'some'
    if args and args[0].startswith('--'):
        mode = args[0][2:]
        args = args[1:]
    pf, df = args[0], args[1]
    want = set(int(x, 0) for x in args[2:])
    d = parse_def(df)
    b = open(pf, 'rb').read()
    soff, ents, rowsize = read_table(b)
    print(f'# {os.path.basename(pf)}  def={os.path.basename(df)}  ParamType={d["paramtype"]} '
          f'defRowSize={d["defsize"]} rowSize={rowsize} rows={len(ents)} stringsOffset={soff}')
    print()
    if mode == 'list':
        for rid, doff, noff in ents:
            print(f'{rid:>10}  {str_at(b, noff)!r}')
        return
    for rid, doff, noff in ents:
        if want and rid not in want:
            continue
        print(f'[row {rid}] name={str_at(b, noff)!r}')
        for name, v, bits in decode_row(b, doff, d['fields']):
            if bits is not None:
                print(f'    {name} = {v}  ({" ".join(f"{a}={c}" for a, c in bits)})')
            else:
                print(f'    {name} = {v}')
        print()


if __name__ == '__main__':
    main()
