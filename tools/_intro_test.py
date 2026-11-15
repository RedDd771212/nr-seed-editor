# -*- coding: utf-8 -*-
"""出几帧样张，检查排版/推镜/字幕位置（不编码视频）。"""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('ib', Path(__file__).with_name('_intro_build.py'))
ib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ib)

OUT = Path('work/intro/preview')
OUT.mkdir(parents=True, exist_ok=True)

picks = [0, 1, 3, 5, 8, 9, 10, 12, 21, 23]
for idx in picks:
    sc = ib.SCENES[idx]
    if sc['type'] == 'card':
        img = ib.render_card(sc, min(sc['dur'] * 0.5, 2.0))
    else:
        r = ib.ShotRenderer(sc)
        img = r.render(min(sc['dur'] * 0.55, 3.0))
    name = sc.get('shot') or sc['card'][0]
    img.convert('RGB').save(OUT / f'{idx:02d}_{name}.png')
    print('saved', name)
