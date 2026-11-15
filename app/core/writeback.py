# -*- coding: utf-8 -*-
"""写回：副本上改 → 封包 → 再解包对账 → 备份后覆盖目标 bin。"""
from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from . import writer
from .project import T_SET, T_FLAG, T_AREA, T_SPOT, REGROOL, _run


def _max_id(param_dir: Path, table: str) -> int:
    _, rows, _ = writer.read_table(param_dir, table)
    return max((r['id'] for r in rows), default=0)


def _md5_dir(p: Path) -> str:
    h = hashlib.md5()
    for f in sorted(p.glob('*.param')):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def write_back(project, d, target_bin: Path | None = None, verify_only=False) -> dict:
    base_bin = Path(project.bin_path)
    target = Path(target_bin or base_bin)
    ts = time.strftime('%Y%m%d_%H%M%S')
    wdir = project.work.parent.parent / 'write' / f'{base_bin.stem}_{ts}'

    # 1) 副本
    params = wdir / 'params'
    shutil.copytree(project.param_dir, params)
    before = _md5_dir(params)

    # 2) 追加行
    pay = _payload(project, d)
    nid = _max_id(params, T_SET) + 1
    writer.append_rows(params, T_SET, [(nid, f'[Custom] {d.new_set}', pay['set'])])

    fid = _max_id(params, T_FLAG) + 1
    writer.append_rows(params, T_FLAG,
                       [(fid + i, f'custom_p{d.new_pid}_{i:02d}', r)
                        for i, r in enumerate(pay['flags'])])

    if pay['area']:
        aid = _max_id(params, T_AREA) + 1
        writer.append_rows(params, T_AREA, [(aid, f'custom_p{d.new_pid}', pay['area'])])

    sid = _max_id(params, T_SPOT)
    writer.append_rows(params, T_SPOT,
                       [(sid + i + 1, f'spot_{d.new_pid}_{i:02d}', r)
                        for i, r in enumerate(pay['spots'])])

    # 3) 封包
    out_bin = wdir / f'{base_bin.stem}.new.bin'
    _run(['dotnet', 'exec', str(REGROOL), 'pack', str(base_bin), str(params), str(out_bin)])

    # 4) 再解包对账
    vdir = wdir / 'verify'
    _run(['dotnet', 'exec', str(REGROOL), 'unpack', str(out_bin), str(vdir)])
    after = _md5_dir(vdir)
    if after != before and not verify_only:
        pass  # 有改动是正常的，逐表比对在下面

    report = {'wdir': str(wdir), 'out': str(out_bin), 'target': str(target),
              'before': before, 'after': after, 'checks': []}

    from nrseed.paramdir import ParamDir
    pv = ParamDir(str(vdir), str(project.params.def_dir))
    checks = report['checks']
    checks.append(('MapPatternSet 新行', nid in pv.rows(T_SET)))
    checks.append(('patternId 已入 flag 表',
                   any(r.get('patternId') == d.new_pid for r in pv.rows(T_FLAG).values())))
    checks.append(('patternId 已入 playArea',
                   any(r.get('patternId') == d.new_pid for r in pv.rows(T_AREA).values())))
    n_spot = sum(1 for r in pv.rows(T_SPOT).values() if r.get('patternId') == d.new_pid)
    checks.append((f'地点行数 = {len(pay["spots"])}', n_spot == len(pay['spots'])))

    touched = {T_SET, T_FLAG, T_AREA, T_SPOT}
    diff = []
    for f in sorted(project.param_dir.glob('*.param')):
        if f.stem in touched:
            continue
        g = vdir / f.name
        if not g.exists() or g.read_bytes() != f.read_bytes():
            diff.append(f.stem)
    checks.append(('其它表逐字节未变', not diff))
    report['diff_tables'] = diff

    if not all(ok for _, ok in checks):
        report['ok'] = False
        report['error'] = '对账失败：' + '；'.join(f'{n}={"OK" if ok else "FAIL"}' for n, ok in checks)
        return report

    # 5) 备份 + 覆盖
    if not verify_only:
        if target.exists():
            shutil.copy2(target, target.with_suffix(target.suffix + f'.prev_{ts}'))
        shutil.copy2(out_bin, target)

    report['ok'] = True
    report['test'] = _record_test(project, d, target, ts)
    return report


def _record_test(project, d, target: Path, ts: str) -> dict:
    """把这次写回的 flag 行记进 work/flag_tests.json（给 eventFlag 研究当对照表）。"""
    import json

    root = Path(project.work).resolve().parents[2]   # work\open\<x> → 项目根
    out = root / 'work' / 'flag_tests.json'
    data = []
    if out.exists():
        try:
            data = json.loads(out.read_text(encoding='utf-8'))
        except Exception:
            data = []
    rec = {
        'ts': ts,
        'target': str(target),
        'patternId': d.new_pid,
        'patternSetId': d.new_set,
        'bossId': d.boss_id,
        'templatePid': d.template_pid,
        'spots': len(d.spots),
        'rows': [
            {'modifierSet': e.get('modifierSet'), 'eventFlag': e.get('eventFlag'),
             'modifier': e.get('modifier'), 'name': e.get('name') or ''}
            for e in (d.events or [])
        ],
        'notes': [],
    }
    data.append(rec)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return rec


def _payload(project, d):
    from .draft import payload
    return payload(project, d)

