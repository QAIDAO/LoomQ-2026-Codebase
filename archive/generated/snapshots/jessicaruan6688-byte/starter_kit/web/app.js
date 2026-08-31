const promptEl = document.getElementById("prompt");
const outputEl = document.getElementById("output");
const statusEl = document.getElementById("status");
const sendBtn = document.getElementById("send");
const qasmEl = document.getElementById("qasm");
const backendEl = document.getElementById("backend");
const chartTitle = document.getElementById("chart-title");
const chartPlain = document.getElementById("chart-plain");
const chartNoise = document.getElementById("chart-noise");
const chartMeta = document.getElementById("chart-meta");
const barsEl = document.getElementById("bars");
const shotEl = document.getElementById("shot");
const llmBadge = document.getElementById("llm-badge");
const legendExp = document.getElementById("legend-exp");
const legendSim = document.getElementById("legend-sim");
const gatesEl = document.getElementById("gates");
const repairEl = document.getElementById("repair");
const boardEl = document.getElementById("backend-board");
const demoBannerEl = document.getElementById("demo-banner");

let experiments = [];
let backends = [];
let l2Configured = false;

function setStatus(text, isError) {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", Boolean(isError));
}

function pct(value) {
  const n = Math.round(Number(value) * 100);
  return Math.max(0, Math.min(100, n));
}

function renderBars(experiment, simulation) {
  const keys = Array.from(
    new Set([
      ...Object.keys(experiment || {}),
      ...Object.keys(simulation || {}),
    ]),
  ).sort();
  barsEl.innerHTML = "";
  keys.forEach((key) => {
    const expP = Number((experiment || {})[key] || 0);
    const simP = Number((simulation || {})[key] || 0);
    const ideal = simP >= 0.2 || expP >= 0.2;
    const row = document.createElement("div");
    row.className = "bar-row" + (ideal ? " ideal" : "");
    row.innerHTML =
      '<span class="state">' +
      key +
      "</span>" +
      '<div class="tracks">' +
      '<div class="track"><div class="fill exp" style="width:' +
      pct(expP) +
      '%"></div></div>' +
      '<div class="track"><div class="fill sim" style="width:' +
      pct(simP) +
      '%"></div></div>' +
      "</div>" +
      '<span class="nums">真机 ' +
      pct(expP) +
      "% · 验算 " +
      pct(simP) +
      "%</span>";
    barsEl.appendChild(row);
  });
}

function renderGates(qasm) {
  gatesEl.innerHTML = "";
  if (!qasm) {
    return;
  }
  const matches = qasm.match(/\b(h|x|s|sdg|t|tdg|cx|swap|ccx|rz|ry|cu1)\b[^;]*/gi) || [];
  matches.slice(0, 12).forEach((line) => {
    const pill = document.createElement("span");
    pill.className = "gate";
    pill.textContent = line.trim();
    gatesEl.appendChild(pill);
  });
}

function renderExperiment(exp, localIdeal) {
  if (!exp) {
    return;
  }
  chartTitle.textContent = exp.title;
  chartPlain.textContent = exp.plain;
  chartNoise.textContent = exp.noise;
  const when = (exp.created_at || "").replace("T", " ").replace("+08:00", " (北京时间)");
  chartMeta.innerHTML = "";
  [
    exp.job_id,
    exp.platform_name,
    exp.status,
    when,
    "归档回放 · 不上云排队",
  ]
    .filter(Boolean)
    .forEach((bit) => {
      const li = document.createElement("li");
      li.textContent = bit;
      chartMeta.appendChild(li);
    });
  legendExp.textContent = "真机归档";
  legendSim.textContent = localIdeal ? "这句生成的电路（本地精确验算）" : "理想（无噪声）";
  renderBars(exp.experiment, localIdeal || exp.simulation);
  if (exp.screenshot) {
    shotEl.hidden = false;
    shotEl.src = exp.screenshot;
    shotEl.alt = exp.platform_name + " 任务页截图";
  } else {
    shotEl.hidden = true;
    shotEl.removeAttribute("src");
  }
  if (exp.qasm) {
    qasmEl.textContent = exp.qasm;
    renderGates(exp.qasm);
  }
}

function renderBackendBoard(selectedId, filter15) {
  boardEl.innerHTML = "";
  backends.forEach((item) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "bcard";
    if (filter15 && item.fits_15q_no_queue) {
      card.classList.add("fit");
    }
    if (filter15 && !item.fits_15q_no_queue) {
      card.classList.add("dim");
    }
    if (selectedId && item.id === selectedId) {
      card.classList.add("picked");
    }
    card.innerHTML =
      "<strong>" +
      item.id +
      "</strong><span>" +
      item.name +
      "</span><em>" +
      item.max_qubits +
      " 比特 · 排队 " +
      item.queue +
      " · " +
      item.cost +
      "</em>";
    boardEl.appendChild(card);
  });
}

function experimentForPrompt(prompt) {
  const text = prompt.toLowerCase();
  if (
    text.includes("ghz") ||
    text.includes("三比特") ||
    text.includes("三枚") ||
    text.includes("3 比特") ||
    text.includes("3比特")
  ) {
    return experiments.find((item) => item.id === "ghz3");
  }
  if (
    text.includes("bell") ||
    text.includes("贝尔") ||
    text.includes("两枚") ||
    text.includes("硬币") ||
    text.includes("纠缠")
  ) {
    return experiments.find((item) => item.id === "bell");
  }
  return null;
}

function isBackendTask(prompt) {
  return /15|排队|后端|平台|backend/.test(prompt);
}

function isRepairTask(prompt) {
  return /修好|修复|报错|H q\[0\]|CX q/.test(prompt);
}

function showRepair(show) {
  repairEl.hidden = !show;
}

function setDemoMode(mode, bannerText) {
  document.body.classList.remove("demo-repair", "demo-backend", "demo-ghz");
  if (mode) {
    document.body.classList.add("demo-" + mode);
  }
  if (bannerText) {
    demoBannerEl.hidden = false;
    demoBannerEl.textContent = bannerText;
  } else {
    demoBannerEl.hidden = true;
    demoBannerEl.textContent = "";
  }
}

async function sendPrompt() {
  const prompt = promptEl.value.trim();
  if (!prompt) {
    setStatus("请先写一句话，或点「第一次实验」。", true);
    return;
  }
  const matched = experimentForPrompt(prompt);
  const backendTask = isBackendTask(prompt);
  const repairTask = isRepairTask(prompt);
  showRepair(repairTask);
  if (matched) {
    renderExperiment(matched);
  }
  if (backendTask) {
    renderBackendBoard(null, true);
  }

  sendBtn.disabled = true;
  try {
    const health = await fetch("/api/health").then((r) => r.json());
    l2Configured = Boolean(health.l2_configured);
  } catch (_err) {
    l2Configured = false;
  }
  if (!l2Configured) {
    const missing =
      "Agent 没有调用模型：starter_kit/.env 里的 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY、LOOMQ_LLM_MODEL 还是空的。填好保存后，在运行 ./start_demo.sh 的窗口按 Ctrl+C，再启动一次，然后重新点任务。";
    outputEl.textContent = missing;
    setStatus(missing, true);
    sendBtn.disabled = false;
    return;
  }

  setStatus("Agent 正在把人话变成电路…");
  outputEl.textContent = "正在请求模型…";
  backendEl.hidden = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || res.statusText);
    }
    outputEl.textContent = data.response || "";
    if (data.qasm) {
      qasmEl.textContent = data.qasm;
      renderGates(data.qasm);
    }
    const local = data.local_ideal && data.local_ideal.probabilities;
    if (matched && local) {
      renderExperiment(matched, local);
    } else if (local && !matched) {
      legendExp.textContent = "（无对应真机回放）";
      legendSim.textContent = "这句生成的电路（本地精确验算）";
      renderBars({}, local);
    }
    if (data.backend_id) {
      backendEl.hidden = false;
      backendEl.textContent = "规范后端：" + data.backend_id;
      renderBackendBoard(data.backend_id, true);
    }
    setStatus("完成。棕色是真机归档，灰色是刚才这句电路的本地验算。");
  } catch (err) {
    outputEl.textContent = "";
    setStatus(String(err.message || err), true);
  } finally {
    sendBtn.disabled = false;
  }
}

document.querySelectorAll("[data-experiment]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const prompt = btn.getAttribute("data-prompt") || "";
    promptEl.value = prompt;
    sendPrompt();
  });
});

document.querySelectorAll("[data-prompt]").forEach((btn) => {
  if (btn.hasAttribute("data-experiment")) {
    return;
  }
  btn.addEventListener("click", () => {
    promptEl.value = btn.getAttribute("data-prompt") || "";
    sendPrompt();
  });
});

sendBtn.addEventListener("click", sendPrompt);
promptEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    sendPrompt();
  }
});

Promise.all([
  fetch("/api/experiments").then((r) => r.json()),
  fetch("/api/health").then((r) => r.json()),
  fetch("/api/backends").then((r) => r.json()),
])
  .then(([demo, health, board]) => {
    experiments = demo.experiments || [];
    backends = board.backends || [];
    l2Configured = Boolean(health.l2_configured);
    const wanted = new URLSearchParams(window.location.search).get("exp");
    const initial =
      experiments.find((item) => item.id === wanted) || experiments[0];
    if (initial) {
      renderExperiment(initial);
    }
    renderBackendBoard(null, false);
    const demoMode = new URLSearchParams(window.location.search).get("demo");
    if (demoMode === "repair") {
      setDemoMode(
        "repair",
        "L2 任务 2 · 修 Bell 语法坑 + 对照 G-260809-0018 真机归档",
      );
      showRepair(true);
      promptEl.value =
        "我想制备一个贝尔态，但这段代码报错了，帮我修好：H q[0]; CX q[0] q[1]";
      const bell = experiments.find((item) => item.id === "bell");
      if (bell) {
        renderExperiment(bell);
      }
      setStatus("任务 2：语法坑说明 + 真机 Bell 归档对照。");
    } else if (demoMode === "backend") {
      setDemoMode(
        "backend",
        "L2 任务 3 · ≥15 比特且 queue=none 的后端已高亮（本地模拟器）",
      );
      renderBackendBoard(null, true);
      promptEl.value = "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？";
      setStatus("任务 3：≥15 比特且 queue=none 的本地模拟器已高亮。");
    } else if (demoMode === "ghz" || demoMode === "ghz3") {
      setDemoMode(
        "ghz",
        "L2 任务 1 · 三比特 GHZ 真机归档 S-260810-0001（000/111 主峰）",
      );
      const ghz = experiments.find((item) => item.id === "ghz3");
      if (ghz) {
        renderExperiment(ghz);
        promptEl.value = "生成一个 3 比特 GHZ 态并全测量";
      }
      setStatus("任务 1：三比特 GHZ 真机归档 000/111。");
    } else {
      setDemoMode(null, null);
    }
    if (!l2Configured) {
      llmBadge.textContent = "真机已就绪 · Agent 待填 .env";
      if (!demoMode) {
        setStatus("先点第一次实验。三项任务无钥匙也能看懂；填 .env 后同一按钮会真的调用模型。");
      }
    } else {
      llmBadge.textContent = "真机已就绪 · Agent 可对话";
      if (!demoMode) {
        setStatus("先看真机主峰，再用下面三个按钮走评委三项任务。");
      }
    }
  })
  .catch(() => {
    setStatus("演示服务没有起来。请用 ./tools/start_l2_web.sh 启动。", true);
  });
