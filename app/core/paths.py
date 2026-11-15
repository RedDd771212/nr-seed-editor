# -*- coding: utf-8 -*-
"""统一路径解析：优先用随包携带的依赖（vendor/），找不到再退回本机开发环境。

发布包需要的三样外部东西都在 vendor 里：
  vendor\\regtool\\regtool.dll        —— regtool（dotnet 运行，解包/封包 regulation.bin）
  vendor\\NRDefs\\*.xml               —— Smithbox 的 NR paramdef（235 个）
  src\\vendor\\paramtool.py / paramdump.py —— 读写 .param 字节的脚本
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 开发机上的原始位置（找不到 vendor 时兜底）
_SKILL = Path.home() / '.dsh' / 'skills' / 'fs-bin-modding'


def _first_path(*cands):
    for c in cands:
        if not c:
            continue
        p = Path(c)
        if p.exists():
            return p
    return None


def _smithbox_defs():
    env = os.environ.get('SMITHBOX_DIR')
    cands = [Path(env) / 'Assets' / 'PARAM' / 'NR' / 'Defs'] if env else []
    for root in (r'E:\ERtools', r'D:\ERtools', r'C:\ERtools'):
        try:
            cands += sorted(Path(root).glob('Smithbox*/Assets/PARAM/NR/Defs'))
        except OSError:
            pass
    return _first_path(*cands)


REGROOL = _first_path(
    ROOT / 'vendor' / 'regtool' / 'regtool.dll',
    _SKILL / 'tools' / 'regtool.dll',
)

DEF_DIR = _first_path(
    ROOT / 'vendor' / 'NRDefs',
    os.environ.get('NR_DEFS'),
    _smithbox_defs(),
)

SCRIPTS = _first_path(
    ROOT / 'src' / 'vendor',
    _SKILL / 'scripts',
)


def require() -> None:
    """缺依赖时给一句人话，而不是后面莫名报错。"""
    missing = []
    if REGROOL is None:
        missing.append('vendor\\regtool\\regtool.dll（regtool）')
    if DEF_DIR is None:
        missing.append('vendor\\NRDefs\\（NR 的 paramdef）')
    if SCRIPTS is None:
        missing.append('src\\vendor\\（paramtool.py / paramdump.py）')
    if missing:
        raise SystemExit('缺少随包依赖，请检查：\n  ' + '\n  '.join(missing))
