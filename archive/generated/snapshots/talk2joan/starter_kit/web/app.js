/* LoomQ web entry - chat + circuit viz + histogram. Vanilla JS, no deps. */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const chat = $('chat'), ask = $('ask'), form = $('ask-form');
  const sendBtn = form.querySelector('.send');
  const runBtn = $('run'), targetSel = $('target'), resultEl = $('result');
  const circuitEl = $('circuit'), qasmWrap = $('qasm-wrap'),
        qasmCode = $('qasm-code');

  let currentQasm = null;

  /* ---------------- chat ---------------- */
  function addMsg(kind, html) {
    const div = document.createElement('div');
    div.className = 'msg ' + kind;
    const b = document.createElement('div');
    b.className = 'bubble';
    b.innerHTML = html;
    div.appendChild(b);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return b;
  }

  function addTyping() {
    const div = document.createElement('div');
    div.className = 'msg bot typing';
    div.innerHTML = '<div class="bubble"><i></i><i></i><i></i></div>';
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
  }

  function esc(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
  }

  async function send(text) {
    if (!text.trim() || sendBtn.disabled) return;
    addMsg('user', esc(text));
    sendBtn.disabled = true;
    const typing = addTyping();
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await r.json();
      typing.remove();
      if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
      // strip fenced code blocks - QASM goes to the lab panel instead
      addMsg('bot', esc(data.reply
        .replace(/```\w*\n?[\s\S]*?```/g, '')
        .replace(/\n{3,}/g, '\n\n').trim()));
      if (data.qasm) {
        currentQasm = data.qasm;
        renderCircuit(currentQasm);
        qasmCode.textContent = currentQasm;
        qasmWrap.hidden = false;
        runBtn.disabled = false;
        petMeow('喵~ 织好啦！右边看 👉');
        resultEl.className = 'result empty';
        resultEl.innerHTML =
          '<p class="placeholder">结果会像彩虹一样长出来 🌈</p>';
      }
    } catch (e) {
      typing.remove();
      const b = addMsg('bot', '喵？！Kitty被毛线缠住了：' + esc(e.message) +
        '<br>再摸摸它试一次？');
      b.classList.add('err-bubble');
    } finally {
      sendBtn.disabled = false;
      ask.focus();
    }
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const t = ask.value; ask.value = '';
    send(t);
  });
  document.querySelectorAll('.chip').forEach((c) =>
    c.addEventListener('click', () => send(c.dataset.q)));

  /* ---------------- circuit svg ---------------- */
  const GATE_COLORS = { h: '#FFD9CD', x: '#CDEBD6', s: '#FFEDCB',
    sdg: '#FFEDCB', t: '#E3DAF7', tdg: '#E3DAF7', ry: '#FFE3CF',
    rz: '#E3DAF7', cu1: '#F6BEAC', swap: '#CDEBD6', ccx: '#FFDCD2' };

  function parseQasm(src) {
    const lines = src.split(/\r?\n/);
    let nq = 0; const ops = [];
    for (const raw of lines) {
      const line = raw.split('//')[0].trim();
      if (!line) continue;
      const qreg = line.match(/^qreg\s+q\[(\d+)\]\s*;/);
      if (qreg) { nq = parseInt(qreg[1], 10); continue; }
      if (/^(creg|include|OPENQASM|measure)/i.test(line)) {
        if (/^measure/i.test(line)) ops.push({ g: 'measure' });
        continue;
      }
      const m = line.match(
        /^([a-z]\w*)\s*(?:\(([^)]*)\))?\s+(.+?)\s*;$/);
      if (!m) continue;
      const targets = [...m[3].matchAll(/q\[(\d+)\]/g)]
        .map((x) => parseInt(x[1], 10));
      ops.push({ g: m[1], angle: m[2] ? m[2].trim() : null,
                 qs: targets });
    }
    return { nq, ops };
  }

  function fmtAngle(a) {
    if (!a) return '';
    const v = a.replace(/\s+/g, '');
    if (/^(-?)([\d.]+)pi\/(\d+)$/.test(v)) {
      return (v.startsWith('-') ? '-' : '') + 'π/' +
        v.match(/pi\/(\d+)/)[1];
    }
    if (v === 'pi') return 'π';
    if (v === '-pi') return '-π';
    const num = parseFloat(v);
    if (!isNaN(num)) return Number(num.toFixed(2)).toString();
    return v.replace(/pi/g, 'π');
  }

  function renderCircuit(src) {
    const { nq, ops } = parseQasm(src);
    if (!nq) return;
    const realOps = ops.filter((o) => o.g !== 'measure');
    const colW = 66, rowH = 54, padL = 46, padT = 26;
    const width = Math.max(320,
      padL + (realOps.length + 1) * colW + 30);
    const height = padT * 2 + Math.max(nq, 1) * rowH;
    const cy = (q) => padT + q * rowH + rowH / 2;
    let s = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`;
    for (let q = 0; q < nq; q++) {
      s += `<text x="${padL - 12}" y="${cy(q) + 4}" font-size="11" ` +
           `fill="#B99C8C" text-anchor="end">q${q}</text>`;
      s += `<line x1="${padL}" y1="${cy(q)}" x2="${width - 18}" ` +
           `y2="${cy(q)}" stroke="#EBD9CC" stroke-width="2" ` +
           `stroke-linecap="round"/>`;
    }
    let col = 0;
    for (const op of realOps) {
      const x = padL + col * colW + colW / 2;
      const qs = op.qs && op.qs.length ? op.qs : [0];
      const color = GATE_COLORS[op.g] || '#F0E4DB';
      if (op.g === 'cx' || op.g === 'ccx' || op.g === 'cu1') {
        const cqs = qs.slice(0, -1), tq = qs[qs.length - 1];
        const y1 = Math.min(...qs.map(cy)), y2 = Math.max(...qs.map(cy));
        s += `<line x1="${x}" y1="${y1}" x2="${x}" y2="${y2}" ` +
             `stroke="#8C8180" stroke-width="2"/>`;
        for (const c of cqs)
          s += `<circle cx="${x}" cy="${cy(c)}" r="5" fill="#6B5A55"/>`;
        if (op.g === 'cu1') {
          for (const q of qs)
            s += pill(x, cy(q), op.g.toUpperCase(), color, fmtAngle(op.angle));
        } else {
          s += `<circle cx="${x}" cy="${cy(tq)}" r="11" fill="#fff" ` +
               `stroke="#6B5A55" stroke-width="2"/>` +
               `<line x1="${x - 11}" y1="${cy(tq)}" x2="${x + 11}" ` +
               `y2="${cy(tq)}" stroke="#6B5A55" stroke-width="2"/>` +
               `<line x1="${x}" y1="${cy(tq) - 11}" x2="${x}" ` +
               `y2="${cy(tq) + 11}" stroke="#6B5A55" stroke-width="2"/>`;
        }
      } else if (op.g === 'swap') {
        for (const q of qs) {
          const y = cy(q);
          s += `<line x1="${x - 7}" y1="${y - 7}" x2="${x + 7}" ` +
               `y2="${y + 7}" stroke="#5FA483" stroke-width="2.4"/>` +
               `<line x1="${x - 7}" y1="${y + 7}" x2="${x + 7}" ` +
               `y2="${y - 7}" stroke="#5FA483" stroke-width="2.4"/>`;
        }
        if (qs.length === 2)
          s += `<line x1="${x}" y1="${cy(qs[0])}" x2="${x}" ` +
               `y2="${cy(qs[1])}" stroke="#8C8180" stroke-width="2"/>`;
      } else {
        for (const q of qs)
          s += pill(x, cy(q), op.g.toUpperCase(), color, fmtAngle(op.angle));
      }
      col++;
    }
    const mx = padL + (realOps.length) * colW + colW / 2;
    for (let q = 0; q < nq; q++) {
      s += `<rect x="${mx - 14}" y="${cy(q) - 13}" width="28" height="26" ` +
           `rx="7" fill="#453B38"/>` +
           `<path d="M ${mx - 6} ${cy(q) - 5} h 9 v 7 h -9 z M ${mx - 6} ` +
           `${cy(q) - 5} l 9 7 l 4 -3" fill="none" stroke="#FCE9DF" ` +
           `stroke-width="1.6"/>` +
           `<circle cx="${mx + 8}" cy="${cy(q) + 7}" r="1.6" fill="#F27E63"/>`;
    }
    s += '</svg>';
    circuitEl.className = 'circuit';
    circuitEl.innerHTML = s;
  }

  function pill(x, y, label, fill, sub) {
    const w = Math.max(34, 16 + label.length * 8 + (sub ? sub.length * 6 : 0));
    return `<g><rect x="${x - w / 2}" y="${y - 15}" width="${w}" height="30" ` +
      `rx="10" fill="${fill}" stroke="#E9CDBC" stroke-width="1.4"/>` +
      `<text x="${x - (sub ? 6 : 0)}" y="${y + (sub ? -1 : 4)}" ` +
      `font-size="11.5" font-weight="700" fill="#5A443C" ` +
      `text-anchor="middle">${label}</text>` +
      (sub ? `<text x="${x + 8}" y="${y + 9}" font-size="8.5" ` +
        `fill="#8C6F63" text-anchor="middle">${sub}</text>` : '') +
      `</g>`;
  }

  /* ---------------- histogram ---------------- */
  const BAR_COLORS = ['#F2917A', '#F5B78F', '#FBD9A6', '#BCDFC5',
                      '#B9C7EE', '#CBAEE0'];

  async function run() {
    if (!currentQasm || runBtn.disabled) return;
    runBtn.disabled = true;
    runBtn.textContent = '⏳ Kitty在摇骰子…';
    try {
      const r = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qasm: currentQasm,
                               target: targetSel.value, shots: 1024 }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || ('HTTP ' + r.status));
      drawHist(data.counts, data.target, data.shots);
      petMeow('喵呜！波函数坍缩成结果啦 ✨');
    } catch (e) {
      petMeow('喵？！被毛线缠住了…');
      resultEl.className = 'result empty';
      resultEl.innerHTML = '<p class="placeholder">跑失败了：' +
        esc(e.message) + '</p>';
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = '🎲 掷 1024 次量子骰子';
    }
  }
  runBtn.addEventListener('click', run);

  function drawHist(counts, target, shots) {
    const entries = Object.entries(counts || {})
      .sort((a, b) => b[1] - a[1]).slice(0, 8);
    const max = entries.length ? entries[0][1] : 1;
    let html = '';
    entries.forEach(([k, v], i) => {
      const pct = ((v / shots) * 100).toFixed(1);
      html += `<div class="bar-row">` +
        `<span class="bar-key">${esc(k)}</span>` +
        `<div class="bar-track"><div class="bar-fill" data-w=` +
        `"${Math.max(4, (v / max) * 100)}" style="background:` +
        `${BAR_COLORS[i % BAR_COLORS.length]}"></div></div>` +
        `<span class="bar-val">${pct}%</span></div>`;
    });
    html += `<div class="run-note">Kitty用 <b>${esc(target)}</b> 魔法锅掷了 ` +
      `${shots} 次 · 柱子越高，它越喜欢变出这个结果 ✨</div>`;
    resultEl.className = 'result';
    resultEl.innerHTML = html;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      resultEl.querySelectorAll('.bar-fill').forEach((el) => {
        el.style.width = el.dataset.w + '%';
      });
    }));
  }

  /* ---------------- desktop pet Kitty ---------------- */
  const pet = document.getElementById('pet');
  const petBubble = pet ? pet.querySelector('.pet-bubble') : null;
  let bubbleTimer = null;

  function petMeow(text, ms) {
    if (!pet) return;
    petBubble.textContent = text;
    petBubble.hidden = false;
    pet.classList.add('hop');
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => { petBubble.hidden = true; }, ms || 3400);
  }

  if (pet) {
    let drag = null;
    pet.addEventListener('pointerdown', (ev) => {
      const r = pet.getBoundingClientRect();
      drag = { dx: ev.clientX - r.left, dy: ev.clientY - r.top,
               moved: false };
      pet.setPointerCapture(ev.pointerId);
    });
    pet.addEventListener('pointermove', (ev) => {
      if (!drag) return;
      const r = pet.getBoundingClientRect();
      const nx = ev.clientX - drag.dx, ny = ev.clientY - drag.dy;
      if (Math.abs(nx - r.left) + Math.abs(ny - r.top) > 6) drag.moved =
        true;
      if (!drag.moved) return;
      const maxX = innerWidth - r.width, maxY = innerHeight - r.height;
      pet.style.left = Math.min(Math.max(0, nx), maxX) + 'px';
      pet.style.top = Math.min(Math.max(0, ny), maxY) + 'px';
      pet.style.right = 'auto'; pet.style.bottom = 'auto';
    });
    pet.addEventListener('pointerup', () => {
      if (drag && !drag.moved) {
        petMeow(['喵~', '喵呜？', '在叠加态里等你哦~',
                 '摸猫要负责哦 🐾'][Math.floor(Math.random() * 4)], 2200);
      }
      drag = null;
    });
    const IDLE = ['喵~ 想变出一个贝尔态吗？',
      '薛定谔说：不打开盒子，就不知道我在干嘛',
      '今天也要好好观察呀 🔭', '喵…骰子掷过 1024 次了吗？'];
    setInterval(() => {
      if (document.visibilityState === 'visible' &&
          petBubble.hidden && !sendBtn.disabled &&
          Math.random() < 0.55) {
        petMeow(IDLE[Math.floor(Math.random() * IDLE.length)]);
      }
    }, 50000);
  }
})();


/* ══════════════ 量子Kitty IP · 统一像素精灵库 ══════════════ */
const KITTY_PIX = (() => {
  const PAL = { o: '#4A332E', B: '#FFB49A', L: '#FFE9E2', E: '#33221F',
                N: '#D95F45', W: '#FFF6EF' };
  const SIT = [
    '...oo.......oo.....',
    '..oBBo.....oBBo....',
    '..oBLBo...oBLBo....',
    '..oBBBooooBBBo.....',
    '.oBBBBBBBBBBBBBo...',
    '.oBBBBBBBBBBBBBo...',
    '.oBEeBBBBBBEeBBo...',
    '.oBBBBBBNNBBBBBo...',
    '.oBWWBBBBBBWWBBo...',
    '..oBBBBBBBBBBo.....',
    '..oBBBBBBBBBBo.....',
    '.oBBBBBBBBBBBBo....',
    '.oBBBBBBBBBBBBo....',
    '..oBBBo...oBBBo....',
    '...oo.......oo.....'
  ];
  /* 趴趴面包猫：与 SIT 同一调色板，程序化生成再描边 */
  function buildLoaf(tailUp) {
    const W = 30, H = 13;
    const g = [...Array(H)].map(() => Array(W).fill('.'));
    const put = (x, y, c) => { if (x >= 0 && y >= 0 && x < W && y < H) g[y][x] = c; };
    const ell = (cx, cy, rx, ry, c) => {
      for (let y = -ry; y <= ry; y++)
        for (let x = -rx; x <= rx; x++)
          if ((x * x) / (rx * rx) + (y * y) / (ry * ry) <= 1.05) put(cx + x, cy + y, c);
    };
    ell(17, 8, 10, 3, 'B');                    /* 身体：长面包 */
    ell(8, 6, 5, 4, 'B');                      /* 头 */
    [[5, 1], [11, 1]].forEach(([ax, ay]) => {  /* 耳朵 */
      for (let d = 0; d < 3; d++)
        for (let x = ax - d; x <= ax + d; x++) put(x, ay + d, 'B');
    });
    [[5, 6], [6, 6], [10, 6], [11, 6]].forEach(([x, y]) => put(x, y, 'E'));
    put(8, 7, 'N');
    ell(13, 9, 4, 1, 'L');
    const tail = tailUp
      ? [[27, 7], [28, 6], [28, 5], [29, 4]]
      : [[27, 8], [28, 7], [28, 6], [29, 5]];
    tail.forEach(([x, y], i) => put(x, y, i === 3 ? 'N' : 'B'));
    const out = g.map(r => r.slice());
    for (let y = 0; y < H; y++)
      for (let x = 0; x < W; x++) {
        if (g[y][x] !== '.') continue;
        const touch = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => {
          const yy = y + dy, xx = x + dx;
          return yy >= 0 && xx >= 0 && yy < H && xx < W && g[yy][xx] !== '.';
        });
        if (touch) out[y][x] = 'o';
      }
    return out.map(r => r.join(''));
  }
  const PSI = ['l.l.l', 'l.l.l', 'lllll', '..l..', '..l..'];
  function drawMat(ctx, mat, px, ox, oy, pal) {
    mat.forEach((row, r) => { [...row].forEach((ch, c) => {
      const col = (pal || PAL)[ch];
      if (!col) return;
      ctx.fillStyle = col;
      ctx.fillRect((ox + c) * px, (oy + r) * px, px, px);
    }); });
  }
  function drawSit(canvas, closedEyes) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawMat(ctx, SIT, 1, 0, 0);
    if (closedEyes) SIT.forEach((row, r) => { [...row].forEach((ch, c) => {
      if (ch !== 'E') return;
      ctx.fillStyle = PAL.o;
      ctx.fillRect(c, r, 1, 1);
    }); });
  }
  const brand = document.getElementById('brand-cat');
  const petCv = document.getElementById('pet-canvas');
  if (brand) drawSit(brand, false);
  if (petCv) {
    drawSit(petCv, false);
    setInterval(() => {
      drawSit(petCv, true);
      setTimeout(() => drawSit(petCv, false), 150);
    }, 4300);
  }
  return { PAL, SIT, PSI, buildLoaf, drawMat, drawSit };
})();
/* ══════════════ 开场：像素 Kitty 展开式入场 ══════════════ */
(() => {
  'use strict';
  const intro = document.getElementById('intro');
  if (!intro) return;
  document.body.classList.add('intro-open');
  const cvs = document.getElementById('intro-cat');
  const ctx = cvs.getContext('2d');
  const CELL = 2, CW = cvs.width / CELL, CH = cvs.height / CELL; /* 116×84 格 */
  const T0 = performance.now();
  /* —— 富士山几何（格坐标）：平顶平台正好够一只猫躺 —— */
  const APX_L = 41, APX_R = 74, APX_Y = 32, BASE_Y = 77,
        FOOT_L = 5, FOOT_R = 110, SNOW_Y = 45;
  const fujiTop = (x) =>
    x < APX_L ? APX_Y + (APX_L - x) * (BASE_Y - APX_Y) / (APX_L - FOOT_L)
    : x > APX_R ? APX_Y + (x - APX_R) * (BASE_Y - APX_Y) / (FOOT_R - APX_R)
    : APX_Y;
  /* 星星：固定种子，避开月亮和山体 */
  const stars = [];
  {
    let s = 20260824;
    const rnd = () => ((s = (s * 1103515245 + 12345) % 2147483648) / 2147483648);
    let guard = 0;
    while (stars.length < 46 && guard++ < 900) {
      const x = 2 + Math.floor(rnd() * (CW - 4));
      const y = 2 + Math.floor(rnd() * (CH * 0.55));
      if (Math.hypot(x - 20, y - 14) < 12) continue;
      if (y > fujiTop(x) - 3) continue;
      stars.push({ x, y, ph: rnd() * 6.28 });
    }
  }
  const rock = [], snow = [];
  for (let x = 0; x < CW; x++) {
    const top = fujiTop(x);
    for (let y = Math.max(1, Math.ceil(top)); y < CH; y++) {
      if (y <= SNOW_Y + ((x * 7) % 3 === 0 ? 1 : 0)) snow.push({ x, y });
      else rock.push({ x, y, c: x > 65 ? '#3E4879' : '#4A5590' });
    }
  }
  const loafA = KITTY_PIX.buildLoaf(true);
  const loafB = KITTY_PIX.buildLoaf(false);
  const CAT_OX = 42, CAT_OY = 19;
  const catPixels = [];
  loafA.forEach((row, r) => [...row].forEach((ch, c) => {
    if (KITTY_PIX.PAL[ch]) catPixels.push({ c, r, ch });
  }));
  catPixels.sort((a, b) =>
    (Math.hypot(a.c - 15, a.r - 6) + Math.random() * 2) -
    (Math.hypot(b.c - 15, b.r - 6) + Math.random() * 2));
  const SPARK = [[40, 21], [73, 19], [66, 27]];
  const lpal = Object.assign({ l: '#CBB4E8' }, KITTY_PIX.PAL);
  const ease = (v) => 1 - Math.pow(1 - Math.max(0, Math.min(1, v)), 2);
  const stage = (t, a, b) => ease((t - a) / (b - a));

  function render(now) {
    const t = now - T0;
    const SKY = ['#141132', '#1A1540', '#211B4E', '#29225D', '#32296D'];
    for (let i = 0; i < SKY.length; i++) {
      ctx.fillStyle = SKY[i];
      ctx.fillRect(0, Math.floor(CH * i / SKY.length) * CELL,
                   cvs.width, Math.ceil(CH / SKY.length) * CELL + 1);
    }
    const sp = stage(t, 0, 520);
    stars.forEach((st, i) => {
      if (i > sp * stars.length) return;
      const tw = 0.55 + 0.45 * Math.sin(t / 420 + st.ph);
      ctx.globalAlpha = tw;
      ctx.fillStyle = tw > 0.78 ? '#FFF6EF' : '#B9AFE8';
      ctx.fillRect(st.x * CELL, st.y * CELL, CELL, CELL);
      ctx.globalAlpha = 1;
    });
    const mp = stage(t, 1080, 1420);
    if (mp > 0) {
      const mr = Math.max(1, Math.round(8 * mp));
      for (let y = -mr; y <= mr; y++)
        for (let x = -mr; x <= mr; x++)
          if (x * x + y * y <= mr * mr) {
            ctx.fillStyle = (x * 5 + y * 3) % 11 === 0 ? '#F1E2BC' : '#FFF1CE';
            ctx.fillRect((20 + x) * CELL, (14 + y) * CELL, CELL, CELL);
          }
    }
    const rp = stage(t, 320, 1020), np2 = stage(t, 880, 1280);
    const maxX = 2 + rp * (CW - 4);
    rock.forEach(p => { if (p.x <= maxX) {
      ctx.fillStyle = p.c;
      ctx.fillRect(p.x * CELL, p.y * CELL, CELL, CELL); } });
    if (np2 > 0) { ctx.fillStyle = '#F4F1FF';
      snow.forEach((p, i) => { if (i <= np2 * snow.length)
        ctx.fillRect(p.x * CELL, p.y * CELL, CELL, CELL); }); }
    const cp = stage(t, 1260, 2050);
    if (cp >= 1) {
      KITTY_PIX.drawMat(ctx, Math.floor(t / 850) % 2 ? loafB : loafA,
                        CELL, CAT_OX, CAT_OY);
    } else {
      const nShow = Math.floor(cp * catPixels.length);
      for (let i = 0; i < nShow && i < catPixels.length; i++) {
        const p = catPixels[i];
        ctx.fillStyle = KITTY_PIX.PAL[p.ch] || KITTY_PIX.PAL.B;
        ctx.fillRect((CAT_OX + p.c) * CELL, (CAT_OY + p.r) * CELL, CELL, CELL);
      }
    }
    if (t > 1980) {
      const bob = Math.round(Math.sin((t - 1980) / 620) * 1.4);
      ctx.save();
      ctx.shadowColor = '#CBB4E8'; ctx.shadowBlur = 8;
      KITTY_PIX.drawMat(ctx, KITTY_PIX.PSI, CELL, 49, 13 + bob, lpal);
      ctx.restore();
    }
    SPARK.forEach(([sx, sy], i) => {
      if (t < 2050 || ((t / 430 + i) | 0) % 2 === 0) return;
      ctx.fillStyle = '#FFD9E8';
      [[0, 0], [-1, 0], [1, 0], [0, -1], [0, 1]].forEach(([dx, dy]) =>
        ctx.fillRect((sx + dx) * CELL, (sy + dy) * CELL, CELL, CELL));
    });
  }
  let raf = null, done = false;
  function loop(now) { render(now); raf = requestAnimationFrame(loop); }

  const titleEl = document.getElementById('intro-title');
  const TITLE = '量子Kitty';
  let ti = 0;
  const typeTimer = setInterval(() => {
    titleEl.textContent = TITLE.slice(0, ++ti);
    if (ti >= TITLE.length) clearInterval(typeTimer);
  }, 130);
  raf = requestAnimationFrame(loop);

  function finish() {
    if (done) return; done = true;
    cancelAnimationFrame(raf); clearInterval(typeTimer);
    titleEl.textContent = TITLE;
    intro.classList.add('bye');
    document.body.classList.remove('intro-open');
    document.body.classList.add('app-in');
    setTimeout(() => intro.remove(), 700);
  }
  document.getElementById('intro-go').addEventListener('click', finish);
  intro.addEventListener('click', (ev) => {
    if (ev.target.id !== 'intro-go') setTimeout(finish, 240); // 点任意处快进
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === 'Escape') finish();
  }, { once: false });
})();

/* ══════════════ 量子试炼：游戏化学习模块 ══════════════ */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const rail = $('lvl-rail'), goalEl = $('q-goal'), tgtEl = $('q-target'),
        slotsEl = $('q-slots'), padEl = $('q-pad'), barsEl = $('q-bars'),
        msgEl = $('q-msg'), badgesEl = $('badges');
  if (!rail) return;

  /* ---- 内置状态向量模拟器（实数版，覆盖 H/X/CX） ---- */
  function simulate(nq, seq) {
    let amp = new Array(1 << nq).fill(0); amp[0] = 1;
    const R2 = Math.SQRT1_2;
    for (const g of seq) {
      if (g.k === 'H') {
        for (let i = 0; i < amp.length; i++) {
          if (i & (1 << g.q)) continue;
          const x = amp[i], y = amp[i | (1 << g.q)];
          amp[i] = (x + y) * R2; amp[i | (1 << g.q)] = (x - y) * R2;
        }
      } else if (g.k === 'X') {
        for (let i = 0; i < amp.length; i++) {
          if (i & (1 << g.q)) continue;
          const t = amp[i]; amp[i] = amp[i | (1 << g.q)];
          amp[i | (1 << g.q)] = t;
        }
      } else if (g.k === 'CX') {
        for (let i = 0; i < amp.length; i++) {
          if (!((i >> g.c) & 1) || (i & (1 << g.t))) continue;
          const j = i | (1 << g.t);
          const t2 = amp[i]; amp[i] = amp[j]; amp[j] = t2;
        }
      }
    }
    const probs = {};
    for (let i = 0; i < amp.length; i++) {
      let key = '';
      for (let q = nq - 1; q >= 0; q--) key += ((i >> q) & 1);
      probs[key] = (probs[key] || 0) + amp[i] * amp[i];
    }
    return probs;
  }
  const close = (p, t) => Math.abs(p - t) <= 0.02;

  /* ---- 关卡表 ---- */
  const GATES = {
    H:  { k:'H',  label:'H',  cn:'叠加' },
    X:  { k:'X',  label:'X',  cn:'翻转' },
    CX: { k:'CX', label:'CX', cn:'控制 q₀→q₁', c:0, t:1 },
    CX2:{ k:'CX', label:'CX', cn:'控制 q₁→q₂', c:1, t:2 }
  };
  const LEVELS = [
    { id:1, name:'唤醒',   nq:1, pal:['X'], par:1,
      goal:'小猫在 |0⟩ 里睡着啦。用 <b>X 门</b>把它翻个面，变成确定的 |1⟩。',
      target:{'0':0,'1':1} },
    { id:2, name:'叠加',   nq:1, pal:['H','X'], par:1,
      goal:'让比特同时站在 0 和 1 之间——<b>H 门</b>一劈两半，各 50%。',
      target:{'0':.5,'1':.5} },
    { id:3, name:'纠缠',   nq:2, pal:['H','CX'], par:2,
      goal:'贝尔态来了：<b>H</b> 劈开 q₀，再用 <b>CX</b> 让 q₁ 牵手——从此它俩同起同落。',
      target:{'00':.5,'11':.5} },
    { id:4, name:'镜像贝尔', nq:2, pal:['H','X','CX'], par:3,
      goal:'这次要 01 和 10 各一半。提示：<b>先纠缠，再翻转其中一根线</b>。',
      target:{'01':.5,'10':.5} },
    { id:5, name:'三胞胎', nq:3, pal:['H','CX','CX2'], par:3,
      goal:'GHZ 态：三根线要么全 000，要么全 111。<b>CX 接力两次</b>。',
      target:{'000':.5,'111':.5} },
    { id:6, name:'反转三胞胎', nq:3, pal:['H','X','CX','CX2'], par:4,
      goal:'毕业考！目标变成 <b>001 / 110</b> 各半。先做出三胞胎，再想想哪里差一下。',
      target:{'001':.5,'110':.5} }
  ];
  const RANKS = [[0,'见习猫'],[120,'量子学徒'],[260,'纠缠骑士'],
                 [420,'叠加法师'],[600,'薛定谔大师']];
  const BADGES = [
    ['first','🐾 初出茅庐'], ['entangle','🔗 首次纠缠'],
    ['ghz','🍬 三胞胎诞辰'], ['grad','🎓 毕业礼'],
    ['perfect','⭐ 完美主义']
  ];
  let S = load();
  function load() {
    try { return JSON.parse(localStorage.getItem('kitty-quest-v1')) ||
      { xp:0, done:{}, bad:[] }; }
    catch (e) { return { xp:0, done:{}, bad:[] }; }
  }
  function save() { try { localStorage.setItem('kitty-quest-v1',
    JSON.stringify(S)); } catch (e) {} }

  let cur = null, seq = [], wrong = 0;
  const unlocked = (lv) => lv.id === 1 || S.done[lv.id - 1];
  function curLevel() {
    for (const lv of LEVELS) if (!S.done[lv.id]) return lv;
    return LEVELS[LEVELS.length - 1];
  }

  function rankOf(xp) {
    let r = RANKS[0], idx = 1;
    for (let i = 0; i < RANKS.length; i++)
      if (xp >= RANKS[i][0]) { r = RANKS[i]; idx = i + 1; }
    const next = RANKS[idx];
    const base = r[0], span = next ? next[0] - base : 1;
    const pct = next ? Math.min(100,
      Math.round(((xp - base) / span) * 100)) : 100;
    return { name:r[1], lv:idx, pct };
  }
  function paintXP() {
    const r = rankOf(S.xp);
    $('xp-rank').textContent = r.name;
    $('xp-num').textContent = 'Lv.' + r.lv;
    $('xp-fill').style.width = r.pct + '%';
  }
  function paintBadges() {
    badgesEl.innerHTML = BADGES.map(([id, name]) =>
      `<span class="badge-pill${S.bad.includes(id) ? '' : ' off'}">${name}</span>`
    ).join('');
  }
  function grant(id) {
    if (!S.bad.includes(id)) { S.bad.push(id); save(); paintBadges();
      say(`解锁徽章：<b>${BADGES.find(b=>b[0]===id)[1]}</b>`, true); }
  }

  function say(html, ok) {
    msgEl.className = 'q-msg show ' + (ok ? 'ok' : 'no');
    msgEl.innerHTML = html;
  }
  function confetti(el) {
    const r = el.getBoundingClientRect();
    const colors = ['#FF9D78','#FFD36B','#9CCDAF','#9F86D6','#7FC8A9'];
    for (let i = 0; i < 26; i++) {
      const d = document.createElement('div');
      d.className = 'fx-pixel';
      d.style.left = (r.left + r.width/2) + 'px';
      d.style.top = (r.top + r.height/2) + 'px';
      d.style.background = colors[i % colors.length];
      d.style.setProperty('--fx', (Math.random()*260-130)+'px');
      d.style.setProperty('--fy', (-40-Math.random()*160)+'px');
      document.body.appendChild(d);
      setTimeout(() => d.remove(), 950);
    }
  }

  function openLevel(lv) {
    cur = lv; seq = []; wrong = 0;
    rail.querySelectorAll('.lvl-node').forEach((n) => {
      n.classList.toggle('cur', +n.dataset.id === lv.id);
    });
    goalEl.innerHTML = `<b>第 ${lv.id} 关 · ${lv.name}</b>　${lv.goal}`;
    const keys = Object.keys(lv.target).sort();
    tgtEl.innerHTML = '<h3>目标分布</h3>' + keys.map((k) =>
      `<div class="tgt-row"><span class="tgt-key">${k}</span>` +
      `<div class="tgt-track"><div class="tgt-fill" style="width:${lv.target[k]*100}%"></div></div>` +
      `<span class="tgt-val">${Math.round(lv.target[k]*100)}%</span></div>`).join('');
    padEl.innerHTML = lv.pal.map((key) => {
      const g = GATES[key];
      return `<button class="q-gate ${g.k==='CX'?'cx':''}" data-g="${key}">` +
        `<b>${g.label}</b><span>${g.cn}</span></button>`;
    }).join('');
    padEl.querySelectorAll('.q-gate').forEach((b) =>
      b.addEventListener('click', () => place(b.dataset.g)));
    barsEl.innerHTML = ''; sayHide();
    paintSlots(); paintRail();
  }
  function sayHide() { msgEl.className = 'q-msg'; msgEl.innerHTML = ''; }
  function paintSlots() {
    slotsEl.innerHTML = seq.length
      ? seq.map((g) => `<span class="gate-chip-in"><b>${GATES[g].label}</b>${GATES[g].cn}</span>`).join('')
      : '<span class="slot-empty">点击下方门按钮，把电路拼出来 →</span>';
  }
  function paintRail() {
    rail.innerHTML = LEVELS.map((lv) => {
      const cls = S.done[lv.id] ? 'done' : (unlocked(lv) ? 'cur' : 'lock');
      const st = S.done[lv.id]
        ? '<small>' + '★'.repeat(S.done[lv.id].stars) + '</small>' : '';
      return `<button class="lvl-node ${cls}" data-id="${lv.id}" ` +
        `${unlocked(lv) ? '' : 'disabled'}>第${lv.id}关${st}</button>`;
    }).join('');
    rail.querySelectorAll('.lvl-node:not(.lock)').forEach((n) =>
      n.addEventListener('click', () =>
        openLevel(LEVELS.find((l) => l.id === +n.dataset.id))));
  }
  function place(key) {
    if (seq.length >= 8) { say('电路太长啦，猫会打结的。先验证或重来吧。', false); return; }
    seq.push(key); paintSlots(); sayHide();
  }
  $('q-undo').addEventListener('click', () => { seq.pop(); paintSlots(); });
  $('q-reset').addEventListener('click', () => { seq = []; paintSlots(); sayHide(); });
  $('q-check').addEventListener('click', () => {
    if (!cur) return;
    if (!seq.length) { say('先放一个门进去试试？', false); return; }
    const mine = simulate(cur.nq, seq.map((k) => GATES[k]));
    let ok = true;
    const keys = new Set([...Object.keys(cur.target), ...Object.keys(mine)]);
    let html = '<h3 style="font-size:11.5px;color:#8C8180;margin-bottom:6px">你的分布 vs 目标</h3>';
    [...keys].sort().forEach((k) => {
      const m = mine[k] || 0, t = cur.target[k] || 0;
      const good = close(m, t); if (!good) ok = false;
      html += `<div class="tgt-row"><span class="tgt-key">${k}</span>` +
        `<div class="tgt-track"><div class="tgt-fill" style="width:${Math.round(m*100)}%;` +
        `background:${good ? 'linear-gradient(90deg,#9CCDAF,#5FB48D)' : 'linear-gradient(90deg,#F6BEAC,#F27E63)'}"></div></div>` +
        `<span class="tgt-val">你 ${Math.round(m*100)}% / 目标 ${Math.round(t*100)}%</span></div>`;
    });
    barsEl.innerHTML = html;
    if (ok) {
      const stars = (seq.length <= cur.par) ? 3 : (seq.length <= cur.par + 2 ? 2 : 1);
      const prev = S.done[cur.id];
      if (!prev || stars > prev.stars) S.done[cur.id] = { stars };
      const gain = stars * 30;
      S.xp += gain; save(); paintXP(); paintRail();
      confetti($('q-check'));
      say(`🎉 融合成功！<b>${'★'.repeat(stars)}</b>　经验 +${gain}` +
        (stars === 3 ? '　完美操作，猫爪点赞！' : '　试试更少的门数拿三星？'), true);
      if (cur.id === 1) grant('first');
      if (cur.id === 3) grant('entangle');
      if (cur.id === 5) grant('ghz');
      if (cur.id === 6) { grant('grad');
        say('🎉 全部通关！你已经掌握了叠加与纠缠的入门魔法。去左边跟 Kitty 说点别的吧～', true); }
      if (stars === 3) grant('perfect');
      const nxt = LEVELS.find((l) => l.id === cur.id + 1);
      if (nxt && !S.done[nxt.id])
        setTimeout(() => openLevel(nxt), 1400);
    } else {
      wrong++;
      say('还差一点！对照下面的目标分布，看看哪根线不对劲。Kitty 相信你 🐾', false);
    }
  });

  paintXP(); paintBadges(); openLevel(curLevel());
})();

/* ══════════ 知识卡 Quiz ══════════ */
(function () {
  const $ = (id) => document.getElementById(id);
  const CARDS = [
    { tag: '入门', q: '什么是量子比特（qubit）？',
      a: '经典比特只能当 0 或 1；量子比特可以同时处于 0 和 1 的「叠加态」——像一枚还没落地的旋转硬币。' },
    { tag: '入门', q: '叠加态是什么？',
      a: '旋转中的硬币：停下之前既不是正面也不是反面，而是两者的混合。测量（看它）的一瞬间才坍缩成确定结果。' },
    { tag: '核心', q: '量子纠缠是什么？',
      a: '两个比特绑定命运：无论相隔多远，一个被测量，另一个的结果立刻确定——爱因斯坦称之为「幽灵般的超距作用」。' },
    { tag: '门', q: 'X 门做什么？',
      a: '翻转门：把 0 变成 1、1 变成 0。相当于经典的 NOT 开关。' },
    { tag: '门', q: 'H 门（Hadamard）的魔法是什么？',
      a: '把确定的 0 劈成 50%/50% 的叠加；对叠加态再劈一次会因干涉回到确定态——它是量子算法的心脏。' },
    { tag: '门', q: 'CX 门为什么重要？',
      a: '纠缠制造机：控制比特为 1 时翻转目标比特，把两个比特的命运绑在一起——贝尔态就是 H + CX 拼出来的。' },
    { tag: '核心', q: '测量的时候发生了什么？',
      a: '叠加态坍缩成一个确定结果。单次测量看不出概率，掷 1024 次「量子骰子」才能看到分布。' },
    { tag: '进阶', q: '贝尔态是什么？',
      a: '最简单的纠缠态：两个比特的测量结果永远相同，00 和 11 各占 50%。' },
    { tag: '进阶', q: 'GHZ 态和贝尔态是什么关系？',
      a: '三胞胎版：三个比特纠缠在一起，000 和 111 各 50%——一荣俱荣，一损俱损。' },
    { tag: '冷知识', q: '为什么真机要泡在极低温里？',
      a: '退相干：环境的热噪声会破坏量子态。超导芯片要在接近绝对零度（约 -273°C）才能保住量子性。' }
  ];
  const KEY = 'kitty-cards-v1';
  let deck = [], idx = 0;
  let mastered = new Set();
  try {
    (JSON.parse(localStorage.getItem(KEY) || '{"mastered":[]}').mastered || [])
      .forEach(k => mastered.add(Number(k)));
  } catch (e) {}
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify({ mastered: [...mastered] })); }
    catch (e) {}
  }
  function shuffle() {
    deck = CARDS.map((_, i) => i);
    for (let i = deck.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [deck[i], deck[j]] = [deck[j], deck[i]];
    }
    idx = 0;
  }
  function remaining() { return deck.filter(i => !mastered.has(i)); }
  function render() {
    $('kcard').classList.remove('flipped');
    $('quiz-score').textContent =
      '已掌握 ' + mastered.size + '/' + CARDS.length;
    $('quiz-dots').innerHTML = CARDS.map((_, i) =>
      '<span class="dot' + (mastered.has(i) ? ' done' : '') + '"></span>').join('');
    const left = remaining();
    if (!left.length) {
      $('k-tag').textContent = '毕业';
      $('k-q').textContent = '全部记住了！你是量子Kitty认证的小小学霸 🎓';
      $('k-tag2').textContent = '毕业';
      $('k-a').textContent = '去下面的试炼关卡露一手吧～';
      $('quiz-actions').style.display = 'none';
      return;
    }
    $('quiz-actions').style.display = '';
    const c = CARDS[left[idx % left.length]];
    $('kcard').dataset.ci = CARDS.indexOf(c);
    $('k-tag').textContent = c.tag;
    $('k-tag2').textContent = c.tag;
    $('k-q').textContent = c.q;
    $('k-a').textContent = c.a;
  }
  $('flip-zone').addEventListener('click', () =>
    $('kcard').classList.toggle('flipped'));
  $('k-got').addEventListener('click', () => {
    mastered.add(Number($('kcard').dataset.ci));
    save(); render();
  });
  $('k-again').addEventListener('click', () => { idx++; render(); });
  $('k-shuffle').addEventListener('click', () => { shuffle(); render(); });
  $('k-reset').addEventListener('click', () => {
    mastered.clear(); save(); shuffle(); render();
  });
  shuffle(); render();
})();

/* ══════════ 吸顶导航高亮 ══════════ */
(function () {
  const links = [...document.querySelectorAll('.nav-link')];
  const secs = ['learn', 'cards', 'game'].map(id => document.getElementById(id));
  window.addEventListener('scroll', () => {
    const y = window.scrollY + 150;
    let cur = 0;
    secs.forEach((s, i) => { if (s && s.offsetTop <= y) cur = i; });
    links.forEach((l, i) => l.classList.toggle('active', i === cur));
  }, { passive: true });
})();
