# -*- coding: utf-8 -*-
"""打开任意 regulation.bin：解包 → 建索引 → 供界面查询。

只读，不改原文件；解包目录放在项目 work\\open\\<名字>。
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from nrseed.model import SeedModel  # noqa: E402
from nrseed.paramdir import ParamDir  # noqa: E402
from app.core.paths import REGROOL, DEF_DIR, require  # noqa: E402

require()

T_BOSS = 'NightBossMenuParam'
EVERGAOL_TILES = {4650, 4660, 4670, 4680}   # Evergaol A/B/C/D
T_SET = 'MapPatternSet'
T_FLAG = 'LotResultMapPatternFlag'
T_AREA = 'LotResultPlayAreaParam'
T_SPOT = 'LotResultSmallBaseAndSpot'
T_ATTACH = 'SmallBaseAndSpotAttachPoint'
T_DEFINE = 'SmallBaseAndSpotDefine'
T_VAR = 'SmallBaseMapVariationParam'

# 有些 regulation.bin（如 moremap 那份）不带行名，用内置表兜底
_NAME_JSON = ROOT / 'src' / 'data' / 'boss_names.json'
try:
    import json
    _FALLBACK_NAMES = json.loads(_NAME_JSON.read_text(encoding='utf-8'))
except Exception:  # noqa: BLE001
    _FALLBACK_NAMES = {}

_ALLOW_JSON = ROOT / 'src' / 'data' / 'attach_allowlist.json'
try:
    _ALLOW_RAW = json.loads(_ALLOW_JSON.read_text(encoding='utf-8'))
    ALLOW_PAIRS = {(int(a), int(t)) for a, t in _ALLOW_RAW.get('pairs', [])}
except Exception:  # noqa: BLE001
    _ALLOW_RAW, ALLOW_PAIRS = {}, set()


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError((p.stdout or '') + (p.stderr or ''))
    return (p.stdout or '') + (p.stderr or '')


class Project:
    """一个已打开的 bin。"""

    def __init__(self, bin_path: str | Path):
        self.bin_path = Path(bin_path).resolve()
        if not self.bin_path.exists():
            raise FileNotFoundError(f'找不到文件：{self.bin_path}')
        tag = hashlib.md5(str(self.bin_path).encode('utf-8')).hexdigest()[:8]
        self.work = ROOT / 'work' / 'open' / f'{self.bin_path.stem}_{tag}'
        self.param_dir = self.work / 'params'
        self.work.mkdir(parents=True, exist_ok=True)
        log = _run(['dotnet', 'exec', str(REGROOL), 'unpack',
                    str(self.bin_path), str(self.param_dir)])
        self.unpack_log = log.strip().splitlines()[-1:] or []

        self.params = ParamDir(str(self.param_dir), str(DEF_DIR))
        self.model = SeedModel(self.params)
        self._cell_index = None
        self._pairs = None
        self._boss_names = None

    # ---------- 基础 ----------
    def param_count(self) -> int:
        return len(list(self.param_dir.glob('*.param')))

    def boss_name(self, boss_id) -> str:
        if self._boss_names is None:
            self._boss_names = {}
            for rid, r in self.params.rows(T_BOSS).items():
                self._boss_names[rid] = r.get('_name', '').strip()
        nm = self._boss_names.get(boss_id, '')
        if nm:
            return nm
        return _FALLBACK_NAMES.get(str(boss_id), f'Boss {boss_id}')

    def bosses(self) -> list[dict]:
        out = []
        for rid, r in self.params.rows(T_BOSS).items():
            bid = rid
            sets = [s for s in self.model.sets.values()
                    if s.get('targetBoss') == bid or str(s.get('_name', '')).startswith('[')]
            out.append({
                'id': rid,
                'name': self.boss_name(rid),
                'rowName': r.get('_name', ''),
            })
        return out

    def sets_of_boss(self, boss_id) -> list[dict]:
        res = []
        for sid, s in self.model.sets.items():
            name = s.get('_name', '') or ''
            # set 名形如 "[Gnoster] Standard Map"，按名字里的 Boss 归属
            if f'[{self.boss_name(boss_id)}]' in name or s.get('targetBoss') == boss_id:
                rng = self.model.ranges.get(sid)
                res.append({
                    'set': sid,
                    'name': name,
                    'count': s.get('patternCount'),
                    'weight': s.get('weight'),
                    'range': list(rng) if rng else None,
                })
        return res

    def pattern_info(self, pid: int) -> dict:
        info = self.model.pattern_info(pid)
        s = info.get('set') or {}
        out = {
            'patternId': pid,
            'set': s.get('set'),
            'setName': s.get('name'),
            'range': list(s.get('range') or []),
            'weight': s.get('weight'),
            'variants': info['variants'],
            'playArea': info['playArea'],
            'spots': [],
        }
        for sp in info['spots']:
            ov = self.attach_overrides().get(sp['attachId'])
            out['spots'].append({
                'row': sp['row'].get('_id'),
                'attachId': sp['attachId'],
                'tile': sp['tile'],
                'grid': list(sp['grid']),
                'pos': list(sp['pos']),
                'world': list(ov) if ov else list(sp['world']),
                'icon': sp['icon'],
                'realName': sp.get('realName') or '',
                'attrIcon': sp.get('attrIcon'),
                'attrName': self.attr_name(sp.get('attrIcon')),
                'attachName': sp['attachName'],
                'attachSize': sp['attachSize'],
                'defineNames': sp['define_names'],
                'name': sp['name'],
            })
        return out

    # ---------- 地图点选 ----------
    def cell_index(self) -> dict:
        """(gridX, gridZ) → 该格里官方出现过的 attach × tile 组合。"""
        if self._cell_index is not None:
            return self._cell_index
        idx: dict[tuple, dict] = {}
        attach = {k: v for k, v in self.model.attach.items()}
        for r in self.params.rows(T_SPOT).values():
            aid = r.get('attachId')
            tile = r.get('smallBaseMapId')
            ap = attach.get(aid)
            if not ap:
                continue
            key = (ap.get('gridXNo'), ap.get('gridZNo'))
            slot = idx.setdefault(key, {})
            item = slot.setdefault(aid, {'attachId': aid, 'tiles': set()})
            if tile is not None:
                item['tiles'].add(tile)
        for key, slot in idx.items():
            for aid, item in slot.items():
                ap = attach[aid]
                item['attachName'] = ap.get('_name', '')
                item['attachSize'] = self.model.attach_size(ap.get('_name', ''))
                item['pos'] = [ap.get('posX'), ap.get('posY'), ap.get('posZ')]
                item['tiles'] = sorted(item['tiles'])
                item['tileNames'] = [self._define_name(t) for t in item['tiles']]
        self._cell_index = idx
        return idx

    def _define_name(self, tile) -> str:
        for did in self.model.define_of_tile.get(tile, []):
            nm = self.model.define[did].get('_name', '')
            if nm:
                return nm
        return ''

    def minor_base_tiles(self) -> set:
        """官方出现过的所有 minor base（小据点建筑），m04591。

        判定用 define 行名：church / sorcerer's rise / camp / township 算小据点，
        field boss（野外BOSS）、caravan（商队）、evergaol（监牢）都不算。
        """
        if getattr(self, '_minor_tiles', None) is not None:
            return self._minor_tiles
        out = set()
        for t in self.model.variation:
            if self.tile_size(t) != '小':
                continue
            nm = self._define_name(t).lower()
            vn = (self.model.variation[t].get('_name') or '').lower()
            if not nm or 'field boss' in nm or 'evergaol' in nm or 'caravan' in nm:
                continue
            if 'caravan' in vn:      # 「Caravans B」挂在 Small Camp 名下，但它是商队
                continue
            out.add(t)
        self._minor_tiles = out
        return out

    def tile_size(self, tile: int):
        """这个建筑（smallBaseMapId）属于「大据点」还是「小据点」。

        依据是历史上它被塞进过哪种 attach 槽位（同一建筑只会在同一种槽位出现）。
        """
        if not hasattr(self, '_tile_size') or self._tile_size is None:
            m = {}
            for r in self.model.spots:
                t = r.get('smallBaseMapId')
                if not t:
                    continue
                ap = self.model.attach.get(r.get('attachId')) or {}
                sz = self.model.attach_size(ap.get('_name') or '')
                if sz in ('大', '小'):
                    m.setdefault(t, sz)
            self._tile_size = m
        return self._tile_size.get(tile)

    def attach_pad(self) -> dict:
        """AttachPoint 的 `pad[1]`（paramdef 里是 dummy8，解析器会丢掉）。

        m04741：**0 = 普通地图，非 0 = 特殊地形**（1..5 各一种）。
        这些点不能当普通地图的据点用，所以要从「空闲点」里排掉。
        """
        path = self.param_dir / 'SmallBaseAndSpotAttachPoint.param'
        b = path.read_bytes()
        _, ents, _ = self.params._read_table(b)
        # 行首布局：s32 _id(4) + u8 areaNo + u8 gridX + u8 gridZ + u8 pad → pad 在 +7
        return {rid: b[doff + 7] for rid, doff, _ in ents}

    def playarea_pad(self) -> dict:
        """PlayAreaCreateParam 的 `pad[1]`（dummy8，解析器会丢）。

        m05770：pad = 地图类型编号，**普通地图 = 0**；咱们的地图就是普通地图。
        行首布局：s32 _id(4) + u8 ×4（NT / reserve2 / areaNo / gridX）+ u8 gridZ + u8 pad
        → 实测 pad 在 doff + 7（gridX 在 +5、gridZ 在 +6）。
        """
        path = self.param_dir / 'PlayAreaCreateParam.param'
        b = path.read_bytes()
        _, ents, _ = self.params._read_table(b)
        return {rid: b[doff + 7] for rid, doff, _ in ents}

    def boss_modifier(self) -> dict:
        """夜王 → bossModifier（m05801：bossModifierx 与 bossId x 一一对应）。

        从 LotResultPlayAreaParam 实测：36 个 bossId 各只有一个 modifier，无歧义。
        """
        out = {}
        for r in self.model.playarea.values():
            for bid, mod in ((r.get('bossId1'), r.get('bossModifier1')),
                             (r.get('bossId2'), r.get('bossModifier2'))):
                if bid and bid > 0 and mod is not None:
                    out.setdefault(bid, mod)
        return out

    def deleted_attach(self) -> set:
        """m05074 标掉的点（删除标记，不改 bin）。"""
        p = Path(__file__).resolve().parents[2] / 'src' / 'data' / 'attach_deleted.json'
        if not p.exists():
            return set()
        try:
            return set(json.loads(p.read_text(encoding='utf-8')).get('ids') or [])
        except Exception:
            return set()

    def attr_names(self) -> dict:
        """426xx 属性图标 → 中文名（m05452 属性变体）。"""
        p = Path(__file__).resolve().parents[2] / 'src' / 'data' / 'attr_icons.json'
        if not p.exists():
            return {}
        try:
            raw = json.loads(p.read_text(encoding='utf-8')).get('icons') or {}
        except Exception:  # noqa: BLE001
            return {}
        return {int(k): v for k, v in raw.items()}

    def attr_name(self, icon_id) -> str:
        if not icon_id:
            return ''
        return self.attr_names().get(int(icon_id), '')

    def playarea_options(self, pid: int, map_id: str | None = None) -> list:
        """该夜王（按模板 playArea 行的 [名字] 前缀）用过的缩圈/BOSS 组合（m05590）。

        只给官方真出现过的组合，避免选出游戏里不存在的搭配。
        """
        import re
        from collections import Counter

        me = self.model.playarea.get(pid) or {}
        name = me.get('_name') or ''
        m = re.match(r'\[[^\]]+\]', name)
        prefix = m.group(0) if m else ''
        pad = self.playarea_pad()          # m05770：pad=0 才是普通地图
        # m06792：特殊地形的一缩/二缩（1021 Rotted / 1023 Mountaintop / 1024 Crater / 1025-1026 Shrouded）
        prof = (self.map_profiles().get(map_id) or {}) if map_id else {}
        terrain = prof.get('terrain') or '[Standard]'
        allowed_prefix = ('[Standard]', terrain)
        seen = set()
        cnt = Counter()
        first = {}
        for r in self.model.playarea.values():
            if prefix and not (r.get('_name') or '').startswith(prefix):
                continue
            p1, p2 = r.get('playArea1'), r.get('playArea2')
            ca = self.params.rows('PlayAreaCreateParam')

            def _prefix(aid):
                nm = (ca.get(aid) or {}).get('_name') or ''
                m2 = re.match(r'\[[^\]]+\]', nm)
                return m2.group(0) if m2 else ''

            # m06792：两个缩圈点都必须是「普通」或「当前地形」的
            if any(rp and rp not in allowed_prefix
                   for rp in (_prefix(p1), _prefix(p2))):
                continue
            # 同名字同坐标同缩圈只留一行（2xxxx 是 1000 段的无名副本）
            sig = (r.get('playArea1'), r.get('playArea2'), r.get('_name'),
                   r.get('gridXNo'), r.get('gridZNo'), r.get('posX'), r.get('posZ'))
            if sig in seen:
                continue
            seen.add(sig)
            key = (r.get('playArea1'), r.get('playArea2'),
                   r.get('bossId1'), r.get('bossId2'))
            cnt[key] += 1
            first.setdefault(key, r)
        out = []
        for key, n in cnt.most_common():
            r = first[key]
            out.append({'row': r.get('_id'), 'playArea1': key[0], 'playArea2': key[1],
                        'bossId1': key[2], 'bossId2': key[3],
                        'name': (r.get('_name') or '').strip(), 'count': n,
                        'isTemplate': key == (me.get('playArea1'), me.get('playArea2'),
                                              me.get('bossId1'), me.get('bossId2'))})
        return out

    def attach_overrides(self) -> dict:
        """人工校准过的坐标（m05210 采纳，只影响显示/摆点，不写回 bin）。"""
        p = Path(__file__).resolve().parents[2] / 'src' / 'data' / 'attach_overrides.json'
        if not p.exists():
            return {}
        try:
            pts = json.loads(p.read_text(encoding='utf-8')).get('points') or {}
        except Exception:
            return {}
        return {int(k): v['world'] for k, v in pts.items() if v.get('world')}

    def map_profiles(self) -> dict:
        """src/data/maps.json（地图档案：底图 + 这张图的 attachPool / overrides）。"""
        p = Path(__file__).resolve().parents[2] / 'src' / 'data' / 'maps.json'
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding='utf-8')).get('maps') or {}
        except Exception:
            return {}

    def attach_points(self, map_id: str | None = None) -> list:
        """AttachPoint 全表 → 画点用的列表（m04640：补上「图上没有的点」）。"""
        pad = self.attach_pad()
        drop = self.deleted_attach()     # m05074：标掉的点不参与编辑
        overrides = self.attach_overrides()
        prof = (self.map_profiles().get(map_id) or {}) if map_id else {}
        pool = prof.get('attachPool')
        pool = set(pool) if pool else None
        local = {int(k): v for k, v in (prof.get('overrides') or {}).items()}
        overrides = {**overrides, **local}
        out = []
        layer_sets = {}
        for lname, ids in ((prof.get('layers') or {}) or {}).items():
            for a in ids or []:
                layer_sets[int(a)] = lname
        for aid, ap in self.model.attach.items():
            if pool is not None:
                # 有显式池子（大空洞等 1xxx 段）→ 完全按池子来，跳过 id/pad 过滤
                if aid not in pool:
                    continue
            else:
                if aid >= 1000:
                    continue
                if pad.get(aid, 0) != 0:      # 特殊地形（pad != 0）不算普通地图的点
                    continue
                if aid in drop:
                    continue
            gx, gz = ap.get('gridXNo'), ap.get('gridZNo')
            if gx is None or gz is None:
                continue
            size = self.model.attach_size(ap.get('_name') or '')
            ov = overrides.get(aid)
            out.append({
                'attachId': aid,
                'attachName': ap.get('_name') or '',
                'attachSize': size,
                'layer': layer_sets.get(aid),
                'grid': [gx, gz],
                'world': list(ov) if ov else [
                    gx * 256 + 128 + (ap.get('posX') or 0),
                    gz * 256 + 128 + (ap.get('posZ') or 0)],
            })
        return sorted(out, key=lambda x: x['attachId'])

    def official_tiles(self) -> dict:
        """attachId → 官方种子里在这个位置实际用过的 tile 集合（m05400）。

        合并 ±2000 的 DLC 孪生：attach 101 和 2101 是同一个世界位置（坐标完全相同），
        锻造村 / 毒池（tile 5000/5001/5010/5011…）只挂在 21xx 那边，
        不合并的话 101 的候选列表里永远没有它们。
        """
        if getattr(self, '_official_tiles', None) is not None:
            return self._official_tiles
        out: dict[int, set] = {}
        for r in self.model.spots:
            aid = r.get('attachId')
            tile = r.get('smallBaseMapId')
            if aid is None or tile is None:
                continue
            a, t = int(aid), int(tile)
            out.setdefault(a, set()).add(t)
            for off in (-2000, 2000):
                if a + off > 0:
                    out.setdefault(a + off, set()).add(t)
        self._official_tiles = out
        return out

    def base_combos(self) -> dict:
        """modifierSet → 可选的 (eventFlag, modifier, weight, name) 列表（来自 LotBaseMapPatternFlag）。

        m05915：结果表的三元组必须在 base 表里存在，才算「填对了」。
        """
        if getattr(self, '_base_combos', None) is not None:
            return self._base_combos
        out: dict[int, list] = {}
        for r in self.params.rows('LotBaseMapPatternFlag').values():
            st = int(r.get('modifierSet') or 0)
            out.setdefault(st, []).append({
                'eventFlag': int(r.get('eventFlag') or 0),
                'modifier': int(r.get('modifier') or 0),
                'weight': int(r.get('weight') or 0),
                'name': (r.get('_name') or '').strip(),
            })
        for v in out.values():
            v.sort(key=lambda x: (x['eventFlag'], x['modifier']))
        self._base_combos = out
        return out

    def flag_name(self, event_flag: int, modifier: int, modifier_set: int) -> str:
        """三元组在 base 表里的名字（查不到就返回空串）。"""
        for c in self.base_combos().get(int(modifier_set), []):
            if c['eventFlag'] == int(event_flag) and c['modifier'] == int(modifier):
                return c['name']
        return ''

    def attach_candidates(self, attach_id: int) -> dict:
        """某个 attach 点能放什么 —— 直接照抄官方种子在这个位置用过的建筑（m05400）。"""
        ap = self.model.attach.get(attach_id) or {}
        name = ap.get('_name') or ''
        size = self.model.attach_size(name)
        tiles = sorted(t for t in self.official_tiles().get(int(attach_id), ())
                       if self.model.variation.get(t))
        if not tiles:
            # 官方从没用过这个点：退回按尺寸给池（保留能力，但不作为默认）
            low = name.lower()
            if 'evergaol' in low:
                tiles = sorted(EVERGAOL_TILES)
            elif 'field boss' in low:
                tiles = sorted(t for t in self.model.variation
                               if 'field boss' in (self._define_name(t) or '').lower())
            elif size == '小':
                tiles = sorted(self.minor_base_tiles())
            elif size == '大':
                tiles = sorted(t for t in self.model.variation if self.tile_size(t) == '大')
        tiles = [t for t in tiles if self.model.variation.get(t)]
        tiles.sort(key=lambda t: 0 if self.model.variation.get(t) else 1)
        base = self.spot_view(attach_id, tiles[0]) if tiles else {}
        return {
            'attachId': attach_id,
            'attachName': name,
            'attachSize': size,
            'grid': [ap.get('gridXNo'), ap.get('gridZNo')],
            'pos': [ap.get('posX'), ap.get('posY'), ap.get('posZ')],
            'icon': base.get('icon'),
            'realName': base.get('realName'),
            'attrIcon': base.get('attrIcon'),
            'attrName': self.attr_name(base.get('attrIcon')),
            'tiles': tiles,
            'tileNames': [self._define_name(t) for t in tiles],
            'tileInfo': [{'tile': t, 'define': self._define_name(t),
                          'variation': bool(self.model.variation.get(t)),
                          'icon': self.spot_view(attach_id, t)['icon'],
                          'realName': self.spot_view(attach_id, t)['realName'],
                          'attrIcon': self.spot_view(attach_id, t)['attrIcon'],
                          'attrName': self.attr_name(self.spot_view(attach_id, t)['attrIcon']),
                          'variants': self.tile_variants(t)}
                         for t in tiles],
        }

    def cell_candidates(self, gx: int, gz: int) -> dict:
        slot = self.cell_index().get((gx, gz), {})

        # m04411：同一格里，同尺寸的据点共用一套「能放的建筑」——
        # 规则：能选要塞和教堂，就一定能选遗迹和营地。
        # 所以不再按 (attachId, tile) 逐对限制，改成「按尺寸取这一格出现过的所有建筑」。
        pool = {'大': set(), '小': set()}
        for c in slot.values():
            sz = c.get('attachSize')
            if sz not in ('大', '小'):
                continue
            if int(c['attachId']) >= 1000:
                continue
            for t in c['tiles']:
                if self.tile_size(t) == sz:
                    pool[sz].add(t)

        # m04591：小据点不按格子限制 —— 官方出现过的 minor base 全量入池
        pool['小'] |= self.minor_base_tiles()

        cands = []
        for c in slot.values():
            # 只保留普通地图的点（m02278）：地下/大空洞那批 attachId >= 1000 全不要
            if int(c['attachId']) >= 1000:
                continue
            sz = c.get('attachSize')
            if 'evergaol' in (c.get('attachName') or '').lower():
                tiles = [t for t in c['tiles'] if t in EVERGAOL_TILES]
            elif sz in ('大', '小'):
                tiles = sorted(pool[sz])
            else:
                continue
            if not tiles:
                continue
            # 把有 variation 行的 tile 排前面，避免拿 2030 那种空壳算不出建筑（m02276）
            tiles.sort(key=lambda t: 0 if self.model.variation.get(t) else 1)
            c = dict(c)
            c['tiles'] = tiles
            c['tileNames'] = [self._define_name(t) for t in tiles]
            sv = self.spot_view(c['attachId'], tiles[0])
            c['icon'] = sv['icon']
            c['realName'] = sv['realName']
            c['attrIcon'] = sv['attrIcon']
            c['attrName'] = self.attr_name(sv['attrIcon'])
            ti = []
            for t in tiles:
                v = self.spot_view(c['attachId'], t)
                ti.append({'tile': t, 'define': self._define_name(t),
                           'variation': bool(self.model.variation.get(t)),
                           'icon': v['icon'], 'realName': v['realName'],
                           'attrIcon': v['attrIcon'],
                           'attrName': self.attr_name(v['attrIcon']),
                           'variants': self.tile_variants(t),
                           'variationId': 0})
            c['tileInfo'] = ti
            cands.append(c)
        cands.sort(key=lambda d: (d['attachSize'] != '小', d['attachId']))
        return {'grid': [gx, gz], 'candidates': cands}

    def allowed_pairs(self) -> set:
        """可放的 (attachId, smallBaseMapId)：以真实数据里出现过的组合为准。
        m02094：建筑真身是 smallBaseMapId（SmallBaseMapVariationParam），
        spot 行的 Name 只是地块名 —— 所以能不能放，看这一对在表里出现过没有。
        """
        if self._pairs is None:
            pairs = set()
            for r in self.model.spots:
                t = r.get('smallBaseMapId')
                if t:
                    pairs.add((r['attachId'], t))
            self._pairs = pairs
        return self._pairs

    def tile_variants(self, tile) -> list:
        """这一格能选的「属性变体」（m04153 / m04160 / m04368）。

        variationId 是 **0 基**：0 = 第 1 号变体，1 = 第 2 号变体 …
        槽位号 = variationId + 1；槽位「存不存在」看 `variationValue_x ≠ 0`。
        图标为 0 的那一档 = 无属性变体。
        """
        var = self.model.variation.get(tile) or {}
        out = []
        for slot in range(1, 11):
            val = var.get(f'variationValue_{slot}')
            if not val:
                continue
            ic = var.get(f'variationIconId_{slot}')
            out.append({'variationId': slot - 1, 'slot': slot,
                        'icon': (ic or None), 'value': val,
                        'attrName': self.attr_name(ic)})
        return out

    def variant_probe(self, tile, variation_id) -> dict:
        """m06850：手输一个 variationId，查出它落在哪个槽位、是不是真有这一档。

        variationId 是 **0 基**（槽位 = variationId + 1）；槽位存在看
        `variationValue_x ≠ 0`；`variationIconId_x = 0` = 这一档没有属性图标。
        """
        tile = int(tile)
        try:
            vid = int(variation_id)
        except (TypeError, ValueError):
            vid = 0
        slot = vid + 1
        var = self.model.variation.get(tile) or {}
        val = var.get(f'variationValue_{slot}')
        ic = var.get(f'variationIconId_{slot}')
        return {
            'tile': tile,
            'variationId': vid,
            'slot': slot,
            'exists': bool(val),
            'value': val or 0,
            'icon': ic or None,
            'attrName': self.attr_name(ic),
            'hasRow': bool(var),
        }

    def tile_info(self, tile) -> dict:
        names = []
        for did in self.model.define_of_tile.get(tile, []):
            nm = self.model.define[did].get('_name', '')
            if nm:
                names.append(nm)
        var = self.model.variation.get(tile)
        return {'tile': tile, 'defineNames': names, 'variation': bool(var),
                'variants': self.tile_variants(tile)}

    def tile_probe(self, attach_id: int, tile: int) -> dict:
        """m06316：用户手输一个小 smallBaseMapId，回来查它是什么建筑。

        返回结构对齐 `cell_candidates()` 里 `tileInfo` 的单项，外加 `exists`
        （SmallBaseMapVariationParam 里到底有没有这一行）。
        """
        var = self.model.variation.get(tile)
        sv = self.spot_view(attach_id, tile)
        return {
            'tile': tile,
            'exists': bool(var),
            'define': self._define_name(tile),
            'variation': bool(var),
            'icon': sv.get('icon'),
            'realName': sv.get('realName'),
            'attrIcon': sv.get('attrIcon'),
            'attrName': self.attr_name(sv.get('attrIcon')),
            'variants': self.tile_variants(tile),
        }

    def spot_view(self, attach_id: int, tile: int, variation_id: int = 0) -> dict:
        """草稿里的一行 → 供界面画点用。"""
        row = {'_id': 0, 'patternId': 0, 'attachId': attach_id,
               'smallBaseMapId': tile, 'mapIndex': 0,
               'variationId': variation_id or 0, 'modifier': 0}
        sp = self.model.describe_spot(row)
        # m05210：校准过的点，显示用校准坐标（数据仍用原始行）
        ov = self.attach_overrides().get(attach_id)
        if ov:
            sp['world'] = list(ov)
        return {
            'attachId': attach_id,
            'tile': tile,
            'variationId': variation_id or 0,
            'icon': sp['icon'],
            'attrIcon': sp.get('attrIcon'),
            'attrName': self.attr_name(sp.get('attrIcon')),
            'realName': sp.get('realName') or '',
            'name': sp['name'],
            'attachName': sp['attachName'],
            'attachSize': sp['attachSize'],
            'grid': list(sp['grid']),
            'world': list(sp['world']),
            # m02506：把这一行（以及 attach/variation 行）的原始字段全交出去，右边直接列
            'raw': self.raw_fields(attach_id, tile),
        }

    def raw_fields(self, attach_id: int, tile) -> dict:
        """草稿行 + attach 行 + variation 行 的原始字段，供界面「全部参数」展示。"""
        out = {}
        row = {'_id': 0, 'patternId': 0, 'attachId': attach_id,
               'smallBaseMapId': tile, 'mapIndex': 0, 'variationId': 0, 'modifier': 0}
        for k, v in row.items():
            out['spot.' + k] = v
        ap = self.model.attach.get(attach_id) or {}
        for k, v in sorted(ap.items()):
            out['attach.' + k] = v
        var = self.model.variation.get(tile) or {}
        for k, v in sorted(var.items()):
            out['variation.' + k] = v
        return out





