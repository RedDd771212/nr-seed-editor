// 真浏览器验证：点大圈 → 高亮（右侧表格行变亮）+ 截图
const http = require('http');
const fs = require('fs');
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});
(async () => {
  const targets = await getJson('http://127.0.0.1:9336/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  if (!page) { console.log('NO_PAGE'); process.exit(1); }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable', {});
  await send('Page.enable', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 6000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const out = {};
    for (let k = 0; k < 40 && !document.querySelector('.srow'); k++) await wait(200);
    const cv = document.getElementById('map');
    // 等布局稳定（fit() 可能被 resize 触发，宽高会变）
    let w0 = -1, w1 = -1;
    for (let k = 0; k < 30; k++) {
      w0 = cv.getBoundingClientRect().width;
      await wait(200);
      w1 = cv.getBoundingClientRect().width;
      if (w0 === w1 && w0 > 100) break;
    }
    const tree = await (await fetch('/api3/tree')).json();
    out.selPid = tree.selPid;
    const sp = (tree.pidInfo && tree.pidInfo.spotView || [])[0];
    if (!sp) return { err: 'no spot' };
    const rect = cv.getBoundingClientRect();
    const cx = rect.left + sp.px * rect.width / cv.width;
    const cy = rect.top + sp.py * rect.height / cv.height;
    out.rect = { w: Math.round(rect.width), h: Math.round(rect.height) };
    out.clickedAt = [Math.round(cx), Math.round(cy)];
    cv.dispatchEvent(new MouseEvent('click', { clientX: cx, clientY: cy, bubbles: true }));
    await wait(600);
    out.onRows = document.querySelectorAll('table.spots tr.on').length;
    out.sel = typeof SEL !== 'undefined' && SEL ? SEL.kind : null;
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  const v = r.result && r.result.result ? r.result.result.value : r.result.value;
  console.log(JSON.stringify(v, null, 2));

  // 回到选中地点那一下再截图（第二次点小圈会改选择）
  await send('Runtime.evaluate', { expression: `(async()=>{const t=await (await fetch('/api3/tree')).json();const sp=t.pidInfo.spotView[0];const cv=document.getElementById('map');const r=cv.getBoundingClientRect();cv.dispatchEvent(new MouseEvent('click',{clientX:r.left+sp.px*r.width/cv.width,clientY:r.top+sp.py*r.height/cv.height,bubbles:true}));await new Promise(x=>setTimeout(x,800));})()`, awaitPromise: true });
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(process.argv[2] || 'work/_ui_v3_final.png', Buffer.from(shot.result.data, 'base64'));
  console.log('saved');
  ws.close();
})();
