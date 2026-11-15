// 用 CDP 在真浏览器里跑一遍「拖动排序」，验证前端事件处理 + /api/move 闭环
const http = require('http');

const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});

(async () => {
  const targets = await getJson('http://127.0.0.1:9333/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8777'));
  if (!page) { console.log('NO_PAGE', JSON.stringify(targets.map(t => [t.type, t.url]))); process.exit(1); }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => {
    const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
  });

  await send('Runtime.enable', {});

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const chips = () => [...document.querySelectorAll('#chips .chip')];
    const label = c => (c.dataset.i + ':' + ((c.querySelector('img') || {}).getAttribute ? c.querySelector('img').getAttribute('src') : 'txt'));
    for (let k = 0; k < 40 && chips().length < 3; k++) await wait(200);
    const n = chips().length;
    if (n < 3) return { error: 'chips<3', n };
    const before = chips().map(label);
    const dt = new DataTransfer();
    const c0 = chips()[0], c2 = chips()[2];
    c0.dispatchEvent(new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: dt }));
    const r = c2.getBoundingClientRect();
    const at = { clientX: r.left + r.width - 1, clientY: r.top + r.height / 2 };
    c2.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt, ...at }));
    const hint = c2.className;
    c2.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt, ...at }));
    c0.dispatchEvent(new DragEvent('dragend', { bubbles: true, cancelable: true, dataTransfer: dt }));
    await wait(2000);
    const after = chips().map(label);
    return { before, after, hintClassDuringDrag: hint, undoDisabled: document.getElementById('btnUndo').disabled };
  })()`;

  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.value ? r.result.value : r, null, 2));
  ws.close();
})();
