const $ = id => document.getElementById(id);
const cv = $('map');
const ctx = cv.getContext('2d');
const hcv = $('hl');
const hctx = hcv.getContext('2d');

const HIT_R = 30;          // 命中半径（内部坐标）
const COLOR = {
  hover: '#6fd3ff',
  sel: '#4da3ff',
  pulse: '#8fe3ff',
};

let S = {
  bin: null, map: null, draft: null, template: null, issues: [],
  img: null, cell: null, buildings: null, bpick: null, hoverB: null,
  hits: [], hoverPoint: null, selPoint: null, pulse: null, cellGrid: null,
  varSel: {},          // smallBaseMapId → 选中的 variationId（m04153 的属性变体）
  manualVar: {},       // m06850：手输过的 variationId → 查回来的档位信息
  custom: {},          // m06316：手输过的 smallBaseMapId → 建筑信息
  dragFrom: null,      // m06840：拖动排序的起点 / 落点
  dropAt: null,
};

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

function sizeTag(s) {
  if (s === '小') return '<span class="tag small">小</span>';
  if (s === '大') return '<span class="tag big">大</span>';
  if (!s) return '';
  return `<span class="tag unk">${s}</span>`;
}

/* ---------- 地图底图 ---------- */
let mapRev = 0;
function loadMap() {
  const im = new Image();
  im.onload = () => { S.img = im; draw(); };
  im.src = '/api/map.png?rev=' + (mapRev++) + '&t=' + Date.now();
}
loadMap();

function toPx(world, sp) {
  if (sp && sp.px != null) return [sp.px, sp.py];
  if (!S.map || !world) return [0, 0];
  return [world[0] - S.map.ox, S.map.oz - world[1]];
}

function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (S.img) ctx.drawImage(S.img, 0, 0, cv.width, cv.height);
}


/* ---------- m06466：地图切换（只换底图） ---------- */
function renderMaps(st) {
  const sel = $('mapSel');
  if (!st.maps) return;
  if (sel.dataset.filled !== st.maps.map(m => m.id).join(',')) {
    sel.innerHTML = st.maps.map(m =>
      `<option value="${m.id}">${m.name}</option>`).join('');
    sel.dataset.filled = st.maps.map(m => m.id).join(',');
  }
  if (st.mapId) sel.value = st.mapId;
}

$('mapSel').onchange = async () => {
  const r = await api('/api/map', { id: $('mapSel').value });
  if (!r.ok) { alert(r.error || '切换失败'); return; }
  if (r.map) S.map = r.map;
  // m06769：先清掉上一张图的点，避免「切图后旧点还留在画面上」
  S.extra = [];
  S.template = [];
  S.spots = [];
  S.selPoint = null;
  S.hoverPoint = null;
  S.pick = null;
  S.hits = [];
  draw();
  drawOverlay();
  const st = await api('/api/state');
  applyState(st);
};

/* ---------- 命中层 ---------- */
// 与 app/core/render.py 的 _place 保持一致：同 10px 网格内成组 → 绕圈错开
// （756 楼顶 / 757 楼底 坐标完全一样，不错开就永远点不到第二个）
const BOSS_ICONS = new Set([42015, 42016, 42019, 42027, 42034, 42035]);

function placeSpots(list) {
  const pts = list.map((sp, i) => {
    const [x, y] = toPx(sp.world, sp);   // 位置以服务器算好的 px/py 为准
    return { x, y, sp, i };
  });
  const buckets = new Map();
  pts.forEach((p, k) => {
    const key = Math.round(p.x / 10) + ',' + Math.round(p.y / 10);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(k);
  });
  buckets.forEach(grp => {
    if (grp.length < 2) return;
    if (pts[grp[0]].sp.px != null) return;   // 服务器已经摆好位置，前端不再挪
    grp.sort((a, b) => (BOSS_ICONS.has(pts[a].sp.icon) ? 1 : 0) -
                       (BOSS_ICONS.has(pts[b].sp.icon) ? 1 : 0));
    const r = 40 + 10 * (grp.length - 2);
    grp.forEach((k, n) => {
      const ang = -Math.PI / 2 + 2 * Math.PI * n / grp.length;
      pts[k].x += r * Math.cos(ang);
      pts[k].y += r * Math.sin(ang);
    });
  });
  return pts;
}

function rebuildHits() {
  const out = [];
  // m05283：模板点不再画、也不再参与命中（以前会把没画出来的「Field Boss」当成可点）。
  placeSpots(S.draft?.spots || []).forEach(p =>
    out.push({ kind: 'draft', sp: p.sp, i: p.i, x: p.x, y: p.y }));
  // 47 个校准锚点：全部可点（在那里放建筑）
  for (const sp of (S.extra || [])) {
    const [x, y] = toPx(sp.world, sp);
    out.push({ kind: 'extra', sp, x, y });
  }
  S.hits = out;
}

/* ---------- 1缩 / 2缩 的地图标记 ---------- */
function areaWorld(a) {
  if (!a) return null;
  return [a.grid[0] * 256 + 128 + a.pos[0], a.grid[1] * 256 + 128 + a.pos[1]];
}

function drawAreaMarkers() {
  const pa = S.playarea;
  if (!pa || !S.map) return;
  const byId = {};
  for (const a of (pa.areas || [])) byId[a.id] = a;
  const cur = pa.cur || {};
  const hov = S.areaHover || {};

  const one = (key, label, color) => {
    const hovering = hov.key === key;
    const id = hovering ? (hov.id ?? cur[key]) : cur[key];
    const a = byId[id];
    if (!a) return;
    const w = areaWorld(a);
    if (!w) return;
    const [x, y] = toPx(w);
    hctx.save();
    hctx.beginPath(); hctx.arc(x, y, 17, 0, Math.PI * 2);
    hctx.fillStyle = 'rgba(12,14,18,.82)'; hctx.fill();
    hctx.lineWidth = hovering ? 2 : 3;
    if (hovering) hctx.setLineDash([5, 4]);
    hctx.strokeStyle = color;
    hctx.stroke();
    hctx.setLineDash([]);
    hctx.fillStyle = color;
    hctx.font = 'bold 17px "Microsoft YaHei", sans-serif';
    hctx.textAlign = 'center'; hctx.textBaseline = 'middle';
    hctx.fillText(label, x, y + 1);
    // 外圈扩散（固定时）
    if (!hovering) {
      const t = (performance.now() / 1400) % 1;
      hctx.beginPath(); hctx.arc(x, y, 17 + t * 14, 0, Math.PI * 2);
      hctx.strokeStyle = color.replace('1)', String(0.5 * (1 - t)) + ')');
      hctx.lineWidth = 2; hctx.stroke();
    }
    hctx.restore();
  };

  one('pa1', '1', 'rgba(255,196,84,1)');
  one('pa2', '2', 'rgba(120,200,255,1)');
}

function hitTest(x, y) {
  let best = null, bd = HIT_R;
  for (const h of S.hits) {
    const d = Math.hypot(h.x - x, h.y - y);
    // 草稿优先于模板（同一点上两者重合时）
    if (d < bd || (d <= bd + 0.5 && h.kind === 'draft')) { best = h; bd = d; }
  }
  return best;
}

function evPos(ev) {
  const r = cv.getBoundingClientRect();
  return [(ev.clientX - r.left) * cv.width / r.width,
          (ev.clientY - r.top) * cv.height / r.height];
}

/* ---------- 交互层绘制 ---------- */
let anim = 0;
function drawOverlay() {
  hctx.clearRect(0, 0, hcv.width, hcv.height);
  const now = performance.now();

  // 没被这个种子用到的 attach 点：灰色空心小圈（m04640）
  hctx.save();
  for (const sp of (S.extra || [])) {
    const [x, y] = toPx(sp.world, sp);
    const col = sp.attachSize === '大' ? '77,163,255'
      : (sp.attachSize === '小' ? '65,209,138' : '190,190,200');
    hctx.strokeStyle = 'rgba(20,22,26,.8)';
    hctx.lineWidth = 4;
    hctx.beginPath(); hctx.arc(x, y, 8, 0, Math.PI * 2); hctx.stroke();
    hctx.strokeStyle = 'rgba(' + col + ',.95)';
    hctx.lineWidth = 1.8;
    hctx.beginPath(); hctx.arc(x, y, 8, 0, Math.PI * 2); hctx.stroke();
    hctx.fillStyle = 'rgba(' + col + ',.9)';
    hctx.beginPath(); hctx.arc(x, y, 2, 0, Math.PI * 2); hctx.fill();
  }
  hctx.restore();

  // 1缩 / 2缩 的地图标记（主人 m05770）：悬停临时显示，选完固定
  drawAreaMarkers();

  // 悬停
  const hp = S.hoverPoint;
  if (hp && hp !== S.selPoint) {
    const { x, y } = hp;
    hctx.save();
    hctx.strokeStyle = COLOR.hover;
    hctx.lineWidth = 3;
    hctx.setLineDash([6, 5]);
    hctx.globalAlpha = 0.95;
    hctx.beginPath();
    hctx.arc(x, y, 30, 0, Math.PI * 2);
    hctx.stroke();
    hctx.restore();
  }

  // 选中
  const sp = S.selPoint;
  if (sp) {
    const { x, y } = sp;
    hctx.save();
    hctx.shadowColor = COLOR.sel;
    hctx.shadowBlur = 14;
    hctx.strokeStyle = COLOR.sel;
    hctx.lineWidth = 4;
    hctx.beginPath();
    hctx.arc(x, y, 33, 0, Math.PI * 2);
    hctx.stroke();
    hctx.restore();
  }

  // 放置动画：一次扩散环
  if (S.pulse && now - S.pulse.t0 < 420) {
    const k = (now - S.pulse.t0) / 420;
    hctx.save();
    hctx.strokeStyle = COLOR.pulse;
    hctx.globalAlpha = 1 - k;
    hctx.lineWidth = 4 * (1 - k) + 1;
    hctx.beginPath();
    hctx.arc(S.pulse.x, S.pulse.y, 30 + 34 * k, 0, Math.PI * 2);
    hctx.stroke();
    hctx.restore();
    requestAnimationFrame(drawOverlay);
  } else if (S.pulse) {
    S.pulse = null;
  }

  // 悬停提示条
  if (hp) {
    const label = pointLabel(hp);
    hctx.save();
    hctx.font = 'bold 20px "Microsoft YaHei", sans-serif';
    const w = hctx.measureText(label).width;
    const bx = Math.min(Math.max(8, hp.x + 26), hcv.width - w - 26);
    const by = Math.max(12, hp.y - 44);
    hctx.fillStyle = 'rgba(14,16,20,.92)';
    hctx.strokeStyle = COLOR.hover;
    hctx.lineWidth = 2;
    roundRect(hctx, bx, by, w + 22, 34, 8);
    hctx.fill();
    hctx.stroke();
    hctx.fillStyle = '#eaf6ff';
    hctx.fillText(label, bx + 11, by + 24);
    hctx.restore();
  }
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}

function pointLabel(h) {
  const s = h.sp;
  // 模板点只是地块参照，不显示「建筑业」（m02451：我啥都没放，别写遗迹/城镇）
  const nm = (h.kind === 'template')
    ? (s.attachName || ('#' + s.attachId))
    : (s.realName || s.attachName || ('#' + s.attachId));
  return (h.kind === 'draft' ? '✓ ' : '') + nm;
}

/* ---------- 鼠标事件 ---------- */
cv.addEventListener('mousemove', ev => {
  if (!S.map) return;
  const [x, y] = evPos(ev);
  const h = hitTest(x, y);
  if (h !== S.hoverPoint) {
    S.hoverPoint = h;
    cv.style.cursor = h ? 'pointer' : 'crosshair';
    drawOverlay();
  }
});

cv.addEventListener('mouseleave', () => {
  if (S.hoverPoint) { S.hoverPoint = null; drawOverlay(); }
});

cv.addEventListener('click', async ev => {
  if (!S.map) return;
  const [x, y] = evPos(ev);
  const h = hitTest(x, y);
  if (h) { await selectPoint(h); return; }
  // m04392：只有红圈（模板可放点）/ 已有的点才能点，空白处不再响应
  S.selPoint = null;
  S.hoverB = null;
  S.buildings = [];
  drawOverlay();
  $('pickRow').hidden = true;
});

async function selectPoint(h) {
  S.selPoint = h;
  const s = h.sp;
  // m06316：换锚点就别把上一个点手输的建筑带过来
  S.custom = {};
  S.pickTile = null;
  S.pickIndex = 0;

  // m04640：官方种子没用到的 attach 点 → 单独问 /api/attach，按尺寸给全量池
  if (h.kind === 'extra') {
    const r = await api(`/api/attach?id=${s.attachId}`);
    S.cell = r.ok && r.candidate ? [r.candidate] : [];
    S.cellGrid = s.grid;
    S.bpick = null; S.hoverB = null;
    if (!S.cell.length) { renderPickerEmpty(s.grid[0], s.grid[1], s); return; }
    renderPicker(s.grid[0], s.grid[1]);
    drawOverlay();
    return;
  }

  // 格号直接用数据里的 grid（m03060）：world = 格号*256 + 128 + pos，
  // 而 pos 可能是 -167 这种小于 -128 的值，从 world 反推会掉到上一格（759 就栽在这）。
  const cellGx = s.grid ? s.grid[0] : Math.round((s.world[0] - 128) / S.map.tile);
  const cellGz = s.grid ? s.grid[1] : Math.round((s.world[1] - 128) / S.map.tile);
  const res = await api(`/api/cell?gx=${cellGx}&gz=${cellGz}`);
  const all = res.ok ? res.candidates : [];
  S.cell = all.filter(c => c.attachId === s.attachId);
  S.cellGrid = [cellGx, cellGz];
  S.bpick = null; S.hoverB = null;
  if (!S.cell.length) {
    // 这个点没有可放选项（比如野外BOSS槽位） → 只显示信息
    S.bpick = null; S.hoverB = null;
    renderPickerEmpty(cellGx, cellGz, s);
    renderPointInfo(h);
    drawOverlay();
    return;
  }
  renderPicker(cellGx, cellGz);
  pickCandidate(0);
  drawOverlay();
}

async function openCell(x, y) {
  const wx = x + S.map.ox;
  const wz = S.map.oz - y;
  // 点空白处：world = 格号*256 + 128 + pos，pos ∈ [-167,125]
  // → 格号 = round((world - 128) / 256)，比 floor 稳（m03060）
  const gx = Math.round((wx - 128) / S.map.tile);
  const gz = Math.round((wz - 128) / S.map.tile);
  const res = await api(`/api/cell?gx=${gx}&gz=${gz}`);
  S.cell = res.ok ? res.candidates : [];
  S.cellGrid = [gx, gz];
  S.bpick = null; S.hoverB = null;
  renderPicker(gx, gz);
  renderInfo(null);
}

/* ---------- 底部选择条 ---------- */
/* m06840：「这一格还剩几个空位」—— 一格里的校准建筑位减去草稿已占的 */
function cellSlots(cell) {
  cell = cell || (S.selPoint && S.selPoint.sp && S.selPoint.sp.grid);
  if (!cell) return null;
  const [gx, gz] = cell;
  const ids = (S.extra || [])
    .filter(a => a.grid && a.grid[0] === gx && a.grid[1] === gz)
    .map(a => a.attachId);
  if (!ids.length) return null;
  const used = new Set();
  for (const s of (S.draft && S.draft.spots) || []) {
    if (ids.includes(s.attachId)) used.add(s.attachId);
  }
  return { total: ids.length, used: used.size, left: ids.length - used.size };
}

function pickLabelText(gx, gz) {
  const sl = cellSlots([gx, gz]);
  let t = `X${gx}/Z${gz}`;
  if (sl) {
    t += ` · 建筑位 ${sl.used}/${sl.total}`;
    t += sl.left > 0 ? `，还剩 ${sl.left}` : '，已排满';
  }
  return t;
}

function renderPickerEmpty(gx, gz, sp) {
  $('pickRow').hidden = false;
  $('pickLabel').textContent = pickLabelText(gx, gz);
  $('picker').innerHTML = `<span class="muted">这个点（attach ${sp.attachId}）没有可放的官方建筑</span>` + customTileHtml();
  bindCustom(sp.attachId);
}

function renderPicker(gx, gz) {
  const row = $('pickRow');
  const box = $('picker');
  $('pickLabel').textContent = pickLabelText(gx, gz);
  if (!S.cell.length) {
    row.hidden = false;
    box.innerHTML = '<span class="muted">这一格没有可放的官方建筑</span>';
    return;
  }
  row.hidden = false;
  // m02666：底部只放图标，不放名字、不放大小字；一个 tile 一个建筑
  const seen = new Set();
  S.buildings = [];
  for (const c of S.cell) {
    for (const t of c.tiles) {
      const info = (c.tileInfo || []).find(x => x.tile === t) || {};
      if (seen.has(t)) continue;
      seen.add(t);
      S.buildings.push({
        attachId: c.attachId, tile: t, icon: info.icon, realName: info.realName || '',
        attrIcon: info.attrIcon, define: info.define || '', variation: info.variation,
        variants: info.variants || [],
        attachName: c.attachName || '', attachSize: c.attachSize,
      });
    }
  }
  // m06316：手输过的建筑也要一直留在条子里
  for (const k in S.custom) {
    const obj = S.custom[k];
    if (!S.buildings.some(b => b.tile === obj.tile)) S.buildings.push(obj);
  }
  // 有建筑的排前面
  S.buildings.sort((a, b) => (a.variation ? 0 : 1) - (b.variation ? 0 : 1) || a.tile - b.tile);
  box.innerHTML = S.buildings.map((b, i) => `
    <div class="pick" data-i="${i}" title="${b.realName || ('tile ' + b.tile)}">
      ${b.icon ? `<img src="/pin/${b.icon}.png">` : `<span class="noicon">${b.tile}</span>`}
      ${(() => {
        const v = (b.variants || []).find(x => x.variationId === (S.varSel[b.tile] || 0));
        return v && v.icon ? `<img class="attr" src="/pin/${v.icon}.png">` : '';
      })()}
    </div>`).join('') + customTileHtml();
  box.querySelectorAll('.pick').forEach(el => {
    el.onclick = () => pickBuilding(+el.dataset.i);
    el.onmouseenter = () => { S.hoverB = S.buildings[+el.dataset.i]; renderInfo(); };
    el.onmouseleave = () => { S.hoverB = null; renderInfo(); };
  });
  bindCustom(S.cell.length ? S.cell[0].attachId : 0);
  // 调试：?custom=<smallBaseMapId> 自动走一遍手输流程
  if (!S._customDone) {
    const cid = +(new URLSearchParams(location.search).get('custom') || 0);
    if (cid) { S._customDone = true; confirmCustom(S.cell.length ? S.cell[0].attachId : 0, cid); }
  }
  if (S.pickTile) {
    const k = S.buildings.findIndex(b => b.tile === S.pickTile);
    if (k >= 0) pickBuilding(k);
    else if (S.buildings.length) pickBuilding(0);
  } else if (S.buildings.length) {
    pickBuilding(Math.min(S.pickIndex ?? 0, S.buildings.length - 1));
  }
  // 调试：?pick=<smallBaseMapId> 直接选中某个建筑（截图 / 复现问题用）
  const want = +(new URLSearchParams(location.search).get('pick') || 0);
  if (want) {
    const k = S.buildings.findIndex(b => b.tile === want);
    if (k >= 0) pickBuilding(k);
  }
}

function pickBuilding(i) {
  const b = S.buildings && S.buildings[i];
  if (!b) return;
  S.bpick = b;
  S.pickIndex = i;
  S.pickTile = b.tile;
  document.querySelectorAll('.pick').forEach(el =>
    el.classList.toggle('on', +el.dataset.i === i));
  renderInfo();
}

async function addPicked() {
  const b = S.bpick;
  if (!b) return;
  const res = await api('/api/add', { attachId: b.attachId, tile: b.tile, mapIndex: 0, variationId: S.varSel[b.tile] || 0 });
  applyState(res);
  const spot = (res.draft?.spots || []).find(s => s.attachId === b.attachId && s.tile === b.tile);
  if (spot) {
    const [x, y] = toPx(spot.world);
    S.pulse = { x, y, t0: performance.now() };
    S.selPoint = { kind: 'draft', sp: spot, x, y };
    drawOverlay();
  }
}


/* ---------- m06316：手输 smallBaseMapId ---------- */
function customTileHtml() {
  return `<div class="pick custom" id="pickCustom" title="手输 smallBaseMapId">＋</div>`;
}

function bindCustom(attachId) {
  const el = $('pickCustom');
  if (!el) return;
  el.onclick = () => {
    el.outerHTML = `<input id="customId" class="customInput" type="number" min="1"
      placeholder="smallBaseMapId" title="输入后按回车">`;
    const inp = $('customId');
    inp.focus();
    inp.onkeydown = ev => {
      if (ev.key === 'Enter') { ev.preventDefault(); confirmCustom(attachId, inp.value); }
      if (ev.key === 'Escape') { el.outerHTML = customTileHtml(); bindCustom(attachId); }
    };
    inp.onblur = () => {
      if (inp.value.trim()) confirmCustom(attachId, inp.value);
    };
  };
}

async function confirmCustom(attachId, raw) {
  const tile = parseInt(String(raw).trim(), 10);
  if (!tile || tile <= 0) { renderPicker(S.cellGrid[0], S.cellGrid[1]); return; }
  const r = await api(`/api/tile?attach=${attachId}&id=${tile}`);
  if (!r.ok) { alert(r.error || '查不到'); renderPicker(S.cellGrid[0], S.cellGrid[1]); return; }
  const info = r.info;
  let i = S.buildings.findIndex(b => b.tile === tile);
  if (i < 0) {
    S.buildings.push({
      attachId, tile, icon: info.icon, realName: info.realName || `smallBaseMapId ${tile}`,
      attrIcon: info.attrIcon, attrName: info.attrName, define: info.define || '',
      variation: info.variation, variants: info.variants || [], custom: true,
      exists: info.exists,
      attachName: (S.cell[0] || {}).attachName || '',
      attachSize: (S.cell[0] || {}).attachSize,
    });
    i = S.buildings.length - 1;
  }
  S.pickIndex = i;
  S.pickTile = tile;
  S.custom[tile] = S.buildings[i];
  renderPicker(S.cellGrid[0], S.cellGrid[1]);
  if (!info.exists) {
    alert(`smallBaseMapId ${tile} 在 SmallBaseMapVariationParam 里没有这一行——可以放，但游戏里可能没有建筑/没有名字。`);
  }
}

/* ---------- 右侧信息 ---------- */
function kv(rows) {
  return `<div class="kv">${rows.filter(r => r).map(([k, v]) =>
    `<b>${k}</b><span>${v}</span>`).join('')}</div>`;
}

function renderPointInfo(h) {
  const sp = h.sp;
  const isExtra = h.kind === 'extra';
  $('infoTag').textContent = isExtra ? '建筑位' : (h.kind === 'draft' ? '草稿里' : '模板里');
  const rows = [['attachId', sp.attachId]];
  if (h.kind === 'draft') {
    rows.push(['建筑', sp.realName || '—']);
    rows.push(['mapIndex', sp.mapIndex ?? 0]);   // m06209：同一建筑第几次出现
  }
  rows.push(['tile', isExtra ? '—' : (sp.tile ?? '—')]);
  rows.push(['位置', sp.attachName || '—']);
  rows.push(['大小', sizeTag(sp.attachSize) || '—']);
  if (isExtra) {
    const sl = cellSlots(sp.grid);      // m06840：这一格还剩几个空位
    if (sl) {
      rows.push(['这一格', sl.left > 0
        ? `还剩 <b>${sl.left}</b> 个空位（共 ${sl.total}，已用 ${sl.used}）`
        : `已排满（共 ${sl.total}）`]);
    }
  }
  rows.push(['world', (sp.world || []).map(v => Number(v).toFixed(3)).join(', ')]);
  $('infoBody').innerHTML = kv(rows) + (h.kind === 'draft'
    ? `<div style="margin-top:8px"><button onclick="removeByAttach(${sp.attachId}, ${sp.tile})">从草稿删除</button></div>`
    : (isExtra
      ? `<div class="muted" style="margin-top:8px">校准过的建筑位，点下面图标就能放建筑</div>`
      : `<div class="muted" style="margin-top:8px">这是模板里的点（只做参照）</div>`));
}

function attrOf(vars, id) {
  const v = (vars || []).find(x => x.variationId === id);
  return v && v.attrName ? v.attrName : '';
}

function renderInfo() {
  const body = $('infoBody');
  const tag = $('infoTag');

  // m02666：右边只显示 smallBaseMapId（SmallBaseMapVariationParam）这一行的信息
  const b = S.hoverB || S.bpick;
  if (b) {
    tag.textContent = '建筑';
    const vars = b.variants || [];
    let cur = S.varSel[b.tile];
    if (cur === undefined || cur === null) cur = 0;
    // m06850：属性变体也能手输数字。手输的那档若不在官方列表里，
    // 就补一个虚线格子挂在条尾（跟「建筑 ＋」同一套习惯）。
    const manual = S.manualVar[b.tile];
    const list = vars.slice();
    if (manual && manual.variationId === cur && !list.some(v => v.variationId === cur)) {
      list.push({ ...manual, manual: true });
    }
    const missing = !!(manual && manual.variationId === cur && manual.exists === false);
    const curAttr = attrOf(list, cur);
    const chips = list.map(v => `
      <div class="vpick ${v.variationId === cur ? 'on' : ''}${v.manual ? ' manual' : ''}" data-v="${v.variationId}"
           title="variationId ${v.variationId}${v.attrName ? ' · ' + v.attrName : ''}${v.manual ? ' · 手输' : ''}">
        ${v.icon ? `<img src="/pin/${v.icon}.png">` : `<span class="noicon">${v.manual ? '手' : '无属性'}</span>`}
        <span class="vid">${v.variationId}${v.attrName ? ' ' + v.attrName : ''}</span>
      </div>`).join('');
    // 属性变体条：variationId 就是槽位号（m04153：3410 的 4 = 冻伤遗迹）
    const strip = `
      <div class="muted" style="margin:8px 0 4px">属性变体（variationId）
        ${vars.length ? '' : '<span class="muted">· 官方没有档位</span>'}</div>
      <div id="varStrip" class="varstrip">
        ${chips}
      </div>
      <div class="varadd" id="varAddWrap">
        <button id="btnVarAdd" title="手输 variationId（0 基，回车确认，Esc 取消）">＋ 手输 variationId</button>
      </div>
      ${missing ? `<div class="warnline">variationId ${cur} 在 SmallBaseMapVariationParam 里没有这一档 —— 能放，但游戏里可能没属性 / 表现异常</div>` : ''}`;
    body.innerHTML = `
      <div class="bhead">
        ${b.icon ? `<img class="bicon" src="/pin/${b.icon}.png">` : ''}
        <div>
          <div class="bname">${b.realName || '（这个 tile 没有建筑）'}</div>
          <div class="muted">smallBaseMapId = ${b.tile} · variationId = ${cur}${curAttr ? ' · ' + curAttr : ''}</div>
        </div>
      </div>
      ${strip}
      <div style="margin:6px 0 8px"><button class="primary" onclick="addPicked()">加入草稿</button></div>
      <div id="varBox" class="rawbox"><span class="muted">读取中…</span></div>`;
    body.querySelectorAll('.vpick').forEach(el => {
      el.onclick = () => {
        S.varSel[b.tile] = +el.dataset.v;
        renderInfo();
        renderPicker(S.cellGrid[0], S.cellGrid[1]);
      };
    });
    bindVarCustom(b.tile);
    fillVariation(b.tile);
    return;
  }

  if (S.selPoint) { renderPointInfo(S.selPoint); return; }
  tag.textContent = '';
  body.innerHTML = '点一下地图';
}

/* m06850：手输 variationId（跟「建筑 ＋」一样：点开变输入框，回车确认） */
function bindVarCustom(tile) {
  const btn = $('btnVarAdd');
  if (!btn) return;
  btn.onclick = () => {
    const wrap = $('varAddWrap') || btn.parentNode;
    wrap.innerHTML = `<input id="varInput" class="varInput" type="number" min="0" step="1"
      placeholder="variationId" title="0 基；回车确认，Esc 取消">`;
    const inp = $('varInput');
    if (!inp) return;
    inp.focus();
    inp.select();
    let done = false;
    const finish = v => { if (done) return; done = true; confirmVar(tile, v); };
    inp.onkeydown = ev => {
      if (ev.key === 'Enter') { ev.preventDefault(); finish(inp.value); }
      else if (ev.key === 'Escape') { ev.preventDefault(); done = true; renderInfo(); }
    };
    inp.onblur = () => {
      if (done) return;
      if (String(inp.value).trim() !== '') finish(inp.value);
      else { done = true; renderInfo(); }
    };
  };
}

async function confirmVar(tile, raw) {
  const v = parseInt(String(raw).trim(), 10);
  if (!Number.isFinite(v) || v < 0) { renderInfo(); return; }
  const r = await api(`/api/variant?tile=${tile}&v=${v}`);
  if (!r.ok) { alert(r.error || '查不到这一档'); renderInfo(); return; }
  S.varSel[tile] = v;
  S.manualVar[tile] = { ...r.info };
  renderInfo();
  if (S.cellGrid) renderPicker(S.cellGrid[0], S.cellGrid[1]);
}

/* 只列 smallBaseMapId 那一行（variation.*）的字段 */
async function fillVariation(tile) {
  const box = $('varBox');
  if (!box) return;
  try {
    const r = await api(`/api/params?attach=0&tile=${tile}`);
    if (!r.ok) { box.innerHTML = '<span class="muted">读不到</span>'; return; }
    const rows = Object.entries(r.fields)
      .filter(([k]) => k.startsWith('variation.'))
      .map(([k, v]) => `<tr><th>${k.slice(10)}</th><td>${v === '' || v === null ? '<span class="muted">—</span>' : v}</td></tr>`);
    if (!rows.length) {
      box.innerHTML = '<div class="muted">这个 smallBaseMapId 没有建筑行（空壳 tile）</div>';
      return;
    }
    box.innerHTML = `<table class="rawtable">${rows.join('')}</table>`;
  } catch (e) {
    box.innerHTML = '<span class="muted">读不到</span>';
  }
}

/* 全部参数（m02506：不猜了，把字段原样摆出来） */
async function fillParams(attachId, tile) {
  const box = $('rawParams');
  if (!box) return;
  try {
    const r = await api(`/api/params?attach=${attachId}&tile=${tile}`);
    if (!r.ok) { box.innerHTML = '<span class="muted">读不到参数</span>'; return; }
    const rows = Object.entries(r.fields).map(([k, v]) =>
      `<tr><th>${k}</th><td>${v === '' || v === null ? '<span class="muted">—</span>' : v}</td></tr>`);
    box.innerHTML = `<details class="more"><summary>全部参数（${rows.length} 个字段）</summary>
      <table class="rawtable">${rows.join('')}</table></details>`;
  } catch (e) {
    box.innerHTML = '<span class="muted">读不到参数</span>';
  }
}

async function removeByAttach(attachId, tile) {
  const i = (S.draft?.spots || []).findIndex(s => s.attachId === attachId && s.tile === tile);
  if (i < 0) return;
  const res = await api('/api/remove', { index: i });
  S.selPoint = null;
  applyState(res);
}


async function renderTests() {
  if (!location.search.includes('tests=1')) { $('cardTests').hidden = true; return; }
  const r = await api('/api/tests');
  const list = (r.tests || []).slice().reverse();
  const card = $('cardTests');
  if (!list.length) { card.hidden = true; return; }
  card.hidden = false;
  $('testCount').textContent = `共 ${list.length} 次`;
  $('testList').innerHTML = list.slice(0, 12).map(t => {
    const rows = (t.rows || []).map(e => `${e.modifierSet}:${e.eventFlag}/${e.modifier}`).join(' · ');
    return `<div class="trow" title="${rows}">
      <span class="twhen">${t.ts.slice(4, 6)}-${t.ts.slice(6, 8)} ${t.ts.slice(9, 11)}:${t.ts.slice(11, 13)}</span>
      <span class="tpid">pid ${t.patternId}</span>
      <span class="tflags">${(t.rows || []).length} 行</span>
    </div>`;
  }).join('');
}



/* ---------- 状态 ---------- */
function applyState(res) {
  renderMaps(res);
  if (!res.ok) { alert(res.error || '出错'); return; }
  S.draft = res.draft;
  S.template = res.template;
  S.extra = res.extra || [];
  S.issues = res.issues;
  S.playarea = res.playarea || null;
  S.events = res.events || [];
  if (res.map) S.map = res.map;
  if (res.rev !== undefined) { S.rev = res.rev; loadMap(); }
  $('btnWrite').disabled = false;
  if ($('btnUndo')) $('btnUndo').disabled = !res.canUndo;
  rebuildHits();
  renderChips();
  renderIssues();
  renderArea();
  renderEvents();
  renderTests();
  renderInfo();
  drawOverlay();
}

function renderEvents() {
  const card = $('cardEvents');
  const list = $('eventList');
  const evs = S.events || [];
  if (!evs.length) { card.hidden = true; return; }
  card.hidden = false;
  list.innerHTML = evs.map(ev => {
    const cur = `${ev.eventFlag || 0}/${ev.modifier}`;
    const opts = ev.options.map(o => {
      const k = `${o.eventFlag || 0}/${o.modifier}`;
      const label = `${k} ${o.name || ''}`.trim();
      return `<option value="${k}"${k === cur ? ' selected' : ''}>${label}</option>`;
    }).join('');
    return `<div class="erow">
      <span class="eset" title="modifierSet">${ev.modifierSet}</span>
      <select data-i="${ev.i}">${opts}</select>
    </div>`;
  }).join('');
  list.querySelectorAll('select').forEach(sel => {
    sel.onchange = async () => {
      const [eventFlag, modifier] = sel.value.split('/').map(Number);
      const res = await api('/api/event', { index: +sel.dataset.i, eventFlag, modifier });
      applyState(res);
    };
  });
}

function renderArea() {
  const pa = S.playarea;
  const card = $('cardArea');
  if (!pa) { card.hidden = true; return; }
  card.hidden = false;

  const c = pa.cur || {};
  const t = pa.curText || {};
  $('areaCur').innerHTML =
    (pa.isTemplate ? '<span class="tag">模板</span> ' : '')
    + `1缩 <b>${c.pa1 ?? '—'}</b> · 2缩 <b>${c.pa2 ?? '—'}</b><br>`
    + `<span class="muted">${t.pa1 || ''} / ${t.pa2 || ''}</span><br>`
    + `1夜 <b>${c.nb1 ?? '—'}</b> · 2夜 <b>${c.nb2 ?? '—'}</b><br>`
    + `<span class="muted">${t.nb1 || ''} / ${t.nb2 || ''}</span>`;

  const opt = (list, cur, fmt) => {
    const head = `<option value="">（跟模板）</option>`;
    return head + list.map(x => {
      const sel = String(x.id) === String(cur) ? ' selected' : '';
      return `<option value="${x.id}"${sel}>${fmt(x)}</option>`;
    }).join('');
  };

  const rows = [
    ['pa1', '1缩', opt(pa.areas, c.pa1, x => `${x.id} ${x.name}`)],
    ['pa2', '2缩', opt(pa.areas, c.pa2, x => `${x.id} ${x.name}`)],
    ['nb1', '1夜', opt(pa.nights, c.nb1, x => x.name)],
    ['nb2', '2夜', opt(pa.nights, c.nb2, x => x.name)],
  ];
  const areaName = id => {
    const a = (pa.areas || []).find(x => x.id === id);
    return a ? `${a.id} ${a.name}` : '（跟模板）';
  };
  const drop = (k, label, cur) => `
    <div class="arow"><span>${label}</span>
      <div class="adrop" data-k="${k}">
        <button type="button" class="abtn">${areaName(cur)}</button>
        <div class="alist" hidden>${(pa.areas || []).map(a =>
          `<div class="aitem${a.id === cur ? ' on' : ''}" data-k="${k}" data-id="${a.id}">${a.id} ${a.name}</div>`
        ).join('')}</div>
      </div>
    </div>`;

  $('areaSel').innerHTML =
    drop('pa1', '1缩', c.pa1) + drop('pa2', '2缩', c.pa2) +
    rows.slice(2).map(([k, label, html]) =>
      `<label class="arow"><span>${label}</span>
         <select data-k="${k}">${html}</select></label>`).join('');

  // 自定义下拉（1缩/2缩）：悬停某一项 → 地图临时出标记；点一下 → 固定（主人 m05770）
  $('areaSel').querySelectorAll('.adrop').forEach(dp => {
    const k = dp.dataset.k;
    const btn = dp.querySelector('.abtn');
    const list = dp.querySelector('.alist');
    btn.onclick = e => {
      e.stopPropagation();
      document.querySelectorAll('.adrop .alist').forEach(x => { if (x !== list) x.hidden = true; });
      list.hidden = !list.hidden;
    };
    list.querySelectorAll('.aitem').forEach(it => {
      it.onmouseenter = () => {
        S.areaHover = { key: k, id: +it.dataset.id };
        drawOverlay();
        list.querySelectorAll('.aitem').forEach(y => y.classList.toggle('hover', y === it));
      };
      it.onclick = async ev => {
        ev.stopPropagation();
        list.hidden = true;
        S.areaHover = null;
        const res = await api('/api/playarea', { [k]: +it.dataset.id });
        applyState(res);
      };
    });
    list.onmouseleave = () => { S.areaHover = null; drawOverlay(); };
  });

  $('areaSel').querySelectorAll('select').forEach(sel => {
    sel.onchange = async () => {
      const body = {};
      body[sel.dataset.k] = sel.value === '' ? null : +sel.value;
      const res = await api('/api/playarea', body);
      applyState(res);
    };
    // 1缩/2缩：鼠标停在下拉上时，把当前项在地图上临时标出来（主人 m05770）
    if (sel.dataset.k === 'pa1' || sel.dataset.k === 'pa2') {
      const k = sel.dataset.k;
      sel.onfocus = sel.onmouseenter = () => { S.areaHover = { key: k }; drawOverlay(); };
      sel.onblur = sel.onmouseleave = () => { S.areaHover = null; drawOverlay(); };
      sel.oninput = () => { S.areaHover = { key: k, id: +sel.value || null }; drawOverlay(); };
    }
  });
}

function renderChips() {
  const d = S.draft;
  const row = $('chipRow');
  const box = $('chips');
  if (!d) { row.hidden = true; return; }
  row.hidden = false;
  $('draftMeta').innerHTML =
    `夜王 ${d.bossId} · set <b>${d.newSet}</b> · patternId <b>${d.newPid}</b> · ${d.spots.length} 个地点`
    + (d.spots.length > 1 ? ' <span class="muted">（拖动可排序）</span>' : '');
  box.innerHTML = d.spots.map((sp, i) => `
    <div class="chip" data-i="${i}" draggable="true"
         title="${sp.realName || sp.attachName || ''}（拖动可排序）">
      <span class="ord">${i + 1}</span>
      ${sp.icon ? `<img src="/pin/${sp.icon}.png">` : `<span class="noicon">#${sp.attachId}</span>`}
      <span class="x" data-x="${i}">✕</span>
    </div>`).join('');

  box.querySelectorAll('.chip').forEach(el => {
    const i = +el.dataset.i;
    el.onmouseenter = () => {
      const sp = d.spots[i];
      const [x, y] = toPx(sp.world);
      S.selPoint = { kind: 'draft', sp, x, y };
      drawOverlay();
    };
    el.onclick = ev => {
      if (ev.target.dataset.x !== undefined) { removeSpot(+ev.target.dataset.x); return; }
      const sp = d.spots[i];
      const [x, y] = toPx(sp.world);
      S.selPoint = { kind: 'draft', sp, x, y };
      renderPointInfo(S.selPoint);
      drawOverlay();
    };

    // m06840：拖动排序（插到左边 = 放在它前面，右边 = 后面）
    el.ondragstart = ev => {
      S.dragFrom = i;
      S.dropAt = i;
      ev.dataTransfer.effectAllowed = 'move';
      ev.dataTransfer.setData('text/plain', String(i));
      el.classList.add('dragging');
    };
    el.ondragover = ev => {
      if (S.dragFrom == null) return;
      ev.preventDefault();
      ev.stopPropagation();
      ev.dataTransfer.dropEffect = 'move';
      const r = el.getBoundingClientRect();
      const after = ev.clientX > r.left + r.width / 2;
      box.querySelectorAll('.chip').forEach(x => x.classList.remove('dropL', 'dropR'));
      el.classList.add(after ? 'dropR' : 'dropL');
      S.dropAt = i + (after ? 1 : 0);
    };
    el.ondrop = ev => { ev.preventDefault(); ev.stopPropagation(); finishDrag(); };
    el.ondragend = () => { el.classList.remove('dragging'); clearDropHints(); };
  });

  // 拖到空白处 = 放到最后
  box.ondragover = ev => {
    if (S.dragFrom == null) return;
    ev.preventDefault();
    S.dropAt = d.spots.length;
  };
  box.ondrop = ev => { ev.preventDefault(); finishDrag(); };
}

function clearDropHints() {
  document.querySelectorAll('#chips .chip').forEach(x => x.classList.remove('dropL', 'dropR'));
}

async function finishDrag() {
  const from = S.dragFrom;
  const at = S.dropAt;
  S.dragFrom = null;
  S.dropAt = null;
  clearDropHints();
  if (from == null || at == null) return;
  let to = at;
  if (to > from) to -= 1;          // 目标是「插在 at 前面」，摘掉自己后下标要减 1
  if (to === from) return;
  const res = await api('/api/move', { from, to });
  applyState(res);
}

/* ---------- 撤销 / 导出（m06840） ---------- */
let toastTimer = null;
function toast(msg) {
  let el = $('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), 1800);
}

async function undoLast() {
  if (!S.draft) return;
  const res = await api('/api/undo', {});
  S.selPoint = null;
  S.hoverB = null;
  S.bpick = null;
  if (res.undone === false) toast('没有可撤销的操作');
  else toast('已撤销上一步');
  applyState(res);
}

async function exportJson() {
  const r = await api('/api/export');
  if (!r.ok) { toast(r.error || '导出失败'); return; }
  const blob = new Blob([JSON.stringify(r.json, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = r.file || 'nrseed.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  toast('已导出 ' + (r.file || 'JSON'));
}

$('btnUndo').onclick = () => undoLast();
$('btnExport').onclick = () => exportJson();

window.addEventListener('keydown', ev => {
  if (!(ev.ctrlKey || ev.metaKey) || ev.shiftKey) return;
  if (String(ev.key).toLowerCase() !== 'z') return;
  const t = document.activeElement && document.activeElement.tagName;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(t || '')) return;   // 正在输入框里就别抢 Ctrl+Z
  ev.preventDefault();
  undoLast();
});

async function removeSpot(i) {
  const res = await api('/api/remove', { index: i });
  S.selPoint = null;
  applyState(res);
}

function renderIssues() {
  $('issueList').innerHTML = S.issues.map(it => `
    <li class="issue"><span class="dot ${it.level}"></span><div>${it.msg}</div></li>
  `).join('') || '<li class="muted">—</li>';
}

/* ---------- 顶部动作 ---------- */
$('btnOpen').onclick = async () => {
  const r = await api('/api/open', { path: $('binPath').value });
  if (r.needChoose) { renderBinPicker(r.bins); return; }
  if (!r.ok) { alert(r.error); return; }
  $('binPath').value = r.bin;
  S.bin = r.bin;
  $('outLabel').textContent = '写回 → ' + r.bin;
  $('bossSel').innerHTML = r.bosses.map(b =>
    `<option value="${b.id}">#${b.id} · ${b.name}</option>`).join('');
  $('btnDraft').disabled = false;
};

/* 文件夹里有多个 bin → 列出来让主人点一个 */
function renderBinPicker(bins) {
  $('infoTag').textContent = '选一个 bin';
  $('infoBody').innerHTML = bins.map(p => {
    const name = p.split(/[\\/]/).pop();
    return `<button class="binpick" data-p="${p.replace(/"/g, '&quot;')}"
      style="display:block;width:100%;text-align:left;margin:4px 0">${name}</button>`;
  }).join('') + `<div class="muted" style="margin-top:6px">${bins.length} 个候选</div>`;
  $('infoBody').querySelectorAll('.binpick').forEach(b => {
    b.onclick = async () => {
      $('binPath').value = b.dataset.p;
      $('btnOpen').click();
    };
  });
}

$('btnDraft').onclick = async () => {
  const boss = +$('bossSel').value;
  const r = await api('/api/draft', { boss });
  S.bpick = null; S.hoverB = null; S.selPoint = null; S.cell = null;
  $('pickRow').hidden = true;
  applyState(r);
};

$('btnWrite').onclick = async () => {
  const target = S.bin || '';
  if (!target) { alert('先打开 bin'); return; }
  if (!confirm('将要写到：' + target + '\n原文件会自动备份。继续？')) return;
  const r = await api('/api/write', { target });
  $('cardResult').hidden = false;
  $('resultBody').innerHTML = `
    <div class="${r.ok ? 'ok-text' : 'err-text'}">${r.ok ? '写回成功' : (r.error || '失败')}</div>
    <div class="muted">patternId ${r.patternId} · set ${r.set}</div>
    <ul>${(r.checks || []).map(([n, ok]) =>
      `<li class="issue"><span class="dot ${ok ? 'ok' : 'error'}"></span><div>${n}</div></li>`).join('')}</ul>`;
};

/* ---------- 启动 ---------- */
(async () => {
  const q = new URLSearchParams(location.search);
  if (q.get('bin')) {
    $('binPath').value = q.get('bin');
    $('btnOpen').click();
    if (q.get('boss') !== null) {
      setTimeout(() => {
        $('bossSel').value = q.get('boss');
        $('btnDraft').click();
      }, 1200);
    }
    return;
  }
  const st = await api('/api/state');
  if (!st.ok) return;
  $('binPath').value = st.bin;
  S.bin = st.bin; $('binPath').value = st.bin; $('outLabel').textContent = '写回 → ' + st.bin;
  $('bossSel').innerHTML = st.bosses.map(b =>
    `<option value="${b.id}">#${b.id} · ${b.name}</option>`).join('');
  $('btnDraft').disabled = false;
  S.map = st.map;
  applyState(st);
  if (st.draft) $('bossSel').value = st.draft.bossId;
  const cell = q.get('cell');
  if (cell) {
    const [gx, gz] = cell.split(',').map(Number);
    setTimeout(() => {
      openCell((gx * S.map.tile + S.map.center) - S.map.ox + 8,
               S.map.oz - ((gz * S.map.tile + S.map.center) + 8));
    }, 600);
  }
  const mq = q.get('map');       // 调试用：?map=crater 走一遍切图流程
  if (mq) {
    setTimeout(() => {
      const sel = $('mapSel');
      if (sel) { sel.value = mq; sel.dispatchEvent(new Event('change')); }
    }, 1000);
  }

  const anc = q.get('anchor');   // 调试用：?anchor=313 直接选中那个建筑位
  if (anc) {
    setTimeout(() => {
      const sp = (S.extra || []).find(x => x.attachId === +anc);
      if (sp) {
        const [ax, ay] = toPx(sp.world, sp);
        selectPoint({ kind: 'extra', sp, x: ax, y: ay });
      }
    }, 1200);
  }

  const hl = q.get('hl');       // 调试用：?hl=346,425 直接高亮那个点
  if (hl) {
    const [hx, hy] = hl.split(',').map(Number);
    setTimeout(() => {
      S.hoverPoint = hitTest(hx, hy);
      drawOverlay();
      if (S.hoverPoint) renderPointInfo(S.hoverPoint);
    }, 800);
  }
})();

/* 地图舞台：等比塞进可用区域，永不出现滚动条（内部 canvas 仍是 1536²） */
function fitStage() {
  const wrap = mapWrap, box = mapBox;
  if (!wrap || !box) return;
  const w = wrap.clientWidth - 16;
  const h = wrap.clientHeight - 16;
  const s = Math.max(320, Math.min(w, h, 1024));
  box.style.width = s + 'px';
  box.style.height = s + 'px';
}
window.addEventListener('resize', fitStage);
fitStage();
setTimeout(fitStage, 50);

















