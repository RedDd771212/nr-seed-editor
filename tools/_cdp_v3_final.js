// 一步到位：先选中 pid → 打开页面 → 统计圆圈 → 点大圈 → 截图
const http = require('http');
const fs = require('fs');

function post(u, body) {
  return new Promise((res, rej) => {
    const data = Buffer.from(JSON.stringify(body || {}), 'utf8');
    const req = http.request(u, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': data.length } },
      r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); });
    req.on('error', rej); req.write(data); req.end();
  });
}
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});

(async () => {
  const sel = await post('http://127.0.0.1:8779/api3/select', { pid: Number(process.argv[2] || 156) });
  console.log('服务端选中 pid=', sel.selPid, 'set=', sel.selSet);

  const targets = await getJson('http://127.0.0.1:9336/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable', {});
  await send('Page.enable', {});
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 7000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const cv = document.getElementById('map');
    for (let k = 0; k < 40 && !document.querySelector('.srow'); k++) await wait(200);
    let w0=-1,w1=-1;
    for (let k=0;k<30;k++){w0=cv.getBoundingClientRect().width;await wait(200);w1=cv.getBoundingClientRect().width;if(w0===w1&&w0>100)break;}
    const tr = await (await fetch('/api3/tree')).json();
    const sp = (tr.pidInfo && tr.pidInfo.spotView || [])[0];
    const out = {
      spots: (tr.pidInfo && tr.pidInfo.spotView || []).length,
      kinds: CIRCLES.reduce((a,c)=>(a[c.kind]=(a[c.kind]||0)+1,a),{}),
      colors: CIRCLES.reduce((a,c)=>(a[c.color]=(a[c.color]||0)+1,a),{}),
    };
    if (sp) {
      const r = cv.getBoundingClientRect();
      cv.dispatchEvent(new MouseEvent('click', {
        clientX: r.left + sp.px * r.width / cv.width,
        clientY: r.top + sp.py * r.height / cv.height, bubbles: true }));
      await wait(600);
      out.onRows = document.querySelectorAll('table.spots tr.on').length;
      out.sel = SEL ? SEL.kind : null;
      // 同位置的建筑位不应该再画小圈
      out.samePosAnchorDrawn = CIRCLES.filter(c => c.kind==='anchor' &&
        Math.abs(c.anchor.world[0]-sp.world[0])<14 && Math.abs(c.anchor.world[1]-sp.world[1])<14).length;
    }
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.result ? r.result.result.value : r, null, 2));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(process.argv[3] || 'work/_ui_v3_final.png', Buffer.from(shot.result.data, 'base64'));
  console.log('saved');
  ws.close();
})();
