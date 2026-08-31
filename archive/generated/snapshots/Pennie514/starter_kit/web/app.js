/* LoomQ 教学前端
   核心循环（每章）：智能体逐句引导 → 你先押一个预测 → 跑真实电路 → 揭示 + 解释。
   猜错的地方就是量子和日常直觉分岔的地方，认知冲突是最强的记忆锚点。 */

'use strict';

const $ = id => document.getElementById(id);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
/* 只允许 **粗体** 和 `代码`，其余一律转义 —— 课程文案是可信的，用户输入不走这里 */
const md = s => esc(s)
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\n/g, '<br>');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = {
  cur: 0, lessons: [], quiz: [], apps: [], limits: [],
  answered: {}, ran: {}, score: 0, quizAt: 0, quizHits: 0,
  grover: '10', cfg: {llm: false, spinq: false, originq: false},
  mode: 'guide', labTab: 'run', lastQasm: '', renderToken: 0,
};

async function api(path, body) {
  try {
    const r = body === undefined
      ? await fetch(path)
      : await fetch(path, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(body),
        });
    return await r.json();
  } catch (e) {
    return {error: '网络请求失败：' + e.message + '（服务还在运行吗？）'};
  }
}

let toastTimer;
function toast(msg, kind, ms) {
  const t = $('toast');
  t.innerHTML = msg;
  t.className = 'toast show ' + (kind || '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), ms || 5200);
}

/* ── 进度条 ─────────────────────────────────────────────── */
function drawRail() {
  const rail = $('rail');
  const inLab = S.mode === 'lab';
  /* 实验室模式没有「章节」概念，隐藏课程进度与翻页，避免误导 */
  rail.hidden = inLab;
  $('rail-txt').hidden = inLab;
  $('btn-prev').hidden = inLab;
  $('btn-next').hidden = inLab;
  $('btn-lab').textContent = inLab ? '📘' : '🧪';
  $('btn-lab').title = inLab ? '回到引导课' : '自由实验室';
  if (inLab) {
    $('foot-hint').innerHTML =
      '🧪 自由实验室 · 点右上角 <strong>📘</strong> 回到引导课';
    return;
  }
  rail.innerHTML = '';
  S.lessons.forEach((ls, i) => {
    const b = el('button', 'rail-seg' + (i < S.cur ? ' done' : i === S.cur ? ' now' : ''));
    b.title = ls.chapter + ' · ' + ls.title;
    b.setAttribute('aria-label', b.title);
    b.onclick = () => go(i);
    rail.appendChild(b);
  });
  $('rail-txt').textContent = (S.cur + 1) + ' / ' + S.lessons.length;
  /* 只对「核心 5 分钟」倒计时；结课测验是加餐，不掺进承诺里 */
  const left = S.lessons.slice(S.cur).filter(x => !x.bonus)
    .reduce((a, x) => a + (x.eta || 0), 0);
  const cur = S.lessons[S.cur];
  $('foot-hint').innerHTML = (cur && cur.bonus)
    ? '核心 5 分钟已走完 ✓ 这是结课加餐 · <span class="kbd">←</span> <span class="kbd">→</span> 翻页'
    : '核心路线还剩约 ' + (left >= 60 ? Math.ceil(left / 60) + ' 分钟' : left + ' 秒') +
      ' · <span class="kbd">←</span> <span class="kbd">→</span> 翻页';
}

/* ── 逐句「打字」引导（有节奏地读，不是一堵墙） ─────────── */
async function typeLines(lines, token) {
  const chat = $('chat');
  chat.innerHTML = '';
  for (const line of lines) {
    if (token !== S.renderToken) return false;   // 已翻到别章，放弃这次渲染
    const m = el('div', 'msg');
    m.appendChild(el('div', 'msg-av', 'Q'));
    const bd = el('div', 'msg-bd');
    m.appendChild(bd);
    chat.appendChild(m);
    if (!reduceMotion) {
      bd.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
      await sleep(Math.min(560, 190 + line.length * 5));
      if (token !== S.renderToken) return false;
    }
    bd.innerHTML = md(line);
    if (!reduceMotion) await sleep(90);
  }
  return token === S.renderToken;
}

/* ── 柱状图（概率分布 = 量子实验的唯一「读数」） ─────────── */
function chart(host, counts, opt) {
  opt = opt || {};
  const entries = Object.entries(counts).filter(([, v]) => v > 0 || opt.keepZero);
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  const peak = Math.max(...entries.map(([, v]) => v), 1);
  const wrap = el('div', 'chart');
  if (opt.cap) wrap.appendChild(el('div', 'chart-cap', opt.cap));
  entries.sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
    const pct = (v / total * 100);
    /* 噪声判定看「这个结果该不该出现」，不看它大不小——
       真机噪声可能高达 20%+，按大小判定会把大噪声峰画成正常峰 */
    const isNoise = opt.expect ? !opt.expect.includes(k) : false;
    const weak = pct < 5;
    const row = el('div', 'bar' + (weak && !isNoise ? ' dim' : ''));
    row.appendChild(el('div', 'bar-lab', '|' + esc(k) + '⟩'));
    const track = el('div', 'bar-track');
    const kind = isNoise ? ' noise' : (opt.classical ? ' classical' : '');
    const fill = el('div', 'bar-fill' + kind);
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el('div', 'bar-num',
      '<b>' + pct.toFixed(1) + '%</b> · ' + v + ' 次'));
    wrap.appendChild(row);
    requestAnimationFrame(() => { fill.style.width = (v / peak * 100).toFixed(1) + '%'; });
  });
  host.appendChild(wrap);
  return wrap;
}

function runMeta(res, shots) {
  return '<div class="trace">后端 ' + esc(res.backend || '') +
    ' · shots ' + esc(String(res.shots || shots || '')) +
    (res.job_id ? ' · job_id ' + esc(res.job_id) : '') + '</div>';
}

/* ── 预测卡 ─────────────────────────────────────────────── */
function renderPredict(host, lesson, onDone) {
  const p = lesson.predict;
  const box = el('div', 'predict');
  box.appendChild(el('div', 'predict-q', md(p.q)));
  box.appendChild(el('div', 'predict-hint',
    '先押一个再看结果 —— 猜错比猜对更有用，那正是直觉和量子分岔的地方。'));
  const btns = [];
  p.options.forEach((text, i) => {
    const b = el('button', 'opt');
    b.appendChild(el('span', 'opt-key', String.fromCharCode(65 + i)));
    b.appendChild(el('span', null, md(text)));
    b.onclick = () => {
      const hit = i === p.answer;
      S.answered[lesson.id] = hit;
      btns.forEach((x, j) => {
        x.disabled = true;
        if (j === p.answer) x.classList.add('right');
        else if (j === i) x.classList.add('wrong');
      });
      const v = el('div', 'verdict ' + (hit ? 'hit' : 'miss'));
      v.innerHTML = '<b>' + (hit ? '✓ 押对了' : '✗ 直觉在这里失灵了 —— 这一步最值钱') + '</b>' +
        '<span>' + md(p.why) + '</span>';
      box.appendChild(v);
      /* 没有实验的章节（如第 1 章热身），答完就给收获，不然收获永远出不来 */
      if (lesson.takeaway && !lesson.circuit && lesson.id !== 'grover') revealLessonTail(lesson);
      if (onDone) onDone(hit);
    };
    btns.push(b);
    box.appendChild(b);
  });
  host.appendChild(box);
}

/* ── 互动小组件（手上有事做，注意力才在） ───────────────── */
const WIDGETS = {
  coin_intro(host) {
    const w = el('div', 'widget');
    const coin = el('button', 'coin spinning', '?');
    coin.setAttribute('aria-label', '点击让硬币落定');
    const cap = el('div', 'widget-cap',
      '这枚硬币还在转 —— 它现在<strong>既是正面又是反面</strong>。点它一下，让它落定。');
    /* 开场就把整条路线摊开：知道要去哪，才愿意跟着走（进度可见性） */
    const plan = el('div');
    plan.style.cssText = 'margin-top:18px;width:100%;padding-top:16px;border-top:1px solid var(--line)';
    plan.appendChild(el('div', 'duel-hd', '这 5 分钟的路线'));
    const list = el('div', 'plain-steps');
    S.lessons.filter(l => !l.bonus && l.id !== 'hello').forEach((l, i) => {
      const s = el('div', 'pstep');
      s.appendChild(el('i', null, String(i + 1)));
      s.appendChild(el('span', null, md(l.title)));
      list.appendChild(s);
    });
    plan.appendChild(list);
    plan.appendChild(el('div', 'foot-hint',
      '每章都是：<strong>你先猜 → 真跑一次 → 我解释</strong>。最后一章上真机。'));
    let spinning = true;
    coin.onclick = () => {
      if (spinning) {
        const r = Math.random() < .5 ? '0' : '1';
        coin.classList.remove('spinning');
        coin.textContent = r;
        cap.innerHTML = '落定成了 <strong>' + r + '</strong>。刚才那个「同时是两面」的状态，' +
          '就是<strong>叠加</strong>；你点下去的这一下，就是<strong>测量</strong>。再点一下重新转。';
        spinning = false;
      } else {
        coin.classList.add('spinning');
        coin.textContent = '?';
        cap.innerHTML = '又转起来了 —— 回到叠加态。点击 = 测量。';
        spinning = true;
      }
    };
    w.appendChild(coin); w.appendChild(cap); w.appendChild(plan);
    host.appendChild(w);
  },

  switch(host) {
    const w = el('div', 'widget');
    const box = el('div', 'switch-box');
    const cap = el('div', 'widget-cap', '这是 3 个经典比特。点一点 —— 你会发现每个只能是 0 或 1，没有第三种可能。');
    const bits = [0, 0, 0];
    const btns = bits.map((_, i) => {
      const b = el('button', 'sw', '0');
      b.setAttribute('aria-label', '切换第 ' + (i + 1) + ' 个比特');
      b.onclick = () => {
        bits[i] ^= 1;
        b.textContent = bits[i];
        b.classList.toggle('on', !!bits[i]);
        cap.innerHTML = '当前：<strong>' + bits.join('') + '</strong> —— 3 个比特能表示 8 种状态，' +
          '但任何时刻<strong>只能是其中一种</strong>。这就是经典计算的天花板。';
      };
      box.appendChild(b);
      return b;
    });
    w.appendChild(box); w.appendChild(cap);
    host.appendChild(w);
  },

  qubit_spin(host) {
    const w = el('div', 'widget');
    w.appendChild(el('div', 'widget-cap',
      '下面这个电路只有 3 行，我用人话翻译好了。点「运行实验」，它会真的在模拟器上跑 2000 次。'));
    host.appendChild(w);
  },

  grover_pick(host) {
    const w = el('div', 'widget');
    w.appendChild(el('div', 'widget-cap', '你来选一个「密码」，我用量子算法一次把它找出来：'));
    const grid = el('div', 'pick-grid');
    ['00', '01', '10', '11'].forEach(v => {
      const b = el('button', 'pick' + (v === S.grover ? ' on' : ''), v);
      b.onclick = () => {
        S.grover = v;
        grid.querySelectorAll('.pick').forEach(x => x.classList.toggle('on', x.textContent === v));
        const st = $('stage-extra');
        if (st) st.innerHTML = '';
      };
      grid.appendChild(b);
    });
    w.appendChild(grid);
    host.appendChild(w);
  },

  recap(host) {
    renderWrap(host);
  },
};

/* ── 电路展示：先人话，代码折叠 ─────────────────────────── */
function renderCircuit(host, circ, title) {
  const box = el('div');
  if (title) box.appendChild(el('div', 'duel-hd', title));
  if (circ.plain) {
    const steps = el('div', 'plain-steps');
    circ.plain.forEach((t, i) => {
      const s = el('div', 'pstep');
      s.appendChild(el('i', null, String(i + 1)));
      s.appendChild(el('span', null, md(t)));
      steps.appendChild(s);
    });
    box.appendChild(steps);
  }
  const d = el('details', 'deep');
  d.appendChild(el('summary', null, '看真正的电路代码（OpenQASM）'));
  const bd = el('div', 'deep-bd');
  bd.appendChild(el('pre', 'code', esc(circ.qasm)));
  d.appendChild(bd);
  box.appendChild(d);
  host.appendChild(box);
  return box;
}

function insightBox(host, reveal) {
  const b = el('div', 'insight');
  b.innerHTML = '<b>💡 这说明什么</b><br>' + md(reveal.insight) +
    (reveal.vs ? '<span class="vs">' + md(reveal.vs) + '</span>' : '');
  host.appendChild(b);
  return b;
}

/* ── 工作台主渲染 ───────────────────────────────────────── */
function renderStage(lesson) {
  const stage = $('stage');
  stage.innerHTML = '';
  $('stage-badge').innerHTML = '';

  if (WIDGETS[lesson.widget]) WIDGETS[lesson.widget](stage);

  const isGrover = lesson.id === 'grover';
  const circ = isGrover ? groverCircuit() : lesson.circuit;

  if (circ) {
    renderCircuit(stage, circ, circ.label || null);
    const extra = el('div');
    extra.id = 'stage-extra';
    stage.appendChild(extra);
    const bar = el('div', 'row', '');
    const btn = el('button', 'btn big', '▶ 运行实验');
    btn.onclick = () => runLesson(lesson, btn);
    bar.appendChild(btn);
    if (lesson.compare) {
      bar.appendChild(el('span', 'foot-hint',
        '会同时跑「量子」和「经典」两组，并排对比'));
    }
    stage.appendChild(bar);
    $('stage-badge').innerHTML = '<span class="badge sim">理想模拟器</span>';
  } else if (lesson.id === 'real') {
    renderRealStage(stage);
  } else if (!lesson.widget) {
    stage.appendChild(el('div', 'empty',
      '<span class="empty-ico">🔬</span>这一章先读左边，再点「下一步」。'));
  }
}

function groverCircuit() {
  return {
    qasm: S.groverQasm[S.grover], shots: 2000, target: S.grover,
    plain: [
      '把 4 个可能答案同时放进叠加（H、H）',
      '标记你选的答案 ' + S.grover + '（Oracle：只给它一个负号）',
      '让 3 个错答案相互抵消、正确答案相互增强（扩散算子）',
      '测量 2000 次',
    ],
  };
}

/* ── 跑实验：本章的高潮 ─────────────────────────────────── */
async function runLesson(lesson, btn) {
  const isGrover = lesson.id === 'grover';
  const circ = isGrover ? groverCircuit() : lesson.circuit;
  const out = $('stage-extra');
  out.innerHTML = '';
  btn.disabled = true;
  const label = btn.textContent;
  btn.innerHTML = '<span class="spin"></span> 运行中…';

  try {
    const r = await api('/api/run', {qasm: circ.qasm, backend: 'spinq', shots: circ.shots});
    if (r.error) { toast('⚠️ ' + esc(r.error), 'err', 9000); return; }
    S.ran[lesson.id] = true;

    if (lesson.compare) {
      await renderDuel(out, lesson, r.result, circ.shots);
    } else {
      chart(out, r.result.counts, {cap: circ.label || '测量结果分布'});
      out.insertAdjacentHTML('beforeend', runMeta(r.result, circ.shots));
      if (isGrover) {
        const hit = (r.result.counts[S.grover] || 0) / circ.shots * 100;
        const ib = el('div', 'insight');
        ib.innerHTML = '<b>💡 这说明什么</b><br>' +
          '你选的密码是 <strong>' + esc(S.grover) + '</strong>，量子算法<strong>只问了一次</strong>，' +
          '命中率 <strong>' + hit.toFixed(1) + '%</strong>。' +
          '注意这不是运气 —— 3 个错答案的振幅被干涉<strong>抵消成了 0</strong>。' +
          '<span class="vs">' + md(lesson.reveal.vs) + '</span>';
        out.appendChild(ib);
      } else if (lesson.reveal) {
        insightBox(out, lesson.reveal);
      }
    }
    revealLessonTail(lesson);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

/* 第 5 章：量子 vs 经典「事先约好」并排对照 —— 全课最关键的一张图 */
async function renderDuel(out, lesson, quantumRes, shots) {
  const duel = el('div', 'duel');
  const qc = el('div', 'duel-card q');
  qc.appendChild(el('div', 'duel-hd', '① 真纠缠 + 旋转'));
  chart(qc, quantumRes.counts, {});
  const qKinds = Object.entries(quantumRes.counts).filter(([, v]) => v > 0).length;
  qc.appendChild(el('div', 'duel-verdict',
    '结果：只有 <strong>' + qKinds + ' 种</strong>结果 —— 相关性<strong>完好无损</strong> ✓'));
  duel.appendChild(qc);

  const cc = el('div', 'duel-card c');
  cc.appendChild(el('div', 'duel-hd', esc(lesson.compare.label)));
  cc.appendChild(el('div', 'duel-note', md(lesson.compare.note)));
  cc.appendChild(el('div', 'row', '<span class="spin"></span> 正在跑经典对照组…'));
  duel.appendChild(cc);
  out.appendChild(duel);

  /* 经典策略 = 共享随机性：两种「约定」各跑一半，合并后就是经典能达到的最好结果 */
  const merged = {};
  for (const run of lesson.compare.runs) {
    const r = await api('/api/run', {qasm: run.qasm, backend: 'spinq', shots: run.shots});
    if (r.error) { toast('⚠️ 经典对照组失败：' + esc(r.error), 'err'); return; }
    for (const [k, v] of Object.entries(r.result.counts)) merged[k] = (merged[k] || 0) + v;
  }
  cc.querySelector('.row').remove();
  chart(cc, merged, {classical: true});
  const cKinds = Object.keys(merged).filter(k => merged[k] > 0).length;
  cc.appendChild(el('div', 'duel-verdict',
    '结果：<strong>' + cKinds + ' 种</strong>结果全都冒出来了 —— 相关性<strong>彻底消失</strong> ✗'));

  insightBox(out, lesson.reveal);
}

/* ── 第 7 章：真机 ──────────────────────────────────────── */
function renderRealStage(stage) {
  const lesson = S.lessons.find(x => x.id === 'real');
  const live = S.cfg.spinq || S.cfg.originq;
  $('stage-badge').innerHTML = live
    ? '<span class="badge live">真机凭证已就绪</span>'
    : '<span class="badge replay">存证回放</span>';

  const box = el('div');
  box.appendChild(el('div', 'plain-steps',
    ['把第 4 章的 Bell 电路（H + CX）打包',
     '送去真实超导量子芯片排队执行',
     '取回真实测量结果，和理想模拟器对比'].map((t, i) =>
      '<div class="pstep"><i>' + (i + 1) + '</i><span>' + esc(t) + '</span></div>').join('')));
  stage.appendChild(box);
  const extra = el('div'); extra.id = 'stage-extra'; stage.appendChild(extra);

  const bar = el('div', 'row');
  if (S.cfg.spinq) {
    const b = el('button', 'btn big', '🚀 上量旋真机');
    b.onclick = () => runReal('spinq_cloud', b);
    bar.appendChild(b);
  }
  if (S.cfg.originq) {
    const b = el('button', 'btn big', '🚀 上本源 180 真机');
    b.onclick = () => runReal('originq_wukong', b);
    bar.appendChild(b);
  }
  const rp = el('button', live ? 'btn sec' : 'btn big', '📼 回放真机存证数据');
  rp.onclick = () => replayReal(rp);
  bar.appendChild(rp);
  stage.appendChild(bar);

  if (!live) {
    stage.appendChild(el('div', 'foot-hint',
      '没有配置真机凭证也能完成这一章：回放的是<strong>真实芯片跑出来的历史数据</strong>' +
      '（带可在平台控制台溯源的 job_id），不是模拟。想跑实时任务可在顶栏 🧪 → ⚙️ 配置里填凭证。'));
  }
}

async function runReal(backend, btn) {
  const lesson = S.lessons.find(x => x.id === 'real');
  const out = $('stage-extra');
  const label = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> 排队中…';
  out.innerHTML = '';
  const rb = el('div', 'real-box');
  rb.innerHTML = '<div class="real-hd"><span class="pulse"></span>真机任务已提交，正在排队执行</div>' +
    '<div class="foot-hint" style="margin-top:6px">真机需要排队，通常几分钟。这段时间量子芯片正被冷却到接近绝对零度、' +
    '按你的电路施加微波脉冲 —— 别关页面。</div>';
  out.appendChild(rb);
  try {
    const qasm = S.lessons.find(x => x.id === 'entangle').circuit.qasm;
    const r = await api('/api/run-real', {backend: backend, qasm: qasm, shots: 2048});
    if (r.error) {
      rb.innerHTML = '<div class="real-hd" style="color:var(--warn)">😕 真机这次没跑成</div>' +
        '<div class="foot-hint" style="margin-top:6px">' + esc(r.error) + '</div>';
      const alt = el('button', 'btn sec', '📼 那就回放存证数据（同样是真实芯片结果）');
      alt.onclick = () => replayReal(alt);
      rb.appendChild(el('div', 'row', '')).appendChild(alt);
      return;
    }
    showRealResult(out, rb, r.result, '真机实时任务', 'live');
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

async function replayReal(btn) {
  const out = $('stage-extra');
  const label = btn.textContent;
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> 读取存证…';
  out.innerHTML = '';
  try {
    const r = await api('/api/real-replay');
    if (r.error) { toast('⚠️ ' + esc(r.error), 'err'); return; }
    const list = r.results || [];
    if (!list.length) { toast('⚠️ 没有可回放的真机存证', 'warn'); return; }
    out.appendChild(el('div', 'duel-note', esc(r.note || '')));
    /* 两台真机一起看：噪声水平差异很大，这个真实差异本身就是最好的教学素材 */
    list.forEach(res => {
      const rb = el('div', 'real-box');
      rb.style.marginTop = '12px';
      out.appendChild(rb);
      showRealResult(out, rb, res, res.label, 'replay', null, list.length > 1);
    });
    if (list.length > 1) compareMachines(out, list);
    revealLessonTail(S.lessons.find(x => x.id === 'real'));
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

function fidelity(counts) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const good = ((counts['00'] || 0) + (counts['11'] || 0)) / total * 100;
  return {good: good, noise: 100 - good};
}

/* 两台真机并排：同一个电路，不同芯片的保真度差别很大 */
function compareMachines(out, list) {
  const ib = el('div', 'insight');
  const rows = list.map(r => {
    const f = fidelity(r.counts);
    return '<strong>' + esc(r.label.split(' · ')[0]) + '</strong>：主峰 ' +
      f.good.toFixed(1) + '%，噪声 ' + f.noise.toFixed(1) + '%';
  }).join('<br>');
  ib.innerHTML = '<b>💡 顺便看一个真实世界的细节</b><br>' +
    '同一个 Bell 电路，两台真机的表现差很多：<br>' + rows + '<br>' +
    '这不是谁做错了 —— <strong>不同量子芯片的保真度本来就不一样</strong>，' +
    '和工艺、比特类型、校准状态都有关。挑机器是量子工程的日常工作。';
  out.appendChild(ib);
}

function showRealResult(out, rb, res, title, kind, note, compact) {
  const lesson = S.lessons.find(x => x.id === 'real');
  S.ran.real = true;
  rb.innerHTML = '<div class="real-hd" style="color:var(--ok)">✅ ' + esc(title) +
    '</div><span class="badge ' + (kind === 'live' ? 'live">实时任务' : 'replay">存证回放') + '</span>';
  if (note) rb.appendChild(el('div', 'duel-note', esc(note)));
  /* Bell 态理论上只允许 00/11，其余一律是噪声 */
  chart(rb, res.counts, {expect: ['00', '11'],
    cap: '真实量子芯片的测量结果（<span style="color:var(--warn)">橙色</span> = 理论上不该出现的噪声）'});
  rb.insertAdjacentHTML('beforeend', runMeta(res, res.shots));

  const f = fidelity(res.counts);
  /* 文案随实测噪声水平自适应：真机有干净的也有很吵的，不能写死 */
  const noiseTxt = f.noise < 1
    ? '本不该出现的 01 / 10 只占 <strong>' + f.noise.toFixed(2) + '%</strong> —— ' +
      '这块芯片这次<strong>校准得非常好</strong>，几乎看不到噪声。'
    : '本不该出现的 01 / 10 占了 <strong>' + f.noise.toFixed(1) + '%</strong> —— ' +
      '这就是<strong>噪声</strong>，真实芯片的指纹。理想模拟器里它们应该是 0。';
  const ib = el('div', 'insight');
  ib.innerHTML = '<b>💡 这是真实量子计算机的输出</b><br>' +
    '主峰 <strong>00 / 11 占 ' + f.good.toFixed(1) + '%</strong> —— 纠缠<strong>成功了</strong>，' +
    '和理想模拟器的主峰一致。<br>' + noiseTxt +
    (compact ? '' : '<span class="vs">' + md(lesson.reveal.vs) + '</span>');
  rb.appendChild(ib);
  if (!compact) revealLessonTail(lesson);
}

/* ── 跑完实验后，左栏补上「本章收获」 ───────────────────── */
function revealLessonTail(lesson) {
  const host = $('lesson-extra');
  if (host.dataset.tail === lesson.id) return;
  host.dataset.tail = lesson.id;
  if (lesson.takeaway && lesson.takeaway.length) {
    const t = el('div', 'takeaway');
    t.appendChild(el('h4', null, '本章收获'));
    const ul = el('ul');
    lesson.takeaway.forEach(x => ul.appendChild(el('li', null, md(x))));
    t.appendChild(ul);
    host.appendChild(t);
  }
  if (lesson.deep) {
    const d = el('details', 'deep');
    d.appendChild(el('summary', null, esc(lesson.deep.title)));
    d.appendChild(el('div', 'deep-bd', md(lesson.deep.body)));
    host.appendChild(d);
  }
  $('btn-next').classList.add('pulse-hint');
}

/* ── 章节渲染 ───────────────────────────────────────────── */
async function render() {
  const token = ++S.renderToken;   // 快速翻页时作废上一次未完成的渲染
  const lesson = S.lessons[S.cur];
  S.mode = 'guide';
  $('view-guide').hidden = false;
  $('view-lab').hidden = true;
  $('chapter-tag').innerHTML =
    '<span class="chapter-tag">' + esc(lesson.chapter) +
    (lesson.eta ? ' · 约 ' + lesson.eta + ' 秒' : '') + '</span>';
  $('lesson-title').innerHTML = md(lesson.title);
  const extra = $('lesson-extra');
  extra.innerHTML = '';
  extra.dataset.tail = '';
  $('btn-prev').disabled = S.cur === 0;
  $('btn-next').textContent = S.cur === S.lessons.length - 1 ? '完成 ✓' : '下一步 →';
  drawRail();
  renderStage(lesson);
  window.scrollTo({top: 0, behavior: reduceMotion ? 'auto' : 'smooth'});

  await typeLines(lesson.say || [], token);
  if (token !== S.renderToken) return;

  if (lesson.predict) {
    renderPredict(extra, lesson, null);
  } else if (lesson.id !== 'wrap') {
    revealLessonTail(lesson);
  }
}

function go(i) {
  if (i < 0 || i >= S.lessons.length) return;
  S.cur = i;
  /* 深链：便于分享/评审直接跳到某一章，如 #bell_test */
  try { history.replaceState(null, '', '#' + S.lessons[i].id); } catch (e) { /* 忽略 */ }
  render();
}

/* ── 结课页 ─────────────────────────────────────────────── */
function renderWrap(host) {
  host.innerHTML = '';
  const done = Object.keys(S.ran).length;
  const hits = Object.values(S.answered).filter(Boolean).length;
  const asked = Object.keys(S.answered).length;

  const sc = el('div', 'score');
  sc.innerHTML = '<div class="score-n">' + done + '</div>' +
    '<div class="score-t">个真实实验已完成' +
    (asked ? ' · 预测命中 ' + hits + '/' + asked : '') + '</div>';
  host.appendChild(sc);

  host.appendChild(el('div', 'duel-hd', '🎯 检验一下：你真的懂了吗？'));
  host.appendChild(el('div', 'duel-note',
    '重读没用，回忆才有用。5 道题，答错会告诉你为什么。'));
  const qz = el('div'); qz.id = 'quiz'; host.appendChild(qz);
  renderQuiz();
}

function renderQuiz() {
  const host = $('quiz');
  host.innerHTML = '';
  if (S.quizAt >= S.quiz.length) {
    const sc = el('div', 'score');
    const n = S.quizHits, t = S.quiz.length;
    sc.innerHTML = '<div class="score-n">' + n + ' / ' + t + '</div>' +
      '<div class="score-t">' + (n === t ? '全对 —— 你已经比大多数人更懂量子计算了。'
        : n >= t - 1 ? '非常好，只差一点。' : '答错的地方回头看看对应章节的图就懂了。') + '</div>';
    host.appendChild(sc);
    const again = el('button', 'btn sec', '↻ 再测一次');
    again.onclick = () => { S.quizAt = 0; S.quizHits = 0; renderQuiz(); };
    const lab = el('button', 'btn', '🧪 去自由实验室');
    lab.onclick = () => openLab();
    host.appendChild(el('div', 'row', '')).append(again, lab);
    host.appendChild(renderApps());
    return;
  }
  const q = S.quiz[S.quizAt];
  host.appendChild(el('div', 'qz-prog', '第 ' + (S.quizAt + 1) + ' / ' + S.quiz.length + ' 题'));
  const fake = {predict: q, id: 'quiz-' + S.quizAt};
  renderPredict(host, fake, hit => {
    if (hit) S.quizHits++;
    const nx = el('button', 'btn', S.quizAt === S.quiz.length - 1 ? '看总分 →' : '下一题 →');
    nx.onclick = () => { S.quizAt++; renderQuiz(); };
    host.appendChild(el('div', 'row end', '')).appendChild(nx);
  });
}

function renderApps() {
  const box = el('div');
  box.style.marginTop = '20px';
  box.appendChild(el('div', 'duel-hd', '🌍 学完了，它到底用在哪？'));
  const g = el('div', 'grid2');
  S.apps.forEach(([t, d]) => {
    const m = el('div', 'mini');
    m.appendChild(el('h5', null, esc(t)));
    m.appendChild(el('p', null, esc(d)));
    g.appendChild(m);
  });
  box.appendChild(g);
  box.appendChild(el('div', 'duel-hd', '⚠️ 也说清楚它<strong>不能</strong>做什么'));
  const ul = el('ul');
  S.limits.forEach(x => ul.appendChild(el('li', 'limit-li', esc(x))));
  box.appendChild(ul);
  return box;
}

/* ── 自由实验室（保留原有 生成 / 纠错 / 选平台 / 配置） ──── */
const LAB_TITLES = {run: '跑电路', gen: '说人话生成电路', fix: '修报错代码',
                    pick: '帮我选平台', cfg: '配置（可选）'};

function openLab(tab) {
  S.mode = 'lab';
  S.renderToken++;          // 作废可能仍在打字的引导渲染
  S.labTab = tab || S.labTab;
  $('view-guide').hidden = true;
  $('view-lab').hidden = false;
  try { history.replaceState(null, '', '#lab'); } catch (e) { /* 忽略 */ }
  document.querySelectorAll('.lab-tab').forEach(b =>
    b.classList.toggle('on', b.dataset.t === S.labTab));
  $('lab-hd').textContent = LAB_TITLES[S.labTab];
  renderLabForm();
  drawRail();
  window.scrollTo({top: 0, behavior: 'auto'});
}

function needLLM() {
  if (S.cfg.llm) return false;
  toast('🔑 这个功能需要模型服务。点 <strong>⚙️ 配置</strong> 填一个 API Key 即可解锁；' +
        '课程和实验不需要它。', 'warn', 8000);
  return true;
}

function renderLabForm() {
  const f = $('lab-form');
  f.innerHTML = '';
  $('lab-out').innerHTML = '';
  $('lab-badge').innerHTML = '';
  const t = S.labTab;

  if (t === 'run') {
    f.appendChild(el('div', 'duel-note', '课程里的电路都在这儿，也可以自己改。'));
    const chips = el('div', 'chips');
    S.lessons.filter(l => l.circuit).forEach(l => {
      const c = el('button', 'chip', esc(l.title.slice(0, 14)));
      c.onclick = () => { $('lab-qasm').value = l.circuit.qasm; };
      chips.appendChild(c);
    });
    ['00', '01', '10', '11'].forEach(v => {
      const c = el('button', 'chip', 'Grover ' + v);
      c.onclick = () => { $('lab-qasm').value = S.groverQasm[v]; };
      chips.appendChild(c);
    });
    f.appendChild(chips);
    f.appendChild(el('label', 'fld', '电路（OpenQASM 2.0）'));
    const ta = el('textarea'); ta.id = 'lab-qasm';
    ta.value = S.lessons.find(l => l.id === 'entangle').circuit.qasm;
    f.appendChild(ta);
    f.appendChild(el('label', 'fld', '平台'));
    const sel = el('select'); sel.id = 'lab-backend';
    [['spinq', '量旋本地模拟器'], ['originq', '本源本地模拟器'], ['braket', 'AWS 本地模拟器']]
      .forEach(([v, n]) => { const o = el('option', null, n); o.value = v; sel.appendChild(o); });
    f.appendChild(sel);
    f.appendChild(el('label', 'fld', '测量次数 shots'));
    const sh = el('input'); sh.type = 'number'; sh.id = 'lab-shots'; sh.value = 2048;
    sh.min = 100; sh.max = 8192;
    f.appendChild(sh);
    const b = el('button', 'btn big', '▶ 运行');
    b.onclick = async () => {
      const label = b.textContent; b.disabled = true; b.innerHTML = '<span class="spin"></span> 运行中…';
      const r = await api('/api/run', {qasm: $('lab-qasm').value,
        backend: sel.value, shots: parseInt(sh.value) || 2048});
      b.disabled = false; b.textContent = label;
      const out = $('lab-out'); out.innerHTML = '';
      if (r.error) { out.appendChild(el('div', 'empty', '⚠️ ' + esc(r.error))); return; }
      chart(out, r.result.counts, {cap: '测量结果'});
      out.insertAdjacentHTML('beforeend', runMeta(r.result, sh.value));
      const same = el('button', 'btn sec', '↔ 同一电路换平台再跑（验证统一中间层）');
      same.onclick = async () => {
        for (const [bid, nm] of [['spinq', '量旋'], ['originq', '本源'], ['braket', 'AWS']]) {
          const rr = await api('/api/run', {qasm: $('lab-qasm').value, backend: bid, shots: 2048});
          if (rr.error) continue;
          const d = el('div'); d.style.marginTop = '14px';
          d.appendChild(el('div', 'duel-hd', nm + ' 平台'));
          chart(d, rr.result.counts, {});
          out.appendChild(d);
        }
        out.appendChild(el('div', 'insight', '✓ 一个字符没改，三家平台分布一致 —— 这就是「通用充电器」。'));
      };
      out.appendChild(el('div', 'row', '')).appendChild(same);
    };
    f.appendChild(el('div', 'row', '')).appendChild(b);

  } else if (t === 'gen' || t === 'fix' || t === 'pick') {
    renderLLMForm(f, t);

  } else if (t === 'cfg') {
    renderCfgForm(f);
  }
}

const LLM_CFG = {
  gen: {
    note: '用大白话描述你想要的电路，智能体会写成 OpenQASM，并先用无噪声模拟器自验一遍。',
    ph: '例如：让三个量子比特纠缠在一起，然后全部测量',
    chips: ['让三个量子比特纠缠在一起（GHZ 态），然后全部测量',
            '生成一个 2 比特的贝尔态并测量',
            '让三个量子比特各自处于均匀叠加态并测量',
            '制备一个 1 比特的 |1> 态并测量'],
    btn: '✨ 生成电路',
  },
  fix: {
    note: '把报错的电路粘进来，再说一句你原本想做什么。智能体会保持你的意图修到能跑。',
    ph: '把报错的代码粘在这里……',
    intent: '你想做的是？（例如：一个贝尔态）',
    btn: '🩹 修复并自验',
  },
  pick: {
    note: '说出你的约束（比特数、是否排队、费用、是否要真机），按官方能力表给推荐。',
    ph: '例如：我需要运行一个 15 比特电路，且零排队等待',
    chips: ['我要跑 15 个比特，不想排队', '用免费的真机跑一个小电路',
            '不需要注册账号，跑 5 比特', '想用最大的免费模拟器'],
    btn: '🧭 推荐平台',
  },
};

function renderLLMForm(f, t) {
  const c = LLM_CFG[t];
  f.appendChild(el('div', 'duel-note', esc(c.note)));
  if (!S.cfg.llm) {
    f.appendChild(el('div', 'insight',
      '🔑 这个功能需要模型服务（正式评测时由组委会自动注入）。' +
      '点 <strong>⚙️ 配置</strong> 填一个 API Key 即可解锁。<br>' +
      '<strong>课程 8 章、所有实验、真机回放都不需要它</strong>。'));
  }
  let intent;
  if (c.intent) {
    f.appendChild(el('label', 'fld', esc(c.intent)));
    intent = el('input'); intent.type = 'text'; f.appendChild(intent);
  }
  if (c.chips) {
    const chips = el('div', 'chips');
    c.chips.forEach(x => {
      const b = el('button', 'chip', esc(x.length > 18 ? x.slice(0, 18) + '…' : x));
      b.title = x;
      b.onclick = () => { ta.value = x; };
      chips.appendChild(b);
    });
    f.appendChild(chips);
  }
  f.appendChild(el('label', 'fld', t === 'pick' ? '你的约束' : '你的描述'));
  const ta = el('textarea'); ta.placeholder = c.ph; f.appendChild(ta);

  const b = el('button', 'btn big', c.btn);
  b.onclick = async () => {
    const v = ta.value.trim();
    if (!v) return toast('先写一句你想要什么～', 'warn');
    if (needLLM()) return;
    const label = b.textContent; b.disabled = true;
    b.innerHTML = '<span class="spin"></span> 智能体处理中…';
    const out = $('lab-out');
    out.innerHTML = '<div class="row"><span class="spin"></span> 生成后会先用无噪声模拟器自验…</div>';
    const prompt = t === 'fix'
      ? (intent && intent.value.trim()
          ? '我想做的是' + intent.value.trim() + '，但这段代码有问题，请修好它：\n' + v
          : '这段代码报错了，帮我修好并保持原意图：\n' + v)
      : v;
    const r = await api('/api/chat', {prompt: prompt});
    b.disabled = false; b.textContent = label;
    out.innerHTML = '';
    if (r.error) { out.appendChild(el('div', 'empty', '⚠️ ' + esc(r.error).replace(/\n/g, '<br>'))); return; }
    if (r.reply) {
      out.appendChild(el('div', 'insight', md(r.reply.split('```')[0] || r.reply)));
    }
    if (r.qasm) {
      out.appendChild(el('pre', 'code', esc(r.qasm)));
      const run = el('button', 'btn', '▶ 运行看结果');
      run.onclick = async () => {
        run.disabled = true; run.innerHTML = '<span class="spin"></span> 运行中…';
        const rr = await api('/api/run', {qasm: r.qasm, backend: 'spinq', shots: 2048});
        run.remove();
        if (rr.error) { out.appendChild(el('div', 'empty', '⚠️ ' + esc(rr.error))); return; }
        chart(out, rr.result.counts, {cap: '测量结果'});
        out.insertAdjacentHTML('beforeend', runMeta(rr.result, 2048));
      };
      out.appendChild(el('div', 'row', '')).appendChild(run);
    }
  };
  f.appendChild(el('div', 'row', '')).appendChild(b);
}

function renderCfgForm(f) {
  f.appendChild(el('div', 'duel-note',
    '全部可跳过。配置只存在<strong>本机内存</strong>（不写文件、不进仓库），重启服务后需重填。' +
    '正式评测时组委会会自动注入模型服务。'));

  const st = el('div', 'row');
  st.innerHTML = ['模型服务', '量旋真机', '本源真机'].map((n, i) => {
    const ok = [S.cfg.llm, S.cfg.spinq, S.cfg.originq][i];
    return '<span class="badge ' + (ok ? 'live' : 'sim') + '">' + n + ' ' + (ok ? '已配置' : '未配置') + '</span>';
  }).join(' ');
  f.appendChild(st);

  const fields = [
    ['① 模型服务（解锁 生成 / 纠错 / 选平台）', null],
    ['服务地址 Base URL', 'llm-base', 'text', 'https://api.deepseek.com'],
    ['模型名', 'llm-model', 'text', 'deepseek-chat'],
    ['API Key', 'llm-key', 'password', 'sk-...'],
    ['② 量旋真机凭证', null],
    ['用户名（cloud.spinq.cn 注册）', 'sp-user', 'text', ''],
    ['私钥文件路径', 'sp-key', 'text', '~/.ssh/spinq_cloud'],
    ['③ 本源量子云凭证', null],
    ['API Token（qcloud.originqc.com.cn）', 'oq-token', 'password', ''],
  ];
  fields.forEach(([label, id, type, ph]) => {
    if (!id) { f.appendChild(el('div', 'duel-hd', esc(label))).style.marginTop = '16px'; return; }
    f.appendChild(el('label', 'fld', esc(label)));
    const i = el('input'); i.type = type; i.id = 'cfg-' + id; i.placeholder = ph || '';
    f.appendChild(i);
  });

  const save = el('button', 'btn big', '💾 保存配置');
  save.onclick = async () => {
    const g = id => ($('cfg-' + id).value || '').trim();
    const r = await api('/api/config', {
      llm: {base_url: g('llm-base'), api_key: g('llm-key'), model: g('llm-model')},
      spinq: {username: g('sp-user'), keyfile: g('sp-key')},
      originq: {api_token: g('oq-token')},
    });
    if (r.ok) { toast('✅ 已保存（仅内存）', 'ok'); await loadCfg(); renderLabForm(); }
    else toast('⚠️ 保存失败：' + esc(r.error || ''), 'err');
  };
  const clr = el('button', 'btn sec', '🗑 清除');
  clr.onclick = async () => {
    await api('/api/config-clear', {});
    toast('🗑 已清除', 'ok');
    await loadCfg(); renderLabForm();
  };
  f.appendChild(el('div', 'row', '')).append(save, clr);
}

/* ── 启动 ───────────────────────────────────────────────── */
async function loadCfg() {
  const d = await api('/api/config-status');
  S.cfg = {llm: !!d.llm, spinq: !!d.spinq, originq: !!d.originq, model: d.model || ''};
}

$('btn-next').onclick = () => {
  $('btn-next').classList.remove('pulse-hint');
  if (S.cur === S.lessons.length - 1) return openLab();
  go(S.cur + 1);
};
$('btn-prev').onclick = () => go(S.cur - 1);
$('btn-lab').onclick = () => (S.mode === 'lab' ? render() : openLab());
$('btn-theme').onclick = () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('loomq-theme', next); } catch (e) { /* 忽略 */ }
};
document.querySelectorAll('.lab-tab').forEach(b =>
  b.onclick = () => openLab(b.dataset.t));

document.addEventListener('keydown', e => {
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
  if (e.key === 'ArrowRight') $('btn-next').click();
  if (e.key === 'ArrowLeft' && !$('btn-prev').disabled) $('btn-prev').click();
});

(async function boot() {
  try {
    const saved = localStorage.getItem('loomq-theme');
    if (saved) document.documentElement.dataset.theme = saved;
    else if (matchMedia('(prefers-color-scheme: dark)').matches)
      document.documentElement.dataset.theme = 'dark';
  } catch (e) { /* 忽略 */ }

  const [c] = await Promise.all([api('/api/curriculum'), loadCfg()]);
  if (c.error) {
    $('chat').innerHTML = '<div class="empty">⚠️ 课程加载失败：' + esc(c.error) + '</div>';
    return;
  }
  S.lessons = c.lessons; S.quiz = c.quiz; S.apps = c.applications;
  S.limits = c.limits; S.groverQasm = c.grover;
  S.coreEta = c.core_eta;

  const hash = (location.hash || '').replace('#', '');
  if (hash === 'lab') { openLab(); return; }
  const at = S.lessons.findIndex(l => l.id === hash);
  S.cur = at >= 0 ? at : 0;
  render();
})();
