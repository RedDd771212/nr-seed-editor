'use strict';

window.onerror = (m, s, l) => { const h = document.getElementById('hint'); if (h) h.textContent = 'ERR ' + m + ' @' + l; };

const S = {
  pts: [],            // 原始点
  edits: new Map(),   // id -> {world:[x,z], deleted:bool, orig:[x,z]}
  sel: null,
  map: null,
  showSpecial: false,
};

const $ = id => document.getElementById(id);

/* ---------- 画布 ---------- */
const img = $('map');
const cv = $('cv');
const ctx = cv.getContext('2d');
let W = 1536, H = 1536, scale = 1;

function fit() {
  const stage = $('stage');
  const aw = stage.clientWidth - 20, ah = stage.clientHeight - 20;
  const s = Math.min(aw / W, ah / H, 1);
  const w = Math.round(W * s), h = Math.round(H * s);
  const left = Math.round((stage.clientWidth - w) / 2);
  const top = Math.round((stage.clientHeight - h) / 2);
  for (const el of [img, cv]) {
    el.style.width = w + 'px'; el.style.height = h + 'px';
    el.style.left = left + 'px'; el.style.top = top + 'px';
  }
  cv.width = W; cv.height = H;
  scale = s;
}

function toPx(world) {
  return [world[0] - S.map.ox, S.map.oz - world[1]];
}
function toWorld(x, y) {
  return [x + S.map.ox, S.map.oz - y];
}
function cur(p) {
  const e = S.edits.get(p.id);
  return e ? e.world : p.world;
}

/* ---------- 状态 ---------- */
async function api(path, body) {
  const r = await fetch(path, body ? {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  } : undefined);
  return r.json();
}

function applyState(st) {
  S.map = st.map;
  S.pts = st.points || [];
  S.edits.clear();
  const items = (st.corrections && st.corrections.items) || [];
  for (const it of items) {
    const p = S.pts.find(x => x.id === it.id);
    if (!p) continue;
    S.edits.set(it.id, {
      world: it.world ? [it.world[0], it.world[1]] : [p.world[0], p.world[1]],
      deleted: !!it.deleted,
      note: it.note || '',
    });
  }
  $('binPath').textContent = st.bin || '未打开';
  const sel = $('mapSel');
  if (sel && st.maps) {
    if (!sel.dataset.ready) {
      sel.innerHTML = st.maps.map(m => `<option value="${m.id}">${m.name}</option>`).join('');
      sel.dataset.ready = '1';
    }
    sel.value = st.mapId;
    S.mapId = st.mapId;
  }
  $('counter').textContent = visible().length + ' / ' + S.pts.length + ' 个点';
  fit();
  draw();
  renderList();
}

/* ---------- 绘制 ---------- */
function draw() {
  ctx.clearRect(0, 0, W, H);
  const zoom = 1;
  for (const p of visible()) {
    const e = S.edits.get(p.id);
    const w = e ? e.world : p.world;
    const [x, y] = toPx(w);
    const del = e && e.deleted;
    const col = del ? '#e2555b'
      : p.pad !== 0 ? '#e0a33c'
      : p.id >= 1000 ? '#7b8494'
      : (p.size === '大' ? '#7fd0ff' : p.size === '小' ? '#7fe0b0' : '#a8b3c4');
    ctx.beginPath();
    ctx.arc(x, y, del ? 6 : 4.5, 0, Math.PI * 2);
    ctx.fillStyle = del ? 'rgba(226,85,91,.15)' : col;
    ctx.fill();
    if (del) {
      ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x - 4, y - 4); ctx.lineTo(x + 4, y + 4);
      ctx.moveTo(x + 4, y - 4); ctx.lineTo(x - 4, y + 4); ctx.stroke();
    }
    if (S.sel === p.id) {
      ctx.beginPath(); ctx.arc(x, y, 11, 0, Math.PI * 2);
      ctx.strokeStyle = '#4da3ff'; ctx.lineWidth = 2; ctx.stroke();
    }
  }
}

/* ---------- 命中 ---------- */
function visible() {
  return S.showSpecial ? S.pts : S.pts.filter(p => p.pad === 0 && p.id < 1000);
}

function hit(x, y) {
  let best = null, bd = 12;
  for (const p of visible()) {
    const [px, py] = toPx(cur(p));
    const d = Math.hypot(px - x, py - y);
    if (d < bd) { bd = d; best = p; }
  }
  return best;
}

function evPos(ev) {
  const r = cv.getBoundingClientRect();
  return [(ev.clientX - r.left) * W / r.width, (ev.clientY - r.top) * H / r.height];
}

/* ---------- 交互 ---------- */
let drag = null;

cv.addEventListener('mousedown', ev => {
  const [x, y] = evPos(ev);
  const p = hit(x, y);
  if (!p) { S.sel = null; renderInfo(); draw(); return; }
  S.sel = p.id;
  drag = { id: p.id, moved: false };
  renderInfo(); draw();
});

cv.addEventListener('mousemove', ev => {
  const [x, y] = evPos(ev);
  if (drag) {
    const w = toWorld(x, y);
    const p = S.pts.find(q => q.id === drag.id);
    const e = S.edits.get(p.id) || { deleted: false, orig: p.world.slice() };
    S.edits.set(p.id, { ...e, world: [w[0], w[1]] });
    drag.moved = true;
    draw(); renderInfo(); renderList();
    return;
  }
  const p = hit(x, y);
  cv.style.cursor = p ? 'pointer' : 'crosshair';
  if (p) {
    const [px, py] = toPx(cur(p));
    const tip = $('tip');
    tip.hidden = false;
    tip.textContent = `#${p.id}  ${p.name}`;
    tip.style.left = px * scale + 'px';
    tip.style.top = py * scale + 'px';
  } else {
    $('tip').hidden = true;
  }
});

window.addEventListener('mouseup', () => { drag = null; });

cv.addEventListener('contextmenu', ev => {
  ev.preventDefault();
  const [x, y] = evPos(ev);
  const p = hit(x, y);
  if (!p) return;
  toggleDelete(p.id);
});

window.addEventListener('keydown', ev => {
  if (ev.key !== 'Delete' || S.sel == null) return;
  toggleDelete(S.sel);
});

function toggleDelete(id) {
  const p = S.pts.find(q => q.id === id);
  const e = S.edits.get(id) || { world: p.world.slice(), orig: p.world.slice() };
  const deleted = !e.deleted;
  if (!deleted && same(e.world, p.world)) {
    S.edits.delete(id);
  } else {
    S.edits.set(id, { ...e, deleted });
  }
  draw(); renderInfo(); renderList();
}

function same(a, b) {
  return Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;
}

/* ---------- 右栏 ---------- */
function renderInfo() {
  const tag = $('tag'), box = $('info');
  if (S.sel == null) { tag.textContent = ''; box.innerHTML = '<span class="muted">点一个点</span>'; return; }
  const p = S.pts.find(q => q.id === S.sel);
  if (!p) return;
  const e = S.edits.get(p.id);
  const w = e ? e.world : p.world;
  const moved = Math.hypot(w[0] - p.world[0], w[1] - p.world[1]);
  tag.textContent = e ? (e.deleted ? '已标记删除' : (moved > 0.5 ? '已移动' : '已改')) : '原始';
  box.innerHTML = `
    <div class="kv">
      <b>attachId</b><span>${p.id}</span>
      <b>名称</b><span>${p.name || '—'}</span>
      <b>grid</b><span>X${p.grid[0]} / Z${p.grid[1]}</span>
      <b>pad</b><span>${p.pad}${p.pad ? '（特殊地形）' : ''}</span>
      <b>大小</b><span>${p.size || '—'}</span>
      <b>被种子用</b><span>${p.used} 次</span>
      <b>原始世界</b><span>${fmt(p.world)}</span>
      <b>现在世界</b><span>${fmt(w)}</span>
      <b>posX</b><span><input type="number" step="0.001" value="${(w[0] - p.grid[0] * 256 - 128).toFixed(3)}" data-f="x"></span>
      <b>posZ</b><span><input type="number" step="0.001" value="${(w[1] - p.grid[1] * 256 - 128).toFixed(3)}" data-f="z"></span>
    </div>
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
      <button onclick="toggleDelete(${p.id})">${e && e.deleted ? '恢复这个点' : '标记删除'}</button>
      <button onclick="revertOne(${p.id})">还原位置</button>
      <button onclick="focusPoint(${p.id})">定位</button>
    </div>`;
  for (const inp of box.querySelectorAll('input')) {
    inp.onchange = () => {
      const px = +(box.querySelector('[data-f=x]').value);
      const pz = +(box.querySelector('[data-f=z]').value);
      const world = [p.grid[0] * 256 + 128 + px, p.grid[1] * 256 + 128 + pz];
      S.edits.set(p.id, { ...(S.edits.get(p.id) || {}), world });
      draw(); renderInfo(); renderList();
    };
  }
}

function fmt(w) { return `${w[0].toFixed(3)}, ${w[1].toFixed(3)}`; }

function revertOne(id) {
  const p = S.pts.find(q => q.id === id);
  const e = S.edits.get(id);
  if (!e) return;
  S.edits.delete(id);
  draw(); renderInfo(); renderList();
}

function focusPoint(id) { S.sel = id; renderInfo(); draw(); }

function renderList() {
  const items = [...S.edits.entries()].filter(([id, e]) => {
    const p = S.pts.find(q => q.id === id);
    return e.deleted || !same(e.world, p.world);
  });
  const kept = items.filter(([, e]) => !e.deleted).length;
  $('cnt').textContent = items.length
    ? `${items.length} 处（删 ${items.length - kept} / 移 ${kept}）` : '';
  $('list').innerHTML = items.map(([id, e]) => {
    const p = S.pts.find(q => q.id === id);
    const what = e.deleted ? '删除' : '移动';
    return `<div class="row"><span class="nm" title="${p.name}">#${id} ${p.name}</span>
      <span class="muted">${what}</span>
      <span class="act" onclick="revertOne(${id})">撤销</span></div>`;
  }).join('') || '<span class="muted">还没有改动</span>';
}

/* ---------- 保存 ---------- */
$('btnReset').onclick = () => {
  if (!confirm('撤销本次所有改动？')) return;
  S.edits.clear(); draw(); renderList(); renderInfo();
};

$('btnSave').onclick = async () => {
  const items = [];
  for (const [id, e] of S.edits) {
    const p = S.pts.find(q => q.id === id);
    if (!e.deleted && same(e.world, p.world)) continue;
    items.push({
      id, name: p.name,
      orig: p.world, world: e.world,
      moved: +Math.hypot(e.world[0] - p.world[0], e.world[1] - p.world[1]).toFixed(3),
      deleted: !!e.deleted,
    });
  }
  if (!items.length) { alert('没有改动'); return; }
  const r = await api('/api/save', { items });
  alert(r.ok ? `已保存 ${r.count} 处改动\n${r.file}` : '保存失败');
};

/* ---------- 启动 ---------- */
(async () => {
  window.addEventListener('resize', () => { fit(); draw(); });
  $('chkSpecial').onchange = () => {
    S.showSpecial = $('chkSpecial').checked;
    $('counter').textContent = visible().length + ' / ' + S.pts.length + ' 个点';
    draw();
  };
  const st = await api('/api/state');
  if (!st.ok) {
    $('info').innerHTML = '<span class="muted">没有打开 bin：请用 <code>python calib/server.py 8778 &lt;regulation.bin&gt;</code> 启动</span>';
    return;
  }
  applyState(st);
})();

$('mapSel') && ($('mapSel').onchange = async () => {
  const id = $('mapSel').value;
  await api('/api/map', { id });
  img.src = '/map.png?t=' + Date.now();
  const st = await api('/api/state');
  S.edits.clear();
  applyState(st);
});

$('btnClearMap') && ($('btnClearMap').onclick = async () => {
  if (!confirm('清空「' + ($('mapSel').selectedOptions[0] || {}).text + '」这张图的全部校对？（会先备份到 history）')) return;
  await api('/api/reset', {});
  const st = await api('/api/state');
  S.edits.clear();
  applyState(st);
});
