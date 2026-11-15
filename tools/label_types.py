# -*- coding: utf-8 -*-
"""把 building_types.json / attribute_types.json 画成带编号+中文名的对照图，方便主人核验。

用法:
  python tools/label_types.py                      # 两套都画
  python tools/label_types.py building             # 只画建筑
  python tools/label_types.py attr                 # 只画属性
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

BG = (26, 27, 32)
CELL = (36, 38, 45)
WHITE = (238, 238, 240)
GRAY = (130, 132, 140)
GREEN = (110, 200, 130)
ORANGE = (235, 165, 70)
BLUE = (110, 165, 235)
RED = (225, 110, 105)

CELL_W, CELL_H = 210, 200
COLS = 6
ICON_MAX = 116


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT, size)
    except Exception:
        return ImageFont.load_default()


def find_icon(icon):
    for sub in ("map", "attr", "misc"):
        p = ROOT / "assets" / "icon" / sub / (icon + ".png")
        if p.exists():
            return p
    return None


def tags_for_building(t):
    out = []
    if t.get("category") == "未使用":
        return [("不用", RED)]
    if t.get("attrOnly"):
        out.append(("只属性", BLUE))
    size = t.get("attachSize")
    guessed = t.get("attachSizeGuessed")
    if size == "小":
        out.append(("小据点", GREEN))
    elif size == "大":
        out.append(("大(推定)" if guessed else "大据点", ORANGE if guessed else GREEN))
    elif size == "未知":
        out.append(("?大小", ORANGE))
    if not t.get("placeable") and not t.get("attrOnly"):
        out.append(("不加", GRAY))
    elif t.get("placeable"):
        out.append(("可加", GREEN))
    if not t.get("visible"):
        out.append(("不显示", GRAY))
    return out


def tags_for_attr(t):
    return [("可用", GREEN)] if t.get("used") else [("不用", GRAY)]


def render(items, tagfn, out_png, title):
    rows = (len(items) + COLS - 1) // COLS
    W, H = CELL_W * COLS, CELL_H * rows + 64
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((16, 14), title, font=font(24, True), fill=WHITE)
    for i, t in enumerate(items):
        cx, cy = (i % COLS) * CELL_W, 64 + (i // COLS) * CELL_H
        d.rounded_rectangle([cx + 4, cy + 4, cx + CELL_W - 4, cy + CELL_H - 4], 10, fill=CELL)
        icon = find_icon(t["icon"])
        if icon:
            im = Image.open(icon).convert("RGBA")
            im.thumbnail((ICON_MAX, ICON_MAX), Image.LANCZOS)
            sheet.paste(im, (cx + (CELL_W - im.width) // 2, cy + 12 + (ICON_MAX - im.height) // 2), im)
        d.text((cx + 10, cy + 8), "#%04d" % t["index"], font=font(14), fill=GRAY)
        name = t.get("name") or "（用不到）"
        d.text((cx + CELL_W // 2, cy + 136), name, font=font(19, True), fill=WHITE, anchor="mm")
        d.text((cx + CELL_W // 2, cy + 156), t["icon"].replace("MENU_FL_", "FL ").replace("KG_MENU_MAP_", "MAP ").replace("KG_TEX_", "TEX "),
               font=font(12), fill=GRAY, anchor="mm")
        x = cx + 14
        for label, color in tagfn(t):
            w = d.textlength(label, font=font(13))
            d.rounded_rectangle([x, cy + 168, x + w + 12, cy + 186], 8, fill=color)
            d.text((x + 6, cy + 169), label, font=font(13), fill=(20, 20, 22))
            x += w + 20
    sheet.save(out_png)
    print(out_png, sheet.size)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "building"):
        data = json.loads((ROOT / "src" / "data" / "building_types.json").read_text(encoding="utf-8"))
        render(data["types"], tags_for_building,
               ROOT / "assets" / "icon" / "_预览_建筑分类.png",
               "建筑分类  0-25（主人 m00388 口授，蓝鲸按图集顺序编号）")
    if which in ("all", "attr"):
        data = json.loads((ROOT / "src" / "data" / "attribute_types.json").read_text(encoding="utf-8"))
        render(data["types"], tags_for_attr,
               ROOT / "assets" / "icon" / "attr" / "_预览_属性分类.png",
               "建筑属性  0-11（主人 m00403 口授）")


if __name__ == "__main__":
    main()
