import sys
sys.path.insert(0, r'src')
import numpy as np
from PIL import Image

REF = r'C:\Users\19803\.dsh\attachments\v1\objects\da\daadf4878ce5b89ab93a8eb5b7dcdf3270a7499792c82637773ea59af8f9c4d6'
ref = Image.open(REF).convert('RGB')
scale = 0.5
ref_s = ref.resize((int(ref.width * scale), int(ref.height * scale)), Image.LANCZOS)
G = np.array(ref_s.convert('L')).astype(np.float32)

for icon in (42009, 42001, 42005, 42010, 42006, 42002):
    ic = Image.open(rf'assets\icon\pin\{icon}.png').convert('RGBA')
    w = max(12, int(30 * scale))
    h = max(12, int(ic.height * w / ic.width))
    bg = Image.new('RGBA', ic.size, (0, 0, 0, 0))
    bg.alpha_composite(ic)
    T = np.array(bg.convert('L').resize((w, h), Image.LANCZOS)).astype(np.float32)
    mask = np.array(bg.split()[3].resize((w, h), Image.LANCZOS)).astype(np.float32) / 255.0
    win = np.lib.stride_tricks.sliding_window_view(G, (h, w))
    wmean = win.mean(axis=(2, 3), keepdims=True)
    wstd = win.std(axis=(2, 3), keepdims=True) + 1e-3
    Tm = (T * mask).sum() / mask.sum()
    Tn = (T - Tm) * mask
    tn = np.sqrt((Tn * Tn).sum()) + 1e-6
    num = (win * Tn).sum(axis=(2, 3)) - wmean[:, :, 0, 0] * Tn.sum()
    corr = num / (wstd[:, :, 0, 0] * tn)
    flat = corr.ravel()
    order = np.argsort(flat)[-3:][::-1]
    print(icon, [(int(i % corr.shape[1]) * 2, int(i // corr.shape[1]) * 2, round(float(flat[i]), 3)) for i in order])
