// 调试：看看圈有没有建出来、点击坐标算得对不对
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
  const expr = `(async () => {
    const tree = await (await fetch('/api3/tree')).json();
    const cv = document.getElementById('map');
    const rect = cv.getBoundingClientRect();
    const sp = (tree.pidInfo && tree.pidInfo.spotView || [])[0];
    return {
      hasT: typeof T !== 'undefined' && !!T,
      nCircles: typeof CIRCLES !== 'undefined' ? CIRCLES.length : 'undefined',
      first3: typeof CIRCLES !== 'undefined' ? CIRCLES.slice(0,3).map(c => ({kind:c.kind,x:c.x,y:c.y,r:c.r})) : null,
      rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
      cvSize: [cv.width, cv.height],
      sp0: sp ? {px: sp.px, py: sp.py} : null,
      hlPointer: getComputedStyle(document.getElementById('hl')).pointerEvents,
      onRows: document.querySelectorAll('table.spots tr[data-row]').length,
    };
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.result ? r.result.result.value : r, null, 2));
  ws.close();
})();
