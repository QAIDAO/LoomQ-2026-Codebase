"use strict";

/* LoomQ · 一道只能问一次的谜题
   只做 Deutsch。助手留在右下角，不挡主线。 */

const $ = (id) => document.getElementById(id);
function on(id, event, fn) {
  const el = $(id);
  if (!el) {
    console.error("页面缺了 #" + id + "，这一处按钮绑不上");
    return;
  }
  el.addEventListener(event, fn);
}

const state = {
  act: 0,
  deutschSession: null,
  deutschAsked: {},
  secretSession: null,
  secretVerdict: null,
  pathVerdict: null,
  loadedReady: false,
  loadedFlips: 0,
  trySession: null,
  tryAsked: {},
  tryFlips: 0,
  runPromise: null,
};

async function api(path, body) {
  const opts =
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        };
  const res = await fetch(path, opts);
  let data;
  try {
    data = await res.json();
  } catch (e) {
    throw new Error("服务器返回了看不懂的内容（HTTP " + res.status + "）");
  }
  if (!res.ok) throw new Error(data.error || "请求失败，HTTP " + res.status);
  return data;
}

function esc(value) {
  return String(value == null ? "" : value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function startDrop() {
  const stage = $("drop-stage");
  const next = $("to-recall");
  if (!stage) return;
  if (next) next.hidden = true;
  stage.classList.remove("dropping");
  void stage.offsetWidth;
  stage.classList.add("dropping");
  setTimeout(() => {
    if (state.act === "drop" && next) next.hidden = false;
  }, 2100);
}

async function startLoaded() {
  const screen = $("loaded-screen");
  const digit = $("loaded-digit");
  const btn = $("loaded-action");
  const lever = $("loaded-lever");
  const note = $("loaded-note");
  if (digit) digit.textContent = "?";
  if (screen) {
    screen.classList.remove("lit-one", "lit-zero");
  }
  if (lever) lever.dataset.bit = "0";
  if (btn) {
    btn.textContent = "点一下摇杆";
    btn.disabled = false;
  }
  if (note) {
    note.textContent = "盒子里已经有一个程序。输入什么，输出不一定还是什么。";
  }
  state.loadedReady = false;
  state.loadedFlips = 0;
  try {
    const data = await api("/api/session/new", {});
    state.deutschSession = data.session_id;
    state.deutschAsked = {};
  } catch (err) {
    if (note) note.textContent = err.message;
  }
}

function showAct(n) {
  state.act = n;
  document.querySelectorAll(".act").forEach((el) => {
    el.hidden = true;
  });
  const id =
    n === "boot"
      ? "act-boot"
      : n === "box"
        ? "act-box"
        : n === "deal"
          ? "act-deal"
          : n === "drop"
            ? "act-drop"
            : n === "recall"
              ? "act-recall"
              : n === "loaded"
                ? "act-loaded"
                : n === "ask"
                  ? "act-ask"
                  : n === "try"
                    ? "act-try"
                    : n === "limit"
                      ? "act-limit"
                      : n === "path"
                        ? "act-path"
                          : n === "meaning"
                            ? "act-meaning"
                            : n === "algo"
                              ? "act-algo"
                          : n === "lab"
                            ? "act-lab"
                            : n === "cheer"
                              ? "act-cheer"
                            : n === "run"
                              ? "act-run"
                            : n === "end"
                              ? "act-end"
                            : "act-" + n;
  const target = $(id);
  if (target) target.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (n === "drop") startDrop();
  if (n === "recall") startRecall();
  if (n === "loaded") startLoaded();
  if (n === "try") startTry();
  if (n === "path") startPath();
  if (n === 4) startFinal();
  if (n === "lab") startLab();
  if (n === "cheer") startCheer();
  if (n === "run") startRun();
  if (n === "end") startEnd();
  if (n !== 0 && n !== "cheer") clearConfetti();
  syncAssistant();
}

let confettiTimers = [];

function clearConfetti() {
  confettiTimers.forEach((id) => clearTimeout(id));
  confettiTimers = [];
  const layer = $("build-confetti");
  if (layer) layer.innerHTML = "";
}

function spawnConfettiWave(layer, count) {
  const colors = [
    "#ff5c5c",
    "#ffc857",
    "#58a6ff",
    "#3ddc97",
    "#ff7ad9",
    "#fff4c4",
    "#c9a227",
    "#ff8a3d",
    "#b388ff",
    "#80cbc4",
  ];
  const easings = [
    "cubic-bezier(0.2, 0.05, 0.55, 0.35)",
    "cubic-bezier(0.28, 0, 0.62, 0.38)",
    "linear",
  ];
  for (let i = 0; i < count; i++) {
    const piece = document.createElement("span");
    const kind = Math.random();
    piece.className =
      kind > 0.72 ? "confetti ribbon" : kind < 0.22 ? "confetti dot" : "confetti";
    const origin = 8 + Math.random() * 84;
    piece.style.left = origin + "vw";
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    if (piece.classList.contains("ribbon")) {
      piece.style.width = 4 + Math.random() * 6 + "px";
      piece.style.height = 18 + Math.random() * 28 + "px";
    } else if (piece.classList.contains("dot")) {
      const size = 6 + Math.random() * 10;
      piece.style.width = size + "px";
      piece.style.height = size + "px";
    } else {
      piece.style.width = 6 + Math.random() * 12 + "px";
      piece.style.height = 8 + Math.random() * 16 + "px";
    }
    piece.style.animationDelay = Math.random() * 0.28 + "s";
    piece.style.animationDuration = 2.1 + Math.random() * 1.1 + "s";
    piece.style.animationTimingFunction = easings[Math.floor(Math.random() * easings.length)];
    piece.style.setProperty("--dx", Math.random() * 280 - 140 + "px");
    piece.style.setProperty("--dx2", Math.random() * 160 - 80 + "px");
    piece.style.setProperty("--h", 48 + Math.random() * 62 + "vh");
    piece.style.setProperty("--spin", Math.random() * 1400 - 700 + "deg");
    piece.style.setProperty("--r1", Math.random() * 240 - 120 + "deg");
    piece.style.opacity = String(0.75 + Math.random() * 0.25);
    layer.appendChild(piece);
  }
}

function spawnRibbonWave(layer, count) {
  const colors = [
    "#ff5c5c",
    "#ffc857",
    "#58a6ff",
    "#3ddc97",
    "#ff7ad9",
    "#fff4c4",
    "#c9a227",
    "#ff8a3d",
    "#b388ff",
    "#80cbc4",
  ];
  const easings = [
    "cubic-bezier(0.2, 0.05, 0.55, 0.35)",
    "cubic-bezier(0.28, 0, 0.62, 0.38)",
    "linear",
  ];
  for (let i = 0; i < count; i++) {
    const piece = document.createElement("span");
    piece.className = "confetti ribbon";
    piece.style.left = 8 + Math.random() * 84 + "vw";
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.width = 4 + Math.random() * 7 + "px";
    piece.style.height = 22 + Math.random() * 32 + "px";
    piece.style.animationDelay = Math.random() * 0.28 + "s";
    piece.style.animationDuration = 2.2 + Math.random() * 1.2 + "s";
    piece.style.animationTimingFunction = easings[Math.floor(Math.random() * easings.length)];
    piece.style.setProperty("--dx", Math.random() * 280 - 140 + "px");
    piece.style.setProperty("--dx2", Math.random() * 160 - 80 + "px");
    piece.style.setProperty("--h", 48 + Math.random() * 62 + "vh");
    piece.style.setProperty("--spin", Math.random() * 1400 - 700 + "deg");
    piece.style.setProperty("--r1", Math.random() * 240 - 120 + "deg");
    piece.style.opacity = String(0.75 + Math.random() * 0.25);
    layer.appendChild(piece);
  }
}

function burstConfetti() {
  let layer = $("build-confetti");
  if (!layer) {
    layer = document.createElement("div");
    layer.id = "build-confetti";
    layer.className = "confetti-layer";
    layer.setAttribute("aria-hidden", "true");
    document.body.appendChild(layer);
  }
  confettiTimers.forEach((id) => clearTimeout(id));
  confettiTimers = [];
  layer.innerHTML = "";
  spawnConfettiWave(layer, 150);
  confettiTimers.push(setTimeout(() => spawnConfettiWave(layer, 110), 320));
  confettiTimers.push(setTimeout(() => spawnConfettiWave(layer, 90), 780));
}

function burstRibbons() {
  let layer = $("build-confetti");
  if (!layer) {
    layer = document.createElement("div");
    layer.id = "build-confetti";
    layer.className = "confetti-layer";
    layer.setAttribute("aria-hidden", "true");
    document.body.appendChild(layer);
  }
  confettiTimers.forEach((id) => clearTimeout(id));
  confettiTimers = [];
  layer.innerHTML = "";
  spawnRibbonWave(layer, 240);
  confettiTimers.push(setTimeout(() => spawnRibbonWave(layer, 200), 260));
  confettiTimers.push(setTimeout(() => spawnRibbonWave(layer, 160), 620));
  confettiTimers.push(setTimeout(() => spawnRibbonWave(layer, 120), 1080));
}

function assistantAllowed() {
  if (typeof state.act === "number") return true;
  return state.act === "path" || state.act === "meaning" || state.act === "lab" || state.act === "cheer" || state.act === "run" || state.act === "end" || state.act === "algo";
}

function syncAssistant() {
  const fab = $("assistant-fab");
  const panel = $("assistant-panel");
  if (!fab || !panel) return;
  if (!assistantAllowed()) {
    fab.hidden = true;
    panel.hidden = true;
    return;
  }
  if (typeof renderPresetChips === "function" && typeof PRESET_CHIPS_END !== "undefined") {
    renderPresetChips(state.act === "end" ? PRESET_CHIPS_END : PRESET_CHIPS_PLAY);
  }
  if (state.act === "end") {
    fab.hidden = true;
    return;
  }
  if (panel.hidden) fab.hidden = false;
}

function startRecall() {
  const hand = $("recall-hand");
  if (!hand) return;
  hand.classList.remove("dealt");
  void hand.offsetWidth;
  hand.classList.add("dealt");
}

async function startTry() {
  const screen = $("try-screen");
  const digit = $("try-digit");
  const lever = $("try-lever");
  const note = $("try-note");
  const count = $("try-count");
  const quiz = $("try-quiz");
  const feedback = $("try-feedback");
  const next = $("to-limit");
  if (digit) digit.textContent = "?";
  if (screen) screen.classList.remove("lit-one", "lit-zero");
  if (lever) lever.dataset.bit = "0";
  if (count) count.textContent = "0";
  if (quiz) quiz.hidden = true;
  if (feedback) {
    feedback.hidden = true;
    feedback.innerHTML = "";
  }
  if (next) next.hidden = true;
  document.querySelectorAll("#try-options .opt").forEach((el) => {
    el.disabled = false;
    el.classList.remove("right", "wrong");
  });
  ["try-def-diff", "try-def-same"].forEach((id) => {
    const el = $(id);
    if (el) el.classList.remove("glow", "idle");
  });
  if (note) {
    note.textContent =
      "自己拨一拨摇杆。拨完以后，选一选：要知道是一样组还是不一样组，得拨几次？";
  }
  state.tryFlips = 0;
  state.tryAsked = {};
  try {
    const data = await api("/api/session/new", {});
    state.trySession = data.session_id;
  } catch (err) {
    if (note) note.textContent = err.message;
  }
}

function knownGroup() {
  const asked = state.deutschAsked || {};
  if (asked[0] === undefined || asked[1] === undefined) return null;
  return asked[0] === asked[1] ? "same" : "diff";
}

function startFinal() {
  const bench = $("final-bench");
  const lamp = $("final-lamp");
  const ask = $("final-ask");
  const feedback = $("final-feedback");
  const next = $("to-meaning");
  const btn = $("final-run");
  const note = $("final-note");
  if (note) {
    note.textContent = "再试一次";
  }
  if (lamp) lamp.classList.remove("same", "diff");
  if (ask) ask.hidden = true;
  if (feedback) {
    feedback.hidden = true;
    feedback.innerHTML = "";
  }
  if (next) next.hidden = true;
  if (btn) btn.disabled = false;
  ["final-def-diff", "final-def-same"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.classList.remove("glow", "idle", "pickable");
  });
  state.secretSession = null;
  state.secretVerdict = null;
  if (bench) {
    bench.classList.remove("seated", "running");
    void bench.offsetWidth;
    bench.classList.add("seated");
  }
}

let pathIntroTimer = 0;

function startPath() {
  const bench = $("path-bench");
  const lamp = $("path-lamp");
  const result = $("path-result");
  const next = $("to-guess");
  const run = $("path-run");
  const laserBtn = $("path-laser");
  const note = $("path-note");
  const why = $("path-glass-why");
  clearTimeout(pathIntroTimer);
  if (note) note.textContent = "让我们把刚才那个盒子放到机器中间。";
  if (lamp) lamp.classList.remove("same", "diff");
  if (result) {
    result.hidden = true;
    result.textContent = "";
  }
  if (next) next.hidden = true;
  if (why) why.hidden = true;
  if (run) {
    run.hidden = true;
    run.disabled = false;
  }
  if (laserBtn) {
    laserBtn.hidden = true;
    laserBtn.disabled = false;
  }
  if (bench) {
    bench.classList.remove("seated", "running", "explained", "laser-on");
    void bench.offsetWidth;
    pathIntroTimer = setTimeout(() => {
      if (state.act !== "path") return;
      bench.classList.add("seated");
      pathIntroTimer = setTimeout(() => {
        if (state.act !== "path") return;
        if (laserBtn) laserBtn.hidden = false;
      }, 850);
    }, 480);
  }
}

function finishPath(verdict) {
  const lamp = $("path-lamp");
  const result = $("path-result");
  const next = $("to-guess");
  const same = verdict === "constant";
  const group = same ? "same" : "diff";
  if (lamp) {
    lamp.classList.remove("same", "diff");
    lamp.classList.add(group);
  }
  const known = knownGroup();
  let text = same
    ? "灯亮了。这个程序是「一样组」。我们只操作了盒子 1 次。"
    : "灯没有亮。这个程序是「不一样组」。我们只操作了盒子 1 次。";
  if (known) {
    text +=
      known === group
        ? " 但效果和你刚才拨两次摇杆、操作盒子两次是一样的。"
        : " 灯和你拨两次看到的对不上，这一轮不能算数。";
  }
  if (result) {
    result.hidden = false;
    result.textContent = text;
  }
  if (next) next.hidden = false;
}

on("path-laser", "click", () => {
  const bench = $("path-bench");
  const laserBtn = $("path-laser");
  const why = $("path-glass-why");
  const run = $("path-run");
  if (!bench || !laserBtn || laserBtn.disabled) return;
  laserBtn.disabled = true;
  laserBtn.hidden = true;
  bench.classList.add("laser-on");
  clearTimeout(pathIntroTimer);
  pathIntroTimer = setTimeout(() => {
    if (state.act !== "path") return;
    bench.classList.add("explained");
    if (why) why.hidden = false;
    if (run) run.hidden = false;
  }, 520);
});

on("path-run", "click", async () => {
  const btn = $("path-run");
  const bench = $("path-bench");
  const note = $("path-note");
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  if (bench) bench.classList.add("running");
  try {
    if (!state.deutschSession) {
      const created = await api("/api/session/new", {});
      state.deutschSession = created.session_id;
    }
    const started = Date.now();
    const run = await api("/api/session/quantum", {
      session_id: state.deutschSession,
      shots: 1024,
    });
    const wait = 1100 - (Date.now() - started);
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    const verdict = run.reading && run.reading.verdict;
    if (!verdict) throw new Error("这次没有读到灯的结果。");
    state.pathVerdict = verdict;
    finishPath(verdict);
  } catch (err) {
    if (note) note.textContent = err.message;
    if (btn) btn.disabled = false;
    if (bench) bench.classList.remove("running");
  }
});

function lampSet(id, value) {
  const lamp = $(id);
  if (!lamp) return;
  lamp.classList.remove("zero", "one");
  const span = lamp.querySelector("span");
  if (value === 0) {
    lamp.classList.add("zero");
    if (span) span.textContent = "0";
  } else if (value === 1) {
    lamp.classList.add("one");
    if (span) span.textContent = "1";
  } else if (span) {
    span.textContent = "?";
  }
}

function meterSet(id, kind) {
  const meter = $(id);
  if (!meter) return;
  meter.classList.remove("lit", "dark");
  if (kind === "lit") meter.classList.add("lit");
  if (kind === "dark") meter.classList.add("dark");
}

const BUILD = [
  {
    part: "laser",
    next: "再放一块玻璃",
    line: "光打出来了。它还只会走直线。",
  },
  {
    part: "glass",
    next: "尽头放一盏灯",
    line: "这块玻璃叫做分束镜，它有神奇的效果，让我们稍后看看。",
  },
  {
    part: "lamp",
    next: null,
    line: "这就是一台简易的光学量子计算机。<br>解这道题，它刚好够用。",
  },
];
let buildStep = 0;

on("build-next", "click", () => {
  const step = BUILD[buildStep];
  if (!step) return;
  const part = $("part-" + step.part);
  if (part) part.hidden = false;
  $("build-line").hidden = false;
  $("build-line").innerHTML = step.line;
  buildStep += 1;
  $("optical-bench").dataset.step = String(buildStep);
  if (buildStep >= BUILD.length) {
    $("build-next").hidden = true;
    $("to-1").hidden = false;
    $("optical-bench").classList.add("alive");
    const title = $("build-title");
    if (title) {
      title.textContent = "🎉Congratulations！刚刚你搭好了一台量子计算机🎉";
    }
    burstConfetti();
  } else {
    $("build-next").textContent = step.next;
  }
});

on("to-box", "click", () => showAct("box"));
on("to-drop", "click", (ev) => {
  ev.stopPropagation();
  showAct("loaded");
});
on("to-recall", "click", (ev) => {
  ev.stopPropagation();
  showAct("recall");
});
on("to-loaded", "click", (ev) => {
  ev.stopPropagation();
  showAct("loaded");
});
on("to-try", "click", () => showAct("try"));
on("to-limit", "click", () => showAct("limit"));
on("to-build", "click", () => showAct(0));
on("to-1", "click", () => showAct("path"));
on("to-guess", "click", () => showAct("meaning"));
on("to-meaning", "click", () => showAct("meaning"));
on("to-lab", "click", () => showAct("lab"));
on("assistant-fab", "click", () => openAssistant());

(function bindLever() {
  const lever = $("lever");
  const btn = $("box-action");
  if (!lever || !btn) return;
  let bit = 0;
  let flips = 0;
  let popTimer = 0;

  function setBit(next) {
    bit = next;
    lever.dataset.bit = String(bit);
    const screen = $("out-screen");
    const digit = $("out-digit");
    digit.textContent = String(bit);
    screen.classList.toggle("lit-one", bit === 1);
    screen.classList.toggle("lit-zero", bit === 0);
    screen.classList.remove("pop");
    void screen.offsetWidth;
    screen.classList.add("pop");
    clearTimeout(popTimer);
    popTimer = setTimeout(() => screen.classList.remove("pop"), 280);
    flips += 1;
    btn.textContent = flips >= 2 ? "下一步" : "点一下摇杆";
  }

  function toggle() {
    setBit(bit === 1 ? 0 : 1);
  }

  lever.addEventListener("click", toggle);
  btn.addEventListener("click", () => {
    if (flips >= 2 && btn.textContent === "下一步") {
      showAct("deal");
      return;
    }
    toggle();
  });
})();

(function bindLoadedLever() {
  const lever = $("loaded-lever");
  const btn = $("loaded-action");
  if (!lever || !btn) return;
  let busy = false;
  let popTimer = 0;

  function showOut(output) {
    const screen = $("loaded-screen");
    const digit = $("loaded-digit");
    digit.textContent = String(output);
    screen.classList.toggle("lit-one", output === 1);
    screen.classList.toggle("lit-zero", output === 0);
    screen.classList.remove("pop");
    void screen.offsetWidth;
    screen.classList.add("pop");
    clearTimeout(popTimer);
    popTimer = setTimeout(() => screen.classList.remove("pop"), 280);
  }

  async function flip() {
    if (busy) return;
    const next = Number(lever.dataset.bit || 0) === 1 ? 0 : 1;
    lever.dataset.bit = String(next);
    busy = true;
    btn.disabled = true;
    try {
      if (!state.deutschSession) {
        const created = await api("/api/session/new", {});
        state.deutschSession = created.session_id;
        state.deutschAsked = {};
      }
      const data = await api("/api/session/classical", {
        session_id: state.deutschSession,
        bit: next,
      });
      state.deutschAsked[next] = data.output;
      showOut(data.output);
      state.loadedFlips += 1;
      if (state.loadedFlips >= 2) {
        state.loadedReady = true;
        btn.textContent = "下一步";
        const asked = state.deutschAsked;
        const note = $("loaded-note");
        if (note && asked[0] !== undefined && asked[1] !== undefined) {
          const same = asked[0] === asked[1];
          note.textContent = same
            ? "拨 0 出 " + asked[0] + "，拨 1 出 " + asked[1] + "。两次一样，所以这个程序是「一样组」。"
            : "拨 0 出 " + asked[0] + "，拨 1 出 " + asked[1] + "。两次不一样，所以这个程序是「不一样组」。";
        }
      } else {
        btn.textContent = "点一下摇杆";
      }
    } catch (err) {
      const note = $("loaded-note");
      if (note) note.textContent = err.message;
    } finally {
      busy = false;
      btn.disabled = false;
    }
  }

  lever.addEventListener("click", () => flip());
  btn.addEventListener("click", () => {
    if (state.loadedReady && btn.textContent === "下一步") {
      showAct("limit");
      return;
    }
    flip();
  });
})();

function updateTryGlow() {
  const asked = state.tryAsked || {};
  const diff = $("try-def-diff");
  const same = $("try-def-same");
  if (!diff || !same) return;
  diff.classList.remove("glow", "idle");
  same.classList.remove("glow", "idle");
  if (asked[0] === undefined || asked[1] === undefined) return;
  const isSame = asked[0] === asked[1];
  const hit = isSame ? same : diff;
  const miss = isSame ? diff : same;
  hit.classList.add("glow");
  miss.classList.add("idle");
}

(function bindTryLever() {
  const lever = $("try-lever");
  const btn = $("try-action");
  if (!lever || !btn) return;
  let busy = false;
  let popTimer = 0;

  function showOut(output) {
    const screen = $("try-screen");
    const digit = $("try-digit");
    digit.textContent = String(output);
    screen.classList.toggle("lit-one", output === 1);
    screen.classList.toggle("lit-zero", output === 0);
    screen.classList.remove("pop");
    void screen.offsetWidth;
    screen.classList.add("pop");
    clearTimeout(popTimer);
    popTimer = setTimeout(() => screen.classList.remove("pop"), 280);
  }

  async function flip() {
    if (busy) return;
    const next = Number(lever.dataset.bit || 0) === 1 ? 0 : 1;
    lever.dataset.bit = String(next);
    busy = true;
    btn.disabled = true;
    try {
      if (!state.trySession) {
        const created = await api("/api/session/new", {});
        state.trySession = created.session_id;
        state.tryAsked = {};
      }
      const data = await api("/api/session/classical", {
        session_id: state.trySession,
        bit: next,
      });
      state.tryAsked[next] = data.output;
      state.tryFlips += 1;
      showOut(data.output);
      updateTryGlow();
      const count = $("try-count");
      if (count) count.textContent = String(state.tryFlips);
      const quiz = $("try-quiz");
      if (quiz && quiz.hidden) {
        quiz.hidden = false;
        quiz.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    } catch (err) {
      const note = $("try-note");
      if (note) note.textContent = err.message;
    } finally {
      busy = false;
      btn.disabled = false;
    }
  }

  lever.addEventListener("click", () => flip());
  btn.addEventListener("click", () => flip());
})();

$("try-options").addEventListener("click", (ev) => {
  const btn = ev.target.closest(".opt");
  if (!btn || btn.disabled) return;
  const value = Number(btn.dataset.value);
  document.querySelectorAll("#try-options .opt").forEach((el) => {
    el.disabled = true;
    el.classList.toggle("right", Number(el.dataset.value) === 2);
    el.classList.toggle("wrong", el === btn && value !== 2);
  });
  const feedback = $("try-feedback");
  feedback.hidden = false;
  feedback.innerHTML =
    value === 2
      ? "<p>对。必须拨 <b>2 次</b>：一次拨 0，一次拨 1。两次都看到了，才能说是一样组还是不一样组。</p>"
      : "<p>只拨 <b>1 次</b>不够。另一次是什么你完全没看到，没法判断两次一不一样。</p>";
  const next = $("to-limit");
  if (next) {
    next.hidden = false;
    next.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
});

on("act-deal", "click", (ev) => {
  if (ev.target.closest("#to-drop")) return;
  const hand = $("deal-hand");
  if (!hand || hand.classList.contains("dealt")) return;
  hand.classList.add("dealt");
  $("act-deal").classList.add("showing-cards");
  $("deal-hint").hidden = true;
  setTimeout(() => {
    $("to-drop").hidden = false;
    $("to-drop").scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, 720);
});

$("hook-options").addEventListener("click", (ev) => {
  const btn = ev.target.closest(".opt");
  if (!btn) return;
  const value = Number(btn.dataset.value);
  document.querySelectorAll("#hook-options .opt").forEach((el) => {
    el.disabled = true;
    el.classList.toggle("right", Number(el.dataset.value) === 2);
    el.classList.toggle("wrong", el === btn && value !== 2);
  });
  const feedback = $("hook-feedback");
  feedback.hidden = false;
  feedback.innerHTML =
    value === 2
      ? "对。<b>两次。</b>你必须先拨 0，再拨 1，两个输出都知道了，才能说一不一样。"
      : "答案是 <b>两次</b>。只拨一次，另一个输出是什么你完全没线索，没法判断一不一样。";
  $("to-2").hidden = false;
});

$("to-2").addEventListener("click", async () => {
  showAct(2);
  await ensureClassicSession();
});

async function ensureClassicSession() {
  if (state.deutschSession) return;
  try {
    const data = await api("/api/session/new", {});
    state.deutschSession = data.session_id;
  } catch (err) {
    $("classic-feedback").hidden = false;
    $("classic-feedback").innerHTML = `<p>${esc(err.message)}</p>`;
  }
}

async function pressClassic(bit) {
  await ensureClassicSession();
  if (!state.deutschSession) return;
  try {
    const data = await api("/api/session/classical", {
      session_id: state.deutschSession,
      bit,
    });
    state.deutschAsked[bit] = data.output;
    lampSet("classic-lamp", data.output);
    $("classic-count").textContent = String(data.classical_queries);

    const asked = Object.keys(state.deutschAsked);
    if (asked.length >= 2) {
      const same = state.deutschAsked[0] === state.deutschAsked[1];
      $("classic-feedback").hidden = false;
      $("classic-feedback").innerHTML = `
        <p>拨 0 出 <b>${state.deutschAsked[0]}</b>，拨 1 出 <b>${state.deutschAsked[1]}</b>。</p>
        <p>所以答案是：<b>${same ? "一样" : "不一样"}</b>。你用了 <b>2 次</b>，这是普通办法的下限。</p>`;
      $("to-3").hidden = false;
    }
  } catch (err) {
    $("classic-feedback").hidden = false;
    $("classic-feedback").innerHTML = `<p>${esc(err.message)}</p>`;
  }
}

$("press-0").addEventListener("click", () => pressClassic(0));
$("press-1").addEventListener("click", () => pressClassic(1));
$("to-3").addEventListener("click", () => showAct(3));

$("once-0").addEventListener("click", () => pressOnce(0));
$("once-1").addEventListener("click", () => pressOnce(1));

async function pressOnce(bit) {
  await ensureClassicSession();
  if (!state.deutschSession) return;
  try {
    const data = await api("/api/session/classical", {
      session_id: state.deutschSession,
      bit,
    });
    lampSet("once-lamp", data.output);
    $("once-feedback").hidden = false;
    $("once-feedback").innerHTML = `
      <p>你拨了 <b>${bit}</b>，盒子出了 <b>${data.output}</b>。</p>
      <p>另一个输出是多少？你还是不知道。一次，确实不够。</p>`;
    $("tilt-block").hidden = false;
  } catch (err) {
    $("once-feedback").hidden = false;
    $("once-feedback").innerHTML = `<p>${esc(err.message)}</p>`;
  }
}

$("quantum-run").addEventListener("click", async () => {
  const btn = $("quantum-run");
  btn.disabled = true;
  $("quantum-feedback").hidden = false;
  $("quantum-feedback").innerHTML = `<p>正在把两样一起送进去，只看一次…</p>`;
  try {
    const run = await api("/api/session/quantum", {
      session_id: state.deutschSession,
      shots: 1024,
    });
    const verdict = run.reading && run.reading.verdict;
    const text = verdict === "constant" ? "一样" : "不一样";
    const known =
      Object.keys(state.deutschAsked).length >= 2
        ? state.deutschAsked[0] === state.deutschAsked[1]
          ? "一样"
          : "不一样"
        : null;
    lampSet("quantum-lamp", verdict === "constant" ? 0 : 1);
    meterSet("quantum-meter", verdict === "constant" ? "lit" : "dark");
    const match =
      known == null
        ? ""
        : known === text
          ? `<p>这和你刚才拨两次得到的答案一样。</p>`
          : `<p>这次读数和刚才拨两次的答案对不上，这一轮不能算数。</p>`;
    $("quantum-feedback").innerHTML = `
      <p><b>只看了一次，读数已经出来了：${text}。</b></p>
      <p>盒子只被用了 <b>1 次</b>。</p>
      ${match}`;
    $("to-4").hidden = false;
  } catch (err) {
    $("quantum-feedback").innerHTML = `<p>${esc(err.message)}</p>`;
    btn.disabled = false;
  }
});

$("to-4").addEventListener("click", () => showAct(4));

async function ensureSecretSession() {
  if (state.secretSession) return;
  try {
    const data = await api("/api/session/new", {});
    state.secretSession = data.session_id;
  } catch (err) {
    $("final-feedback").hidden = false;
    $("final-feedback").innerHTML = `<p>${esc(err.message)}</p>`;
  }
}

$("final-run").addEventListener("click", async () => {
  const btn = $("final-run");
  const bench = $("final-bench");
  const note = $("final-note");
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  if (bench) bench.classList.add("running");
  try {
    await ensureSecretSession();
    if (!state.secretSession) throw new Error("新盒子还没准备好。");
    const started = Date.now();
    const run = await api("/api/session/quantum", {
      session_id: state.secretSession,
      shots: 1024,
    });
    const wait = 1100 - (Date.now() - started);
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    const verdict = run.reading && run.reading.verdict;
    if (!verdict) throw new Error("这次没有读到灯的结果。");
    state.secretVerdict = verdict;
    const lamp = $("final-lamp");
    if (lamp) {
      lamp.classList.remove("same", "diff");
      lamp.classList.add(verdict === "constant" ? "same" : "diff");
    }
    const ask = $("final-ask");
    if (ask) ask.hidden = false;
    ["final-def-diff", "final-def-same"].forEach((id) => {
      const el = $(id);
      if (el) el.classList.add("pickable");
    });
    const feedback = $("final-feedback");
    if (feedback) {
      feedback.hidden = true;
      feedback.innerHTML = "";
    }
  } catch (err) {
    if (note) note.textContent = err.message;
    if (btn) btn.disabled = false;
    if (bench) bench.classList.remove("running");
  }
});

function bindFinalGuess(id) {
  const card = $(id);
  if (!card) return;
  card.addEventListener("click", async () => {
    if (!card.classList.contains("pickable")) return;
    if (!state.secretSession || !state.secretVerdict) return;
    const guess = card.dataset.value;
    document.querySelectorAll("#final-def-diff, #final-def-same").forEach((el) => {
      el.classList.remove("pickable", "glow", "idle");
    });
    const hitId =
      state.secretVerdict === "constant" ? "final-def-same" : "final-def-diff";
    const missId =
      state.secretVerdict === "constant" ? "final-def-diff" : "final-def-same";
    const hit = $(hitId);
    const miss = $(missId);
    if (hit) hit.classList.add("glow");
    if (miss) miss.classList.add("idle");
    const correct = state.secretVerdict === guess;
    const sameGroup = state.secretVerdict === "constant";
    const lampLine = sameGroup
      ? "灯亮了，所以是一样组。"
      : "灯没有亮，所以是不一样组。";
    $("final-feedback").hidden = false;
    $("final-feedback").innerHTML = `
      <p>${correct ? "你点对了。" : "这次点错了。"} ${lampLine}</p>
      <p>两束光一起穿过去，只需启动一次，我们即可知道黑盒里的程序属于哪一组。</p>`;
    $("to-meaning").hidden = false;
  });
}

bindFinalGuess("final-def-diff");
bindFinalGuess("final-def-same");

function startLab() {
  qasmStep = 0;
  qasmLines = [];
  const pre = $("qasm-build");
  const next = $("qasm-next");
  const done = $("qasm-done");
  const runBtn = $("qasm-run");
  if (pre) {
    pre.innerHTML = '<span class="qasm-empty">还是一张空白纸。点下面的按钮，从激光笔开始写。</span>';
  }
  if (next) {
    next.hidden = false;
    next.textContent = QASM_STEPS[0].button;
  }
  if (done) done.hidden = true;
  if (runBtn) {
    runBtn.hidden = true;
    runBtn.disabled = false;
    runBtn.textContent = "运行这个电路";
  }
  state.runPromise = null;
  document.querySelectorAll(".qasm-part").forEach((el) => {
    const i = Number(el.getAttribute("data-i"));
    el.classList.remove("on", "done");
    el.classList.toggle("wait", i === 0);
  });
}

const QASM_STEPS = [
  {
    button: "写下激光笔",
    lines: [
      "// 激光笔：负责开工。",
      "// 写出这是一条量子电路，桌上有两根线。",
      "// 两根线一开始都是 0。",
      "// 辅助那根线先翻到 1，后面黑盒才能把答案写进光的相位里。",
      "OPENQASM 2.0;",
      'include "qelib1.inc";',
      "qreg q[2];",
      "creg c[1];",
      "x q[1];",
    ],
  },
  {
    button: "写下分束镜",
    lines: [
      "// 这块玻璃叫做分束镜。",
      "// h 就是「把一束光劈成两路」的写法：上面一路当 1，下面一路当 0。",
      "// 以前拨摇杆一次只能送一个数，有了它，两个数可以一起走进盒子。",
      "h q[0];",
      "h q[1];",
    ],
  },
  {
    button: "写下黑盒",
    lines: [
      "// 黑盒：只问这一次。",
      "// 里面具体是哪一张牌先藏着，电路里用一行注释挡住。",
      "// 你刚才看灯，并不需要先拆开盒子。",
    ],
  },
  {
    button: "写下灯",
    lines: [
      "// 灯：两路重新合上。",
      "// 量一下 q[0]：读到 0 是一样组，读到 1 是不一样组。",
      "// 这就是灯亮或不亮。",
      "h q[0];",
      "measure q[0] -> c[0];",
    ],
  },
];
let qasmStep = 0;
let qasmLines = [];

function renderQasm(freshCount) {
  const pre = $("qasm-build");
  if (!pre) return;
  const oldCount = qasmLines.length - freshCount;
  pre.innerHTML = qasmLines
    .map((line, i) => {
      const cls = i >= oldCount ? "qasm-new" : "";
      return `<span class="${cls}">${esc(line)}</span>`;
    })
    .join("\n");
}

function revealQasm() {
  const step = QASM_STEPS[qasmStep];
  if (!step) return;
  const chunk = qasmStep === 0 ? step.lines : [""].concat(step.lines);
  qasmLines = qasmLines.concat(chunk);
  renderQasm(chunk.length);
  qasmStep += 1;
  document.querySelectorAll(".qasm-part").forEach((el) => {
    const i = Number(el.getAttribute("data-i"));
    el.classList.toggle("done", i < qasmStep - 1);
    el.classList.toggle("on", i === qasmStep - 1);
    el.classList.toggle("wait", i === qasmStep);
  });
  const next = $("qasm-next");
  if (qasmStep >= QASM_STEPS.length) {
    if (next) next.hidden = true;
    const done = $("qasm-done");
    if (done) done.hidden = false;
    const runBtn = $("qasm-run");
    if (runBtn) runBtn.hidden = false;
    document.querySelectorAll(".qasm-part").forEach((el) => {
      el.classList.remove("on", "wait");
      el.classList.add("done");
    });
    return;
  }
  if (next) next.textContent = QASM_STEPS[qasmStep].button;
}

on("qasm-next", "click", () => revealQasm());
on("qasm-run", "click", () => showAct("cheer"));

let cheerClickable = false;

function beginOriginRun() {
  if (state.runPromise) return;
  state.runPromise = (async () => {
    if (!state.deutschSession) {
      const created = await api("/api/session/new", {});
      state.deutschSession = created.session_id;
    }
    return api("/api/session/quantum", {
      session_id: state.deutschSession,
      shots: 1024,
      target: "originq",
    });
  })();
}

function startCheer() {
  cheerClickable = false;
  const labBtn = $("qasm-run");
  if (labBtn) {
    labBtn.disabled = true;
    labBtn.textContent = "正在运行…";
  }
  beginOriginRun();
  burstRibbons();
  setTimeout(() => {
    cheerClickable = true;
  }, 350);
}

on("act-cheer", "click", () => {
  if (!cheerClickable) return;
  showAct("run");
});

async function startRun() {
  const status = $("run-status");
  const chart = $("run-chart");
  const verdictEl = $("run-verdict");
  const legend = $("run-legend");
  if (status) {
    status.hidden = false;
    status.textContent = "正在运行这个电路…";
  }
  if (chart) chart.innerHTML = "";
  if (verdictEl) {
    verdictEl.hidden = true;
    verdictEl.textContent = "";
  }
  if (legend) legend.hidden = true;
  const next = $("to-end");
  if (next) next.hidden = true;
  try {
    beginOriginRun();
    const run = await state.runPromise;
    const reading = run.reading || {};
    if (!reading.verdict) throw new Error("这次没有读到结果。");
    const same = reading.verdict === "constant";
    const group = same ? "一样组" : "不一样组";
    const bit = same ? "0" : "1";
    if (status) status.hidden = true;
    if (chart) chart.innerHTML = chartHtml(run.counts, "0 和 1 各出现了多少");
    let text = "读数大多是 " + bit + "，所以是「" + group + "」。";
    const known = knownGroup();
    if (known) {
      const lamp = same ? "same" : "diff";
      if (known === lamp) text += " 和刚才灯说的是同一件事。";
    }
    if (verdictEl) {
      verdictEl.hidden = false;
      verdictEl.textContent = text;
    }
    if (legend) legend.hidden = false;
    const next = $("to-end");
    if (next) next.hidden = false;
  } catch (err) {
    if (status) {
      status.hidden = false;
      status.textContent = err.message || "这次没有跑出来。";
    }
    const labBtn = $("qasm-run");
    if (labBtn) {
      labBtn.disabled = false;
      labBtn.textContent = "运行这个电路";
    }
    state.runPromise = null;
  }
}

function startEnd() {
  renderPresetChips(PRESET_CHIPS_END);
  const panel = $("assistant-panel");
  const fab = $("assistant-fab");
  if (panel) panel.hidden = true;
  if (fab) fab.hidden = true;
}

on("to-end", "click", () => showAct("end"));
on("open-end-agent", "click", () => openAssistant("end"));

function openAssistant(kind) {
  const panel = $("assistant-panel");
  const fab = $("assistant-fab");
  const log = $("assistant-log");
  if (!panel) return;
  panel.hidden = false;
  if (fab) fab.hidden = true;
  if (!log) return;
  const onlyIntro = log.children.length <= 1;
  if (kind === "end" && onlyIntro) {
    log.dataset.ready = "1";
    log.innerHTML = `<div class="note">刚才玩完了。想问什么就点下面，或自己打字。</div>`;
    return;
  }
  if (!log.dataset.ready) {
    log.dataset.ready = "1";
    log.innerHTML = `<div class="note">看不懂的地方，直接问我。</div>`;
  }
}

on("assistant-close", "click", () => {
  $("assistant-panel").hidden = true;
  if (assistantAllowed() && state.act !== "end") $("assistant-fab").hidden = false;
});

function actContext() {
  if (state.act === "boot") {
    return "用户刚打开页面，写着：先来玩一次简单的游戏。";
  }
  if (state.act === "box") {
    return "用户在拨一个摇杆：上拨是 1，下拉是 0。旁边有一个黑盒，另一侧屏幕只显示 0 或 1。还没有介绍四条规则。";
  }
  if (state.act === "deal") {
    return "用户在看四张牌被发到桌上，牌面是 F1 到 F4 四条规则。";
  }
  if (state.act === "drop") {
    return "用户在看 F1 到 F4 四张牌掉进黑盒。";
  }
  if (state.act === "recall") {
    return "用户正在回顾四个程序分成两组：F1、F2 两次输出不一样；F3、F4 两次输出一样。依据是只看拨 0 和拨 1 两次结果相不相等，不看具体吐出 0 还是 1。";
  }
  if (state.act === "loaded") {
    return "用户在拨已经装进随机程序的黑盒。输出由服务器在 F1 到 F4 里秘密抽一条，页面看不到是哪一条。";
  }
  if (state.act === "ask") {
    return "用户看到问题：需要拨动几次摇杆，才能够知道这个程序是一样组还是不一样组。下一页会亲手拨摇杆，再选择次数。";
  }
  if (state.act === "try") {
    return "用户正在自己拨摇杆试一个新盒子，然后选择：要知道是一样组还是不一样组，需要拨 1 次还是 2 次。正确答案是 2 次。";
  }
  if (state.act === "limit") {
    return "用户看到说明：你发现了吗？必须输入两次数据，才能知道两次输入的结果是不是一样的。这就是经典计算机的局限。下一页去搭简易量子计算机。";
  }
  if (state.act === "path") {
    return "用户把黑盒放进刚搭好的机器中间。斜玻璃把一束光劈成 0 和 1 两路，一起走进盒子，只问一次。灯亮表示一样组，灯不亮表示不一样组。";
  }
  if (state.act === "meaning") {
    return "用户正在看灯亮灯不亮的解释，并刚读到：桌上刚才的操作来自 1985 年大卫·多伊奇的想法，后来成为 Deutsch–Jozsa 算法。页面写明它人工构造痕迹明显、实际价值不大，但清楚显示量子计算能在特定场景远远超过经典计算，为寻找更有价值的算法提供了线索。不要用平衡/恒定。";
  }
  if (state.act === "lab") {
    return "用户正在把刚才桌上的激光笔、分束镜、黑盒和灯，一步一步写成 OpenQASM 电路。页面说明量子电路是驱动量子计算机的语言。不要用平衡/恒定。不要假装这是真机。";
  }
  if (state.act === "cheer") {
    return "用户刚看到祝贺页：恭喜第一次在量子计算机上运行了电路。点屏幕后会看到 0/1 读数。不要用平衡/恒定。";
  }
  if (state.act === "run") {
    return "用户刚点了运行电路。后台用 L1 中间层转到本源模拟器上跑，页面只展示 0/1 读数和一样组或不一样组。不要讲转译、OriginIR、后端名字。不要用平衡/恒定。";
  }
  if (state.act === "end") {
    return "用户已经玩完整条主线，正在看结束语：量子计算神奇但并非高不可攀。助手已打开，预设问题都是很简单的概念题，例如 Deutsch 算法是什么。用大白话回答。不要用平衡/恒定。不要主动写电路，除非用户自己要求。";
  }
  return ACT_CONTEXT[state.act] || "";
}

const ACT_CONTEXT = [
  "用户正在桌上搭一台自制量子计算机：激光笔、斜玻璃、一盏灯。还没开始解谜。",
  "用户正在看谜面：一个盒子，四条可能规则，问题只问两个输出一样还是不一样。",
  "用户正在用普通办法试，发现要拨两次。",
  "用户发现只拨一次不够，正在尝试把两样一起送进去。",
  "用户换了一个没拨过的新盒子。两束光一起穿过去，只看灯亮不亮，再点一样组或不一样组。",
];

const PRESET_CHIPS_PLAY = [
  { id: "context", label: "这一步在讲什么？" },
  { id: "hello", label: "写一条最简单的电路" },
  { id: "w", label: "帮我生成一个 3 比特 W 态并全部测量", danger: true },
  { id: "fix", label: "修好这段电路：h q[0]; cx q[0] q[1]; measure q -> c;", danger: true },
];
const PRESET_CHIPS_END = [
  { id: "deutsch", label: "Deutsch 算法是什么？" },
  { id: "lamp", label: "灯亮和灯不亮是什么意思？" },
  { id: "twice", label: "为什么普通电脑要问两次？" },
  { id: "faster", label: "量子计算机什么都更快吗？" },
];

const PRESETS = {
  context: () => "用大白话解释一下，我现在这一步到底在做什么？",
  hello: () => "写一条最简单的量子电路：1 个比特，先放 H 门，再测量。在模拟器上跑，告诉我结果是什么感觉。",
  w: () => "帮我生成一个 3 比特 W 态并全部测量",
  fix: () => "修好这段电路：h q[0]; cx q[0] q[1]; measure q -> c;",
  deutsch: () => "用最简单的话说：Deutsch 算法是什么？不要用平衡、恒定这些词。",
  lamp: () => "灯亮和灯不亮分别是什么意思？请对照一样组和不一样组来说。",
  twice: () => "为什么普通电脑必须问两次，量子这边问一次就够？",
  faster: () => "量子计算机是不是什么都比普通电脑快？请老实回答。",
};

function renderPresetChips(chips) {
  const box = $("assistant-presets");
  if (!box) return;
  box.innerHTML = chips
    .map((chip) => {
      const danger = chip.danger ? " danger" : "";
      return `<button class="chip${danger}" type="button" data-preset="${esc(chip.id)}">${esc(chip.label)}</button>`;
    })
    .join("");
}

function askPreset(id) {
  const preset = PRESETS[id];
  if (!preset) return;
  $("assistant-text").value = preset();
  sendAssistant();
}

async function sendAssistant() {
  const box = $("assistant-text");
  const text = (box.value || "").trim();
  const log = $("assistant-log");
  if (!text) {
    log.insertAdjacentHTML(
      "beforeend",
      `<div class="note">先写一句，或点上面的问题。</div>`
    );
    log.scrollTop = log.scrollHeight;
    return;
  }
  log.insertAdjacentHTML("beforeend", `<div class="ask-turn">${esc(text)}</div>`);
  const slot = document.createElement("div");
  slot.innerHTML = `<div class="note">正在想，可能要十几秒…</div>`;
  log.appendChild(slot);
  log.scrollTop = log.scrollHeight;
  box.value = "";
  $("assistant-send").disabled = true;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 90000);
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: text,
        context: actContext(),
        shots: 1024,
      }),
      signal: ctrl.signal,
    });
    let data;
    try {
      data = await res.json();
    } catch (e) {
      throw new Error("服务器返回了看不懂的内容（HTTP " + res.status + "）");
    }
    if (!res.ok) throw new Error(data.error || "请求失败，HTTP " + res.status);
    const reply = data.reply || data.error || "（没有内容）";
    const prov = data.provenance;
    slot.innerHTML =
      (prov && prov.label
        ? `<div class="badge ${esc(prov.level)}">${esc(prov.label)}</div>`
        : "") +
      replyHtml(reply) +
      (data.counts ? chartHtml(data.counts, "这段电路实际跑出来的读数") : "");
  } catch (err) {
    const msg =
      err && err.name === "AbortError"
        ? "想得太久了，没等到回答。请再发一次。"
        : err.message || String(err);
    slot.innerHTML = `<div class="note">${esc(msg)}</div>`;
  } finally {
    clearTimeout(timer);
    $("assistant-send").disabled = false;
    log.scrollTop = log.scrollHeight;
  }
}

window.loomqAsk = sendAssistant;
window.loomqPreset = askPreset;

on("assistant-presets", "click", (ev) => {
  const chip = ev.target.closest(".chip");
  if (!chip) return;
  askPreset(chip.dataset.preset);
});
on("assistant-send", "click", () => sendAssistant());
on("assistant-text", "keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    sendAssistant();
  }
});

async function checkHealth() {
  const note = $("assistant-health");
  if (!note) return;
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.ok) {
      note.hidden = true;
      note.textContent = "";
      note.classList.remove("bad");
      return;
    }
    note.hidden = false;
    note.textContent = "助手暂时连不上。实验还能做，问问题稍后再试。";
    note.classList.add("bad");
  } catch (err) {
    note.hidden = false;
    note.textContent = "助手暂时连不上。实验还能做，问问题稍后再试。";
    note.classList.add("bad");
  }
}

checkHealth();

function replyHtml(text) {
  const source = String(text == null ? "" : text);
  const fence = /```[a-zA-Z0-9]*\r?\n([\s\S]*?)```/g;
  const chunks = [];
  let cursor = 0;
  let match;
  while ((match = fence.exec(source)) !== null) {
    if (match.index > cursor) {
      chunks.push({ code: false, body: source.slice(cursor, match.index) });
    }
    chunks.push({ code: true, body: match[1] });
    cursor = fence.lastIndex;
  }
  if (cursor < source.length) chunks.push({ code: false, body: source.slice(cursor) });

  return chunks
    .map((chunk) => {
      const body = chunk.body.trim();
      if (!body) return "";
      if (!chunk.code) return `<div class="agent-reply">${esc(body)}</div>`;
      const label = body.includes("OPENQASM") ? "量子电路 · OpenQASM 2.0" : "代码";
      return `<div class="code-panel"><div class="code-head">${label}</div><pre>${esc(body)}</pre></div>`;
    })
    .join("");
}

function chartHtml(counts, title) {
  if (!counts || !Object.keys(counts).length) return "";
  const entries = Object.entries(counts)
    .map(([k, v]) => [k, Number(v)])
    .sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, v]) => sum + v, 0) || 1;
  const max = entries[0][1] || 1;
  const rows = entries
    .slice(0, 8)
    .map(([key, value]) => {
      const pct = ((100 * value) / total).toFixed(1);
      const width = Math.max(2, Math.round((100 * value) / max));
      return `<div class="bar-row">
        <div class="bar-key">${esc(key)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
        <div class="bar-val">${esc(pct)}%</div>
      </div>`;
    })
    .join("");
  return `<div class="chart"><div class="chart-title">${esc(title || "读数分布")}</div>${rows}</div>`;
}

showAct("boot");
checkHealth();
