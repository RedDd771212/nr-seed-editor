// 通用：在页面里跑一段 JS 并打印结果。用法: node tools/_cdp_eval.js "<js>"
const http = require('http');
const getJson = (u) => new Promise((res, rej) => { http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej); });
(async () => {
  const list = await getJson('http://127.0.0.1:9333/json/list');
  const page = list.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p || {} })); });
  await send('Runtime.enable');
  const r = await send('Runtime.evaluate', { expression: process.argv[2], returnByValue: true, awaitPromise: true });
  console.log(JSON.stringify(r.result.result.value));
  if (r.exceptionDetails) console.log('EXC', r.exceptionDetails.text);
  ws.close();
})();
