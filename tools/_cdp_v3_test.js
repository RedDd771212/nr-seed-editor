// 真浏览器点一遍 v3 的「新建 set」表单
const http = require('http');
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});
(async () => {
  const targets = await getJson('http://127.0.0.1:9335/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  if (!page) { console.log('NO_PAGE'); process.exit(1); }
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable', {});
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 5000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const $ = id => document.getElementById(id);
    const out = { steps: [] };
    for (let k = 0; k < 40 && !$('tree')?.children.length; k++) await wait(200);
    out.steps.push(['树已加载', !!$('tree') && $('tree').children.length > 0]);
    $('btnNewSet').click();
    await wait(300);
    out.steps.push(['新建表单出现', !!$('nsGo') && !!$('nsBoss')]);
    if (!$('nsGo')) return out;
    $('nsBoss').value = '3';
    $('nsRare').value = '5';
    $('nsName').value = 'UI测试隐城Maris';
    $('nsPools').checked = true;
    $('nsGo').click();
    await wait(4000);
    out.toast = ($('toast') || {}).textContent;
    out.selSet = (window.T || {}).selSet;
    out.sets = (window.T || {}).sets ? window.T.sets.length : null;
    const last = (window.T && window.T.sets) ? window.T.sets[window.T.sets.length - 1] : null;
    out.lastSet = last ? { sid: last.sid, name: last.name, count: last.count } : null;
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  const v = r.result && r.result.result ? r.result.result.value : (r.result ? r.result.value : null);
  console.log(JSON.stringify(v || r, null, 2));
  ws.close();
})();
