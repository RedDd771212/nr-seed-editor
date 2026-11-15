import io

p = r'app\web\app.js'
s = io.open(p, encoding='utf-8').read()

render = '''
async function renderTests() {
  const r = await api('/api/tests');
  const list = (r.tests || []).slice().reverse();
  const card = $('cardTests');
  if (!list.length) { card.hidden = true; return; }
  card.hidden = false;
  $('testCount').textContent = `共 ${list.length} 次`;
  $('testList').innerHTML = list.slice(0, 12).map(t => {
    const rows = (t.rows || []).map(e => `${e.modifierSet}:${e.eventFlag}/${e.modifier}`).join(' · ');
    return `<div class="trow" title="${rows}">
      <span class="twhen">${t.ts.slice(4, 6)}-${t.ts.slice(6, 8)} ${t.ts.slice(9, 11)}:${t.ts.slice(11, 13)}</span>
      <span class="tpid">pid ${t.patternId}</span>
      <span class="tflags">${(t.rows || []).length} 行</span>
    </div>`;
  }).join('');
}
'''

s = s.replace("/* ---------- 状态 ---------- */", render + "\n/* ---------- 状态 ---------- */", 1)
s = s.replace("  renderEvents(res);", "  renderEvents(res);\n  renderTests();", 1)
io.open(p, 'w', encoding='utf-8').write(s)
print('patched', 'renderTests' in s, s.count('renderTests();'))
