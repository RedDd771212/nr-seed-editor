// 用 CDP 在真浏览器里跑「手输 variationId」：＋ 按钮 → 填数字 → 回车 → 加入草稿
// 用法：node tools/_cdp_var_test.js <调试端口> "<页面URL>"
const http = require('http');
const PORT = Number(process.argv[2] || 9334);
const URL_TO_OPEN = process.argv[3] || 'http://127.0.0.1:8777/?anchor=109&pick=3410';

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
  const send = (method, params) => new Promise(r => {
    const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params }));
  });
  await send('Runtime.enable', {});

  // 重新载入，保证状态是「刚打开的锚点」
  await send('Page.navigate', { url: URL_TO_OPEN });
  await new Promise(r => setTimeout(r, 6000));

  const expr = `(async () => {
    const wait = ms => new Promise(r => setTimeout(r, ms));
    const $ = id => document.getElementById(id);
    const chipInfo = () => {
      const el = document.querySelector('#varStrip .vpick.on');
      if (!el) return null;
      return { v: el.getAttribute('data-v'), manual: el.classList.contains('manual'), txt: el.textContent.trim().replace(/\\s+/g, ' ') };
    };
    const out = { steps: [] };
    for (let k = 0; k < 60 && !$('btnVarAdd'); k++) await wait(200);
    out.steps.push(['手输按钮出现', !!$('btnVarAdd')]);
    if (!$('btnVarAdd')) return out;
    out.headerBefore = (document.querySelector('#infoBody .bhead .muted') || {}).textContent;

    // 1) 手输「真实存在」的一档：3410 的 variationId 3 = 冻伤
    $('btnVarAdd').click();
    await wait(150);
    const inp1 = $('varInput');
    out.steps.push(['输入框出现', !!inp1]);
    inp1.value = '3';
    inp1.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await wait(1300);
    out.warnAfterGood = !!document.querySelector('.warnline');
    out.selectedAfterGood = chipInfo();
    out.headerAfterGood = (document.querySelector('#infoBody .bhead .muted') || {}).textContent;
    out.addBtnBack = !!$('btnVarAdd');

    // 2) 手输一个「不存在」的档位 9
    $('btnVarAdd').click();
    await wait(150);
    const inp2 = $('varInput');
    inp2.value = '9';
    inp2.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await wait(1300);
    out.warnAfterBad = !!document.querySelector('.warnline');
    out.selectedAfterBad = chipInfo();
    out.headerAfterBad = (document.querySelector('#infoBody .bhead .muted') || {}).textContent;

    // 3) 回到 3，加入草稿
    $('btnVarAdd').click();
    await wait(150);
    const inp3 = $('varInput');
    inp3.value = '3';
    inp3.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await wait(1300);
    const btn = [...document.querySelectorAll('#infoBody button')].find(b => b.textContent.includes('加入草稿'));
    out.steps.push(['加入草稿按钮', !!btn]);
    if (btn) { btn.click(); await wait(2200); }
    out.draftChips = [...document.querySelectorAll('#chips .chip')].length;
    return out;
  })()`;

  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result && r.result.exceptionDetails) console.log('EXC', JSON.stringify(r.result.exceptionDetails));
  console.log(JSON.stringify(r.result && r.result.value ? r.result.value : r, null, 2));
  ws.close();
})();
