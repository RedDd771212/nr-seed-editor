// 截图：手输一个不存在的 variationId（看虚线"手"格 + 黄字提醒）
// 用法：node tools/_cdp_var_shot.js <调试端口> "<页面URL>" <输出png>
const http = require('http');
const fs = require('fs');
const PORT = Number(process.argv[2] || 9334);
const URL_TO_OPEN = process.argv[3] || 'http://127.0.0.1:8777/?anchor=109&pick=3410';
const OUT = process.argv[4] || 'work/_ui_var.png';

const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});

(async () => {
  const targets = await getJson(`http://127.0.0.1:${PORT}/json`);
  const page = targets.find(t => t.type === 'page' && t.url.includes('8777'));
  if (!page) { console.log('NO_PAGE'); process.exit(1); }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => {
    const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p }));
  });

  await send('Runtime.enable', {});
  await send('Page.enable', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: URL_TO_OPEN });
  await new Promise(r => setTimeout(r, 6000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const $ = id => document.getElementById(id);
    for (let k = 0; k < 60 && !$('btnVarAdd'); k++) await wait(200);
    if (!$('btnVarAdd')) return 'no btnVarAdd';
    $('btnVarAdd').click();
    await wait(200);
    const inp = $('varInput');
    inp.value = '9';
    inp.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await wait(1500);
    const on = document.querySelector('#varStrip .vpick.on');
    return (on ? on.textContent.replace(/\\s+/g, ' ') : 'none') + ' | warn=' + !!document.querySelector('.warnline');
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result && r.result.exceptionDetails) console.log('EXC', JSON.stringify(r.result.exceptionDetails));
  console.log('页面状态:', JSON.stringify(r.result && r.result.value));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(OUT, Buffer.from(shot.result.data, 'base64'));
  console.log('saved', OUT);
  ws.close();
})();
