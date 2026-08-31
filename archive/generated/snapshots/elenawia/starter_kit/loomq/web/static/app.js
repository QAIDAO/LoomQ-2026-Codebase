const routeButtons = Array.from(document.querySelectorAll("[data-mode]"));
const exampleButtons = Array.from(document.querySelectorAll("[data-example]"));

const examplePicker = document.querySelector("#examplePicker");
const inputCard = document.querySelector("#inputCard");
const promptInput = document.querySelector("#prompt");
const promptLabel = document.querySelector("#promptLabel");
const promptHelp = document.querySelector("#promptHelp");
const modeKicker = document.querySelector("#modeKicker");
const modeTitle = document.querySelector("#modeTitle");
const modeIntro = document.querySelector("#modeIntro");
const doText = document.querySelector("#doText");
const seeText = document.querySelector("#seeText");
const learnText = document.querySelector("#learnText");
const runButton = document.querySelector("#runButton");
const interactionStatus = document.querySelector("#interactionStatus");
const resultPanel = document.querySelector("#resultPanel");
const resultTitle = document.querySelector("#resultTitle");
const resultIntro = document.querySelector("#resultIntro");
const resultVisual = document.querySelector("#resultVisual");
const output = document.querySelector("#output");
const loomqText = document.querySelector("#loomqText");
const platformCards = document.querySelector("#platformCards");
const platformSummary = document.querySelector("#platformSummary");
const detailsCard = document.querySelector("#detailsCard");
const detailsHint = document.querySelector("#detailsHint");
const techPrompt = document.querySelector("#techPrompt");
const backendName = document.querySelector("#backendName");
const shotCount = document.querySelector("#shotCount");
const qasm = document.querySelector("#qasm");

const defaultLoomqText = "每台量子计算机都有自己的“方言”和脾气——同一份实验，在不同芯片上的结果会略有不同。LoomQ 把它写成三家各自的方言、并排放在一起：不用看懂任何一家的规则，就能比较哪些一致、哪些不同。";

const examples = {
  random: {
    prompt: "电脑能不能像掷硬币一样，随机给出 0 或 1？",
    do: "重复观察同一种实验 1000 次。",
    see: "0 和 1 分别出现了多少次。",
    learn: "单次结果不固定，但大量结果可能呈现稳定规律。",
    help: "已选好问题，点击开始观察即可运行。",
  },
  bell: {
    prompt: "两个量子结果能不能产生特别的联系？",
    do: "准备两个实验对象，同时揭晓它们的结果，重复观察 1000 次。",
    see: "00、01、10、11 四种组合各出现了多少次。",
    learn: "多个结果之间可能出现特殊关联。",
    help: "已选好问题，点击开始观察即可运行。",
  },
};

const modes = {
  examples: {
    kicker: "普通问题",
    title: "选择一个准备好的问题",
    intro: "下面是两个准备好的问题，点击就能体验一次真实实验。",
    label: "当前选中的问题",
    button: "开始观察",
    readonly: true,
    showExamples: true,
    prompt: examples.random.prompt,
    help: examples.random.help,
    brief: examples.random,
  },
  generate: {
    kicker: "准备实验",
    title: "准备一份能运行的实验",
    intro: "说出你想生成什么实验，LoomQ 会准备步骤、检查并运行。",
    label: "你想生成的实验",
    prompt: "生成一个 3 比特一起产生关联结果的实验，并进行全测量。",
    help: "可以直接运行，也可以先改一下输入。",
    button: "准备并运行实验",
    readonly: false,
    showExamples: false,
    brief: {
      do: "把你的目标整理成一份可运行实验步骤。",
      see: "生成的实验步骤、检查状态和运行结果。",
      learn: "LoomQ 会把想法落到可验证的实验上。",
    },
  },
  repair: {
    kicker: "修复步骤",
    title: "修复跑不动的实验步骤",
    intro: "先告诉 LoomQ 你想达到什么结果，再贴入步骤。LoomQ 会理解目标，修正问题并再次检查。",
    label: "目标和跑不动的步骤",
    prompt: "我想制备一个 Bell 态，但这段代码报错了，请帮我修好：H q[0]; CX q[0] q[1]",
    help: "可以直接运行，也可以先改一下输入。",
    button: "修复并运行",
    readonly: false,
    showExamples: false,
    brief: {
      do: "先听懂原目标，再修正机器无法执行的部分。",
      see: "修复后的步骤、运行结果和是否保持原目标。",
      learn: "修复不是随便重写，而是尽量保留你原本想做的实验。",
    },
  },
  backend: {
    kicker: "选择环境",
    title: "比较可以运行这次实验的环境",
    intro: "告诉 LoomQ 你在意实验规模、费用、等待时间或是否需要注册，它会帮你比较适合的运行环境。",
    label: "你的运行要求",
    prompt: "我需要运行一个 15 比特电路，且零排队等待，选哪个平台？",
    help: "可以直接运行，也可以先改一下输入。",
    button: "比较运行环境",
    readonly: false,
    showExamples: false,
    brief: {
      do: "读取你的限制条件，并对照平台能力筛选。",
      see: "符合条件的平台，以及为什么推荐它们。",
      learn: "平台选择应该由清楚的条件兜底，不能只靠猜。",
    },
  },
};

let currentMode = null;
let currentExample = "random";

routeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
exampleButtons.forEach((button) => button.addEventListener("click", () => setExample(button.dataset.example)));
runButton.addEventListener("click", runExperiment);

resetOutput();
if (window.location.protocol === "file:") showFileWarning();

function setMode(modeName) {
  currentMode = modeName;
  const config = modes[modeName];
  routeButtons.forEach((button) => button.classList.toggle("selected", button.dataset.mode === modeName));
  modeKicker.textContent = config.kicker;
  modeTitle.textContent = config.title;
  modeIntro.textContent = config.intro;
  promptLabel.textContent = config.label;
  promptInput.readOnly = config.readonly;
  promptInput.value = modeName === "examples" ? examples[currentExample].prompt : config.prompt;
  promptHelp.textContent = modeName === "examples" ? examples[currentExample].help : config.help;
  runButton.disabled = false;
  runButton.textContent = config.button;
  inputCard.classList.remove("idle");
  examplePicker.hidden = !config.showExamples;
  if (config.showExamples) {
    exampleButtons.forEach((button) => button.classList.toggle("selected", button.dataset.example === currentExample));
  } else {
    exampleButtons.forEach((button) => button.classList.remove("selected"));
  }
  setBrief(modeName === "examples" ? examples[currentExample] : config.brief);
  interactionStatus.textContent = "";
  resetOutput();
}

function setExample(exampleName) {
  currentExample = exampleName;
  if (currentMode !== "examples") setMode("examples");
  const example = examples[exampleName];
  exampleButtons.forEach((button) => button.classList.toggle("selected", button.dataset.example === exampleName));
  promptInput.value = example.prompt;
  promptHelp.textContent = example.help;
  setBrief(example);
  interactionStatus.textContent = "";
  resetOutput();
}

function setBrief(brief) {
  doText.textContent = brief.do;
  seeText.textContent = brief.see;
  learnText.textContent = brief.learn;
}

function resetOutput() {
  resultTitle.textContent = "等待开始";
  resultIntro.textContent = "你开始实验后，这里会显示结果、次数和它说明了什么。";
  resultVisual.className = "result-visual empty-visual";
  resultVisual.innerHTML = "<span></span><span></span><span></span><span></span>";
  output.className = "output empty";
  output.innerHTML = "<p>这里会显示实验产生了哪些结果、各种结果出现了多少次、这些结果说明什么。</p>";
  techPrompt.textContent = "等待实验";
  backendName.textContent = "等待实验";
  shotCount.textContent = "等待实验";
  qasm.textContent = "等待生成机器步骤";
  detailsCard.classList.add("disabled");
  detailsHint.textContent = "实验完成后可用。";
  loomqText.textContent = defaultLoomqText;
  renderWaitingPlatforms();
}

function showFileWarning() {
  output.className = "output";
  output.innerHTML = `<div class="error"><strong>现在是直接打开文件，所以按钮不能真正运行</strong><p>请先进入 <code>starter_kit</code> 目录，运行：<code>python -m loomq.web.server --port 8765</code></p><p>然后打开 <code>http://127.0.0.1:8765/</code>。</p></div>`;
  resultTitle.textContent = "需要通过本地服务打开";
  interactionStatus.textContent = "需要通过本地服务打开网页。";
}

async function runExperiment() {
  if (!currentMode) {
    interactionStatus.textContent = "请先选择一种开始方式。";
    return;
  }
  const prompt = promptInput.value.trim();
  if (!prompt) {
    interactionStatus.textContent = "先写一句你想做什么。";
    promptInput.focus();
    return;
  }
  if (window.location.protocol === "file:") {
    showFileWarning();
    return;
  }
  setLoading();
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const response = await fetch("/api/experiment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "这次没有跑起来");
    renderResult(data, prompt);
    interactionStatus.textContent = "完成了。你可以换一个问题继续试。";
  } catch (error) {
    renderError(error);
  } finally {
    runButton.disabled = false;
    runButton.textContent = modes[currentMode].button;
  }
}

function setLoading() {
  runButton.disabled = true;
  runButton.textContent = "正在处理…";
  resultTitle.textContent = "正在准备";
  resultIntro.textContent = "LoomQ 正在理解输入、检查步骤并整理结果。";
  resultVisual.className = "result-visual loading-visual";
  resultVisual.innerHTML = "<span></span><span></span><span></span><span></span>";
  output.className = "output empty";
  output.innerHTML = `<div class="loading-list"><span>正在理解你的输入</span><span>正在检查实验步骤</span><span>正在重复观察并整理结果</span></div>`;
  interactionStatus.textContent = "不用操作，等结果出现就好。";
  backendName.textContent = "准备中";
  shotCount.textContent = "准备中";
  qasm.textContent = "等待生成机器步骤";
  detailsCard.classList.add("disabled");
  detailsHint.textContent = "正在准备技术细节。";
  loomqText.textContent = defaultLoomqText;
  renderWaitingPlatforms();
}

function renderResult(data, prompt) {
  resultTitle.textContent = data.title || "完成了";
  resultIntro.textContent = data.mode === "backend" ? "这次请求是在挑选运行环境，不涉及实验步骤。" : "这次实验已经完成，下面是结果和解释。";
  techPrompt.textContent = prompt;
  backendName.textContent = data.backend || (data.mode === "backend" ? "按条件筛选" : "暂未运行");
  shotCount.textContent = data.counts ? `${sumCounts(data.counts)} 次` : "暂未运行";
  qasm.textContent = renderTechnicalText(data);
  detailsCard.classList.remove("disabled");
  detailsHint.textContent = data.mode === "backend" ? "这里显示平台筛选依据和准确平台名称。" : "这里显示输入问题、生成步骤、检查结果、平台版本和统一结果。";
  loomqText.textContent = data.loomq || defaultLoomqText;
  if (data.mode === "backend") {
    renderBackendMode(data);
    renderBackendVisual(data.backends || []);
    renderWaitingPlatforms("等待一次真实实验", false);
    platformSummary.textContent = "这次你在挑选运行环境。等你真正运行一次实验后，这里会展示同一份实验在三个平台上的一致结果。";
    qasm.textContent = renderBackendTechnical(data);
    return;
  }
  renderExperimentMode(data);
  renderResultVisual(data);
  renderPlatforms(data.platforms || []);
}

function renderExperimentMode(data) {
  output.className = "output";
  output.innerHTML = `<div class="result-summary"><div><span>步骤</span><strong>已检查</strong></div><div><span>重复观察</span><strong>${data.counts ? sumCounts(data.counts) : 0} 次</strong></div><div><span>用途</span><strong>看规律</strong></div></div>${renderExplanationBlocks(data)}`;
}

function renderExplanationBlocks(data) {
  const blocks = data.explanation_blocks || explanationBlocksForKind(data.kind, data.mode);
  return `<div class="explanation-blocks">${blocks.map((block) => `<section><strong>${escapeHtml(block.title)}</strong><p>${escapeHtml(block.body)}</p></section>`).join("")}</div>`;
}

function explanationBlocksForKind(kind, mode) {
  if (kind === "random") {
    return [
      { title: "对应什么概念", body: "这是单量子位叠加实验：先让一个量子位处在 0 和 1 都有可能的状态，再测量它。" },
      { title: "这次看到了什么", body: "0 和 1 都出现了，而且次数比较接近。" },
      { title: "结果说明什么", body: "量子实验不一定每次给出同一个固定答案，常常要重复运行很多次，从概率分布里读规律。" },
      { title: "可以怎么理解", body: "有点像反复掷硬币：一次结果不确定，但做很多次后会看到大致比例。" },
    ];
  }
  if (kind === "bell") {
    return [
      { title: "对应什么概念", body: "这是 Bell 态实验。Bell 态用来观察两个量子位之间能不能形成强关联。" },
      { title: "Bell 态是什么意思", body: "可以先理解成“两枚量子硬币被联系起来”：第一枚是 0，第二枚也更可能是 0；第一枚是 1，第二枚也更可能是 1。" },
      { title: "这次看到了什么", body: "00 和 11 出现最多，01 和 10 很少出现。" },
      { title: "结果说明什么", body: mode === "repair" ? "这说明 LoomQ 修复的不是随便一段能跑的代码，而是保留了你的目标：让两个量子结果形成关联。" : "这说明两个结果不是各自乱选，而是表现出成对出现的关系。" },
    ];
  }
  if (kind === "ghz") {
    return [
      { title: "对应什么概念", body: "这是 GHZ3 态实验。GHZ3 可以理解成 Bell 态的三量子位版本，用来观察三个量子位能不能形成整体关联。" },
      { title: "GHZ3 是什么意思", body: "GHZ3 里的 3 表示三个量子位；实验成功时，最常见的结果通常是 000 和 111。" },
      { title: "这次看到了什么", body: "000 和 111 出现最多，其他组合很少出现。" },
      { title: "可以怎么理解", body: "有点像三个人同时举牌，最后经常三个人都举 0，或者三个人都举 1。" },
    ];
  }
  return [
    { title: "对应什么概念", body: "这是量子统计实验。" },
    { title: "这次看到了什么", body: "图表展示了重复运行后，每种结果出现了多少次。" },
  ];
}

function renderBackendMode(data) {
  const backends = data.backends || [];
  output.className = "output backend-output";
  output.innerHTML = `<div class="result-summary"><div><span>已比较</span><strong>平台条件</strong></div><div><span>找到</span><strong>${backends.length} 个</strong></div><div><span>依据</span><strong>规模/费用/等待</strong></div></div><div class="backend-list compact-backends">${backends.map(renderBackend).join("") || "<div>暂时没有找到符合条件的平台。可以放宽一个条件再试试。</div>"}</div>${renderBackendExplanation(backends)}`;
}

function renderBackendExplanation(backends) {
  const names = backends.slice(0, 3).map((backend) => backend.name.split(" ")[0]).join("、") || "暂无平台";
  const blocks = [
    { title: "对应什么任务", body: "这是运行环境选择。LoomQ 不是在生成实验步骤，而是在判断这次实验适合交给哪里运行。" },
    { title: "LoomQ 看了哪些条件", body: "它会看量子位数量、是否排队、是否免费、是否需要注册账号。" },
    { title: "这次找到了什么", body: `找到了 ${backends.length} 个符合条件的平台：${names}。` },
    { title: "结果说明什么", body: "你的要求可以先用本地模拟器完成，不需要等待真实机器排队。" },
  ];
  return `<div class="explanation-blocks backend-explanation">${blocks.map((block) => `<section><strong>${escapeHtml(block.title)}</strong><p>${escapeHtml(block.body)}</p></section>`).join("")}</div>`;
}

function renderResultVisual(data) {
  const rows = expandCountRows(data.counts || []);
  if (!rows.length) {
    resultVisual.className = "result-visual preview-visual";
    resultVisual.innerHTML = "<strong>更多实验</strong><span>正在准备</span>";
    return;
  }
  const total = sumCounts(rows);
  const maxPercent = Math.max(...rows.map((row) => getRowPercent(row, total)), 1);
  const axisMax = maxPercent <= 55 ? 50 : 100;
  resultVisual.className = "result-visual chart-visual";
  resultVisual.innerHTML = `
    <div class="chart-heading">
      <strong>测量结果分布</strong>
      <span>概率</span>
    </div>
    <div class="probability-chart" style="--axis-max:${axisMax}">
      <div class="y-axis">
        <span>${axisMax}%</span>
        <span>${Math.round(axisMax / 2)}%</span>
        <span>0%</span>
      </div>
      <div class="chart-grid">
        ${rows.map((row) => renderChartColumn(row, total, axisMax)).join("")}
      </div>
    </div>
    <p class="chart-note">${formatDominantHint(rows, total)}</p>
  `;
}

function renderBackendVisual(backends) {
  resultVisual.className = "result-visual backend-visual backend-filter-visual";
  resultVisual.innerHTML = `
    <div class="filter-heading"><strong>筛选条件</strong><span>根据你的要求比较平台</span></div>
    <div class="filter-flow">
      <div><span>需要规模</span><strong>15 比特左右</strong></div>
      <div><span>等待时间</span><strong>不用排队</strong></div>
      <div><span>费用</span><strong>可以免费试用</strong></div>
      <div><span>账号</span><strong>无需注册</strong></div>
    </div>
    <p><b>${backends.length}</b> 个平台符合这些条件。</p>
  `;
}

function renderBar(row) {
  const percent = Math.max(Number(row.percent) || 0, 3);
  return `<div class="bar-row"><span class="state">${escapeHtml(row.state)}</span><span class="track"><span class="fill" style="width:${percent}%"></span></span><span class="count">${row.count} 次</span></div>`;
}

function expandCountRows(rows) {
  if (!rows.length) return [];
  const countByState = Object.fromEntries(rows.map((row) => [String(row.state), Number(row.count) || 0]));
  const bitLength = Math.max(...Object.keys(countByState).map((state) => state.length));
  if (bitLength >= 1 && bitLength <= 3) {
    return Array.from({ length: 2 ** bitLength }, (_, index) => {
      const state = index.toString(2).padStart(bitLength, "0");
      return { state, count: countByState[state] || 0 };
    });
  }
  return rows.map((row) => ({ state: String(row.state), count: Number(row.count) || 0 }));
}

function getRowPercent(row, total) {
  if (!total) return 0;
  return (Number(row.count) || 0) / total * 100;
}

function renderChartColumn(row, total, axisMax) {
  const percent = getRowPercent(row, total);
  const height = Math.max(percent / axisMax * 100, row.count ? 2 : 0);
  const isDominant = percent >= Math.max(35, axisMax * 0.62);
  return `
    <div class="chart-column ${isDominant ? "dominant" : ""}" title="${escapeHtml(row.state)}：${row.count} 次，${percent.toFixed(1)}%">
      <div class="column-wrap">
        <span class="column-fill" style="height:${Math.min(height, 100)}%"></span>
      </div>
      <strong>${escapeHtml(row.state)}</strong>
      <small>${row.count} 次</small>
      <em>${percent.toFixed(1)}%</em>
    </div>
  `;
}

function formatDominantHint(rows, total) {
  const activeRows = rows.filter((row) => row.count > 0);
  if (!activeRows.length) return "还没有出现可统计的结果。";
  const sorted = [...activeRows].sort((a, b) => b.count - a.count);
  const topRows = sorted.filter((row) => getRowPercent(row, total) >= 10).slice(0, 3);
  return `主峰结果：${topRows.map((row) => `${row.state}（${getRowPercent(row, total).toFixed(1)}%）`).join("、")}。`;
}

function renderBackend(backend) {
  const queue = backend.queue === "none" ? "不用排队" : "可能需要等待";
  const cost = backend.cost === "paid" ? "需要付费" : "可以免费试用";
  const account = backend.requires_account ? "需要账号" : "无需注册";
  return `<div class="backend-item"><strong>${escapeHtml(backend.name)}</strong><span>${escapeHtml(backend.id)}</span><small>${backend.max_qubits} 比特 · ${queue} · ${cost} · ${account}</small></div>`;
}

function renderPlatforms(platforms) {
  if (!platforms.length) {
    renderWaitingPlatforms();
    return;
  }
  platformCards.innerHTML = platforms.map((platform) => {
    const counts = platform.counts || [];
    const summary = counts.map((row) => `${row.state} 出现 ${row.count} 次`).join(" · ");
    return `<article><strong>${escapeHtml(platform.name)}</strong><span>${escapeHtml(platform.status)}</span><p class="platform-result">该平台返回：${escapeHtml(summary)}</p><div class="mini-counts">${counts.map((row) => `<b>${escapeHtml(row.state)}：${row.count}</b>`).join("")}</div></article>`;
  }).join("");
  const dominantState = (counts) => (counts && counts.length ? [...counts].sort((a, b) => (b.count || 0) - (a.count || 0))[0].state : null);
  const tops = platforms.map((platform) => dominantState(platform.counts)).filter(Boolean);
  const samePeak = tops.length > 1 && tops.every((state) => state === tops[0]);
  platformSummary.textContent = samePeak
    ? "LoomQ 把你的实验分别写成三家平台各自的“方言”。三个平台的结果一致——说明换一种写法，实验本身没有被改变。"
    : "LoomQ 把你的实验分别写成三家平台各自的“方言”。这一次三家的结果并不完全相同——真实量子设备带有噪声，同一份实验出现波动是正常现象。";
}

function renderWaitingPlatforms(message = "等待实验", resetSummary = true) {
  platformCards.innerHTML = ["SpinQ", "OriginQ", "AWS Braket"].map((name) => `<article><strong>${name}</strong><span>${escapeHtml(message)}</span></article>`).join("");
  if (resetSummary) platformSummary.textContent = "完成实验后，这里会说明三个平台看到的结果是否一致。";
}

function renderTechnicalText(data) {
  const sections = [];
  if (data.qasm) sections.push(`生成的实验步骤：\n${data.qasm}`);
  (data.platforms || []).forEach((platform) => sections.push(`${platform.name} 版本：\n${platform.transpiled || ""}`));
  return sections.join("\n\n---\n\n") || "这次请求没有生成实验步骤。";
}

function renderBackendTechnical(data) {
  const rows = (data.backends || []).map((backend) => `${backend.id} | ${backend.name} | ${backend.max_qubits} qubits | queue=${backend.queue} | cost=${backend.cost}`).join("\n");
  return rows || "没有找到符合条件的平台。";
}

function renderError(error) {
  output.className = "output";
  output.innerHTML = `<div class="error"><strong>这次没跑起来</strong><p>${escapeHtml(error.message)}</p><button type="button" class="retry-button">再试一次</button></div>`;
  output.querySelector(".retry-button").addEventListener("click", runExperiment);
  resultTitle.textContent = "需要再试一次";
  resultIntro.textContent = "可以换一种说法，或者先试一个现成问题。";
  interactionStatus.textContent = "可以点“再试一次”，也可以换一种输入。";
}

function sumCounts(rows) {
  return rows.reduce((sum, row) => sum + Number(row.count || 0), 0);
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

