/* teaching-hub 前端：hash 路由的小型 SPA（无框架、无构建） */

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

const HUB = { data: null };
const JUDGES = [
  {label: 'DeepSeek V4 Pro（最稳）', provider: 'deepseek', model: 'deepseek-v4-pro'},
  {label: 'DeepSeek Flash（快、便宜）', provider: 'deepseek', model: 'deepseek-flash'},
  {label: 'Kimi K2.6（便宜）', provider: 'kimi', model: 'kimi-k2.6'},
  {label: 'GLM 4.6（严格、慢）', provider: 'zai', model: 'glm-4.6'},
];

/* ---------------- 路由 ---------------- */
function parseHash() {
  const h = location.hash.replace(/^#/, '') || '/';
  const [pathPart, queryPart] = h.split('?');
  const query = {};
  if (queryPart) queryPart.split('&').forEach(kv => {
    const [k, v] = kv.split('=');
    query[decodeURIComponent(k)] = decodeURIComponent(v || '');
  });
  return {segs: pathPart.split('/').filter(Boolean), query};
}

async function router() {
  if (!HUB.data) HUB.data = await api('/api/data');
  const {segs, query} = parseHash();
  $$('.nav a').forEach(a => a.classList.remove('on'));
  const key = segs[0] || 'home';
  const el = $(`.nav a[data-nav="${key}"]`);
  if (el) el.classList.add('on');
  const app = $('#app');
  if (!segs.length) return renderHome(app);
  if (segs[0] === 'p' && segs[1]) return renderProject(app, segs[1]);
  if (segs[0] === 'library') return renderLibrary(app, query);
  if (segs[0] === 'mark') return renderMark(app, query);
  if (segs[0] === 'help') return renderHelp(app);
  app.innerHTML = '<div class="empty">页面不存在</div>';
}
window.addEventListener('hashchange', router);

/* ---------------- 总览 ---------------- */
function renderHome(app) {
  const projects = HUB.data.projects || [];
  app.innerHTML = `
    <h1>总览</h1>
    <div class="sub">${projects.length} 个项目 · 资料根目录见 /api/ping</div>
    ${projects.map(p => `
      <div class="card">
        <div style="display:flex;align-items:baseline;gap:10px">
          <a href="#/p/${encodeURIComponent(p.id)}"><b>${esc(p.name)}</b></a>
          <span class="pill">${esc(p.status || '')}</span>
          <span style="margin-left:auto;color:var(--muted)">进度 ${p.progress || 0}%</span>
        </div>
        <div class="sub">${esc(p.subtitle || '')}</div>
        <div style="margin-top:8px">${(p.sections || []).map(s =>
          `<div class="rowitem">· ${esc(s.title)} <span class="sub">${(s.blocks || []).length} 个知识点/案例</span></div>`
        ).join('') || '<div class="empty">还没有节次</div>'}</div>
      </div>`).join('') || '<div class="empty">workspace.json 里还没有项目</div>'}`;
}

function findProject(pid) {
  return (HUB.data.projects || []).find(p => String(p.id) === String(pid));
}

function renderProject(app, pid) {
  const p = findProject(pid);
  if (!p) { app.innerHTML = '<div class="empty">项目不存在</div>'; return; }
  app.innerHTML = `
    <h1>${esc(p.name)}</h1>
    <div class="sub">${esc(p.subtitle || '')} · 进度 ${p.progress || 0}%</div>
    <div class="card">${esc(p.notes || '')}</div>
    ${(p.sections || []).map(s => `
      <div class="card">
        <h3>${esc(s.title)} <span class="pill">${esc(s.status || 'draft')}</span></h3>
        <div class="sub">${esc(s.path || '')}</div>
        ${(s.blocks || []).map(b => `<div class="rowitem">
          <b>${esc(b.title)}</b> <span class="sub">[${esc(b.kind || '')}]</span>
          <div>${esc(b.body || '')}</div>
          ${(b.refs || []).map(r => `<div class="sub">↳ ${esc(r)}</div>`).join('')}
        </div>`).join('') || '<div class="empty">还没有内容块</div>'}
        <div style="margin-top:8px">
          <a class="btn" href="#/library?q=${encodeURIComponent(s.title)}">🔎 找这节课的资料</a>
          <a class="btn" href="#/mark?project=${encodeURIComponent(p.id)}&section=${encodeURIComponent(s.id)}">✍️ 批改这一节</a>
        </div>
      </div>`).join('')}`;
}

/* ---------------- 资源库 ---------------- */
async function renderLibrary(app, query) {
  const q = query.q || '';
  app.innerHTML = `<h1>资源库</h1>
    <div class="card">
      <input id="lib-q" value="${esc(q)}" placeholder="搜文件名或文档正文…"
             onkeydown="if(event.key==='Enter'){location.hash='#/library?q='+encodeURIComponent(this.value)}">
      <div class="sub" id="lib-state" style="margin-top:6px">输入关键词后回车</div>
    </div>
    <div id="lib-out"></div>`;
  if (!q) return;
  $('#lib-state').textContent = '搜索中…';
  try {
    const r = await api('/api/search?q=' + encodeURIComponent(q) + '&limit=80');
    $('#lib-state').textContent = `命中 ${r.total} 个文件，显示前 ${r.results.length}`;
    $('#lib-out').innerHTML = `<div class="card"><table>
      <tr><th>文件</th><th>路径</th><th>命中片段</th></tr>
      ${r.results.map(x => `<tr>
        <td><a href="/${encodeURI(x.path)}" target="_blank">${esc(x.name)}</a>
            <div class="sub">${esc(x.ext)} · ${(x.size / 1024).toFixed(1)} KB</div></td>
        <td class="sub">${esc(x.path)}</td>
        <td class="sub">${esc(x.snippet)}</td></tr>`).join('')}
    </table></div>`;
  } catch (e) { $('#lib-state').innerHTML = '<span class="warn">' + esc(e.message) + '</span>'; }
}

/* ---------------- ✍️ 批改台 ---------------- */
async function renderMark(app, query) {
  const projects = HUB.data.projects || [];
  const pid = query.project || (projects[0] && projects[0].id) || '';
  const proj = findProject(pid) || null;
  const secs = (proj && proj.sections) || [];
  const sid = query.section || '';
  app.innerHTML = `
    <h1>✍️ 批改台</h1>
    <div class="sub">按评分标准逐小问打分，指出失分点。<b>分数用于发现问题，不要当最终成绩</b>——
      实测换评委能差 4–6 分（满分 125）。</div>

    <div class="card">
      <div class="grid2">
        <label>项目<br><select id="mk-proj">
          ${projects.map(p => `<option value="${p.id}"${p.id === pid ? ' selected' : ''}>${esc(p.name)}</option>`).join('')}
        </select></label>
        <label>节次（用于错项画像）<br><select id="mk-sec">
          <option value="">（不绑定）</option>
          ${secs.map(s => `<option value="${s.id}"${s.id === sid ? ' selected' : ''}>${esc(s.title)}</option>`).join('')}
        </select></label>
      </div>
      <label style="display:block;margin-top:10px">题目（粘贴，或填资料库相对路径）</label>
      <textarea id="mk-q" rows="4" placeholder="粘贴题目"></textarea>
      <input id="mk-qfile" placeholder="或：题目文件路径，如 courses/week3/exam.md" style="margin-top:4px">
      <label style="display:block;margin-top:10px">评分标准 markscheme（粘贴，或填路径）</label>
      <textarea id="mk-ms" rows="5" placeholder="粘贴评分标准"></textarea>
      <input id="mk-msfile" placeholder="或：评分标准文件路径" style="margin-top:4px">
      <div class="grid3" style="margin-top:10px">
        <label>小问与分值（逗号分隔）<br><input id="mk-parts" placeholder="1(a) [10], 1(b) [15]"></label>
        <label>总分（留空自动算）<br><input id="mk-outof" placeholder="25"></label>
        <label>评委模型<br><select id="mk-judge">
          ${JUDGES.map((j, i) => `<option value="${i}">${esc(j.label)}</option>`).join('')}
        </select></label>
      </div>
      <label style="display:block;margin-top:10px">学生答案</label>
      <textarea id="mk-ans" rows="10" placeholder="粘贴学生答案全文"></textarea>
      <div style="margin-top:10px">
        <label>学生标记（可选）<input id="mk-student" style="width:200px"></label>
        <button class="btn primary" id="mk-go" style="margin-left:10px">开始批改</button>
        <span class="sub" id="mk-status" style="margin-left:8px"></span>
      </div>
    </div>
    <div id="mk-result"></div>
    <div class="card"><h3>📉 错项画像（得分率低的排前面）</h3><div id="mk-diag">加载中…</div></div>
    <div class="card"><h3>🕘 最近批改</h3><div id="mk-history">加载中…</div></div>`;

  $('#mk-proj').onchange = e => { location.hash = '#/mark?project=' + e.target.value; };
  $('#mk-go').onclick = mkSubmit;
  mkSide();
}

async function mkSide() {
  try {
    const d = await api('/api/diagnostics');
    $('#mk-diag').innerHTML = (d.rows || []).length ? `<table>
      <tr><th>项目</th><th>节次</th><th>次数</th><th>平均分</th><th>最常失分</th></tr>
      ${d.rows.slice(0, 12).map(r => `<tr>
        <td>${esc((findProject(r.project) || {}).name || r.project)}</td>
        <td>${esc(r.section)}</td><td>${r.attempts}</td>
        <td>${r.marks}/${r.out_of}（${(r.score_rate * 100).toFixed(0)}%）</td>
        <td>${(r.lost_parts || []).map(kv => esc(kv[0]) + '×' + kv[1]).join('、') || '—'}</td>
      </tr>`).join('')}</table>`
      : '<div class="empty">还没有批改记录。批改几份后这里会告诉你哪个节次最该重讲。</div>';
  } catch (e) { $('#mk-diag').innerHTML = '<div class="empty">读取失败：' + esc(e.message) + '</div>'; }
  try {
    const h = await api('/api/attempts?limit=20');
    $('#mk-history').innerHTML = (h.attempts || []).length ? h.attempts.map(a => `
      <div class="rowitem"><b>${a.total}/${a.out_of}</b>　${esc(a.ts)}　${esc(a.student || '')}
        <span class="sub">${esc(a.section || '')} ｜ ${esc(a.judge || '')}</span>
        <div class="sub">${Object.entries(a.parts || {}).map(([k, v]) =>
          esc(k) + ' ' + v.marks + ((v.errors || []).length ? ' ⚠' : '')).join(' · ')}</div>
      </div>`).join('') : '<div class="empty">暂无记录</div>';
  } catch (e) { $('#mk-history').innerHTML = '<div class="empty">读取失败：' + esc(e.message) + '</div>'; }
}

async function mkSubmit() {
  const j = JUDGES[Number($('#mk-judge').value)] || JUDGES[0];
  const payload = {
    project: $('#mk-proj').value, section: $('#mk-sec').value,
    student: $('#mk-student').value.trim(),
    question_text: $('#mk-q').value.trim(), question_file: $('#mk-qfile').value.trim(),
    markscheme_text: $('#mk-ms').value.trim(), markscheme_file: $('#mk-msfile').value.trim(),
    parts: $('#mk-parts').value.split(',').map(s => s.trim()).filter(Boolean),
    out_of: Number($('#mk-outof').value) || 0,
    answer: $('#mk-ans').value.trim(),
    judge: {provider: j.provider, model: j.model},
  };
  if (payload.answer.length < 20) { alert('请粘贴学生答案'); return; }
  if (!(payload.question_text || payload.question_file) ||
      !(payload.markscheme_text || payload.markscheme_file)) { alert('题目和评分标准都要有'); return; }
  $('#mk-go').disabled = true;
  $('#mk-status').textContent = '批改中…（约 30–120 秒）';
  try {
    const r = await api('/api/mark', {method: 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    $('#mk-result').innerHTML = `<div class="card">
      <h3>结果：<span style="font-size:22px">${r.total}/${r.out_of}</span>
        <span class="sub">${esc(r.attempt_id || '')}</span></h3>
      ${(r.weak_points || []).length ? `<div class="warn">需重点讲：${r.weak_points.map(esc).join('、')}</div>` : ''}
      <table><tr><th>小问</th><th>得分</th><th>理由与失分点</th></tr>
      ${Object.entries(r.parts || {}).map(([k, v]) => `<tr>
        <td><b>${esc(k)}</b></td><td><b>${v.marks}</b></td>
        <td>${esc(v.justification || '')}
          ${(v.errors || []).map(e => `<div class="warn">⚠ ${esc(e)}</div>`).join('')}</td></tr>`).join('')}
      </table></div>`;
    $('#mk-status').textContent = '完成';
    mkSide();
  } catch (e) {
    $('#mk-status').textContent = '';
    $('#mk-result').innerHTML = `<div class="card warn">批改失败：${esc(e.message)}</div>`;
  } finally { $('#mk-go').disabled = false; }
}

/* ---------------- 说明 ---------------- */
function renderHelp(app) {
  app.innerHTML = `
    <h1>说明</h1>
    <div class="card">
      <h3>这个中台做什么</h3>
      <p>把一整个课程资料文件夹索引成可搜索的资料库；用 <code>workspace.json</code> 管理课程、
      节次、知识点与案例；内置批改台，把学生答案按评分标准打分并聚合成本班错项画像。</p>
      <h3>安全边界</h3>
      <ul>
        <li>资料根目录<b>只读</b>：写入只发生在 <code>--data</code> 目录内。</li>
        <li>只绑定 127.0.0.1，不对外网开放。</li>
        <li><code>attempts.json</code> 含学生答案，落盘权限 600，且不在版本控制里。</li>
      </ul>
      <h3>数据文件</h3>
      <ul>
        <li><code>data/index.json</code> — 文件索引（含正文摘要，用于搜索）</li>
        <li><code>data/workspace.json</code> — 课程 / 节次 / 知识点 / 案例</li>
        <li><code>data/attempts.json</code> — 批改记录（错项画像的来源）</li>
      </ul>
      <p class="sub">字段定义见仓库里的 SCHEMA.md。</p>
    </div>`;
}

router();
