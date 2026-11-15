// 看圆圈构成：有多少大圈/小圈、颜色分布
const http = require('http');
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});
(async () => {
  const targets = await getJson('http://127.0.0.1:9336/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable', {});
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 6000));
  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    for (let k = 0; k < 40 && !document.querySelector('.srow'); k++) await wait(200);
    const tr = await (await fetch('/api3/tree')).json();
    return {
      spots: (tr.pidInfo && tr.pidInfo.spotView || []).length,
      anchors: (tr.anchors || []).length,
      circles: typeof CIRCLES !== 'undefined' ? CIRCLES.map(c => c.kind) : null,
      kinds: typeof CIRCLES !== 'undefined' ? CIRCLES.reduce((a, c) => (a[c.kind] = (a[c.kind]||0)+1, a), {}) : null,
      colors: typeof CIRCLES !== 'undefined' ? CIRCLES.reduce((a, c) => (a[c.color] = (a[c.color]||0)+1, a), {}) : null,
    };
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.result ? r.result.result.value : r, null, 2));
  ws.close();
})();
