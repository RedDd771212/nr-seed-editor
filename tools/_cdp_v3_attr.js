// 验证属性小图标出现在地点表 + 换建筑选择条里；并截图
const http = require('http');
const fs = require('fs');
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});
(async () => {
  const targets = await getJson('http://127.0.0.1:9339/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (m, p) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method: m, params: p })); });
  await send('Runtime.enable', {}); await send('Page.enable', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 7000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    for (let k = 0; k < 40 && !document.querySelector('.srow'); k++) await wait(200);
    const out = {};
    out.attrMiniInTable = document.querySelectorAll('table.spots img.attrmini').length;
    const link = document.querySelector('table.spots a.link');
    if (link) { link.click(); await wait(1500); }
    out.pickerShown = !document.getElementById('picker').hidden;
    out.pickerAttrs = document.querySelectorAll('#picker .pick img.attr').length;
    out.pickerPicks = document.querySelectorAll('#picker .pick').length;
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.result ? r.result.result.value : r, null, 2));

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(process.argv[2] || 'work/_ui_v3_attr.png', Buffer.from(shot.result.data, 'base64'));
  console.log('saved');
  ws.close();
})();
