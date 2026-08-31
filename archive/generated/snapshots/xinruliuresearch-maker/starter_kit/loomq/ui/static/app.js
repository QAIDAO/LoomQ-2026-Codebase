"use strict";

const copy = {
  zh: {
    skip: "跳到工作台",
    brandSub: "编译观测台",
    navCompose: "编排",
    navInspect: "检视",
    navEvidence: "证据",
    examples: "已验证起点",
    history: "本次会话历史",
    refresh: "刷新",
    loading: "加载中…",
    noRuns: "尚无本地运行",
    system: "本地系统",
    checking: "检查中",
    ready: "就绪",
    configRequired: "需配置",
    notRun: "未执行",
    truthNote: "执行使用 LoomQ 本地参考模拟器。目标页签仅为方言产物，不是厂商任务。",
    workspaceLabel: "本地 / 请求隔离",
    workspaceTitle: "量子编译工作台",
    localRef: "LoomQ 本地参考模拟器",
    localRefShort: "LOOMQ 参考模拟",
    briefTitle: "这个回路要验证什么？",
    briefHelp: "除非选择 Agent，自然语言描述可留空。",
    promptLabel: "任务描述",
    promptPlaceholder: "例：执行两比特 Bell 态，并检查 00 / 11 相关性。",
    noCot: "仅显示任务元数据；不展示隐藏推理。",
    task: "任务",
    target: "执行目标",
    shots: "采样次数",
    taskSimulate: "编译 + 本地模拟",
    taskTranspile: "仅生成目标方言",
    taskHybrid: "编译 Hybrid-QASM",
    taskAgent: "Agent 请求",
    referenceEngine: "本地参考",
    unsavedInput: "请求输入",
    copy: "复制",
    clear: "清空",
    sourceLabel: "OpenQASM 或 Hybrid-QASM 源码",
    shortcutRun: "运行流水线",
    goToError: "定位源码",
    runPipeline: "运行验证流水线",
    repair: "保守修复",
    cancel: "停止等待",
    retry: "再次运行",
    privacy: "默认仅本地 HTTP · 按请求隔离证据 · 原子写入",
    inspectionTitle: "准入与证据",
    idle: "空闲",
    running: "运行中",
    completed: "完成",
    failed: "失败",
    cancelled: "已停止等待",
    workflow: "工作流",
    wfRequest: "请求准入",
    wfIntent: "意图分类",
    wfNormalize: "源码归一化",
    wfLower: "生成目标方言",
    wfExecute: "本地运行 / 编译",
    wfVerify: "封存证据",
    intent: "意图",
    normalized: "归一化",
    targetArtifacts: "目标方言产物",
    artifactBoundary: "本地生成；不声称厂商任务。",
    noArtifact: "运行源码后查看通过准入的方言产物。",
    counts: "测量计数",
    countsEmpty: "尚无本地执行结果。",
    verification: "验证",
    verificationEmpty: "运行后显示检查项。",
    evidence: "证据台账",
    evidenceHelp: "SHA-256 封存的请求隔离文件。",
    evidenceEmpty: "首个通过或被拒绝的请求后将生成清单。",
    bitOrder: "位序 / LITTLE",
    copied: "已复制到剪贴板",
    loadedExample: "已加载验证示例",
    stopped: "已停止等待；服务端请求可能仍在封存证据。",
    requestFailed: "请求失败",
    sourceCleared: "源码已清空",
    stateInput: "请求输入",
    stateHybrid: "HYBRID / 输入",
    stateAgent: "AGENT / 描述",
    stateAdmitted: "已准入 / 已封存",
    stateRepaired: "已修复 / 已准入",
    stateAgentAdmitted: "AGENT / 已准入",
    conceptTitle: "量子概念速查",
    conceptSubtitle: "新手可展开的 9 个术语",
    conceptBoundary: "本面板解释界面读数，不推断未测量的量子态。",
    conceptQubit: "量子信息的线路单位；电路图的 q0、q1 表示它们的索引。",
    conceptGate: "对指定 qubit 的操作；图中的门来自已准入的规范化 IR。",
    conceptMeasurement: "把 qubit 的测量结果写入经典 bit，电路图标为 M 和 cN。",
    conceptShots: "同一电路重复采样的次数；它不是门数。",
    conceptCounts: "实际观测到的比特串次数；count / shots 是样本频率，不是振幅。",
    conceptEndian: "较低索引的 c0 是最低有效位，在输出比特串中位于最右侧。",
    conceptSimulatorTerm: "模拟器 vs 真机",
    conceptSimulator: "本地参考模拟器计算数学模型；QPU 有物理噪声、排队和凭据。无硬件证据时不声称真机执行。",
    conceptTranspileTerm: "转译 vs 执行",
    conceptTranspile: "转译生成 SpinQ / OriginIR / Braket 方言；执行才会产生 shots 和 counts。",
    conceptPassed: "表示本地语法、往返语义和结果模式检查通过；不等于算法已被证明或 QPU 已运行。",
    conceptGuide: "打开本地 QUANTUM_101.md",
    circuitTitle: "规范化电路图",
    circuitHelp: "由已准入操作绘制线、门和测量；不显示未测量量子态。",
    circuitEmpty: "运行 OpenQASM 后生成本地 SVG 电路图。",
    circuitAria: "规范化电路",
    topStates: "Top states · 测量态排行",
    observedOnly: "仅实际观测 counts",
    topStatesEmpty: "运行后按实际计数降序显示。"
  },
  en: {
    skip: "Skip to workbench",
    brandSub: "Compiler observatory",
    navCompose: "Compose",
    navInspect: "Inspect",
    navEvidence: "Evidence",
    examples: "Verified starters",
    history: "Session history",
    refresh: "Refresh",
    loading: "Loading…",
    noRuns: "No local runs yet",
    system: "Local systems",
    checking: "Checking",
    ready: "Ready",
    configRequired: "Config required",
    notRun: "Not run",
    truthNote: "Execution uses LoomQ's local reference simulator. Target tabs are dialect artifacts, not vendor jobs.",
    workspaceLabel: "LOCAL / REQUEST-SCOPED",
    workspaceTitle: "Quantum compiler workbench",
    localRef: "LoomQ local reference simulator",
    localRefShort: "LOOMQ REF.",
    briefTitle: "What should the circuit prove?",
    briefHelp: "Plain language is optional unless Agent is selected.",
    promptLabel: "Prompt",
    promptPlaceholder: "Example: execute a two-qubit Bell state and inspect 00 / 11 correlation.",
    noCot: "Only task metadata is shown; hidden reasoning is never displayed.",
    task: "Task",
    target: "Execution target",
    shots: "Shots",
    taskSimulate: "Compile + local simulate",
    taskTranspile: "Generate target dialects only",
    taskHybrid: "Compile Hybrid-QASM",
    taskAgent: "Agent request",
    referenceEngine: "LOCAL REF.",
    unsavedInput: "REQUEST INPUT",
    copy: "Copy",
    clear: "Clear",
    sourceLabel: "OpenQASM or Hybrid-QASM source",
    shortcutRun: "run pipeline",
    goToError: "Go to source",
    runPipeline: "Run verified pipeline",
    repair: "Conservative repair",
    cancel: "Stop waiting",
    retry: "Run again",
    privacy: "Local HTTP only by default · evidence isolated per request · atomic writes",
    inspectionTitle: "Admission & evidence",
    idle: "IDLE",
    running: "RUNNING",
    completed: "COMPLETED",
    failed: "FAILED",
    cancelled: "WAIT STOPPED",
    workflow: "Workflow",
    wfRequest: "Request admitted",
    wfIntent: "Intent classified",
    wfNormalize: "Source normalized",
    wfLower: "Target dialects generated",
    wfExecute: "Local runtime / compiler",
    wfVerify: "Evidence sealed",
    intent: "Intent",
    normalized: "Normalized",
    targetArtifacts: "Target dialect artifacts",
    artifactBoundary: "Generated locally; no vendor job is claimed.",
    noArtifact: "Run a source to inspect admitted dialect artifacts.",
    counts: "Measurement counts",
    countsEmpty: "No local execution result yet.",
    verification: "Verification",
    verificationEmpty: "Checks appear after a run.",
    evidence: "Evidence ledger",
    evidenceHelp: "SHA-256 sealed, request-scoped files.",
    evidenceEmpty: "A manifest appears after the first admitted or rejected request.",
    bitOrder: "BIT ORDER / LITTLE",
    copied: "Copied to clipboard",
    loadedExample: "Verified example loaded",
    stopped: "Stopped waiting; the server may still be sealing this request's evidence.",
    requestFailed: "Request failed",
    sourceCleared: "Source cleared",
    stateInput: "REQUEST INPUT",
    stateHybrid: "HYBRID / INPUT",
    stateAgent: "AGENT / PROMPT",
    stateAdmitted: "ADMITTED / SEALED",
    stateRepaired: "REPAIRED / ADMITTED",
    stateAgentAdmitted: "AGENT / ADMITTED",
    conceptTitle: "Quantum concept quick reference",
    conceptSubtitle: "9 expandable terms for newcomers",
    conceptBoundary: "This panel explains interface readings; it does not infer an unmeasured quantum state.",
    conceptQubit: "A circuit unit of quantum information; q0 and q1 in the diagram are qubit indices.",
    conceptGate: "An operation on named qubits; every drawn gate comes from the admitted normalized IR.",
    conceptMeasurement: "Writes a measured qubit outcome to a classical bit, shown as M and cN in the diagram.",
    conceptShots: "How many times the same circuit is sampled; this is not the number of gates.",
    conceptCounts: "Observed bit-string totals; count / shots is a sample frequency, not an amplitude.",
    conceptEndian: "Lower-index c0 is the least-significant bit and appears at the right edge of an output bit string.",
    conceptSimulatorTerm: "Simulator vs QPU",
    conceptSimulator: "The local reference simulator computes a mathematical model. A QPU adds physical noise, queues, and credentials. No QPU run is claimed without hardware evidence.",
    conceptTranspileTerm: "Transpile vs execute",
    conceptTranspile: "Transpilation creates SpinQ / OriginIR / Braket dialects; execution is what produces shots and counts.",
    conceptPassed: "Local syntax, semantic round-trip, and result-schema checks passed. It does not prove the algorithm or claim a QPU run.",
    conceptGuide: "Open local QUANTUM_101.md",
    circuitTitle: "Normalized circuit diagram",
    circuitHelp: "Wires, gates, and measurements come from admitted operations; no unmeasured state is shown.",
    circuitEmpty: "Run OpenQASM to generate a local SVG circuit diagram.",
    circuitAria: "Normalized circuit",
    topStates: "Top states · measurement ranking",
    observedOnly: "observed counts only",
    topStatesEmpty: "Run a circuit to rank actual observed counts."
  }
};

const state = {
  language: "zh",
  examples: [],
  history: [],
  selectedExample: "",
  ir: {},
  selectedIr: "spinq",
  lastPayload: null,
  lastError: null,
  controller: null,
  busy: false,
  health: null,
  runStatus: "idle",
  fileState: "stateInput",
  lastResult: null,
  lastNormalized: null
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheDom();
  bindEvents();
  updateEditorMetrics();
  setLanguage("zh");
  bootstrap();
});

function cacheDom() {
  const ids = [
    "example-list", "history-list", "refresh-history", "component-status",
    "language-toggle", "run-form", "prompt", "prompt-count", "task", "target",
    "shots", "qasm", "line-numbers", "source-stats", "file-state", "copy-source",
    "clear-source", "diagnostic", "diagnostic-code", "diagnostic-message",
    "diagnostic-suggestion", "focus-error", "run-button", "repair-button",
    "cancel-button", "retry-button", "session-label", "run-status",
    "run-id-short", "workflow-list", "intent-data", "normalized-data",
    "ir-output", "copy-ir", "counts-chart", "counts-caption",
    "verification-status", "verification-list", "artifact-count", "artifact-list",
    "toast-region", "circuit-diagram", "circuit-operation-count", "top-states"
  ];
  ids.forEach((id) => { dom[toCamel(id)] = document.getElementById(id); });
  dom.irTabs = Array.from(document.querySelectorAll("[data-ir]"));
  dom.scrollButtons = Array.from(document.querySelectorAll("[data-scroll]"));
}

function toCamel(value) {
  return value.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

function bindEvents() {
  dom.languageToggle.addEventListener("click", () => {
    setLanguage(state.language === "zh" ? "en" : "zh");
  });
  dom.runForm.addEventListener("submit", (event) => {
    event.preventDefault();
    submitRun(buildPayload());
  });
  dom.repairButton.addEventListener("click", () => {
    const payload = buildPayload();
    payload.task = "repair";
    submitRun(payload);
  });
  dom.retryButton.addEventListener("click", () => {
    if (state.lastPayload) submitRun({ ...state.lastPayload });
  });
  dom.cancelButton.addEventListener("click", cancelWaiting);
  dom.refreshHistory.addEventListener("click", loadHistory);
  dom.prompt.addEventListener("input", updatePromptCount);
  dom.qasm.addEventListener("input", updateEditorMetrics);
  dom.qasm.addEventListener("scroll", () => {
    dom.lineNumbers.scrollTop = dom.qasm.scrollTop;
  });
  dom.qasm.addEventListener("keydown", editorKeydown);
  dom.runForm.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      submitRun(buildPayload());
    }
  });
  dom.task.addEventListener("change", updateTaskMode);
  dom.copySource.addEventListener("click", () => copyText(dom.qasm.value));
  dom.clearSource.addEventListener("click", () => {
    dom.qasm.value = "";
    dom.prompt.value = "";
    state.selectedExample = "";
    updateEditorMetrics();
    updatePromptCount();
    renderExamples();
    toast(t("sourceCleared"));
  });
  dom.focusError.addEventListener("click", focusDiagnostic);
  dom.copyIr.addEventListener("click", () => copyText(state.ir[state.selectedIr] || ""));
  dom.irTabs.forEach((tab) => {
    tab.addEventListener("click", () => selectIr(tab.dataset.ir));
    tab.addEventListener("keydown", irTabKeydown);
  });
  dom.scrollButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.scroll);
      if (target) target.scrollIntoView({ block: "start" });
      dom.scrollButtons.forEach((item) => item.classList.toggle("is-active", item === button));
    });
  });
}

async function bootstrap() {
  try {
    const [health, examples, history] = await Promise.all([
      getJson("/api/health"), getJson("/api/examples"), getJson("/api/history")
    ]);
    state.examples = Array.isArray(examples.examples) ? examples.examples : [];
    state.history = Array.isArray(history.runs) ? history.runs : [];
    renderHealth(health);
    renderExamples();
    renderHistory();
    dom.sessionLabel.textContent = `SESSION / ${String(health.session_id || "—").slice(0, 8)}`;
    if (!dom.qasm.value && state.examples.length) loadExample(state.examples[0], false);
  } catch (error) {
    renderHealth(null);
    toast(`${t("requestFailed")}: ${safeMessage(error)}`, true);
  }
}

async function getJson(url) {
  const response = await fetch(url, { headers: { "Accept": "application/json" } });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message || `HTTP ${response.status}`);
  return body;
}

function buildPayload() {
  const numericShots = Number(dom.shots.value);
  return {
    task: dom.task.value,
    target: dom.target.value,
    shots: Number.isInteger(numericShots) ? numericShots : dom.shots.value,
    prompt: dom.prompt.value,
    qasm: dom.qasm.value
  };
}

async function submitRun(payload) {
  if (state.busy) return;
  state.busy = true;
  state.lastPayload = { ...payload };
  state.lastError = null;
  state.lastResult = null;
  state.lastNormalized = null;
  state.controller = new AbortController();
  setLoading(true);
  clearDiagnostic();
  renderIntent({});
  renderNormalized({});
  configureIrTabs({});
  renderCounts({});
  renderWorkflow([{ id: "request", status: "running" }]);
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: state.controller.signal
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || `HTTP ${response.status}`);
    renderRun(body);
    await loadHistory();
  } catch (error) {
    if (error.name === "AbortError") {
      setStatus("cancelled");
      toast(t("stopped"));
    } else {
      setStatus("failed");
      state.lastError = { message: safeMessage(error) };
      showDiagnostic({ code: "NETWORK_ERROR", message: safeMessage(error), retryable: true });
      toast(`${t("requestFailed")}: ${safeMessage(error)}`, true);
    }
  } finally {
    state.busy = false;
    state.controller = null;
    setLoading(false);
  }
}

function cancelWaiting() {
  if (state.controller) state.controller.abort();
}

function setLoading(active) {
  dom.runButton.disabled = active;
  dom.repairButton.disabled = active;
  dom.cancelButton.classList.toggle("is-hidden", !active);
  if (active) {
    dom.retryButton.classList.add("is-hidden");
    setStatus("running");
  }
}

function renderRun(body) {
  renderWorkflow(body.workflow || []);
  renderArtifacts(body.manifest, body.run_id);
  dom.runIdShort.textContent = String(body.run_id || "").slice(0, 8) || "————————";
  if (!body.ok) {
    state.lastError = body.error || {};
    showDiagnostic(body.error || {});
    renderVerification({
      status: "failed",
      checks: [{ id: "request", passed: false, detail: body.error?.message || "Request rejected" }]
    });
    setStatus("failed");
    dom.retryButton.classList.toggle("is-hidden", !body.error?.retryable);
    toast(`${body.error?.code || t("failed")}: ${body.error?.message || ""}`, true);
    return;
  }

  setStatus("completed");
  dom.retryButton.classList.add("is-hidden");
  renderIntent(body.intent || {});
  renderNormalized(body.normalized || {});
  configureIrTabs(body.ir || {});
  renderCounts(body.result || {});
  renderVerification(body.verification || {});
  if (body.source && (state.lastPayload?.task === "repair" || state.lastPayload?.task === "agent")) {
    dom.qasm.value = body.source;
    updateEditorMetrics();
    setFileState(state.lastPayload.task === "repair" ? "stateRepaired" : "stateAgentAdmitted");
  } else {
    setFileState("stateAdmitted");
  }
}

function setStatus(status) {
  state.runStatus = status;
  dom.runStatus.className = `run-status ${status}`;
  dom.runStatus.textContent = t(status);
}

function renderHealth(health) {
  state.health = health;
  const values = health?.components || {};
  const rows = Array.from(dom.componentStatus.querySelectorAll("div"));
  const states = [
    values.qasm_parser,
    values.reference_runtime,
    values.llm_agent,
    "not_run"
  ];
  rows.forEach((row, index) => {
    const dot = row.querySelector("i");
    const label = row.querySelector("span");
    const value = states[index];
    dot.className = "status-dot " + (
      value === "ready" ? "ready" : value === "configuration_required" ? "pending" : value === "not_run" ? "neutral" : "failed"
    );
    label.textContent = value === "ready" ? t("ready") : value === "configuration_required" ? t("configRequired") : value === "not_run" ? t("notRun") : t("failed");
  });
}

function renderExamples() {
  dom.exampleList.replaceChildren();
  if (!state.examples.length) {
    const empty = document.createElement("div");
    empty.className = "rail-placeholder";
    empty.textContent = t("loading");
    dom.exampleList.append(empty);
    return;
  }
  state.examples.forEach((example) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "example-button" + (state.selectedExample === example.id ? " is-selected" : "");
    button.dataset.exampleId = example.id;
    const title = document.createElement("strong");
    title.textContent = state.language === "zh" ? example.title_zh : example.title_en;
    const note = document.createElement("span");
    note.textContent = state.language === "zh" ? example.note_zh : example.note_en;
    button.append(title, note);
    button.addEventListener("click", () => loadExample(example));
    dom.exampleList.append(button);
  });
}

function loadExample(example, notify = true) {
  state.selectedExample = example.id;
  dom.prompt.value = example.prompt || "";
  dom.qasm.value = example.qasm || "";
  dom.task.value = example.task || "simulate";
  dom.target.value = example.target || "spinq";
  dom.shots.value = String(example.shots || 1024);
  clearDiagnostic();
  updatePromptCount();
  updateEditorMetrics();
  updateTaskMode();
  renderExamples();
  if (notify) toast(t("loadedExample"));
}

async function loadHistory() {
  try {
    const body = await getJson("/api/history");
    state.history = Array.isArray(body.runs) ? body.runs : [];
    renderHistory();
  } catch (error) {
    toast(`${t("requestFailed")}: ${safeMessage(error)}`, true);
  }
}

function renderHistory() {
  dom.historyList.replaceChildren();
  if (!state.history.length) {
    const item = document.createElement("li");
    item.className = "rail-placeholder";
    item.textContent = t("noRuns");
    dom.historyList.append(item);
    return;
  }
  state.history.slice(0, 6).forEach((record) => {
    const item = document.createElement("li");
    item.className = `history-item ${record.status || ""}`;
    const dot = document.createElement("i");
    const label = document.createElement("span");
    label.textContent = `${record.summary?.task || "request"} / ${record.summary?.target || "—"}`;
    const code = document.createElement("code");
    code.textContent = String(record.run_id || "").slice(0, 6);
    item.append(dot, label, code);
    dom.historyList.append(item);
  });
}

function renderWorkflow(steps) {
  const map = new Map(steps.map((step) => [step.id, step.status]));
  Array.from(dom.workflowList.children).forEach((item) => {
    const status = map.get(item.dataset.step) || "pending";
    item.className = status;
  });
}

function renderIntent(intent) {
  const values = [intent.task, intent.target, intent.shots];
  Array.from(dom.intentData.querySelectorAll("dd")).forEach((item, index) => {
    item.textContent = values[index] ?? "—";
    item.title = String(values[index] ?? "—");
  });
}

function renderNormalized(normalized) {
  state.lastNormalized = normalized;
  const values = [normalized.qubit_count, normalized.classical_count, normalized.operation_count];
  Array.from(dom.normalizedData.querySelectorAll("dd")).forEach((item, index) => {
    item.textContent = values[index] ?? "—";
  });
  renderCircuit(normalized);
}

function renderCircuit(normalized) {
  const operations = Array.isArray(normalized?.operations) ? normalized.operations : [];
  const qubitCount = Number(normalized?.qubit_count);
  dom.circuitDiagram.replaceChildren();
  dom.circuitOperationCount.textContent = `${String(operations.length).padStart(2, "0")} OPS`;
  if (!Number.isInteger(qubitCount) || qubitCount < 1 || !operations.length) {
    const empty = document.createElement("p");
    empty.className = "circuit-empty";
    empty.textContent = t("circuitEmpty");
    dom.circuitDiagram.append(empty);
    dom.circuitDiagram.setAttribute("aria-label", t("circuitEmpty"));
    return;
  }

  const maximumOperations = 120;
  const visible = operations.slice(0, maximumOperations);
  const truncated = operations.length - visible.length;
  const rowHeight = 40;
  const top = 30;
  const left = 48;
  const step = 54;
  const width = Math.max(360, left + visible.length * step + (truncated ? 92 : 28));
  const height = top + (qubitCount - 1) * rowHeight + 48;
  const svg = svgElement("svg", {
    class: "circuit-svg",
    viewBox: `0 0 ${width} ${height}`,
    width,
    height,
    role: "img"
  });
  const title = svgElement("title");
  title.textContent = `${t("circuitAria")}: ${qubitCount} qubits, ${operations.length} operations`;
  svg.append(title);

  for (let qubit = 0; qubit < qubitCount; qubit += 1) {
    const y = top + qubit * rowHeight;
    const label = svgElement("text", { x: 8, y: y + 3, class: "circuit-label" });
    label.textContent = `q${qubit}`;
    const wire = svgElement("line", { x1: 31, y1: y, x2: width - 16, y2: y, class: "circuit-wire" });
    svg.append(label, wire);
  }

  visible.forEach((operation, position) => {
    const x = left + position * step;
    const group = svgElement("g", {
      class: `circuit-operation ${operation.kind === "measure" ? "circuit-measurement" : "circuit-gate"}`,
      "data-operation-index": operation.index ?? position
    });
    const index = svgElement("text", { x, y: 11, class: "circuit-index-label" });
    index.textContent = String((operation.index ?? position) + 1);
    group.append(index);
    if (operation.kind === "measure") {
      drawMeasurement(group, x, top + Number(operation.qubit) * rowHeight, operation.qubit, operation.cbit);
    } else if (operation.kind === "gate") {
      drawGate(group, x, top, rowHeight, operation);
    }
    svg.append(group);
  });

  if (truncated > 0) {
    const notice = svgElement("text", {
      x: left + visible.length * step,
      y: 18,
      class: "circuit-label"
    });
    notice.textContent = `… +${truncated} ops`;
    svg.append(notice);
  }
  dom.circuitDiagram.append(svg);
  dom.circuitDiagram.setAttribute(
    "aria-label",
    `${t("circuitAria")}, ${qubitCount} qubits, ${operations.length} operations`
  );
}

function drawMeasurement(group, x, y, qubit, cbit) {
  const box = svgElement("rect", { x: x - 14, y: y - 13, width: 28, height: 26, rx: 1, class: "circuit-measure-box" });
  const label = svgElement("text", { x, y: y + 3, class: "circuit-gate-label" });
  label.textContent = "M";
  const classical = svgElement("text", { x, y: y + 24, class: "circuit-index-label" });
  classical.textContent = `c${cbit}`;
  const title = svgElement("title");
  title.textContent = `measure q${qubit} -> c${cbit}`;
  group.append(title, box, label, classical);
}

function drawGate(group, x, top, rowHeight, operation) {
  const qubits = Array.isArray(operation.qubits) ? operation.qubits.map(Number) : [];
  if (!qubits.length) return;
  const name = String(operation.name || "gate").toUpperCase();
  const ys = qubits.map((qubit) => top + qubit * rowHeight);
  const title = svgElement("title");
  const params = Array.isArray(operation.params) && operation.params.length
    ? `(${operation.params.map((value) => Number(value).toPrecision(6)).join(", ")})`
    : "";
  title.textContent = `${name}${params} q[${qubits.join("], q[")}]`;
  group.append(title);
  if (ys.length > 1) {
    group.append(svgElement("line", { x1: x, y1: Math.min(...ys), x2: x, y2: Math.max(...ys), class: "circuit-connector" }));
  }
  if (name === "CX" || name === "CCX") {
    ys.slice(0, -1).forEach((y) => group.append(svgElement("circle", { cx: x, cy: y, r: 3.5, class: "circuit-control" })));
    drawTarget(group, x, ys[ys.length - 1]);
    return;
  }
  if (name === "SWAP" && ys.length === 2) {
    ys.forEach((y) => drawSwap(group, x, y));
    return;
  }
  if (name === "CU1" && ys.length === 2) {
    group.append(svgElement("circle", { cx: x, cy: ys[0], r: 3.5, class: "circuit-control" }));
    drawGateBox(group, x, ys[1], "U1");
    return;
  }
  ys.forEach((y) => drawGateBox(group, x, y, name.slice(0, 4)));
}

function drawGateBox(group, x, y, labelText) {
  const box = svgElement("rect", { x: x - 14, y: y - 13, width: 28, height: 26, rx: 1, class: "circuit-gate-box" });
  const label = svgElement("text", { x, y: y + 3, class: "circuit-gate-label" });
  label.textContent = labelText;
  group.append(box, label);
}

function drawTarget(group, x, y) {
  group.append(
    svgElement("circle", { cx: x, cy: y, r: 8, class: "circuit-target-ring" }),
    svgElement("line", { x1: x - 5, y1: y, x2: x + 5, y2: y, class: "circuit-target-ring" }),
    svgElement("line", { x1: x, y1: y - 5, x2: x, y2: y + 5, class: "circuit-target-ring" })
  );
}

function drawSwap(group, x, y) {
  group.append(
    svgElement("line", { x1: x - 6, y1: y - 6, x2: x + 6, y2: y + 6, class: "circuit-swap-line" }),
    svgElement("line", { x1: x + 6, y1: y - 6, x2: x - 6, y2: y + 6, class: "circuit-swap-line" })
  );
}

function configureIrTabs(ir) {
  state.ir = ir;
  const keys = Object.keys(ir);
  const hybrid = keys.includes("quantum") || keys.includes("tinyriscv");
  const config = hybrid
    ? [["quantum", "QUANTUM / OPS"], ["tinyriscv", "TINYRISCV / ASM"]]
    : [["spinq", "SPINQ / QASM2"], ["originq", "ORIGIN / IR"], ["braket", "BRAKET / QASM3"]];
  dom.irTabs.forEach((tab, index) => {
    const entry = config[index];
    tab.hidden = !entry;
    if (entry) {
      tab.dataset.ir = entry[0];
      tab.textContent = entry[1];
    }
  });
  selectIr(config[0]?.[0] || "spinq");
}

function selectIr(key) {
  state.selectedIr = key;
  dom.irTabs.forEach((tab) => {
    const selected = !tab.hidden && tab.dataset.ir === key;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected) dom.irOutput.setAttribute("aria-labelledby", tab.id);
  });
  dom.irOutput.textContent = state.ir[key] || t("noArtifact");
}

function irTabKeydown(event) {
  if (!(["ArrowLeft", "ArrowRight"].includes(event.key))) return;
  const visible = dom.irTabs.filter((tab) => !tab.hidden);
  const current = visible.indexOf(event.currentTarget);
  const delta = event.key === "ArrowRight" ? 1 : -1;
  const next = visible[(current + delta + visible.length) % visible.length];
  event.preventDefault();
  next.focus();
  selectIr(next.dataset.ir);
}

function renderCounts(result) {
  state.lastResult = result;
  const counts = result?.counts;
  dom.countsChart.replaceChildren();
  dom.topStates.replaceChildren();
  if (!counts || typeof counts !== "object" || !Object.keys(counts).length) {
    const empty = document.createElement("div");
    empty.className = "empty-chart";
    const zero = document.createElement("span");
    zero.textContent = "0";
    const line = document.createElement("i");
    const label = document.createElement("span");
    label.textContent = "SHOTS";
    empty.append(zero, line, label);
    dom.countsChart.append(empty);
    dom.countsChart.setAttribute("aria-label", t("countsEmpty"));
    dom.countsCaption.textContent = t("countsEmpty");
    const emptyState = document.createElement("li");
    emptyState.className = "top-states-empty";
    emptyState.textContent = t("topStatesEmpty");
    dom.topStates.append(emptyState);
    return;
  }
  const raw = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  let entries = raw;
  let aggregated = false;
  if (raw.length > 9) {
    const other = raw.slice(8).reduce((sum, item) => sum + item[1], 0);
    entries = raw.slice(0, 8).concat([[state.language === "zh" ? "其他" : "other", other]]);
    aggregated = true;
  }
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
  const max = Math.max(...entries.map((item) => item[1]), 1);
  const width = 420;
  const height = 142;
  const left = 54;
  const right = 45;
  const row = (height - 14) / entries.length;
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "img" });
  const title = svgElement("title");
  title.textContent = `${total} shots, ${raw.length} observed states`;
  svg.append(title);
  entries.forEach(([label, value], index) => {
    const y = 7 + index * row;
    const barHeight = Math.max(5, row - 4);
    const barWidth = ((width - left - right) * value) / max;
    const key = svgElement("text", { x: left - 7, y: y + barHeight - 1, "text-anchor": "end", fill: "#4e5a52", "font-size": "9", "font-family": "Cascadia Mono, Consolas, monospace" });
    key.textContent = label;
    const bar = svgElement("rect", { x: left, y, width: Math.max(1, barWidth), height: barHeight, fill: index === 0 ? "#16725a" : "#275f9c" });
    const amount = svgElement("text", { x: Math.min(width - 3, left + barWidth + 5), y: y + barHeight - 1, fill: "#34433a", "font-size": "8", "font-family": "Cascadia Mono, Consolas, monospace" });
    amount.textContent = String(value);
    svg.append(key, bar, amount);
  });
  dom.countsChart.append(svg);
  dom.countsChart.setAttribute("aria-label", `${total} shots across ${raw.length} observed states`);
  const backend = String(result.backend || "loomq-local-reference");
  const dialect = backend.startsWith("loomq_reference_statevector_")
    ? backend.slice("loomq_reference_statevector_".length)
    : "local";
  dom.countsCaption.textContent = `${t("localRefShort")} / ${dialect} dialect · ${total} shots${aggregated ? " · top 8 + other" : ""}`;
  renderTopStates(raw, total);
}

function renderTopStates(entries, total) {
  const maximum = Math.max(...entries.map((entry) => entry[1]), 1);
  entries.slice(0, 8).forEach(([key, count]) => {
    const item = document.createElement("li");
    const stateKey = document.createElement("span");
    stateKey.className = "top-state-key";
    stateKey.textContent = key;
    const track = document.createElement("span");
    track.className = "top-state-track";
    const fill = document.createElement("i");
    fill.className = "top-state-fill";
    fill.style.width = `${(count / maximum) * 100}%`;
    track.append(fill);
    const amount = document.createElement("span");
    amount.className = "top-state-count";
    amount.textContent = String(count);
    const rate = document.createElement("span");
    rate.className = "top-state-rate";
    rate.textContent = `${((count / total) * 100).toFixed(1)}%`;
    item.setAttribute("aria-label", `${key}: ${count} counts, ${rate.textContent}`);
    item.append(stateKey, track, amount, rate);
    dom.topStates.append(item);
  });
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function renderVerification(verification) {
  const checks = Array.isArray(verification.checks) ? verification.checks : [];
  dom.verificationStatus.textContent = String(verification.status || "—").toUpperCase();
  dom.verificationList.replaceChildren();
  if (!checks.length) {
    const item = document.createElement("li");
    const mark = document.createElement("i");
    mark.className = "check-mark pending";
    const text = document.createElement("span");
    text.textContent = t("verificationEmpty");
    item.append(mark, text);
    dom.verificationList.append(item);
    return;
  }
  checks.forEach((check) => {
    const item = document.createElement("li");
    const mark = document.createElement("i");
    mark.className = `check-mark ${check.passed ? "passed" : "failed"}`;
    const text = document.createElement("span");
    text.textContent = `${check.id}: ${check.detail}`;
    item.append(mark, text);
    dom.verificationList.append(item);
  });
}

function renderArtifacts(manifest, runId) {
  const artifacts = Array.isArray(manifest?.artifacts) ? manifest.artifacts : [];
  dom.artifactCount.textContent = `${String(artifacts.length).padStart(2, "0")} FILES`;
  dom.artifactList.replaceChildren();
  if (!artifacts.length) {
    const empty = document.createElement("p");
    empty.className = "empty-copy";
    empty.textContent = t("evidenceEmpty");
    dom.artifactList.append(empty);
    return;
  }
  artifacts.forEach((artifact) => {
    const row = document.createElement("div");
    row.className = "artifact-row";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = artifact.name;
    button.title = `Open ${artifact.name}`;
    button.addEventListener("click", () => {
      const query = new URLSearchParams({ run_id: runId, name: artifact.name });
      window.open(`/api/artifact?${query}`, "_blank", "noopener,noreferrer");
    });
    const hash = document.createElement("code");
    hash.textContent = String(artifact.sha256 || "").slice(0, 10);
    hash.title = artifact.sha256 || "";
    const bytes = document.createElement("span");
    bytes.textContent = formatBytes(artifact.bytes || 0);
    row.append(button, hash, bytes);
    dom.artifactList.append(row);
  });
}

function showDiagnostic(error) {
  state.lastError = error;
  dom.diagnostic.classList.remove("is-hidden");
  dom.diagnosticCode.textContent = error.code || "WORKFLOW_ERROR";
  const location = error.line ? `L${error.line}:${error.column || 1} · ` : "";
  dom.diagnosticMessage.textContent = location + (error.message || t("requestFailed"));
  dom.diagnosticSuggestion.textContent = error.suggestion || "";
  dom.focusError.classList.toggle("is-hidden", !error.line);
}

function clearDiagnostic() {
  dom.diagnostic.classList.add("is-hidden");
  dom.diagnosticCode.textContent = "";
  dom.diagnosticMessage.textContent = "";
  dom.diagnosticSuggestion.textContent = "";
}

function focusDiagnostic() {
  if (!state.lastError?.line) return;
  const lines = dom.qasm.value.split("\n");
  const lineIndex = Math.max(0, Math.min(lines.length - 1, Number(state.lastError.line) - 1));
  let offset = 0;
  for (let index = 0; index < lineIndex; index += 1) offset += lines[index].length + 1;
  offset += Math.max(0, Math.min(lines[lineIndex].length, Number(state.lastError.column || 1) - 1));
  dom.qasm.focus();
  dom.qasm.setSelectionRange(offset, Math.min(dom.qasm.value.length, offset + 1));
}

function editorKeydown(event) {
  if (event.key !== "Tab") return;
  event.preventDefault();
  const start = dom.qasm.selectionStart;
  const end = dom.qasm.selectionEnd;
  dom.qasm.setRangeText("  ", start, end, "end");
  updateEditorMetrics();
}

function updateEditorMetrics() {
  const lines = Math.max(1, dom.qasm.value.split("\n").length);
  dom.lineNumbers.textContent = Array.from({ length: lines }, (_, index) => index + 1).join("\n");
  const bytes = new TextEncoder().encode(dom.qasm.value).length;
  dom.sourceStats.textContent = `${lines} lines · ${bytes} bytes`;
}

function updatePromptCount() {
  dom.promptCount.textContent = `${dom.prompt.value.length} / 16000`;
}

function updateTaskMode() {
  const task = dom.task.value;
  setFileState(task === "hybrid" ? "stateHybrid" : task === "agent" ? "stateAgent" : "stateInput");
  dom.target.disabled = task === "hybrid";
  dom.shots.disabled = task === "hybrid" || task === "transpile";
}

function setFileState(key) {
  state.fileState = key;
  dom.fileState.textContent = t(key);
}

function setLanguage(language) {
  state.language = language;
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (copy[language][key]) element.textContent = copy[language][key];
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    const key = element.dataset.i18nPlaceholder;
    if (copy[language][key]) element.placeholder = copy[language][key];
  });
  dom.languageToggle.textContent = language === "zh" ? "EN" : "中文";
  dom.languageToggle.setAttribute("aria-pressed", String(language === "en"));
  if (state.health) renderHealth(state.health);
  setStatus(state.runStatus);
  setFileState(state.fileState);
  if (state.lastNormalized) renderNormalized(state.lastNormalized);
  if (state.lastResult) renderCounts(state.lastResult);
  renderExamples();
  renderHistory();
}

function t(key) {
  return copy[state.language][key] || copy.en[key] || key;
}

async function copyText(value) {
  if (!value) return;
  try {
    await navigator.clipboard.writeText(value);
  } catch (_) {
    const temporary = document.createElement("textarea");
    temporary.value = value;
    temporary.setAttribute("readonly", "");
    temporary.style.position = "fixed";
    temporary.style.opacity = "0";
    document.body.append(temporary);
    temporary.select();
    document.execCommand("copy");
    temporary.remove();
  }
  toast(t("copied"));
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.textContent = message;
  dom.toastRegion.append(node);
  window.setTimeout(() => node.remove(), 4200);
}

function safeMessage(error) {
  return String(error?.message || error || "Unknown error").slice(0, 1200);
}

function formatBytes(value) {
  if (value < 1024) return `${value}B`;
  return `${(value / 1024).toFixed(value < 10240 ? 1 : 0)}K`;
}
