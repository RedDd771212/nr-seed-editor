# -*- coding: utf-8 -*-
"""打发布 zip：标准 ZIP（路径用 /），排除运行时目录。"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist' / 'NR地图种子编辑器_v3.1_20261116.zip'
EXCLUDE_DIRS = {'work', 'dist', '__pycache__', '.git'}
EXCLUDE_SUFFIX = {'.pyc', '.mp4'}   # 视频走 Releases，不进发布包

OUT.parent.mkdir(parents=True, exist_ok=True)
if OUT.exists():
    OUT.unlink()

files = []
for p in sorted(ROOT.rglob('*')):
    if not p.is_file():
        continue
    rel = p.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts[:-1]):
        continue
    if rel.name in EXCLUDE_DIRS:
        continue
    if p.suffix in EXCLUDE_SUFFIX:
        continue
    files.append(rel)

with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel in files:
        z.write(ROOT / rel, arcname='NR地图种子编辑器/' + rel.as_posix())

print(f'{OUT.name}: {len(files)} files, {OUT.stat().st_size / 1024 / 1024:.1f} MB')
with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
    print('前 5 个条目:', names[:5])
    bat = next(n for n in names if n.endswith('启动.bat'))
    data = z.read(bat)
    print(bat, len(data), 'bytes, CRLF=', b'\r\n' in data)
    for need in ('app/server_v3.py', 'vendor/regtool/regtool.dll',
                 'vendor/NRDefs/MapPatternSet.xml', 'src/vendor/paramtool.py',
                 'assets/map/limveld.png', 'README.md'):
        full = 'NR地图种子编辑器/' + need
        print(('OK   ' if full in names else '缺   ') + need)
