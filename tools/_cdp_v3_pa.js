// 验证：孪生匹配后的小圈数量 + 缩圈预览；并截图
const http = require('http');
const fs = require('fs');
const getJson = (u) => new Promise((res, rej) => {
  http.get(u, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej);
});
(async () => {
  const targets = await getJson('http://127.0.0.1:9337/json');
  const page = targets.find(t => t.type === 'page' && t.url.includes('8779'));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = new Map();
  ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  await new Promise(r => ws.onopen = r);
  const send = (method, params) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  await send('Runtime.enable', {}); await send('Page.enable', {});
  await send('Emulation.setDeviceMetricsOverride', { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: 'http://127.0.0.1:8779/' });
  await new Promise(r => setTimeout(r, 7000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    for (let k = 0; k < 40 && !document.querySelector('.srow'); k++) await wait(200);
    let w0=-1,w1=-1; const cv = document.getElementById('map');
    for (let k=0;k<30;k++){w0=cv.getBoundingClientRect().width;await wait(200);w1=cv.getBoundingClientRect().width;if(w0===w1&&w0>100)break;}
    const tr = await (await fetch('/api3/tree')).json();
    const out = {
      selPid: tr.selPid, terrain: tr.terrain,
      spots: (tr.pidInfo && tr.pidInfo.spotView || []).length,
      anchors: (tr.anchors || []).length,
      kinds: CIRCLES.reduce((a,c)=>(a[c.kind]=(a[c.kind]||0)+1,a),{}),
      playareas: (tr.playareas || []).length,
      areaIds: (tr.playareas || []).map(p => p.id),
      pa: tr.pidInfo ? [tr.pidInfo.playarea.playArea1, tr.pidInfo.playarea.playArea2] : null,
    };
    // 打开 1缩 下拉，悬停到第 3 个候选，看 PREVIEW 是否生效
    const drop = document.querySelector('#inspector .drop[data-key="pa1"]');
    if (drop) {
      drop.querySelector('.dbtn').click();
      await wait(200);
      const items = drop.querySelectorAll('.aitem');
      if (items.length > 2) {
        items[2].dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
        await wait(200);
        out.preview = PREVIEW;
      }
    }
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result && r.result.result ? r.result.result.value : r, null, 2));

  await send('Runtime.evaluate', { expression: `(async()=>{const d=document.querySelector('#inspector .drop[data-key="pa1"]');if(d){const items=d.querySelectorAll('.aitem');if(items.length>2){items[2].dispatchEvent(new MouseEvent('mouseenter',{bubbles:true}));}}await new Promise(r=>setTimeout(r,600));})()`, awaitPromise: true });
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(process.argv[2] || 'work/_ui_v3_pa.png', Buffer.from(shot.result.data, 'base64'));
  console.log('saved');
  ws.close();
})();
