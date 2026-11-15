# -*- coding: utf-8 -*-
"""用像素比对把 KG_MENU_MAP_xxx 对上 MENU_MenuIcon_42xxx（避免编号推导出错）。"""
import os, re
import numpy as np
from PIL import Image

KG = r'D:\项目\app\NR地图种子编辑器\assets\icon\map'
PIN = r'D:\项目\app\NR地图种子编辑器\work\menuicon_42'


def sig(path, n=48):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (0, 0, 0, 0))
    bg.alpha_composite(im)
    a = np.asarray(bg.resize((n, n), Image.LANCZOS)).astype(np.float32) / 255.0
    # 白底合成，去掉透明度差异
    rgb = a[..., :3] * a[..., 3:4] + (1 - a[..., 3:4])
    return rgb


pins = sorted(os.listdir(PIN))
pin_sig = {p: sig(os.path.join(PIN, p)) for p in pins}

print(f"{'KG':<22} {'best':<26} mse    2nd")
for f in sorted(os.listdir(KG)):
    s = sig(os.path.join(KG, f))
    scored = sorted(((float(((s - v) ** 2).mean()), k) for k, v in pin_sig.items()))
    print(f"{f:<22} {scored[0][1]:<26} {scored[0][0]:.5f}  {scored[1][1]}({scored[1][0]:.4f})")
