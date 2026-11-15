# -*- coding: utf-8 -*-
"""造两个真机验证 bin（只写 work\\verify\\，不碰游戏目录）：

  V1_0组平移.bin
    往 set 0（Gladius · 普通）插一个格罗斯克隆种子 → 0 组 300 个 pid 平移，1000 组不动。
    标记：这个种子的夜晚 BOSS 被强制成 437 / 446（Gladius 普通图平时不会出现）。
    看：玩 Gladius 普通图时，如果刷到夜晚1=那只有点怪的 BOSS，就说明新种子生效、结构没崩。

  V3_新set.bin
    表尾新建 set（Maris · 普通），权重拉高，插一个种子（克隆 pid 120）。
    标记：夜晚 BOSS 强制成 444 / 400（Maris 普通图平时不会出现）。
    看：玩 Maris 普通图时能不能刷到这只"标记种子"。

用法：python tools/make_verify_bins.py
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.paramdir import ParamDir
from app.core.patternset import PatternModel
from app.core.pswriter import Session, save_to_bin
from app.core.project import DEF_DIR

SRC_PARAMS = ROOT / 'work' / 'open' / 'regulation_198c55de' / 'params'
BASE_BIN = Path(r'C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\regulation.bin')
OUT = ROOT / 'work' / 'verify'


class Shim:
    def __init__(self, params_dir: Path, bin_path: Path):
        self.param_dir = Path(params_dir)
        self.bin_path = Path(bin_path)
        self.params = ParamDir(str(self.param_dir), str(DEF_DIR))
        self.pset_model = PatternModel(self.params)


def hr(t):
    print()
    print('=' * 70)
    print(t)
    print('=' * 70)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def build_v1(work_root: Path) -> Path:
    hr('[V1] 往 set 0 插一个种子（0 组 300 个 pid 平移）')
    base_params = work_root / 'v1' / 'params'
    if base_params.parent.exists():
        shutil.rmtree(base_params.parent)
    base_params.parent.mkdir(parents=True)
    shutil.copytree(SRC_PARAMS, base_params)
    shim = Shim(base_params, BASE_BIN)

    sess = Session(shim, work_root=work_root / 'sessions', name='v1')
    m = sess.model()
    old_range_1000 = m.pid_range(1000)
    plan = m.plan_insert_pattern(0, source_pid=0, night=(437, 446))
    for line in plan.summary()[:8]:
        print('  ' + line)
    rep = sess.apply(plan)
    for line in rep.summary()[:10]:
        print('  ' + line)
    if not rep.ok:
        raise SystemExit('V1 应用失败')

    m2 = sess.model()
    st0 = m2.sets[0]
    print(f'  结果：set 0 数量={st0.count}（原 20）  区间={m2.pid_range(0)}')
    print(f'       1000 组区间={m2.pid_range(1000)}（原 {old_range_1000}，应不变）')
    p20 = m2.patterns[20]
    print(f'       新 pid 20：组合={m2.combo_text(p20.combo)} flag={len(p20.flags)} 地点={p20.spot_count} '
          f'夜晚BOSS={p20.boss_modifier}')
    print(f'       整体校验 error={sum(1 for i in m2.validate() if i.level == "error")}')

    out = OUT / 'V1_0组平移.bin'
    report = save_to_bin(shim, sess.params_dir, target_bin=out, base_bin=BASE_BIN)
    for name, ok in report['checks']:
        print(f'  {"✓" if ok else "✗"} {name}')
    if not report['ok']:
        raise SystemExit('V1 封包失败：' + str(report.get('error')))
    return out


def build_v3(work_root: Path) -> Path:
    hr('[V3] 表尾新建 set（Maris · 普通）+ 插一个种子')
    base_params = work_root / 'v3' / 'params'
    if base_params.parent.exists():
        shutil.rmtree(base_params.parent)
    base_params.parent.mkdir(parents=True)
    shutil.copytree(SRC_PARAMS, base_params)
    shim = Shim(base_params, BASE_BIN)

    sess = Session(shim, work_root=work_root / 'sessions', name='v3')
    m = sess.model()
    plan = m.plan_create_set(3, 0, fields={'weight': 7600, 'chaosMatchWeight': 7600},
                             copy_pools=True)
    for line in plan.summary():
        print('  ' + line)
    rep = sess.apply(plan)
    if not rep.ok:
        raise SystemExit('V3 新建 set 失败')
    m = sess.model()
    sid = max(m.sets)
    print(f'  新 set = {sid}，名字={m.sets[sid].name!r} 权重={m.sets[sid].row.get("weight")}'
          f' chaosW={m.sets[sid].row.get("chaosMatchWeight")}')
    print(f'  池子（照抄官方）={m.declared_pool(sid)}')

    plan = m.plan_insert_pattern(sid, source_pid=120, night=(444, 400), recompute_pools=False)
    for line in plan.summary()[:8]:
        print('  ' + line)
    rep = sess.apply(plan)
    for line in rep.summary()[:10]:
        print('  ' + line)
    if not rep.ok:
        raise SystemExit('V3 插入失败')

    m2 = sess.model()
    st = m2.sets[sid]
    print(f'  结果：set {sid} 数量={st.count}  区间={m2.pid_range(sid)}')
    for p in st.patterns:
        print(f'       pid {p.pid}: 组合={m2.combo_text(p.combo)} flag={len(p.flags)} '
              f'地点={p.spot_count} 夜晚BOSS={p.boss_modifier}')
    print(f'       池子：声明={m2.declared_pool(sid)} 实际={m2.pool_of(sid)}')
    print(f'       整体校验 error={sum(1 for i in m2.validate() if i.level == "error")}')

    out = OUT / 'V3_新set.bin'
    report = save_to_bin(shim, sess.params_dir, target_bin=out, base_bin=BASE_BIN)
    for name, ok in report['checks']:
        print(f'  {"✓" if ok else "✗"} {name}')
    if not report['ok']:
        raise SystemExit('V3 封包失败：' + str(report.get('error')))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wr = ROOT / 'work' / 'verify_work'
    p1 = build_v1(wr)
    p3 = build_v3(wr)

    hr('产物')
    for p in (p1, p3):
        print(f'  {p.relative_to(ROOT)}  {p.stat().st_size / 1024 / 1024:.2f} MB  sha256={sha(p)}')
    print()
    print('用法：把想测的那个 bin 改名为 regulation.bin，放进')
    print(r'  C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game\moremap\\')
    print('（原文件先备份；ME3 里勾着 moremap 包启动）')
    print()
    print('V1 期望：Gladius · 普通图能刷出一个「夜晚1 BOSS 不太对」的种子；其他夜王/地形不崩、不黑图、有 BGM。')
    print('V3 期望：Maris · 普通图能刷到一个「夜晚1 是 Gladius 系 BOSS」的种子。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
