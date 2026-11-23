'use strict';
const $ = id => document.getElementById(id);
const cv = $('map'), ctx = cv.getContext('2d');
const hcv = $('hl'), hctx = hcv.getContext('2d');

let T = null;          // 树
let IMG = null;        // 地图底图
let PICK = null;       // 底部选择条状态
let CIRCLES = [];      // 每次 draw 重建：地点大圈 / 建筑位小圈
let SEL = null;        // {kind:'spot'|'anchor', row?, attachId?}
let HOVER = null;      // 悬停的那个圈

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

let toastTimer = null;
function toast(msg, isErr) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.toggle('err', !!isErr);
  el.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), 2600);
}

/* ---------------- 地图 ---------------- */
function fit() {
  const wrap = $('mapWrap'), box = $('mapBox');
  const s = Math.max(360, Math.min(wrap.clientWidth - 16, wrap.clientHeight - 16));
  box.style.width = s + 'px';
  box.style.height = s + 'px';
}
window.addEventListener('resize', () => { fit(); draw(); });

function loadMap() {
  const im = new Image();
  im.onload = () => { IMG = im; draw(); };
  im.onerror = () => { IMG = null; draw(); };
  im.src = '/api3/map.png?rev=' + (T ? T.rev : 0) + '&t=' + Date.now();
}

function colorOf(a) {
  const t = a && a.type;
  if (t === 'blue') return '77,163,255';      // 城 / 塔
  if (t === 'green') return '65,209,138';     // 野外 BOSS / 据点
  return '235,235,240';                        // 其他：白圈
}

/* 圆圈层：建筑位=小圈（校准坐标，全部保留）；地点=大圈。
   地点能认到建筑位时，**大圈直接用建筑位的坐标**（2026-11-15：大圈跟着小圈走）。 */
function buildCircles() {
  CIRCLES = [];
  if (!T || !T.map) return;
  const { ox, oz } = T.map;
  const anchors = T.anchors || [];
  const spots = (T.pidInfo && T.pidInfo.spotView) || [];

  // 先放小圈（全量，不删）
  for (const a of anchors) {
    CIRCLES.push({
      kind: 'anchor', x: a.world[0] - ox, y: oz - a.world[1], r: 7,
      color: colorOf(a), anchor: a,
    });
  }

  for (const sp of spots) {
    if (sp.px == null && sp.world == null) continue;
    // 认亲顺序：原号 → 孪生号（±1000/±2000/±3000）→ 世界坐标
    let anchor = null;
    for (const k of [sp.attachId, sp.attachId - 1000, sp.attachId - 2000, sp.attachId - 3000,
                     sp.attachId + 1000, sp.attachId + 2000]) {
      if (k > 0) {
        const a = anchors.find(x => x.attachId === k);
        if (a) { anchor = a; break; }
      }
    }
    if (!anchor && sp.world) {
      for (const a of anchors) {
        if (Math.abs(a.world[0] - sp.world[0]) < 14 && Math.abs(a.world[1] - sp.world[1]) < 14) {
          anchor = a; break;
        }
      }
    }
    const x = anchor ? (anchor.world[0] - ox) : sp.px;
    const y = anchor ? (oz - anchor.world[1]) : sp.py;
    CIRCLES.push({
      kind: 'spot', x, y, r: 38,
      color: anchor ? colorOf(anchor) : '235,235,240',
      spot: sp, anchor,
    });
  }
}

function isSel(c) {
  if (!SEL) return false;
  if (c.kind === 'spot') return SEL.kind === 'spot' && SEL.row === c.spot.row;
  return SEL.kind === 'anchor' && SEL.attachId === c.anchor.attachId;
}

function drawCircles() {
  const PI2 = Math.PI * 2;
  // 先画小圈（在下），再画大圈（在上）
  for (const c of CIRCLES) {
    if (c.kind !== 'anchor') continue;
    const sel = isSel(c);
    const hov = HOVER === c;
    hctx.strokeStyle = 'rgba(20,22,26,.8)';
    hctx.lineWidth = 4;
    hctx.beginPath(); hctx.arc(c.x, c.y, c.r, 0, PI2); hctx.stroke();
    hctx.strokeStyle = sel ? '#fff' : `rgba(${c.color},${hov ? 1 : .92})`;
    hctx.lineWidth = sel ? 3 : 1.8;
    hctx.beginPath(); hctx.arc(c.x, c.y, c.r, 0, PI2); hctx.stroke();
    hctx.fillStyle = sel ? '#fff' : `rgba(${c.color},.9)`;
    hctx.beginPath(); hctx.arc(c.x, c.y, sel ? 3.2 : 2, 0, PI2); hctx.fill();
  }
  for (const c of CIRCLES) {
    if (c.kind !== 'spot') continue;
    const sel = isSel(c);
    const hov = HOVER === c;
    if (sel) {
      hctx.strokeStyle = 'rgba(120,200,255,.55)';
      hctx.lineWidth = 2;
      hctx.beginPath(); hctx.arc(c.x, c.y, c.r + 7, 0, PI2); hctx.stroke();
    }
    hctx.strokeStyle = sel ? 'rgba(255,255,255,1)'
      : (hov ? `rgba(${c.color},1)` : `rgba(${c.color},.8)`);
    hctx.lineWidth = sel ? 4.5 : (hov ? 4 : 2.6);
    hctx.beginPath(); hctx.arc(c.x, c.y, c.r, 0, PI2); hctx.stroke();
    if (sel) {
      hctx.strokeStyle = 'rgba(77,163,255,.95)';
      hctx.lineWidth = 1.5;
      hctx.beginPath(); hctx.arc(c.x, c.y, c.r - 4, 0, PI2); hctx.stroke();
    }
  }
}

function nearestCircle(x, y) {
  let best = null, bd = 1e9;
  let bestSpot = null, bsd = 1e9;
  for (const c of CIRCLES) {
    const d = Math.hypot(c.x - x, c.y - y);
    const limit = c.kind === 'spot' ? c.r + 6 : 15;
    if (d > limit) continue;
    if (d < bd) { best = c; bd = d; }
    if (c.kind === 'spot' && d < bsd) { bestSpot = c; bsd = d; }
  }
  // 同一个圆心时优先大圈（有地点就选地点）
  if (bestSpot && bd - bsd <= 1.5) return bestSpot;
  return best;
}

function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (IMG) ctx.drawImage(IMG, 0, 0, cv.width, cv.height);
  hctx.clearRect(0, 0, hcv.width, hcv.height);
  if (!T || !T.map) return;
  buildCircles();
  drawCircles();
  drawAreaMarkers();
}

/* 1缩 / 2缩 的位置标记（老界面同款：1 橙、2 蓝；悬停候选点时虚线预演） */
let PREVIEW = null;   // {key:'pa1'|'pa2', id}
function areaWorld(a) {
  return [a.grid[0] * 256 + 128 + a.pos[0], a.grid[1] * 256 + 128 + a.pos[1]];
}
function drawAreaMarkers() {
  const pa = T.pidInfo && T.pidInfo.playarea;
  if (!pa || !T.map) return;
  const byId = {};
  for (const o of (T.playareas || [])) byId[o.id] = o;
  const drawOne = (id, label, color, preview) => {
    const a = byId[id];
    if (!a) return;
    const [wx, wz] = areaWorld(a);
    const x = wx - T.map.ox, y = T.map.oz - wz;
    hctx.save();
    hctx.beginPath(); hctx.arc(x, y, 17, 0, Math.PI * 2);
    hctx.fillStyle = 'rgba(12,14,18,.85)'; hctx.fill();
    hctx.lineWidth = preview ? 2 : 3;
    if (preview) hctx.setLineDash([5, 4]);
    hctx.strokeStyle = color; hctx.stroke();
    hctx.setLineDash([]);
    hctx.fillStyle = color;
    hctx.font = 'bold 17px "Microsoft YaHei",sans-serif';
    hctx.textAlign = 'center'; hctx.textBaseline = 'middle';
    hctx.fillText(label, x, y + 1);
    hctx.restore();
  };
  const p1 = (PREVIEW && PREVIEW.key === 'pa1') ? PREVIEW.id : pa.playArea1;
  const p2 = (PREVIEW && PREVIEW.key === 'pa2') ? PREVIEW.id : pa.playArea2;
  drawOne(p1, '1', 'rgba(255,196,84,1)', !!(PREVIEW && PREVIEW.key === 'pa1'));
  drawOne(p2, '2', 'rgba(120,200,255,1)', !!(PREVIEW && PREVIEW.key === 'pa2'));
}

function evPos(ev) {
  const r = cv.getBoundingClientRect();
  return [(ev.clientX - r.left) * cv.width / r.width,
          (ev.clientY - r.top) * cv.height / r.height];
}

cv.addEventListener('click', async ev => {
  if (!T) return;
  const [x, y] = evPos(ev);
  const c = nearestCircle(x, y);
  if (!c) {
    SEL = null; draw();
    if (PICK) closePicker();
    return;
  }
  if (c.kind === 'spot') {
    // 点地点：只高亮，不弹建筑选择
    SEL = { kind: 'spot', row: c.spot.row };
    draw();
    highlightSpotRow(c.spot.row);
    if (PICK) closePicker();
  } else {
    // 点空建筑位：高亮 + 弹建筑选择条
    SEL = { kind: 'anchor', attachId: c.anchor.attachId };
    draw();
    openAnchorPicker(c.anchor);
  }
});

cv.addEventListener('mousemove', ev => {
  if (!T) return;
  const [x, y] = evPos(ev);
  const c = nearestCircle(x, y);
  if (c !== HOVER) {
    HOVER = c;
    cv.style.cursor = c ? 'pointer' : 'crosshair';
    draw();
  }
});

cv.addEventListener('mouseleave', () => {
  if (HOVER) { HOVER = null; draw(); }
});

// 双击大圈 = 换这个地点的建筑
cv.addEventListener('dblclick', ev => {
  if (!T || T.selPid == null) return;
  const [x, y] = evPos(ev);
  const c = nearestCircle(x, y);
  if (c && c.kind === 'spot') openTilePicker(c.spot.row, c.spot.attachId, T.selPid);
});

function highlightSpotRow(row) {
  const trs = Array.from(document.querySelectorAll('table.spots tr[data-row]'));
  trs.forEach(tr => tr.classList.toggle('on', +tr.dataset.row === row));
  const cur = trs.find(tr => +tr.dataset.row === row);
  if (cur) cur.scrollIntoView({ block: 'nearest' });
}

/* ---------------- 底部选择条 ---------------- */
function closePicker() {
  PICK = null;
  $('picker').hidden = true;
}

async function openAnchorPicker(anchor) {
  if (T.selPid == null) { toast('先在左边选一个种子'); return; }
  const r = await api('/api3/attach?id=' + anchor.attachId);
  if (!r.ok) { toast(r.error || '读不到', true); return; }
  const cand = r.candidate || {};
  const tiles = (cand.tileInfo || []).map(t => ({
    tile: t.tile, icon: t.icon, attrIcon: t.attrIcon, attrName: t.attrName,
    label: t.realName || t.define || t.tile,
  }));
  PICK = { kind: 'anchor', anchor, tiles };
  const box = $('picker');
  box.hidden = false;
  box.innerHTML = `<div class="muted" style="width:100%;margin-bottom:4px">
      ${anchor.attachName || ('attach ' + anchor.attachId)} · 选一个建筑加到 pid ${T.selPid}</div>` +
    tiles.map((t, i) => `<div class="pick" data-i="${i}" title="${t.label}">
        ${t.icon ? `<img src="/pin/${t.icon}.png">` : `<span class="noicon">${t.tile}</span>`}
        ${t.attrIcon ? `<img class="attr" src="/pin/${t.attrIcon}.png" title="${t.attrName || ''}">` : ''}
      </div>`).join('');
  box.querySelectorAll('.pick').forEach(el => {
    el.onclick = () => addSpot(tiles[+el.dataset.i].tile, anchor.attachId);
  });
}

async function addSpot(tile, attachId) {
  const res = await apply('spot_add', { pid: T.selPid, attachId, tile, variationId: 0 });
  if (res.ok) { closePicker(); toast('已加一个地点'); }
}

/* ---------------- 状态刷新 ---------------- */
function render() {
  if (!T || !T.ok) return;
  const sel = T.sets.find(s => s.sid === T.selSet);
  const pi = T.pidInfo;
  $('ctx').textContent = (pi
    ? `${pi.combo ? (T.bosses.find(b => b.id === pi.combo[0]) || {}).name || pi.combo[0] : '—'} · ${rarName(pi.combo && pi.combo[1])} · set ${T.selSet} · pid ${T.selPid}`
    : (sel ? `set ${sel.sid} · ${sel.name}` : '没有选中'));
  $('btnSave').disabled = !T.dirty;
  $('btnSave').textContent = T.dirty ? '保存 ●' : '保存';
  renderLayerBar();
  renderTree();
  renderInspector();
  renderFoot();
  if (SEL && SEL.kind === 'spot') highlightSpotRow(SEL.row);
  loadMap();
}

function renderLayerBar() {
  const bar = $('layerBar');
  const lays = (T && T.layers) || ['surface'];
  bar.hidden = lays.length < 2;
  for (const b of bar.querySelectorAll('.lay')) {
    b.hidden = !lays.includes(b.dataset.layer);
    b.classList.toggle('on', b.dataset.layer === ((T && T.layer) || 'surface'));
  }
}
for (const b of $('layerBar').querySelectorAll('.lay')) {
  b.onclick = async () => {
    const r = await api('/api3/layer', { layer: b.dataset.layer });
    if (!r || !r.ok) { toast((r && r.error) || '切层失败', true); return; }
    T = r;
    SEL = null;
    render();
    toast(b.dataset.layer === 'under' ? '已切到下层 B1' : '已切到上层 L0');
  };
}

function renderFoot() {
  const hist = (T && T.history) || [];
  $('histInfo').textContent = hist.length ? `已操作 ${hist.length} 步` : '还没改过';
  $('btnUndo').disabled = !hist.length;
}

async function undoLast() {
  const hist = (T && T.history) || [];
  if (!hist.length) { toast('没有可撤销的操作'); return; }
  const last = hist[hist.length - 1];
  const r = await api('/api3/rollback', { n: last.n });
  if (!r.ok) { toast(r.error || '回滚失败', true); return; }
  T = r.tree;
  render();
  toast(`已撤销「${last.title}」`);
}
$('btnUndo').onclick = undoLast;

function rarName(id) {
  const r = (T.rares || []).find(x => x.id === id);
  return r ? r.name : '—';
}

/* ---------------- 名称表 ---------------- */
let NAMES = null, NAMES_VAR = {}, NAMES_BOSS = {}, NAMES_TAB = 'tile';

function escH(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function openNames() {
  const r = await api('/api3/names');
  NAMES = r.tiles || {};
  NAMES_VAR = r.variants || {};
  NAMES_BOSS = r.bosses || {};
  document.getElementById('namesModal').hidden = false;
  $('nmSearch').value = '';
  setNamesTab(NAMES_TAB);
}

function setNamesTab(tab) {
  NAMES_TAB = tab;
  document.querySelectorAll('#namesModal .tab').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  $('nmTilePane').hidden = tab !== 'tile';
  $('nmBossPane').hidden = tab !== 'boss';
  $('nmSearch').placeholder = tab === 'tile' ? '搜索 tile id / 名称' : '搜索 bossId / 名字';
  renderNames($('nmSearch').value);
}

function variantCells(tile) {
  const vs = NAMES_VAR[String(tile)] || [];
  if (!vs.length) return '<span class="muted">—</span>';
  return vs.map(v => `<span class="vpair" title="variationId ${v.v}${v.auto ? ' · 自动识别：' + v.auto : ''}">`
    + `<b>${v.v}</b><input class="vmin" data-vk="${tile}" data-v="${v.v}" `
    + `value="${escH(v.custom ? v.name : '')}" placeholder="${escH(v.auto)}"></span>`).join('');
}

function renderNames(filter) {
  const f = (filter || '').trim().toLowerCase();
  if (NAMES_TAB === 'tile') {
    const keys = Object.keys(NAMES).sort((a, b) => Number(a) - Number(b)).filter(k => {
      if (!f) return true;
      const v = NAMES[k] || {};
      const vt = (NAMES_VAR[String(k)] || []).map(x => x.name).join(' ');
      return k.includes(f) || String(v.en || '').toLowerCase().includes(f)
        || String(v.cn || '').includes(f) || vt.includes(f);
    });
    $('nmTable').querySelector('tbody').innerHTML = keys.map(k => {
      const v = NAMES[k] || {};
      return `<tr><td>${k}</td>
        <td><input class="nmin" data-k="${k}" data-f="en" value="${escH(v.en)}"></td>
        <td><input class="nmin" data-k="${k}" data-f="cn" value="${escH(v.cn)}" placeholder="（可留空）"></td>
        <td class="varlist">${variantCells(k)}</td></tr>`;
    }).join('');
    $('nmInfo').textContent = `${keys.length} / ${Object.keys(NAMES).length}`;
  } else {
    const mod = {};
    for (const b of (T && T.nightBosses) || []) mod[b.id] = b.modifier;
    const keys = Object.keys(NAMES_BOSS).sort((a, b) => Number(a) - Number(b)).filter(k => {
      if (!f) return true;
      const v = NAMES_BOSS[k] || {};
      return k.includes(f) || String(v.en || '').toLowerCase().includes(f) || String(v.cn || '').includes(f)
        || String(mod[k] ?? '').includes(f);
    });
    $('nmBossTable').querySelector('tbody').innerHTML = keys.map(k => {
      const v = NAMES_BOSS[k] || {};
      const m = mod[k];
      return `<tr><td>${k}</td><td class="muted">${m == null ? '—' : 'mod ' + m}</td>
        <td><input class="nmin" data-bk="${k}" data-f="cn" value="${escH(v.cn || v.en)}" placeholder="填名字（可留空）"></td></tr>`;
    }).join('');
    $('nmInfo').textContent = `${keys.length} / ${Object.keys(NAMES_BOSS).length}`;
  }
}

function collectNames() {
  const tiles = {};
  document.querySelectorAll('#nmTable .nmin').forEach(inp => {
    const k = inp.dataset.k;
    if (!tiles[k]) tiles[k] = JSON.parse(JSON.stringify(NAMES[k] || {}));
    const val = inp.value.trim();
    if (val) tiles[k][inp.dataset.f] = val;
    else if (inp.dataset.f === 'cn') delete tiles[k].cn;
  });
  // 变体自定义名（空 = 用自动识别的属性名）
  document.querySelectorAll('#nmTable .vmin').forEach(inp => {
    const k = inp.dataset.vk;
    if (!tiles[k]) tiles[k] = JSON.parse(JSON.stringify(NAMES[k] || {}));
    const variants = Object.assign({}, tiles[k].variants || {});
    const val = inp.value.trim();
    if (val) variants[inp.dataset.v] = val;
    else delete variants[inp.dataset.v];
    if (Object.keys(variants).length) tiles[k].variants = variants;
    else delete tiles[k].variants;
  });
  for (const k of Object.keys(NAMES)) if (!(k in tiles)) tiles[k] = NAMES[k];
  const bosses = {};
  document.querySelectorAll('#nmBossTable .nmin').forEach(inp => {
    const k = inp.dataset.bk;
    const val = inp.value.trim();
    bosses[k] = {};
    if (val) bosses[k].cn = val;
    const old = NAMES_BOSS[k] || {};
    if (old.en && old.en !== val) bosses[k].en = old.en;
  });
  for (const k of Object.keys(NAMES_BOSS)) if (!(k in bosses)) bosses[k] = NAMES_BOSS[k];
  return { tiles, bosses };
}

$('btnNames').onclick = openNames;
$('nmClose').onclick = () => { document.getElementById('namesModal').hidden = true; };
$('nmSearch').oninput = e => renderNames(e.target.value);
document.querySelectorAll('#namesModal .tab').forEach(b => {
  b.onclick = () => setNamesTab(b.dataset.tab);
});
$('nmSave').onclick = async () => {
  const { tiles, bosses } = collectNames();
  const r = await api('/api3/names', { tiles, bosses });
  if (!r || !r.ok) { toast((r && r.error) || '保存失败', true); return; }
  NAMES = tiles;
  NAMES_BOSS = bosses;
  toast(`名称表已保存（建筑 ${r.count} · 夜晚 BOSS ${r.bossCount}），立即生效`);
  if (T && T.ok) render();
};

function renderTree() {
  const f = $('bossFilter');
  if (f.dataset.filled !== '1') {
    f.innerHTML = '<option value="">全部夜王</option>' +
      (T.bosses || []).map(b => `<option value="${b.id}">${b.id} · ${b.name}</option>`).join('');
    f.dataset.filled = '1';
  }
  const want = f.value === '' ? null : +f.value;
  const rows = T.sets.filter(s => want === null || s.boss === want);
  $('tree').innerHTML = rows.map(s => {
    const on = s.sid === T.selSet;
    const badge = s.status === 'custom' ? '<span class="badge custom">自建</span>'
      : (s.count !== s.declared ? '<span class="badge">容量≠实际</span>' : '');
    const rng = s.range ? `${s.range[0]}..${s.range[1]}` : '—';
    let html = `<div class="srow ${on ? 'on' : ''}" data-sid="${s.sid}">
        <span class="sid">${s.sid}</span>
        <span class="nm" title="${s.name}">${s.name} <span class="muted">${rng}</span></span>
        <span class="cnt">${s.count}</span>${badge}
      </div>`;
    if (on && s.patterns.length) {
      html += `<div class="pgroup">` + s.patterns.map(p =>
        `<button class="pbtn ${p.pid === T.selPid ? 'on' : ''}" data-pid="${p.pid}"
           title="夜晚 BOSS ${p.night[0]} / ${p.night[1]}">pid ${p.pid}<span class="pc">·${p.spots}</span></button>`
      ).join('') + `</div>`;
    }
    return html;
  }).join('') || '<div class="muted">没有 set</div>';

  $('tree').querySelectorAll('.srow').forEach(el => {
    el.onclick = async () => {
      const r = await api('/api3/select', { set: +el.dataset.sid });
      T = r; render();
    };
  });
  $('tree').querySelectorAll('.pbtn').forEach(el => {
    el.onclick = async ev => {
      ev.stopPropagation();
      const r = await api('/api3/select', { pid: +el.dataset.pid });
      T = r; render();
    };
  });
}

/* ---------------- 右侧 ---------------- */
function renderInspector() {
  const box = $('inspector');
  if (!T || !T.ok) { box.innerHTML = '<div class="muted">先打开 bin</div>'; return; }
  const sel = T.sets.find(s => s.sid === T.selSet);
  const pi = T.pidInfo;
  if (pi) return renderPattern(pi, sel);
  if (sel) return renderSet(sel);
  box.innerHTML = '<div class="muted">选一个 set</div>';
}

function renderSet(s) {
  const rng = s.range ? `${s.range[0]}..${s.range[1]}` : '—';
  $('inspector').innerHTML = `
    <div class="card">
      <h3>Set ${s.sid}</h3>
      <div class="kv">
        <b>名字</b><span>${s.name}</span>
        <b>组合</b><span>${s.bossName || '—'} · ${s.rareName || '—'}</span>
        <b>种子数</b><span>${s.count}（声明 ${s.declared}）</span>
        <b>pid 区间</b><span>${rng}</span>
      </div>
      <div class="row" style="margin-top:8px"><label>weight</label>
        <input class="num" id="fWeight" type="number" value="${s.weight ?? 0}"></div>
      <div class="row"><label>chaosW</label>
        <input class="num" id="fChaos" type="number" value="${s.chaosW ?? 0}"></div>
      <div class="btns">
        <button id="btnSaveFields">保存这两个值</button>
        <button id="btnRecalc">重算池子</button>
        <button id="btnDelSet" class="danger">删整个 set</button>
      </div>
    </div>
    <div class="card">
      <h3>加/删种子</h3>
      <div class="row"><label>源 pid</label>
        <input class="num" id="fSrc" type="number"
          placeholder="${s.patterns.length ? '' : '空 set 需手填一个源 pid'}"
          value="${s.patterns.length ? s.patterns[0].pid : ''}"></div>
      <div class="btns">
        <button id="btnInsert">插入一个种子（克隆源 pid）</button>
      </div>
      <div class="muted" style="margin-top:6px">
        新种子会照抄源 pid 的 <b>全部 flag 行 / playarea / 地点</b>，只改身份字段
        （patternId、patternSetId、夜王、地图类型）。插入会把它后面的 pid 顺移。
      </div>
    </div>
    <div class="card">
      <h3>添加随机种子</h3>
      <div class="muted" style="margin-bottom:6px">
        随机挑一个<b>同地图类型</b>的官方种子当模板，按「随机表」里设的内容随机。
      </div>
      <div class="row"><label>数量</label>
        <input class="num" id="rndCount" type="number" min="1" max="50" value="1" style="flex:0 0 80px">
        <span class="muted">张（1~50，每张都重新挑模板）</span></div>
      <div class="btns">
        <button id="btnRandom" class="primary">＋ 添加随机种子</button>
        <button id="btnRandomTable" title="点位 / 建筑权重 / 夜王 / 缩圈">随机表</button>
      </div>
      <div class="muted" style="margin-top:6px">
        点位筛选、建筑权重（含变体）、夜王、缩圈都在「随机表」里设置。
      </div>
    </div>
    <div class="card">
      <h3>高级：改组合</h3>
      <div class="row"><label>夜王</label><select class="num" id="cBoss">
        ${(T.bosses || []).map(b => `<option value="${b.id}" ${b.id === s.boss ? 'selected' : ''}>${b.id} · ${b.name}</option>`).join('')}
      </select></div>
      <div class="row"><label>地图类型</label><select class="num" id="cRare">
        ${(T.rares || []).map(r => `<option value="${r.id}" ${r.id === s.rare ? 'selected' : ''}>${r.id} · ${r.name}</option>`).join('')}
      </select></div>
      <div class="btns"><button id="btnCombo" class="danger">改组合（会改所有 flag 行）</button></div>
    </div>`;

  $('btnSaveFields').onclick = () => apply('set_fields', {
    sid: s.sid, fields: { weight: +$('fWeight').value, chaosMatchWeight: +$('fChaos').value }
  });
  $('btnRecalc').onclick = () => apply('recompute_pools', { sid: s.sid });
  $('btnDelSet').onclick = () => {
    if (!confirm(`确定删除 set ${s.sid}（连带 ${s.count} 个种子）？`)) return;
    apply('delete_set', { sid: s.sid });
  };
  $('btnInsert').onclick = () => {
    const src = +$('fSrc').value || null;
    apply('insert_pattern', { set: s.sid, source: src });
  };
  $('btnRandom').onclick = () => {
    const n = Math.max(1, Math.min(50, +$('rndCount').value || 1));
    apply('random_batch', { set: s.sid, count: n });
  };
  $('btnRandomTable').onclick = openRandomTable;
  $('btnCombo').onclick = () => {
    if (!confirm('改组合会把 set 里所有 flag 行的 targetBoss/rareMap/地图类型旗标都改掉，继续？')) return;
    apply('change_combo', { sid: s.sid, boss: +$('cBoss').value, rare: +$('cRare').value });
  };
}

function areaText(id) {
  const a = (T.playareas || []).find(x => x.id === id);
  if (!a) return id ? `${id}（不在候选里）` : '（未设置）';
  const nm = a.name && String(a.name) !== String(a.id) ? ` ${a.name}` : '';
  return `${a.id}${nm}`;
}
function areaItems(cur) {
  return (T.playareas || []).map(a => {
    const nm = a.name && String(a.name) !== String(a.id) ? ` ${a.name}` : '';
    return `<div class="aitem ${a.id === cur ? 'on' : ''}" data-id="${a.id}">${a.id}${nm}</div>`;
  }).join('');
}

/* 夜晚 BOSS：bossId 下拉 + 手输；已收录的自动带出 bossModifier */
function bossText(id) {
  if (!id) return '（未设置）';
  const b = (T.nightBosses || []).find(x => x.id === id);
  if (!b) return `${id}（未收录）`;
  return `${b.id}${b.name ? ' ' + b.name : ''} · mod ${b.modifier}`;
}
function bossItems(cur) {
  return (T.nightBosses || []).map(b =>
    `<div class="aitem ${b.id === cur ? 'on' : ''}" data-id="${b.id}" data-mod="${b.modifier}">${b.id}${b.name ? ' ' + b.name : ''} · mod ${b.modifier}</div>`
  ).join('');
}

function grpOf(aid) {
  const gs = (T && T.groups) || {};
  for (const k in gs) {
    const g = gs[k];
    if ((g.members || []).includes(aid)) return g;
  }
  return null;
}

function renderPattern(pi, s) {
  const spots = pi.spotView || [];
  const rows = (pi.spots || []).map((r, i) => {
    const v = spots[i] || {};
    const attr = v.attrIcon
      ? `<img class="attrmini" src="/pin/${v.attrIcon}.png" title="${v.attrName || v.attrIcon}">` : '';
    const g = grpOf(r.attachId);
    const gtag = g ? `<span class="grp" title="成组点：改这个会按配套表带动同组 ${g.members.join(' / ')}">${g.name}</span>` : '';
    return `<tr data-row="${r.row}">
      <td><a class="link" data-tile-row="${r.row}" data-attach="${r.attachId}" title="换建筑（点我）${v.tileName ? ' · ' + v.tileName : ''}">${r.tile}</a></td>
      <td>${r.attachId}${gtag}</td><td>${r.mapIndex}</td>
      <td>${attr}<input class="num tiny" type="number" min="0" value="${r.variationId}"
             data-var-row="${r.row}" title="variationId（改完回车/失焦生效）${v.variantName ? ' · ' + v.variantName : (v.attrName ? ' · ' + v.attrName : '')}"></td>
      <td class="x" data-del="${r.row}" title="删掉这个地点">✕</td></tr>`;
  }).join('');
  const flags = (pi.flags || []).map(f =>
    `<tr><td>${f.modifierSet}</td><td>${f.eventFlag}</td><td>${f.modifier}</td>
      <td class="muted">${f.name || ''}</td></tr>`).join('');
  const pa = pi.playarea || {};
  $('inspector').innerHTML = `
    <div class="card">
      <h3>种子 pid ${pi.pid}</h3>
      <div class="kv">
        <b>所在 set</b><span>${pi.set}</span>
        <b>组合</b><span>${pi.combo ? `${(T.bosses.find(b => b.id === pi.combo[0]) || {}).name || pi.combo[0]} · ${rarName(pi.combo[1])}` : '—'}</span>
        <b>地点数</b><span>${spots.length}</span>
        <b>夜晚 BOSS</b><span>${pi.night[0]} / ${pi.night[1]}</span>
      </div>
      <div class="btns">
        <button id="btnBackSet">回到 set</button>
        <button id="btnDelPid" class="danger">删除这个种子</button>
      </div>
    </div>
    <div class="card">
      <h3>缩圈 / 夜晚 BOSS（playarea）</h3>
      <div class="row"><label>1缩</label>
        <div class="drop" data-key="pa1">
          <button type="button" class="dbtn">${areaText(pa.playArea1)}</button>
          <div class="dlist" hidden>${areaItems(pa.playArea1)}</div>
        </div></div>
      <div class="row"><label>2缩</label>
        <div class="drop" data-key="pa2">
          <button type="button" class="dbtn">${areaText(pa.playArea2)}</button>
          <div class="dlist" hidden>${areaItems(pa.playArea2)}</div>
        </div></div>
      <div class="row"><label>1夜</label>
        <div class="drop" data-key="nb1" data-side="1">
          <button type="button" class="dbtn">${bossText(pa.bossId1)}</button>
          <div class="dlist" hidden>${bossItems(pa.bossId1)}</div>
        </div>
        <input class="num tiny" id="b1" type="number" value="${pa.bossId1 ?? 0}" title="手输 bossId1（未收录的 BOSS）">
      </div>
      <div class="row"><label>1夜 mod</label><input class="num" id="m1" type="number" value="${pa.bossModifier1 ?? 0}" title="选中已收录 BOSS 会自动填"></div>
      <div class="row"><label>2夜</label>
        <div class="drop" data-key="nb2" data-side="2">
          <button type="button" class="dbtn">${bossText(pa.bossId2)}</button>
          <div class="dlist" hidden>${bossItems(pa.bossId2)}</div>
        </div>
        <input class="num tiny" id="b2" type="number" value="${pa.bossId2 ?? 0}" title="手输 bossId2（未收录的 BOSS）">
      </div>
      <div class="row"><label>2夜 mod</label><input class="num" id="m2" type="number" value="${pa.bossModifier2 ?? 0}" title="选中已收录 BOSS 会自动填"></div>
      <div class="btns"><button id="btnSavePa">保存夜王</button></div>
    </div>
    <div class="card">
      <h3>地点（${spots.length}）</h3>
      <div style="max-height:240px;overflow:auto">
        <table class="spots"><tr><th>tile</th><th>attach</th><th>idx</th><th>变体</th><th></th></tr>${rows}</table>
      </div>
      <div class="muted" style="margin-top:6px">点地图上的圈 → 下面选建筑，就能加地点</div>
    </div>
    <div class="card">
      <h3>事件 / flag 行（只读）</h3>
      <div style="max-height:200px;overflow:auto">
        <table class="flags"><tr><th>set</th><th>flag</th><th>mod</th><th>名字</th></tr>${flags}</table>
      </div>
    </div>`;

  $('btnBackSet').onclick = async () => {
    const r = await api('/api3/select', { pid: null });
    T = r; render();
  };
  $('btnDelPid').onclick = () => {
    if (!confirm(`删除 pid ${pi.pid}？后面的种子会顺移。`)) return;
    apply('delete_pattern', { pid: pi.pid });
  };
  $('btnSavePa').onclick = () => apply('playarea', { pid: pi.pid, fields: {
    bossId1: +$('b1').value, bossModifier1: +$('m1').value,
    bossId2: +$('b2').value, bossModifier2: +$('m2').value,
  } });
  // 1缩/2缩：悬停看位置，点一下生效；1夜/2夜：选已收录的 BOSS 自动带出 modifier
  document.querySelectorAll('#inspector .drop').forEach(dp => {
    const key = dp.dataset.key;
    const side = dp.dataset.side;
    const btn = dp.querySelector('.dbtn');
    const list = dp.querySelector('.dlist');
    btn.onclick = ev => { ev.stopPropagation(); list.hidden = !list.hidden; };
    list.querySelectorAll('.aitem').forEach(it => {
      if (key === 'pa1' || key === 'pa2') {
        it.onmouseenter = () => { PREVIEW = { key, id: +it.dataset.id }; draw(); };
        it.onclick = ev => {
          ev.stopPropagation();
          list.hidden = true;
          PREVIEW = null;
          apply('playarea', { pid: pi.pid, fields: key === 'pa1'
            ? { playArea1: +it.dataset.id } : { playArea2: +it.dataset.id } });
        };
      } else {
        it.onclick = ev => {
          ev.stopPropagation();
          list.hidden = true;
          const bid = +it.dataset.id;
          const mod = +it.dataset.mod;
          $('b' + side).value = bid;
          $('m' + side).value = mod;
          apply('playarea', { pid: pi.pid, fields: side === '1'
            ? { bossId1: bid, bossModifier1: mod }
            : { bossId2: bid, bossModifier2: mod } });
        };
      }
    });
    list.onmouseleave = () => { PREVIEW = null; draw(); };
  });
  // 手输 bossId（未收录的 BOSS）：回车/失焦生效，不动 modifier
  for (const side of ['1', '2']) {
    const inp = $('b' + side);
    if (!inp) continue;
    inp.onchange = () => {
      const v = +inp.value || 0;
      apply('playarea', { pid: pi.pid, fields: side === '1' ? { bossId1: v } : { bossId2: v } });
    };
  }
  $('inspector').querySelectorAll('.x').forEach(el => {
    el.onclick = () => {
      if (!confirm('删掉这个地点？')) return;
      apply('spot_remove', { pid: pi.pid, row: +el.dataset.del });
    };
  });
  // 换建筑：点 tile 编号
  $('inspector').querySelectorAll('a.link').forEach(el => {
    el.onclick = () => openTilePicker(+el.dataset.tileRow, +el.dataset.attach, pi.pid);
  });
  // 改变体：改动就生效
  $('inspector').querySelectorAll('input[data-var-row]').forEach(inp => {
    inp.onchange = () => apply('spot_field', {
      pid: pi.pid, row: +inp.dataset.varRow, field: 'variationId', value: +inp.value,
    });
  });
}

/* 换建筑的选择条（跟"加地点"共用底部） */
async function openTilePicker(rowId, attachId, pid) {
  const r = await api('/api3/attach?id=' + attachId);
  if (!r.ok) { toast(r.error || '读不到这个建筑位', true); return; }
  const tiles = (r.candidate.tileInfo || []).map(t => ({
    tile: t.tile, icon: t.icon, attrIcon: t.attrIcon, attrName: t.attrName,
    label: t.name || t.realName || t.define || t.tile,
  }));
  PICK = { kind: 'tile', rowId, attachId, pid, tiles };
  const box = $('picker');
  box.hidden = false;
  box.innerHTML =
    `<div class="muted" style="width:100%;margin-bottom:4px">
       换建筑（attach ${attachId}）：点图标替换；也可以直接输入 tile 编号（右下角小图标是属性）</div>` +
    tiles.map((t, i) => `<div class="pick" data-i="${i}" title="${t.label}">
        ${t.icon ? `<img src="/pin/${t.icon}.png">` : `<span class="noicon">${t.tile}</span>`}
        ${t.attrIcon ? `<img class="attr" src="/pin/${t.attrIcon}.png" title="${t.attrName || ''}">` : ''}
      </div>`).join('') +
    `<div class="pick" id="tileManual"><input class="num tiny" style="width:48px" placeholder="tile"></div>`;
  box.querySelectorAll('.pick[data-i]').forEach(el => {
    el.onclick = async () => {
      const t = tiles[+el.dataset.i];
      const res = await apply('spot_tile', { pid, row: rowId, tile: t.tile });
      if (res.ok) closePicker();
    };
  });
  const inp = document.querySelector('#tileManual input');
  if (inp) {
    inp.onkeydown = async ev => {
      if (ev.key !== 'Enter') return;
      const v = parseInt(inp.value, 10);
      if (!v) return;
      const res = await apply('spot_tile', { pid, row: rowId, tile: v });
      if (res.ok) closePicker();
    };
  }
}

/* ---------------- 操作 ---------------- */
async function apply(op, args) {
  const res = await api('/api3/apply', { op, args });
  if (!res.ok) {
    toast(res.error || '执行失败', true);
    console.warn(res.plan);
    return res;
  }
  T = res.tree;
  render();
  const chg = Object.entries(res.changes || {}).map(([k, v]) => `${k}:${v}`).join(' ');
  toast('完成 ' + (chg ? '（' + chg + ' 行）' : ''));
  return res;
}

/* ---------------- 新建 set ---------------- */
$('btnNewSet').onclick = () => {
  if (!T || !T.ok) { toast('先打开 bin'); return; }
  const box = $('picker');
  PICK = { kind: 'newset' };
  box.hidden = false;
  box.innerHTML = `
    <div style="width:100%;display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <span class="muted">新建 set：</span>
      <select class="num" id="nsBoss" style="flex:0 0 200px">
        ${(T.bosses || []).map(b => `<option value="${b.id}">${b.id} · ${b.name}</option>`).join('')}
      </select>
      <select class="num" id="nsRare" style="flex:0 0 140px">
        ${(T.rares || []).map(r => `<option value="${r.id}">${r.id} · ${r.name}</option>`).join('')}
      </select>
      <input class="num" id="nsName" placeholder="名字（可空）" style="flex:1;min-width:160px">
      <label class="muted" style="white-space:nowrap"><input type="checkbox" id="nsPools" checked> 池子照抄官方</label>
      <button id="nsGo">创建</button>
      <button id="nsCancel">取消</button>
    </div>`;
  $('nsCancel').onclick = closePicker;
  $('nsGo').onclick = async () => {
    const res = await apply('create_set', {
      boss: +$('nsBoss').value, rare: +$('nsRare').value,
      name: $('nsName').value.trim() || null,
      copy_pools: $('nsPools').checked,
    });
    if (res.ok) closePicker();
  };
};

/* ---------------- 随机表 ---------------- */
/* 表1：点位（勾选=参与随机）+ 建筑（全局权重，0=不参与）
   表2：夜晚 BOSS / 缩圈（勾选） */
let RPOOL = null, RSEL = null, RTAB1 = 'calibrated';
const REXPAND = new Set();

async function openRandomTable() {
  const r = await api('/api3/random');
  if (!r || !r.ok) { toast((r && r.error) || '读不到随机表', true); return; }
  RPOOL = r.pool || {};
  const s = r.sel || {};
  const tileW = {};
  (RPOOL.tiles || []).forEach(t => { tileW[t.id] = 10; });
  if (s.tiles) for (const k in s.tiles) tileW[+k] = +s.tiles[k];
  const varW = {};
  (RPOOL.tiles || []).forEach(t => {
    varW[t.id] = {};
    (t.variants || []).forEach(v => { varW[t.id][v.v] = 10; });
  });
  if (s.variants) for (const k in s.variants) {
    const tid = +k;
    varW[tid] = varW[tid] || {};
    for (const v in s.variants[k]) varW[tid][+v] = +s.variants[k][v];
  }
  RSEL = {
    attach: (s.attach && s.attach.length) ? s.attach.slice() : [...(RPOOL.calibrated || [])],
    playarea: (s.playarea && s.playarea.length) ? s.playarea.slice() : [...(RPOOL.playarea || [])],
    night: (s.night && s.night.length) ? s.night.slice() : [...(RPOOL.night || [])],
    tiles: tileW,
    variants: varW,
    lock_jail: s.lock_jail !== false,
  };
  REXPAND.clear();
  document.getElementById('randomModal').hidden = false;
  RTAB1 = 'calibrated';
  document.querySelectorAll('#randomModal .ptab[data-pt]')
    .forEach(b => b.classList.toggle('on', b.dataset.pt === RTAB1));
  showRPage('t1');
  renderRandom();
}

function showRPage(page) {
  $('rmPage1').hidden = page !== 't1';
  $('rmPage2').hidden = page !== 't2';
  document.querySelectorAll('#randomModal .ptab[data-page]')
    .forEach(b => b.classList.toggle('on', b.dataset.page === page));
}

function renderRandom() {
  /* ---- 点位 ---- */
  const ptIds = RPOOL[RTAB1] || [];
  $('rmPts').innerHTML = ptIds.map(id => {
    const a = (T && T.anchors || []).find(x => x.attachId === id);
    const on = RSEL.attach.includes(id);
    return `<label class="rm-item"><input type="checkbox" data-pt-id="${id}" ${on ? 'checked' : ''}>`
      + `<span class="rid">${id}</span><span class="rnm">${escH(a ? (a.attachName || '') : '')}</span></label>`;
  }).join('') || '<div class="rm-sum">这一类没有点位</div>';
  $('rmPts').querySelectorAll('input[data-pt-id]').forEach(el => {
    el.onchange = () => {
      const id = +el.dataset.ptId;
      const i = RSEL.attach.indexOf(id);
      if (i >= 0) RSEL.attach.splice(i, 1); else RSEL.attach.push(id);
      renderRandom();
    };
  });
  document.querySelectorAll('#randomModal .ptab[data-pt]').forEach(b => {
    const t = b.dataset.pt;
    const all = RPOOL[t] || [];
    const n = all.filter(i => RSEL.attach.includes(i)).length;
    b.textContent = `${t === 'calibrated' ? '已校准' : '未校准'} ${n}/${all.length}`;
  });

  /* ---- 建筑（权重 + 变体权重）---- */
  const rows = (RPOOL.tiles || []).map(t => {
    const w = RSEL.tiles[t.id] != null ? RSEL.tiles[t.id] : 10;
    const vs = t.variants || [];
    const open = REXPAND.has(t.id);
    const vrows = (open && vs.length) ? vs.map(v => {
      const vw = (RSEL.variants[t.id] || {})[v.v] != null ? RSEL.variants[t.id][v.v] : 10;
      return `<div class="rm-var"><span class="rexp-sp"></span><span class="rid">变体 ${v.v}</span>`
        + `<span class="rnm">${escH(v.name || '')}</span>`
        + `<input class="rmw" type="number" min="0" data-vw="${t.id}" data-v="${v.v}" value="${vw}"></div>`;
    }).join('') : '';
    return `<div class="rm-tile ${w > 0 ? '' : 'off'}">`
      + `<span class="rm-exp" data-ex="${t.id}">${vs.length ? (open ? '▾' : '▸') : '·'}</span>`
      + `<span class="rid">${t.id}</span><span class="rnm">${escH(t.name || '（无名字）')}</span>`
      + `<input class="rmw" type="number" min="0" data-tw="${t.id}" value="${w}"></div>${vrows}`;
  }).join('');
  $('rmTiles').innerHTML = rows || '<div class="rm-sum">没有建筑</div>';
  $('rmTiles').querySelectorAll('input[data-tw]').forEach(el => {
    el.onchange = () => { RSEL.tiles[+el.dataset.tw] = Math.max(0, +el.value || 0); renderRandom(); };
  });
  $('rmTiles').querySelectorAll('input[data-vw]').forEach(el => {
    el.onchange = () => {
      const t = +el.dataset.vw;
      RSEL.variants[t] = RSEL.variants[t] || {};
      RSEL.variants[t][+el.dataset.v] = Math.max(0, +el.value || 0);
    };
  });
  $('rmTiles').querySelectorAll('.rm-exp').forEach(el => {
    el.onclick = () => {
      const t = +el.dataset.ex;
      if (REXPAND.has(t)) REXPAND.delete(t); else REXPAND.add(t);
      renderRandom();
    };
  });
  const onTiles = (RPOOL.tiles || []).filter(t => (RSEL.tiles[t.id] || 0) > 0).length;
  $('rmTileInfo').textContent = `${onTiles} / ${(RPOOL.tiles || []).length} 参与`;

  /* ---- 夜王 / 缩圈 ---- */
  $('rmNight').innerHTML = (RPOOL.night || []).map(id => {
    const b = (T && (T.nightBosses || []).find(x => x.id === id)) || null;
    const on = RSEL.night.includes(id);
    return `<label class="rm-item"><input type="checkbox" data-ng="${id}" ${on ? 'checked' : ''}>`
      + `<span class="rid">${id}</span><span class="rnm">${escH(b ? (b.name || '') : '')}</span></label>`;
  }).join('');
  $('rmNight').querySelectorAll('input[data-ng]').forEach(el => {
    el.onchange = () => {
      const id = +el.dataset.ng;
      const i = RSEL.night.indexOf(id);
      if (i >= 0) RSEL.night.splice(i, 1); else RSEL.night.push(id);
      renderRandom();
    };
  });
  $('rmNightInfo').textContent = ` ${RSEL.night.length} / ${(RPOOL.night || []).length}`;
  $('rmAreas').innerHTML = (RPOOL.playarea || []).map(id => {
    const a = (T && T.playareas || []).find(x => x.id === id);
    const on = RSEL.playarea.includes(id);
    return `<label class="rm-item"><input type="checkbox" data-ag="${id}" ${on ? 'checked' : ''}>`
      + `<span class="rid">${id}</span><span class="rnm">${escH(a ? (a.name || '') : '')}</span></label>`;
  }).join('');
  $('rmAreas').querySelectorAll('input[data-ag]').forEach(el => {
    el.onchange = () => {
      const id = +el.dataset.ag;
      const i = RSEL.playarea.indexOf(id);
      if (i >= 0) RSEL.playarea.splice(i, 1); else RSEL.playarea.push(id);
      renderRandom();
    };
  });
  $('rmAreaInfo').textContent = ` ${RSEL.playarea.length} / ${(RPOOL.playarea || []).length}`;
  if ($('rmLockJail')) $('rmLockJail').checked = RSEL.lock_jail !== false;
}

if ($('rmLockJail')) $('rmLockJail').onchange = () => { RSEL.lock_jail = $('rmLockJail').checked; };
$('rmClose').onclick = () => { document.getElementById('randomModal').hidden = true; };
document.querySelectorAll('#randomModal .ptab[data-page]').forEach(b => {
  b.onclick = () => showRPage(b.dataset.page);
});
document.querySelectorAll('#randomModal .ptab[data-pt]').forEach(b => {
  b.onclick = () => {
    RTAB1 = b.dataset.pt;
    document.querySelectorAll('#randomModal .ptab[data-pt]')
      .forEach(x => x.classList.toggle('on', x === b));
    renderRandom();
  };
});
$('rmSave').onclick = async () => {
  const r = await api('/api3/random', {
    attach: RSEL.attach, playarea: RSEL.playarea, night: RSEL.night,
    tiles: RSEL.tiles, variants: RSEL.variants, lock_jail: RSEL.lock_jail !== false,
  });
  if (!r || !r.ok) { toast((r && r.error) || '保存失败', true); return; }
  toast(`随机表已保存（建筑权重 ${Object.keys(RSEL.tiles).length} 项）`);
};
// 开发者用：导出随机日志（不显眼的小入口）
if ($('rmLog')) $('rmLog').onclick = async () => {
  const r = await api('/api3/randomlog');
  if (!r || !r.ok) { toast((r && r.error) || '导出失败', true); return; }
  toast(`已导出 ${r.count} 条\n${r.path}`);
};

/* ---------------- 顶部 ---------------- */
$('btnOpen').onclick = async () => {
  const r = await api('/api3/open', { path: $('binPath').value });
  if (r.needChoose) { toast('这个文件夹里有多个 bin，请填具体的文件路径', true); return; }
  if (!r.ok) { toast(r.error || '打开失败', true); return; }
  T = r;
  $('binPath').value = r.bin;
  render();
  toast('已打开（改动都在副本上，点保存才写 bin）');
};

$('btnSave').onclick = async () => {
  if (!T || !T.ok) return;
  if (!confirm('保存会封包 → 解包对账 → 备份原 bin → 覆盖。继续？')) return;
  const r = await api('/api3/save', {});
  if (!r.ok) { toast(r.error || '保存失败', true); return; }
  toast('已保存\n' + (r.checks || []).map(([n, ok]) => (ok ? '✓ ' : '✗ ') + n).join('\n'));
  const t = await api('/api3/tree');
  T = t; render();
};

$('bossFilter').onchange = () => renderTree();

/* ---------------- 启动 ---------------- */
(async () => {
  fit();
  const r = await api('/api3/tree');
  if (r && r.ok) { T = r; $('binPath').value = r.bin; render(); }
  else { render(); }
  // 调试：?names=1 打名称表，?names=boss 直接到夜晚 BOSS 页
  const nm = new URLSearchParams(location.search).get('names');
  if (nm) openNames().then(() => { if (nm === 'boss') setNamesTab('boss'); });
  // 调试：?random=1 直接打开随机表
  if (new URLSearchParams(location.search).get('random')) openRandomTable();
})();
