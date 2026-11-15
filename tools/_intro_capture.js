// 介绍视频素材采集（v3 定稿流程）
// 用法: node tools/_intro_capture.js   （需要 8779 编辑器 + 9333 的 headless Edge）
const http = require('http');
const fs = require('fs');
const path = require('path');

const CDP_PORT = 9333;
const APP = 'http://127.0.0.1:8779/';
const OUTDIR = 'work/intro/shots';
const BIN = 'E:\\ERtools\\tools\\Deepseek\\项目\\app\\NR地图种子编辑器\\work\\demo\\demo_regulation.bin';
const MAP_W = 1536;

fs.mkdirSync(OUTDIR, { recursive: true });

const getJson = (u, method = 'GET') => new Promise((res, rej) => {
  const req = http.request(u, { method }, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => { try { res(JSON.parse(d)); } catch (e) { res(d); } }); });
  req.on('error', rej); req.end();
});
const sleep = ms => new Promise(r => setTimeout(r, ms));

let send, cur = { x: 960, y: 540 };
let trail = [], clicks = [], t0 = Date.now(), shotStart = 0;
const now = () => Date.now() - t0;

const evaluate = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.exceptionDetails.exception && r.exceptionDetails.exception.description));
  return r.result.result.value;
};
const rrect = async (sel) => evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(sel)});if(!e)return null;const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()`);
// scrollIntoView 会把整个窗口滚走 → 每次量坐标前先把窗口滚回顶部
const resetScroll = () => evaluate(`(()=>{window.scrollTo(0,0);document.documentElement.scrollTop=0;document.body.scrollTop=0;})()`);
const center = async (sel, dx = 0, dy = 0) => {
  await resetScroll();
  const r = await rrect(sel);
  if (!r) throw new Error('no element ' + sel);
  return { x: r.x + r.w / 2 + dx, y: r.y + r.h / 2 + dy };
};

async function moveTo(x, y, steps = 14, stepMs = 22) {
  const sx = cur.x, sy = cur.y;
  for (let i = 1; i <= steps; i++) {
    const k = i / steps;
    const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    const px = Math.round(sx + (x - sx) * e), py = Math.round(sy + (y - sy) * e);
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: px, y: py, button: 'none' });
    cur = { x: px, y: py };
    trail.push([now() - shotStart, px, py]);
    await sleep(stepMs);
  }
}
async function clickAt(x, y, clickCount = 1) {
  await moveTo(x, y, 12, 18);
  await sleep(120);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount });
  clicks.push([now() - shotStart, x, y]);
}
async function dblclickAt(x, y) {
  await clickAt(x, y, 1);
  await sleep(60);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 2 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 2 });
  clicks.push([now() - shotStart, x, y]);
}
async function click(sel, dx = 0, dy = 0) { const c = await center(sel, dx, dy); await clickAt(c.x, c.y); }
async function hover(sel, dx = 0, dy = 0) { const c = await center(sel, dx, dy); await moveTo(c.x, c.y, 14, 20); }

let shotIdx = 0;
async function shot(name, extra) {
  await resetScroll();
  await sleep(260);
  const s = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(OUTDIR, name + '.png'), Buffer.from(s.result.data, 'base64'));
  const info = { name, takenAt: now(), cursor: trail.slice(), clicks: clicks.slice(), boxes: {} };
  for (const sel of ['#binPath', '#btnOpen', '#left', '#tree', '#center', '#mapWrap', '#picker', '#right', '#inspector', '#btnUndo', '#btnNewSet', '#bossFilter', '#ctx', '#hint']) {
    const r = await rrect(sel);
    if (r) info.boxes[sel] = r;
  }
  if (extra) Object.assign(info, extra);
  fs.writeFileSync(path.join(OUTDIR, name + '.json'), JSON.stringify(info));
  console.log('shot', name, 'trail', info.cursor.length);
  shotIdx++;
  trail = []; clicks = []; shotStart = now();
}

// 复刻前端的圆圈位置
function circlesOf(tree) {
  const anchors = tree.anchors || [];
  const byId = new Map(anchors.map(a => [a.attachId, a]));
  const OX = tree.map.ox, OZ = tree.map.oz;
  const spots = (tree.pidInfo.spotView || []).map(sp => {
    let cx = null, cy = null, matched = null;
    for (const k of [sp.attachId, sp.attachId - 1000, sp.attachId - 2000, sp.attachId - 3000, sp.attachId + 1000, sp.attachId + 2000]) {
      if (k > 0 && byId.has(k)) { const a = byId.get(k); cx = a.world[0] - OX; cy = OZ - a.world[1]; matched = a; break; }
    }
    if (cx == null && sp.world) {
      for (const a of anchors) {
        if (Math.abs(a.world[0] - sp.world[0]) < 14 && Math.abs(a.world[1] - sp.world[1]) < 14) { cx = a.world[0] - OX; cy = OZ - a.world[1]; matched = a; break; }
      }
    }
    if (cx == null && sp.px != null) { cx = sp.px; cy = sp.py; }
    return { x: cx, y: cy, matched, sp };
  }).filter(c => c.x != null);
  const anchorsPx = anchors.map(a => ({ x: a.world[0] - OX, y: OZ - a.world[1], a }));
  return { anchors, anchorsPx, spots, OX, OZ };
}

(async () => {
  const list = await getJson(`http://127.0.0.1:${CDP_PORT}/json/list`);
  for (const t of list.filter(x => x.type === 'page')) await fetch(`http://127.0.0.1:${CDP_PORT}/json/close/${t.id}`).catch(() => { });
  const page = await getJson(`http://127.0.0.1:${CDP_PORT}/json/new?${encodeURIComponent('about:blank')}`, 'PUT');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Page.javascriptDialogOpening') { console.log('dialog:', m.params.message); send('Page.handleJavaScriptDialog', { accept: true }); }
  });
  await new Promise(r => ws.onopen = r);
  send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: APP + '?v=' + Date.now() });
  for (let i = 0; i < 60; i++) {
    await sleep(250);
    const ok = await evaluate(`document.readyState === 'complete' && !!document.getElementById('tree')`).catch(() => false);
    if (ok) break;
  }
  await sleep(1500);
  console.log('start tree:', (await evaluate(`document.getElementById('tree').textContent`)).trim().slice(0, 30));
  t0 = Date.now(); shotStart = 0;

  // 1 空白界面
  await moveTo(760, 300, 18, 24);
  await shot('01_empty');

  // 2 输入路径
  await click('#binPath', -120, 0);
  await sleep(200);
  await send('Input.insertText', { text: BIN });
  await sleep(700);
  await shot('02_typing');

  // 3 打开
  await click('#btnOpen');
  for (let i = 0; i < 160; i++) {
    const n = await evaluate(`document.querySelectorAll('.srow').length`).catch(() => 0);
    if (n > 0) break;
    await sleep(250);
  }
  await sleep(3500);
  await shot('03_opened');

  // 4 选种子 pid 1
  await click('.pbtn[data-pid="1"]');
  await sleep(2800);
  await shot('04_seed');

  // 5 夜王筛选
  await click('#bossFilter', -60, 0);
  await sleep(300);
  await evaluate(`(()=>{const s=document.getElementById('bossFilter');s.value='8';s.dispatchEvent(new Event('change'));})()`);
  await sleep(1000);
  await hover('.srow', 40, 26);
  await sleep(500);
  await shot('05_filter');
  await evaluate(`(()=>{const s=document.getElementById('bossFilter');s.value='';s.dispatchEvent(new Event('change'));})()`);
  await sleep(1000);

  const tree1 = await getJson('http://127.0.0.1:8779/api3/tree');
  const c1 = circlesOf(tree1);
  await resetScroll();
  const mapRect = await rrect('#map');
  const scale = mapRect.w / MAP_W;
  const toScreen = p => ({ x: mapRect.x + p.x * scale, y: mapRect.y + p.y * scale });

  // 找一个"认到了建筑位"的地点（大圈骑在蓝/绿小圈上）
  const spotCand = c1.spots.filter(s => s.matched && ['大', '小'].includes(s.matched.attachSize));
  const spotTarget = spotCand.find(s => s.matched.attachId === 109) || spotCand[0];
  const sp = toScreen(spotTarget);
  console.log('spot target attach', spotTarget.matched.attachId, spotTarget.sp.tile, 'px', sp);

  // 6 悬停地点大圈
  await moveTo(sp.x - 70, sp.y + 50, 14, 20);
  await moveTo(sp.x, sp.y, 22, 30);
  await sleep(800);
  await shot('06_hover', { attachId: spotTarget.matched.attachId });

  // 7 点选地点 → 右栏高亮
  await clickAt(sp.x, sp.y);
  await sleep(1200);
  await shot('07_spotselected', { attachId: spotTarget.matched.attachId });

  // 8 双击大圈 → 换建筑
  await dblclickAt(sp.x, sp.y);
  await sleep(1400);
  await shot('08_tilepicker', { attachId: spotTarget.matched.attachId });

  // 9 换一个建筑（挑一个跟现在不一样的；换完点空白处收起选择条）
  const nPick = await evaluate(`document.querySelectorAll('#picker .pick[data-i]').length`);
  await click(`#picker .pick[data-i="${Math.min(2, nPick - 1)}"]`);
  await sleep(1800);
  const tileNow = await evaluate(`(()=>{const on=document.querySelector('#inspector table.spots tr.on');return on?on.children[0].textContent:'';})()`);
  console.log('tile after change:', tileNow);
  await clickAt(mapRect.x + 28, mapRect.y + 28); // 空白处：收起选择条 + 取消选中
  await sleep(900);
  await shot('09_tilechanged', { tile: tileNow });

  // 10 改属性变体
  const vr = await evaluate(`(()=>{
    const rows=[...document.querySelectorAll('#inspector table.spots tr[data-row]')];
    const prefer=rows.find(r=>r.children[1] && r.children[1].textContent.trim()==='109');
    const tr=prefer||rows.find(r=>r.querySelector('input[data-var-row]'))||rows[0];
    if(!tr)return null;
    const pick=tr.querySelector('input[data-var-row]');
    if(!pick)return null;
    pick.scrollIntoView({block:'center'});
    const b=pick.getBoundingClientRect();
    return {row:+pick.dataset.varRow,x:b.x,y:b.y,w:b.width,h:b.height};
  })()`);
  if (vr) {
    await sleep(500);
    await clickAt(vr.x + vr.w / 2, vr.y + vr.h / 2);
    await sleep(300);
    await evaluate(`(()=>{const i=document.querySelector('#inspector input[data-var-row="${vr.row}"]');i.value='3';i.blur();})()`);
    await sleep(1600);
    await shot('10_variant');
  }

  // 11-12 缩圈预览 / 落定
  const dr = await evaluate(`(()=>{const b=document.querySelector('#inspector .drop[data-key="pa1"] .dbtn');if(!b)return null;b.scrollIntoView({block:'center'});const r=b.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})()`);
  if (dr) {
    await sleep(400);
    await clickAt(dr.x + dr.w / 2, dr.y + dr.h / 2);
    await sleep(900);
    const list = await evaluate(`(()=>{const its=[...document.querySelectorAll('#inspector .drop[data-key="pa1"] .aitem')];return its.slice(0,6).map(e=>{const r=e.getBoundingClientRect();return {id:+e.dataset.id,x:r.x,y:r.y,w:r.width,h:r.height};});})()`);
    const it = list && (list[3] || list[1]);
    if (it) {
      await moveTo(it.x + it.w / 2, it.y + it.h / 2, 16, 26);
      await sleep(1000);
      await shot('11_area_preview');
      await clickAt(it.x + it.w / 2, it.y + it.h / 2);
      await sleep(1800);
      await shot('12_area_set');
    }
  }

  // 13-15 地形切换
  for (const [sid, name] of [[1, '13_mountain'], [2, '14_crater'], [5, '15_shroud']]) {
    await evaluate(`(()=>{const e=document.querySelector('.srow[data-sid="${sid}"]');if(e)e.scrollIntoView({block:'center'});})()`);
    await sleep(500);
    await click(`.srow[data-sid="${sid}"]`, 60, 0);
    await sleep(2800);
    await shot(name);
  }

  // 16-17 在"有点位空着"的种子里加一个地点（set 1004 / pid 1005，大空洞）
  await evaluate(`(()=>{const e=document.querySelector('.srow[data-sid="1004"]');if(e)e.scrollIntoView({block:'center'});})()`);
  await sleep(600);
  await click('.srow[data-sid="1004"]', 60, 0);
  await sleep(1600);
  await shot('16_gh_set');
  await evaluate(`(()=>{const b=document.querySelector('.pbtn[data-pid="1005"]');if(b)b.scrollIntoView({block:'center'});})()`);
  await sleep(500);
  await click('.pbtn[data-pid="1005"]');
  await sleep(3000);
  await shot('17_gh_seed');

  const tree2 = await getJson('http://127.0.0.1:8779/api3/tree');
  const c2 = circlesOf(tree2);
  await resetScroll();
  const mapRect2 = await rrect('#map');
  const scale2 = mapRect2.w / MAP_W;
  const free = c2.anchorsPx.filter(a => c2.spots.every(s => Math.hypot(s.x - a.x, s.y - a.y) > 46));
  console.log('free anchors', free.length, free.slice(0, 6).map(a => a.a.attachId).join(','));
  const targetAnchor = free.find(a => a.a.attachSize === '大') || free[0];
  if (targetAnchor) {
    const p = { x: mapRect2.x + targetAnchor.x * scale2, y: mapRect2.y + targetAnchor.y * scale2 };
    await moveTo(p.x - 60, p.y + 40, 14, 20);
    await moveTo(p.x, p.y, 20, 26);
    await sleep(700);
    await shot('18_gh_hover', { attachId: targetAnchor.a.attachId });
    await clickAt(p.x, p.y);
    await sleep(1500);
    await shot('19_gh_picker', { attachId: targetAnchor.a.attachId });
    await click('#picker .pick[data-i="0"]');
    await sleep(1800);
    const spotsNow = await evaluate(`document.querySelector('#inspector .kv').textContent.replace(/\\s+/g,' ')`);
    console.log('after add:', spotsNow);
    await clickAt(mapRect2.x + 28, mapRect2.y + 28); // 收起选择条
    await sleep(900);
    await shot('20_gh_added');
  } else {
    console.log('no free anchor on 1005?!');
  }

  // 21 撤销
  await click('#btnUndo');
  await sleep(1400);
  await shot('21_undo');

  // 22 新建 set 面板
  await click('#btnNewSet');
  await sleep(1000);
  await shot('22_newset');
  const cancel = await rrect('#nsCancel');
  if (cancel) await clickAt(cancel.x + cancel.w / 2, cancel.y + cancel.h / 2);
  await sleep(700);

  // 23 保存
  await click('#btnSave');
  for (let i = 0; i < 150; i++) {
    const txt = await evaluate(`document.getElementById('toast').textContent`).catch(() => '');
    if (txt && txt.indexOf('已保存') >= 0) { console.log('save toast:', txt); break; }
    await sleep(250);
  }
  await sleep(250);
  await shot('23_saved');
  await sleep(2800);
  await shot('24_final');

  ws.close();
  console.log('done', shotIdx);
})();
