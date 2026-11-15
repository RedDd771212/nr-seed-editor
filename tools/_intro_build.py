# -*- coding: utf-8 -*-
"""把 work/intro/shots 里采集的界面截图，合成一支无声介绍视频（1920x1080 / 30fps）。

- 每个镜头：Ken Burns 推镜 + 底部字幕讲解 + 跟着鼠标轨迹画的指针/点击涟漪
- 片头/片尾/问题卡：用地图底图做背景的排版卡
- 输出无音轨，方便后面自己加 BGM

用法： python tools/_intro_build.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'work' / 'intro' / 'shots'
OUT = ROOT / 'NR地图种子编辑器_v3.0_介绍.mp4'

W, H, FPS = 1920, 1080, 30
XFADE = 0.45

ACCENT = (77, 163, 255)
ACCENT2 = (255, 196, 84)
WHITE = (240, 244, 250)
MUTED = (176, 186, 200)

FONT_B = r'C:\Windows\Fonts\msyhbd.ttc'
FONT_R = r'C:\Windows\Fonts\msyh.ttc'


def font(path, size):
    return ImageFont.truetype(path, size)


F_TITLE = font(FONT_B, 44)
F_BODY = font(FONT_R, 27)
F_CARD_T = font(FONT_B, 68)
F_CARD_S = font(FONT_R, 30)
F_TAG = font(FONT_B, 18)
F_LABEL = font(FONT_B, 22)
F_BRAND = font(FONT_R, 17)


def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def wrap(draw, text, fnt, max_w):
    """按像素宽度折行，保留显式 \n。"""
    out = []
    for para in text.split('\n'):
        if not para:
            out.append('')
            continue
        line = ''
        for ch in para:
            if draw.textlength(line + ch, font=fnt) <= max_w:
                line += ch
            else:
                out.append(line)
                line = ch
        out.append(line)
    return out


def rounded(draw, box, r, **kw):
    draw.rounded_rectangle(box, radius=r, **kw)


# ------------------------------------------------------------------ 卡片

_card_cache = {}


def make_card(kind: str, title: str, body_lines: list[str], tag: str = '') -> Image.Image:
    key = (kind, title, tuple(body_lines), tag)
    if key in _card_cache:
        return _card_cache[key]
    bg = Image.open(ROOT / 'assets' / 'map' / 'limveld.png').convert('RGB')
    bg = bg.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(9))
    ov = Image.new('RGBA', (W, H), (8, 10, 14, 176))
    img = Image.alpha_composite(bg.convert('RGBA'), ov)
    d = ImageDraw.Draw(img)

    # 渐变压暗：左侧重（放字）、上下加一点
    grad = Image.new('L', (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(150 * (0.35 + 0.65 * (y / H))))
    shade = Image.new('RGBA', (W, H), (6, 8, 12, 255))
    shade.putalpha(grad.resize((W, H)))
    img = Image.alpha_composite(img, shade)
    d = ImageDraw.Draw(img)

    x = 150
    if kind == 'title':
        y = 380
        d.text((x, y - 96), 'NR SEED EDITOR  ·  v3.0', font=font(FONT_B, 24), fill=ACCENT)
        d.text((x, y), title, font=font(FONT_B, 92), fill=WHITE)
        d.rectangle([x, y + 128, x + 120, y + 134], fill=ACCENT)
        yy = y + 170
        for ln in body_lines:
            d.text((x, yy), ln, font=font(FONT_R, 34), fill=MUTED)
            yy += 52
    elif kind == 'end':
        y = 330
        d.text((x, y - 96), 'NIGHTREIGN  ·  MAP SEED EDITOR', font=font(FONT_B, 24), fill=ACCENT)
        d.text((x, y), title, font=font(FONT_B, 66), fill=WHITE)
        d.rectangle([x, y + 96, x + 120, y + 102], fill=ACCENT)
        yy = y + 140
        for ln in body_lines:
            d.text((x, yy), ln, font=font(FONT_R, 30), fill=MUTED)
            yy += 48
    else:
        y = 330
        d.text((x, y - 110), 'WHY', font=font(FONT_B, 24), fill=ACCENT2)
        d.text((x, y), title, font=font(FONT_B, 76), fill=WHITE)
        d.rectangle([x, y + 106, x + 120, y + 112], fill=ACCENT2)
        yy = y + 148
        for ln in body_lines:
            d.text((x, yy), ln, font=font(FONT_R, 32), fill=MUTED)
            yy += 50
    if tag:
        d.text((W - 150 - d.textlength(tag, font=F_TAG), H - 74), tag, font=F_TAG, fill=(120, 130, 145))
    _card_cache[key] = img
    return img


# ------------------------------------------------------------------ 光标

CURSOR_PTS = [(0, 0), (0, 17.5), (4.3, 13.6), (7.6, 20.6), (10.4, 19.3), (7.2, 12.7), (12.2, 12.2)]


def draw_cursor(layer: Image.Image, x: float, y: float, scale: float = 1.65, press: float = 0.0):
    d = ImageDraw.Draw(layer)
    pts = [(x + px * scale, y + py * scale) for px, py in CURSOR_PTS]
    # 阴影
    d.polygon([(px + 2.2, py + 2.6) for px, py in pts], fill=(0, 0, 0, 110))
    d.polygon(pts, fill=(255, 255, 255, 240), outline=(20, 22, 26, 235), width=2)
    if press > 0:
        r = 10 + 26 * (1 - press)
        a = int(150 * press)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 235, 160, a), width=3)


# ------------------------------------------------------------------ 场景

def load(name):
    p = SHOTS / (name + '.png')
    img = Image.open(p).convert('RGB')
    meta_p = SHOTS / (name + '.json')
    meta = json.loads(meta_p.read_text(encoding='utf-8')) if meta_p.exists() else {}
    return img, meta


SCENES = []


def card(kind, title, body, dur, tag=''):
    SCENES.append({'type': 'card', 'card': (kind, title, body), 'dur': dur, 'tag': tag})


def shot(name, dur, title, body, zoom=(1.0, 1.06), focus=None, cap='bottom',
         labels=None, cursor=True, ring=None, tag=''):
    SCENES.append({
        'type': 'shot', 'shot': name, 'dur': dur, 'title': title, 'body': body,
        'zoom': zoom, 'focus': focus, 'cap': cap, 'labels': labels or [],
        'cursor': cursor, 'ring': ring, 'tag': tag,
    })


card('title', '黑夜君临 · 地图种子编辑器', [
    '直接读写 regulation.bin 里的地图种子 param',
    '新建 / 修改 MapPatternSet，在 set 里增删种子，改地点、缩圈、夜晚 BOSS',
    '只动 param，不碰 msb / emevd / onav',
], 7.0, 'v3.0 · 2026-11')

card('problem', '官方的种子，是固定的', [
    '19 个夜王 × 6 类地形，种子由官方抽签决定，你只能刷到它。',
    '这个工具换一条路：不用建模、不用改地图，',
    '直接改四张抽签表，把「官方地点」重新拼成你自己的种子。',
], 9.0, 'MapPatternSet / LotResult*')

shot('01_empty', 9.0,
     '1 / 启动', '双击 启动.bat，浏览器自动打开 127.0.0.1:8779\n第一次用先跑 检查环境.bat：Python + Pillow + .NET 都要有',
     zoom=(1.07, 1.0), cursor=True, tag='启动')

shot('02_typing', 9.0,
     '2 / 打开 bin', '填 regulation.bin 的路径，或者直接填它所在的文件夹\n点【打开】——所有改动都发生在副本上，不点保存不会动你的 bin',
     zoom=(1.38, 1.42), focus=(400, 20), cursor=True, tag='打开', ring='#binPath',
     labels=[('#btnOpen', '打开')])

shot('03_opened', 13.5,
     '3 / 三栏界面', '左：夜王筛选 + set 树　中：地形图　右：set 参数 / 种子内容 / 事件行',
     zoom=(1.0, 1.0), cursor=False, cap='bottom',
     labels=[('#left', 'SET 面板'), ('#center', '地形图'), ('#inspector', '详情')], tag='界面')

shot('04_seed', 11.0,
     '4 / 选一个种子', '点 set 展开 → 再点 pid：地图跟着这个种子重画\n地点、缩圈、夜晚 BOSS 一起换，右上角永远写着当前在看哪一个',
     zoom=(1.12, 1.16), focus=(300, 560), cursor=True, tag='选种子')

shot('05_filter', 9.0,
     '按夜王筛选', '下拉选夜王，只留他名下的 set\n19 个夜王 + 6 类地形，先缩小范围再挑种子',
     zoom=(1.30, 1.34), focus=(180, 220), cursor=True, tag='筛选', ring='#bossFilter')

shot('06_hover', 10.0,
     '5 / 地图上的两类圈', '小圈 = 校准过的建筑位（蓝 = 大据点 / 绿 = 小据点 / 灰 = 未知）\n大圈 = 这个种子里的地点，颜色跟着它所在的建筑位走',
     zoom=(1.16, 1.20), focus=(1075, 620), cursor=True, tag='圈')

shot('07_spotselected', 9.5,
     '点大圈 = 选中地点', '右栏那一行会高亮：tile 多少、attach 多少、第几次出现（idx）',
     zoom=(1.02, 1.06), cursor=True, tag='选中')

shot('08_tilepicker', 10.0,
     '双击大圈 = 换建筑', '底部列出「官方种子在这个位置真的用过」的建筑，照抄不猜\n也能直接手输 tile 编号',
     zoom=(1.0, 1.03), cursor=True, cap='top', tag='换建筑')

shot('09_tilechanged', 9.0,
     '换了就是换了', 'tile 3030 → 3200，idx 自动重排到该 tile 的下一个空位\n写回时 mapIndex 按新 tile 累加，游戏里的 BGM 不会丢',
     zoom=(1.22, 1.26), focus=(1490, 700), cursor=True, cap='top', tag='结果')

shot('10_variant', 10.5,
     '6 / 属性变体', 'variationId 决定这处据点带什么属性（毒 / 冻伤 / 魔力…）\n在那一格直接改数字，回车生效，右边小图标跟着变',
     zoom=(1.24, 1.28), focus=(1500, 600), cursor=True, tag='变体')

shot('11_area_preview', 9.5,
     '7 / 缩圈', '1缩 / 2缩 下拉：鼠标悬停先在地图上虚线预演位置\n点一下才真生效，选之前就知道圈会落在哪',
     zoom=(1.06, 1.10), focus=(1200, 300), cursor=True, tag='缩圈')

shot('12_area_set', 8.5,
     '缩圈落定', '1 号标记直接搬到新位置；夜王的四个数也一样，填完点【保存夜王】',
     zoom=(1.10, 1.14), focus=(700, 620), cursor=True, cap='top', tag='缩圈')

shot('13_mountain', 9.5,
     '8 / 五张地形底图', '山顶：底图和点位池子一起换，世界坐标共用，不需要第二套换算',
     zoom=(1.0, 1.07), cursor=True, tag='地形')

shot('14_crater', 7.5,
     '火山口', '一缩 / 二缩的候选点按地形自动过滤（火山口 13 个候选）',
     zoom=(1.04, 1.10), cursor=False, tag='地形')

shot('15_shroud', 7.5,
     '隐城', '五张：宁姆韦德 / 山顶 / 火山口 / 腐败森林 / 隐城。切地形 = 切档案',
     zoom=(1.04, 1.10), cursor=False, tag='地形')

shot('18_gh_hover', 8.5,
     '9 / 给种子补一个地点', '不是每个点位都被占满：大空洞这类种子还空着 30 多个建筑位\n点空位就能往里加一个据点',
     zoom=(1.10, 1.14), focus=(1030, 470), cursor=True, tag='加点')

shot('19_gh_picker', 8.5,
     '选建筑', '点空位 → 底部列出可选建筑 → 点图标就加进去',
     zoom=(1.02, 1.05), cursor=True, cap='top', tag='加点')

shot('20_gh_added', 8.0,
     '地点数 41 → 42', '新行写进同一张 LotResultSmallBaseAndSpot，跟官方行一个格式\n加完立刻在地图上看到它',
     zoom=(1.08, 1.12), focus=(1030, 600), cursor=True, cap='top', tag='加点')

shot('21_undo', 9.0,
     '10 / 撤销一步', 'Ctrl+Z，或点左下角那个「撤销一步」\n加点、删点、排序、换缩圈、换事件都算一步，最多回退 60 步',
     zoom=(1.0, 1.04), cursor=True, cap='top', tag='撤销', ring='#btnUndo')

shot('22_newset', 9.0,
     '11 / 新建 set', '按「夜王 + 地图类型」建一个空 set，池子可以照抄官方\n再【插入一个种子】克隆源 pid，后面的 pid 自动顺移',
     zoom=(1.0, 1.03), cursor=True, cap='top', tag='新建')

shot('23_saved', 11.0,
     '12 / 保存', '封包 → 再解包 → 逐表字节对账 → 备份 regulation.bin.prev_时间戳 → 才覆盖\n对账不过就停下，不覆盖你的 bin',
     zoom=(1.14, 1.18), focus=(1350, 640), cursor=True, cap='top', tag='保存')

card('end', '黑夜君临 · 地图种子编辑器 v3.0', [
    '只动 param：MapPatternSet / LotResultMapPatternFlag / PlayArea / SmallBaseAndSpot',
    '打开后所有改动都在副本上；写回永远是 对账 → 备份 → 覆盖',
    '注意：改的是游戏目录里的 bin，先自己备份；联机 / 官方环境不要用改过的 bin',
], 10.0, '2026-11-15')


# ------------------------------------------------------------------ 渲染

class ShotRenderer:
    def __init__(self, sc):
        self.sc = sc
        self.img, self.meta = load(sc['shot'])
        self.trail = self.meta.get('cursor') or []
        self.clicks = self.meta.get('clicks') or []
        self.boxes = self.meta.get('boxes') or {}
        if self.trail:
            self.t_end = max(t for t, _, _ in self.trail)
        else:
            self.t_end = 0

    # 镜头几何
    def geom(self, local):
        z0, z1 = self.sc['zoom']
        k = ease(local / max(0.001, self.sc['dur']))
        z = z0 + (z1 - z0) * k
        fx, fy = self.sc['focus'] or (W / 2, H / 2)
        rw, rh = W / z, H / z
        x0 = min(max(fx - rw / 2, 0), W - rw)
        y0 = min(max(fy - rh / 2, 0), H - rh)
        return z, x0, y0, rw, rh

    def to_out(self, g, x, y):
        _, x0, y0, rw, rh = g
        return (x - x0) * (W / rw), (y - y0) * (H / rh)

    def cursor_state(self, local):
        if not self.sc['cursor'] or not self.trail:
            return None
        # 前 1.8 秒把轨迹播完，之后停在最后一点
        span = max(1.0, self.t_end / 1000.0)
        show = 1.8
        t_ms = min(local / show, 1.0) * span * 1000
        pts = self.trail
        x, y = pts[-1][1], pts[-1][2]
        for i in range(1, len(pts)):
            t0, x0, y0 = pts[i - 1]
            t1, x1, y1 = pts[i]
            if t_ms <= t1:
                k = 0 if t1 == t0 else (t_ms - t0) / (t1 - t0)
                x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
                break
        press = 0.0
        for ct, cx, cy in self.clicks:
            dt = local - (ct / 1000.0) * (1.8 / span)
            if 0 <= dt < 0.55:
                press = 1.0 - dt / 0.55
                x, y = cx, cy
        return x, y, press

    def render(self, local, alpha_cap=1.0):
        sc = self.sc
        g = self.geom(local)
        z, x0, y0, rw, rh = g
        if abs(z - 1.0) < 1e-4 and x0 == 0 and y0 == 0:
            base = self.img.copy()
        else:
            base = self.img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + rw, y0 + rh))
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        # 标注环 + 标签
        for item in sc['labels']:
            box = self.boxes.get(item[0])
            if not box:
                continue
            p0 = self.to_out(g, box['x'], box['y'])
            p1 = self.to_out(g, box['x'] + box['w'], box['y'] + box['h'])
            pad = 6
            rounded(d, [p0[0] - pad, p0[1] - pad, p1[0] + pad, p1[1] + pad], 10,
                    outline=(77, 163, 255, 210), width=3)
            tw = d.textlength(item[1], font=F_LABEL)
            tx, ty = p0[0] - pad, max(6, p0[1] - pad - 34)
            rounded(d, [tx, ty, tx + tw + 20, ty + 30], 8, fill=(77, 163, 255, 225))
            d.text((tx + 10, ty + 4), item[1], font=F_LABEL, fill=(8, 12, 18, 255))

        if sc['ring']:
            box = self.boxes.get(sc['ring'])
            if box:
                p0 = self.to_out(g, box['x'], box['y'])
                p1 = self.to_out(g, box['x'] + box['w'], box['y'] + box['h'])
                pulse = 0.5 + 0.5 * math.sin(local * 3.2)
                a = int(120 + 100 * pulse)
                rounded(d, [p0[0] - 5, p0[1] - 5, p1[0] + 5, p1[1] + 5], 8,
                        outline=(255, 196, 84, a), width=3)

        # 光标
        cur = self.cursor_state(local)
        if cur:
            ox, oy = self.to_out(g, cur[0], cur[1])
            draw_cursor(layer, ox, oy, press=cur[2])

        out = Image.alpha_composite(base.convert('RGBA'), layer)
        return add_caption(out, sc, local, alpha_cap)


def add_caption(img: Image.Image, sc: dict, local: float, alpha_cap: float = 1.0):
    dur = sc['dur']
    a = 1.0
    if local < 0.4:
        a = local / 0.4
    if local > dur - 0.4:
        a = max(0.0, (dur - local) / 0.4)
    a *= alpha_cap
    if a <= 0.01:
        return img
    title = sc.get('title') or ''
    body = sc.get('body') or ''
    if not title:
        return img

    probe = ImageDraw.Draw(Image.new('RGBA', (10, 10)))
    cap_top = sc.get('cap', 'bottom') == 'top'
    max_w = 1040 if cap_top else 1560
    body_lines = wrap(probe, body, F_BODY, max_w) if body else []
    line_h = 40
    tw = probe.textlength(title, font=F_TITLE)
    bw = max([probe.textlength(l, font=F_BODY) for l in body_lines] or [0])
    box_w = int(max(tw, bw) + 48 + 26)
    box_h = int(34 + 52 + (len(body_lines) * line_h if body_lines else 0) + 6)

    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = 60
    y = (H - box_h - 46) if not cap_top else 62
    rounded(d, [x, y, x + box_w, y + box_h], 14, fill=(10, 13, 18, 224))
    d.rectangle([x, y + 12, x + 5, y + box_h - 12], fill=ACCENT)
    tx = x + 26
    ty = y + 20
    d.text((tx + 1, ty + 1), title, font=F_TITLE, fill=(0, 0, 0, 160))
    d.text((tx, ty), title, font=F_TITLE, fill=WHITE)
    ty += 52
    for ln in body_lines:
        d.text((tx, ty), ln, font=F_BODY, fill=MUTED)
        ty += line_h
    if a < 1.0:
        alpha = layer.getchannel('A').point(lambda v: int(v * a))
        layer.putalpha(alpha)
    return Image.alpha_composite(img.convert('RGBA'), layer)


def render_card(sc, local, alpha_cap=1.0):
    kind, title, body = sc['card']
    img = make_card(kind, title, body, sc.get('tag', ''))
    img = img.convert('RGBA')
    # 轻微推镜
    z = 1.0 + 0.03 * ease(local / max(0.001, sc['dur']))
    rw, rh = W / z, H / z
    x0, y0 = (W - rw) / 2, (H - rh) / 2
    base = img.convert('RGB').resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + rw, y0 + rh)).convert('RGBA')
    a = 1.0
    if local < 0.5:
        a = local / 0.5
    if local > sc['dur'] - 0.5:
        a = max(0.0, (sc['dur'] - local) / 0.5)
    a *= alpha_cap
    if a < 1.0:
        alpha = base.getchannel('A').point(lambda v: int(v * a))
        base.putalpha(alpha)
    return base


def draw_progress_bar(img, i, n):
    d = ImageDraw.Draw(img)
    w = 120 * (i + 1) / n
    d.rectangle([0, H - 4, W, H], fill=(255, 255, 255, 12))
    d.rectangle([0, H - 4, w, H], fill=ACCENT + (220,))


def main():
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    # 时间轴
    t = 0.0
    for i, sc in enumerate(SCENES):
        sc['start'] = t
        t += sc['dur'] - (XFADE if i < len(SCENES) - 1 else 0)
    total = t
    print(f'scenes={len(SCENES)} total={total:.1f}s -> {OUT.name}')

    renderers = {}
    for i, sc in enumerate(SCENES):
        if sc['type'] == 'shot':
            renderers[i] = ShotRenderer(sc)

    cmd = [ffmpeg, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'veryfast',
           '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT)]
    proc = __import__('subprocess').Popen(cmd, stdin=__import__('subprocess').PIPE,
                                         stdout=__import__('subprocess').DEVNULL,
                                         stderr=__import__('subprocess').DEVNULL)

    n_frames = int(round(total * FPS))
    def find_scene(tt):
        cur = 0
        for i, sc in enumerate(SCENES):
            if sc['start'] <= tt < sc['start'] + sc['dur']:
                cur = i
        return cur

    for f in range(n_frames):
        tt = f / FPS
        i = find_scene(tt)
        sc = SCENES[i]
        local = tt - sc['start']
        frame = (render_card(sc, local) if sc['type'] == 'card'
                 else renderers[i].render(local))
        # 交叉淡入
        if i > 0 and local < XFADE:
            prev = SCENES[i - 1]
            plocal = tt - prev['start']
            if plocal <= prev['dur']:
                pframe = (render_card(prev, plocal) if prev['type'] == 'card'
                          else renderers[i - 1].render(plocal, alpha_cap=1 - local / XFADE))
                frame = Image.alpha_composite(pframe, frame)
        out = frame.convert('RGB')
        draw_progress_bar(out, i, len(SCENES))
        proc.stdin.write(out.tobytes())
        if f % 150 == 0:
            print(f'  frame {f}/{n_frames}  scene {i + 1}  t={tt:.1f}s', flush=True)
    proc.stdin.close()
    proc.wait()
    print('done:', OUT, OUT.stat().st_size // 1024 // 1024, 'MB')


if __name__ == '__main__':
    main()
