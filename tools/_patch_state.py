import io

p = 'app/web/app.js'
s = io.open(p, encoding='utf-8').read()

start = s.index('function renderArea() {')
end = s.index('function renderChips() {')
new = '''function renderArea() {
  const pa = S.playarea;
  const card = $('cardArea');
  if (!pa) { card.hidden = true; return; }
  card.hidden = false;

  const c = pa.cur || {};
  const t = pa.curText || {};
  $('areaCur').innerHTML =
    (pa.isTemplate ? '<span class="tag">模板</span> ' : '')
    + `1缩 <b>${c.pa1 ?? '—'}</b> · 2缩 <b>${c.pa2 ?? '—'}</b><br>`
    + `<span class="muted">${t.pa1 || ''} / ${t.pa2 || ''}</span><br>`
    + `1夜 <b>${c.nb1 ?? '—'}</b> · 2夜 <b>${c.nb2 ?? '—'}</b><br>`
    + `<span class="muted">${t.nb1 || ''} / ${t.nb2 || ''}</span>`;

  const opt = (list, cur, fmt) => {
    const head = `<option value="">（跟模板）</option>`;
    return head + list.map(x => {
      const sel = String(x.id) === String(cur) ? ' selected' : '';
      return `<option value="${x.id}"${sel}>${fmt(x)}</option>`;
    }).join('');
  };

  const rows = [
    ['pa1', '1缩', opt(pa.areas, c.pa1, x => `${x.id} ${x.name}`)],
    ['pa2', '2缩', opt(pa.areas, c.pa2, x => `${x.id} ${x.name}`)],
    ['nb1', '1夜', opt(pa.nights, c.nb1, x => x.name)],
    ['nb2', '2夜', opt(pa.nights, c.nb2, x => x.name)],
  ];
  $('areaSel').innerHTML = rows.map(([k, label, html]) =>
    `<label class="arow"><span>${label}</span>
       <select data-k="${k}">${html}</select></label>`).join('');

  $('areaSel').querySelectorAll('select').forEach(sel => {
    sel.onchange = async () => {
      const body = {};
      body[sel.dataset.k] = sel.value === '' ? null : +sel.value;
      const res = await api('/api/playarea', body);
      applyState(res);
    };
  });
}

'''
s = s[:start] + new + s[end:]
io.open(p, 'w', encoding='utf-8').write(s)
print('app.js ok')
