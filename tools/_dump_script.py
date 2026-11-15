# -*- coding: utf-8 -*-
"""导出分镜脚本（时间轴 + 字幕原文），方便以后配音 / 改字幕。"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('ib', Path(__file__).with_name('_intro_build.py'))
ib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ib)

lines = ['# NR 地图种子编辑器 v3.0 · 介绍视频分镜脚本', '',
         '> 由 `tools/_intro_build.py` 里的场景表自动生成；改文案改那个文件再跑 `_dump_script.py`。',
         '> 画面素材：`work/intro/shots/`（24 张真实界面截图 + 鼠标轨迹 JSON）。', '',
         '| 起 | 时长 | 镜头 / 素材 | 字幕标题 | 字幕正文 |', '|---|---|---|---|---|']
t = 0.0
n = len(ib.SCENES)
for i, sc in enumerate(ib.SCENES):
    dur = sc['dur']
    if sc['type'] == 'card':
        kind = '排版卡'
        shot = kind + '：' + sc['card'][1]
        title = sc['card'][1]
        body = ' / '.join(sc['card'][2])
    else:
        shot = f"`{sc['shot']}.png`"
        title = sc.get('title', '')
        body = (sc.get('body') or '').replace('\n', '<br>')
    mm, ss = divmod(int(t + 0.5), 60)
    lines.append(f"| {mm:02d}:{ss:02d} | {dur:.1f}s | {shot} | {title} | {body} |")
    t += dur - (ib.XFADE if i < n - 1 else 0)

lines += ['', f'总时长约 {int(t + 0.5)} 秒（{int(t // 60)}:{int(t % 60):02d}），1920×1080 / 30fps，无音轨。', '',
          '## 配乐建议', '',
          '- 前 15 秒（片头 + 问题卡）压低、铺氛围；',
          '- 中段（打开 bin → 改地点）可稍快，鼓点对上切镜；',
          '- 保存 / 收尾（02:50 之后）放慢，收在最后一个镜头上。']
out = Path('视频分镜脚本.md')
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('wrote', out, out.stat().st_size, 'bytes')
