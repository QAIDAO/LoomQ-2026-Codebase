import {
  ApiError,
  applyLlmConfig,
  generateExperiment,
  getLlmConfig,
  askQuestion,
  runExperiment,
  testLlmConfig,
} from "./api.js?v=qa-7";
import { escapeMarkup, renderCircuit } from "./circuit.js?v=qa-7";

function byId(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing required UI hook: #${id}`);
  return element;
}

const elements = {
  promptForm: byId("prompt-form"), prompt: byId("prompt"), promptError: byId("prompt-error"), promptStatus: byId("prompt-status"),
  generateButton: byId("generate-experiment"), generateLabel: byId("generate-label"),
  serviceNotice: byId("service-notice"),
  examples: byId("examples"), questions: byId("questions"), firstVisit: byId("first-visit"),
  qaCard: byId("qa-card"), qaMessages: byId("qa-messages"), qaEmpty: byId("qa-empty"),
  qaStatus: byId("qa-status"), qaContext: byId("qa-context"),
  workspace: byId("workspace"), workspaceStatus: byId("workspace-status"), workspaceTitle: byId("workspace-title"),
  backendMark: byId("backend-mark"), backendTitle: byId("backend-title"), backendReason: byId("backend-reason"),
  backendRecommendBadge: byId("backend-recommend-badge"), backendFacts: byId("backend-facts"),
  backendSummary: byId("backend-summary"), backendCapacity: byId("backend-capacity"),
  backendPicker: byId("backend-picker"), backendOptions: byId("backend-options"),
  tabs: [...document.querySelectorAll("[data-experiment-tab]")],
  circuitSvg: byId("circuit-svg"), stateOrder: byId("state-order"), circuitSteps: byId("circuit-steps"),
  gateQuickCard: byId("gate-quick-card"), gateQuickTitle: byId("gate-quick-title"),
  gateQuickTarget: byId("gate-quick-target"), gateQuickChange: byId("gate-quick-change"),
  gateQuickExample: byId("gate-quick-example"), gateQuickExampleText: byId("gate-quick-example-text"),
  gateQuickExperiment: byId("gate-quick-experiment"), gateQuickExperimentText: byId("gate-quick-experiment-text"),
  gatePalette: byId("gate-palette"), gateWhitelistTrigger: byId("gate-whitelist-trigger"),
  gateWhitelistPopover: byId("gate-whitelist-popover"),
  gateCard: byId("gate-card"), gateCardConcept: byId("gate-card-concept"), gateCardTechnical: byId("gate-card-technical"),
  gateCardRule: byId("gate-card-rule"), gateCardTransition: byId("gate-card-transition"), gateCardBefore: byId("gate-card-before"),
  gateCardAfter: byId("gate-card-after"), gateCardCurrent: byId("gate-card-current"), gateMath: byId("gate-math"), gateMathLabel: byId("gate-math-label"),
  gateCardMath: byId("gate-card-math"), gateBloch: byId("gate-bloch"), gateCardBloch: byId("gate-card-bloch"), gateCardClose: byId("gate-card-close"), qasmCode: byId("qasm-code"),
  shots: byId("shots"), runButton: byId("run-experiment"), runLabel: byId("run-label"), runStatus: byId("run-status"),
  results: byId("results"), resultsTitle: byId("results-title"), resultSource: byId("result-source"),
  resultBackend: byId("result-backend"), resultJobId: byId("result-job-id"), resultShots: byId("result-shots"), resultElapsed: byId("result-elapsed"),
  resultChart: byId("result-chart"), resultBars: byId("result-bars"), resultSummary: byId("result-summary"),
  resultChartTitle: byId("result-chart-title"),
  resultMeaning: byId("result-meaning"), resultWhy: byId("result-why"), resultNext: byId("result-next"), gateReferences: byId("gate-references"),
  resultBitOrder: byId("result-bit-order"), rawBitOrder: byId("raw-bit-order"), rawCounts: byId("raw-counts"),
  rawCountsDetails: byId("raw-counts-details"), chartShots: byId("chart-shots"), keyFormulas: byId("key-formulas"),
  circuitEmpty: byId("circuit-empty"), resultStatusText: byId("result-status-text"),
  apiStatusButton: byId("api-status-button"), apiStatusLabel: byId("api-status-label"), apiDialog: byId("api-dialog"),
  apiConfigForm: byId("api-config-form"), apiDialogClose: byId("api-dialog-close"), apiCancel: byId("api-cancel"),
  apiBaseUrl: byId("api-base-url"), apiKey: byId("api-key"), apiModel: byId("api-model"),
  apiTest: byId("api-test"), apiApply: byId("api-apply"), apiConfigMessage: byId("api-config-message"),
};

let generatedPrompt = null;
let generatedResponseType = null;
let activeExperiment = null;
let generationState = "idle";
let runState = "idle";
let pinnedOperationIndex = null;
let availableBackends = [];
let recommendedBackendId = null;
let selectedBackendId = null;
let backendRecommendationReason = "";
let llmStatus = "loading";
let apiTestPassed = false;
let apiPromptShown = false;
let questionState = "idle";
let questionHistory = [];
let latestRunResult = null;
let lastRunConversationNoticeKey = null;

setGenerationState("idle");
setQuestionState("idle");
initializeEmptyState();
initializeLlmConfig();

elements.apiStatusButton.addEventListener("click", openApiDialog);
elements.apiDialogClose.addEventListener("click", closeApiDialog);
elements.apiCancel.addEventListener("click", closeApiDialog);
elements.apiDialog.addEventListener("click", (event) => {
  if (event.target === elements.apiDialog) closeApiDialog();
});

[elements.apiBaseUrl, elements.apiKey, elements.apiModel].forEach((input) => {
  input.addEventListener("input", () => {
    apiTestPassed = false;
    elements.apiApply.disabled = true;
    setApiConfigMessage("配置已修改，请重新测试连接。", "idle");
  });
});

elements.apiTest.addEventListener("click", handleApiTest);
elements.apiConfigForm.addEventListener("submit", handleApiApply);

function setGateWhitelistOpen(open) {
  elements.gateWhitelistPopover.hidden = !open;
  elements.gateWhitelistTrigger.setAttribute("aria-expanded", String(open));
}

elements.gateWhitelistTrigger.addEventListener("click", () => {
  setGateWhitelistOpen(elements.gateWhitelistPopover.hidden);
});

document.addEventListener("click", (event) => {
  if (!elements.gateWhitelistPopover.hidden && !elements.gatePalette.contains(event.target)) {
    setGateWhitelistOpen(false);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.gateWhitelistPopover.hidden) {
    setGateWhitelistOpen(false);
    elements.gateWhitelistTrigger.focus();
  }
});

function readApiPreferences() {
  try {
    return {
      baseUrl: localStorage.getItem("loomq_llm_base_url") || "https://api.deepseek.com",
      model: localStorage.getItem("loomq_llm_model") || "deepseek-v4-flash",
    };
  } catch {
    return { baseUrl: "https://api.deepseek.com", model: "deepseek-v4-flash" };
  }
}

function saveApiPreferences(baseUrl, model) {
  try {
    localStorage.setItem("loomq_llm_base_url", baseUrl);
    localStorage.setItem("loomq_llm_model", model);
  } catch {
    // Non-sensitive preferences are optional; the API key is never persisted here.
  }
}

function setApiStatus(status, message = "") {
  llmStatus = status;
  elements.apiStatusButton.classList.remove("is-loading", "is-connected", "is-error");

  if (status === "connected") {
    elements.apiStatusButton.classList.add("is-connected");
    elements.apiStatusLabel.textContent = "API 已连接";
  } else if (status === "error" || status === "service-error") {
    elements.apiStatusButton.classList.add("is-error");
    elements.apiStatusLabel.textContent = "API 异常";
  } else if (status === "loading") {
    elements.apiStatusButton.classList.add("is-loading");
    elements.apiStatusLabel.textContent = "检查 API…";
  } else {
    elements.apiStatusLabel.textContent = "连接 API";
  }

  const serviceProblem = status === "service-error";
  elements.serviceNotice.hidden = !serviceProblem;
  elements.serviceNotice.textContent = serviceProblem ? message : "";
  elements.apiStatusButton.title = message;
  updateControlAvailability();
}

function setApiConfigMessage(message, state = "idle") {
  elements.apiConfigMessage.textContent = message;
  elements.apiConfigMessage.classList.toggle("is-success", state === "success");
  elements.apiConfigMessage.classList.toggle("is-error", state === "error");
  elements.apiConfigMessage.classList.toggle("is-testing", state === "testing");
}

async function initializeLlmConfig() {
  const preferences = readApiPreferences();
  elements.apiBaseUrl.value = preferences.baseUrl;
  elements.apiModel.value = preferences.model;

  if (window.location.protocol === "file:") {
    const message = "LoomQ Product Service 未连接。请通过 http://127.0.0.1:4173/ 打开 Playground。";
    setApiStatus("service-error", message);
    setApiConfigMessage(message, "error");
    return;
  }

  try {
    const config = await getLlmConfig();
    if (config.configured && config.connected) {
      elements.apiBaseUrl.value = config.base_url || preferences.baseUrl;
      elements.apiModel.value = config.model || preferences.model;
      setApiStatus("connected", "当前浏览器会话已连接 LLM API。");
    } else if (config.configured) {
      elements.apiBaseUrl.value = config.base_url || preferences.baseUrl;
      elements.apiModel.value = config.model || preferences.model;
      const message = "检测到 API 配置，但最近一次连接未通过，请重新测试连接。";
      setApiStatus("error", message);
      scheduleApiConnectionPrompt(message);
    } else {
      const message = "尚未接入 API。请填写 API Key，测试连接后再开始生成实验或提问。";
      setApiStatus("unconfigured", message);
      scheduleApiConnectionPrompt(message);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "LoomQ Product Service 未连接。";
    setApiStatus("service-error", message);
    setApiConfigMessage(message, "error");
  }
}

function scheduleApiConnectionPrompt(message) {
  if (apiPromptShown || elements.apiDialog.open || !["unconfigured", "error"].includes(llmStatus)) return;
  apiPromptShown = true;
  window.setTimeout(() => {
    if (!elements.apiDialog.open && ["unconfigured", "error"].includes(llmStatus)) openApiDialog(message);
  }, 180);
}

function openApiDialog(message = "") {
  apiTestPassed = false;
  elements.apiApply.disabled = true;
  elements.apiKey.value = "";
  if (llmStatus === "connected") {
    setApiConfigMessage("当前会话已连接。若要更换 API，请填写新 Key 并重新测试。", "success");
  } else if (llmStatus === "service-error") {
    setApiConfigMessage("LoomQ Product Service 未连接。请通过 http://127.0.0.1:4173/ 打开 Playground。", "error");
  } else if (message) {
    setApiConfigMessage(message, "error");
  } else {
    setApiConfigMessage("填写后先测试连接，再应用到当前会话。", "idle");
  }
  elements.apiDialog.showModal();
}

function closeApiDialog() {
  elements.apiKey.value = "";
  if (elements.apiDialog.open) elements.apiDialog.close();
}

function currentApiFormConfig() {
  return {
    base_url: elements.apiBaseUrl.value.trim(),
    api_key: elements.apiKey.value,
    model: elements.apiModel.value.trim(),
  };
}

async function handleApiTest() {
  if (!elements.apiConfigForm.reportValidity()) return;
  const config = currentApiFormConfig();
  apiTestPassed = false;
  elements.apiApply.disabled = true;
  elements.apiTest.disabled = true;
  setApiConfigMessage("正在进行一次真实的最小调用…", "testing");

  try {
    const result = await testLlmConfig(config);
    apiTestPassed = Boolean(result.connected);
    elements.apiApply.disabled = !apiTestPassed;
    saveApiPreferences(config.base_url, config.model);
    setApiConfigMessage(result.message || "连接测试成功，可以应用此配置。", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "连接测试失败。";
    setApiConfigMessage(message, "error");
    if (error instanceof ApiError && error.code === "product_service_unavailable") {
      setApiStatus("service-error", message);
    } else {
      setApiStatus("error", message);
    }
  } finally {
    elements.apiTest.disabled = false;
  }
}

async function handleApiApply(event) {
  event.preventDefault();
  if (!apiTestPassed) {
    setApiConfigMessage("请先测试连接。", "error");
    return;
  }

  elements.apiApply.disabled = true;
  try {
    const config = await applyLlmConfig();
    saveApiPreferences(config.base_url, config.model);
    setApiStatus("connected", "当前浏览器会话已连接 LLM API。");
    closeApiDialog();
  } catch (error) {
    const message = error instanceof Error ? error.message : "应用 API 配置失败。";
    setApiConfigMessage(message, "error");
    setApiStatus(error instanceof ApiError && error.code === "product_service_unavailable" ? "service-error" : "error", message);
  } finally {
    elements.apiApply.disabled = !apiTestPassed;
  }
}

function initializeEmptyState() {
  elements.workspace.classList.add("is-empty");
  elements.results.classList.add("is-empty");
  elements.resultBars.classList.remove("is-dense");
  elements.resultChartTitle.textContent = "测量结果";
  elements.resultBars.innerHTML = '<p class="chart-empty">暂无测量数据</p>';
}

function fillPromptFromTrigger(trigger) {
  elements.prompt.value = trigger.dataset.prompt;
  elements.promptError.hidden = true;
  updateDirtyState();
  elements.prompt.focus();
}

elements.examples.addEventListener("click", (event) => {
  const card = event.target.closest("[data-example]");
  if (!card) return;
  fillPromptFromTrigger(card);
});

elements.questions.addEventListener("click", (event) => {
  const card = event.target.closest("[data-question]");
  if (!card) return;
  elements.prompt.value = card.dataset.prompt;
  elements.promptError.hidden = true;
  elements.prompt.focus();
});

elements.firstVisit.addEventListener("click", () => fillPromptFromTrigger(elements.firstVisit));

elements.prompt.addEventListener("input", updateDirtyState);

elements.promptForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = elements.prompt.value.trim();

  if (!prompt) {
    elements.promptError.hidden = false;
    elements.prompt.focus();
    return;
  }

  elements.promptError.hidden = true;
  if (classifyPrompt(prompt) === "question") {
    await handleQuestionAsk();
    return;
  }

  await handleExperimentGeneration(prompt);
});

function classifyPrompt(prompt) {
  const text = String(prompt).trim().toLowerCase();
  const generationLead = /^(请)?(生成|创建|构建|设计|演示|模拟|搭建|做一个|运行一个)/;
  // The three L2 task families must reach /api/generate before the generic
  // tutor heuristics below. Repair prompts often contain "代码"/"QASM", and
  // backend prompts often end with a question mark; both are still tasks,
  // not explanatory questions.
  const repairIntent = /(修复|修好|纠错|改正|修正|报错|错误|repair|fix|correct|invalid|malformed)/i;
  const circuitContext = /(qasm|openqasm|qreg|creg|cx|cnot|ccx|量子门|电路|代码)/i;
  const backendIntent = /(推荐|选择|选哪个|选什么|用哪个|适合|可用|recommend|select|choose)/i;
  const backendContext = /(后端|平台|真机|模拟器|backend(?:_id)?|排队|队列|等待|比特|qubit)/i;
  const questionSignals = [
    /[?？]/,
    /^(什么|啥|为何|为什么|如何|怎么|能否|是否|请解释|解释|说明|介绍|讲讲|告诉我)/,
    /(什么是|啥是|什么叫|啥叫|为什么|怎么回事|怎么.*发生|发生了什么|含义|意义|数学逻辑|原理|区别|解释|看不懂|不懂|代码|qasm)/,
  ];
  if (repairIntent.test(text) && circuitContext.test(text)) return "experiment";
  if (backendIntent.test(text) && backendContext.test(text)) return "experiment";
  if (generationLead.test(text)) return "experiment";
  return questionSignals.some((signal) => signal.test(text)) ? "question" : "experiment";
}

async function handleExperimentGeneration(prompt) {
  if (llmStatus !== "connected") {
    const message = llmStatus === "service-error"
      ? "LoomQ Product Service 未连接，请先启动服务。"
      : "请先接入 API：填写 API Key 并测试连接后再生成实验。";
    setApiStatus(llmStatus === "service-error" ? "service-error" : "unconfigured", message);
    openApiDialog(message);
    return;
  }
  setGenerationState("generating");
  clearRunResult();

  try {
    const generated = await generateExperiment(prompt);
    if (generated.response_type === "backend_recommendation") {
      generatedPrompt = prompt;
      generatedResponseType = "backend_recommendation";
      renderBackendChooser(generated.backends || [], generated.backend_recommendation || {});
      elements.workspace.hidden = false;
      setGenerationState("backend-ready", generated.message);
      setRunState(activeExperiment ? "ready" : "idle");
      appendConversationNotice(buildBackendTutorMessage(prompt, generated), "notice");
      elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    const experiment = generated.experiment;
    activeExperiment = experiment;
    generatedPrompt = prompt;
    generatedResponseType = "experiment";
    renderExperiment(experiment);
    elements.workspace.hidden = false;
    selectTab("circuit-tab");
    setGenerationState("ready");
    setRunState("ready");
    appendConversationNotice(buildExperimentTutorMessage(experiment, prompt), "notice");
    elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "生成实验失败，请稍后重试。";
    setGenerationState("error", message);
    if (error instanceof ApiError) {
      if (error.code === "product_service_unavailable") setApiStatus("service-error", message);
      else if (error.code === "llm_not_configured") setApiStatus("unconfigured", message);
      else if (["invalid_api_key", "model_unavailable", "rate_limited", "llm_timeout", "base_url_unreachable", "llm_call_failed"].includes(error.code)) setApiStatus("error", message);
    }
  }
}

async function handleQuestionAsk() {
  const question = elements.prompt.value.trim();
  if (!question) {
    setQuestionState("error", "先输入一个问题，例如“什么是量子纠缠？”");
    elements.prompt.focus();
    return;
  }

  if (llmStatus !== "connected") {
    const message = "请先点击右上角「连接 API」，问答需要使用你自己的 LLM。";
    setQuestionState("error", message);
    setApiStatus(llmStatus === "service-error" ? "service-error" : "unconfigured", message);
    openApiDialog(message);
    return;
  }

  setGenerationState("generating");
  const history = questionHistory.slice(-8);
  appendQuestionMessage("user", question);
  const pending = appendQuestionMessage("assistant", "正在结合当前实验整理答案…", "pending");
  setQuestionState("asking", "正在回答…");
  elements.qaCard.scrollIntoView({ behavior: "smooth", block: "nearest" });

  try {
    const result = await askQuestion(question, buildQuestionContext(), history);
    pending.remove();
    appendQuestionMessage("assistant", result.answer);
    elements.prompt.value = "";
    setGenerationState(activeExperiment ? "ready" : "idle");
    questionHistory = [...history, { role: "user", content: question }, { role: "assistant", content: result.answer }].slice(-8);
    setQuestionState("success", "回答完成；继续输入下一个问题或实验描述，系统会自动判断。" );
  } catch (error) {
    pending.remove();
    const message = error instanceof Error ? error.message : "问答失败，请稍后重试。";
    appendQuestionMessage("assistant", message, "error");
    setGenerationState(activeExperiment ? "ready" : "idle");
    setQuestionState("error", message);
    if (error instanceof ApiError) {
      if (error.code === "product_service_unavailable") setApiStatus("service-error", message);
      else if (error.code === "llm_not_configured") setApiStatus("unconfigured", message);
      else if (["invalid_api_key", "model_unavailable", "rate_limited", "llm_timeout", "base_url_unreachable", "llm_call_failed", "invalid_llm_response"].includes(error.code)) setApiStatus("error", message);
    }
  }
}

function appendQuestionMessage(role, content, state = "") {
  elements.qaEmpty.hidden = true;
  const message = document.createElement("article");
  message.className = `qa-message ${role}${state ? ` ${state}` : ""}`;
  const label = document.createElement("span");
  label.className = "qa-message-label";
  label.textContent = role === "user" ? "你" : "LoomQ 量子导师";
  const body = document.createElement("div");
  body.className = "qa-message-body";
  if (role === "assistant" && state !== "pending") {
    body.innerHTML = renderTutorAnswer(content);
  } else {
    body.textContent = content;
  }
  message.append(label, body);
  elements.qaMessages.append(message);
  elements.qaMessages.scrollTop = elements.qaMessages.scrollHeight;
  return message;
}

function appendConversationNotice(content, state = "notice") {
  const message = appendQuestionMessage("assistant", content, state);
  elements.qaCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
  return message;
}

function buildExperimentTutorMessage(experiment, prompt = "") {
  if (isRepairPrompt(prompt)) return buildRepairTutorMessage(experiment, prompt);

  const circuit = experiment?.circuit || {};
  const operations = Array.isArray(circuit.operations) ? circuit.operations : [];
  const steps = Array.isArray(experiment?.steps) ? experiment.steps : [];
  const kind = experiment?.kind || "generic";
  const kindLabels = {
    coin: "量子硬币",
    bell: "Bell 纠缠态",
    ghz: "GHZ 多比特纠缠态",
    phase_interference: "相位干涉实验",
    qft: "量子傅里叶变换",
    generic: "量子电路实验",
  };
  const operationSummary = operations.map((operation) => {
    if (operation.type === "measure") return `Measure q${operation.qubit}→c${operation.cbit}`;
    const gate = String(operation.gate || operation.title || "门").toUpperCase();
    const parameter = operation.parameter ? `(${operation.parameter})` : "";
    return `${gate}${parameter} ${Array.isArray(operation.qubits) ? operation.qubits.map((qubit) => `q${qubit}`).join(",") : ""}`.trim();
  }).join(" → ");
  const stepLines = steps.slice(0, 8).map((step, index) => {
    const number = step.index ?? index + 1;
    const title = step.purpose || step.title || "电路步骤";
    const detail = step.explanation || step.simple_change || step.change || "这一步改变了后续测量所看到的状态。";
    return `- 第 ${number} 步：${title}。${detail}`;
  }).join("\n");
  const measurementStep = steps.find((step) => step.measurement_analysis);
  const predictedCounts = measurementStep?.measurement_analysis?.predicted_counts || [];
  const predictedLine = predictedCounts.length
    ? `在理想 statevector 下，测量前可预期的结果约为：${predictedCounts.map((item) => `${item.result} ${item.percent}`).join("、")}。`
    : "运行后以真实 counts 为准；有限 shots 得到的是概率分布的统计估计。";
  const resultExplanation = experiment?.result_explanation || {};
  const kindExplanation = {
    coin: "H 门先让 q0 同时保留 0 和 1 两种可能，Measure 再把每次运行读成一个经典结果；理想情况下，0 和 1 会接近各占一半。",
    bell: "H 门先把 q0 变成叠加，CX 再让 q1 按 q0 的值条件翻转，因此两个比特会形成 00/11 的成组关联，而不是两个独立的随机比特。",
    ghz: "H 门先在一个比特上准备叠加，连续 CX 把这两条可能传播到其他比特；理想结果应主要集中在全 0 和全 1 两种比特串。",
    phase_interference: "相位门改变不同路径之间的相对相位，后续 H 等门把原本看不见的相位差转成概率差；因此要比较柱子的分布，而不只是看单个结果。",
    qft: "电路用受控相位和 H 等门重新组合各条计算路径，把输入信息的相位结构转换成可测的概率分布。",
    generic: "电路中的量子门按顺序改变量子态，最后由 Measure 把量子态转换成可以统计的经典比特。",
  }[kind] || "电路中的量子门按顺序改变量子态，最后由 Measure 把量子态转换成可以统计的经典比特。";

  return [
    "### 我已经把这个实验拆开说明",
    `你的任务是：${prompt || experiment?.prompt || "观察一个量子电路的测量结果"}。这是一个 **${kindLabels[kind] || kindLabels.generic}**，使用 ${circuit.num_qubits ?? "—"} 个量子比特和 ${circuit.num_clbits ?? "—"} 个经典比特。`,
    "",
    "### 实验里发生了什么",
    kindExplanation,
    `电路顺序：\`${operationSummary || "等待电路步骤"}\`。`,
    "",
    "### 每一步为什么存在",
    stepLines || "电路步骤已经写入右侧 Circuit 面板；点击具体量子门可以查看前后状态、数学规则和直观解释。",
    "",
    "### 运行后应该看什么",
    predictedLine,
    resultExplanation.meaning || "柱子表示不同测量结果在重复运行中出现的频率。",
    "点击下方 Run Experiment 后，我会把真实 counts、运行后端和测量分布再解释一遍；你也可以继续问我“这个实验里发生了什么”或“为什么会得到这个结果”。",
  ].join("\n");
}

function isRepairPrompt(prompt) {
  return /(修复|修好|纠错|改正|修正|报错|错误|repair|fix|correct|invalid|malformed)/i.test(String(prompt || ""));
}

function extractPromptCode(prompt) {
  const source = String(prompt || "");
  const fenced = source.match(/```(?:qasm|openqasm)?\s*([\s\S]*?)```/i);
  if (fenced?.[1]?.trim()) return fenced[1].trim();
  const marker = source.lastIndexOf("：");
  if (marker >= 0 && source.slice(marker + 1).match(/(qreg|creg|q\[|OPENQASM|CX|H\s)/i)) {
    return source.slice(marker + 1).trim();
  }
  return "";
}

function buildRepairTutorMessage(experiment, prompt) {
  const original = extractPromptCode(prompt);
  const corrected = experiment?.qasm || "";
  const issues = [];
  if (/\b(H|CX|X|Measure|CNOT)\b/.test(original)) {
    issues.push("门名统一为 OpenQASM 2.0 语法要求的小写形式，例如 `h`、`cx` 和 `measure`。");
  }
  if (/CX\s+q\[\d+\]\s+q\[\d+\]/i.test(original)) {
    issues.push("CX 的两个量子比特参数需要用逗号分隔，例如 `cx q[0],q[1];`。");
  }
  if (original && /(?:H|CX|X|Measure|CNOT)[^;\n]*(?:\n|$)/i.test(original) && !/;\s*(?:$|\n)/.test(original)) {
    issues.push("门操作需要以分号结束，避免解析器把下一行继续拼进同一条指令。");
  }
  if (!issues.length) {
    issues.push("我把原始输入重新交给统一 OpenQASM parser/IR 校验，修正了寄存器、门参数或测量语句的格式问题。");
  }
  const circuit = experiment?.circuit || {};
  const operationCount = Array.isArray(circuit.operations) ? circuit.operations.length : 0;
  return [
    "### QASM 修复结果",
    "这次输入属于代码纠错任务，我不会把它当成普通的量子概念介绍。",
    `已生成一份可继续运行的 OpenQASM 2.0 电路：${circuit.num_qubits ?? "—"} 个量子比特、${circuit.num_clbits ?? "—"} 个经典比特、${operationCount} 个操作。`,
    "",
    "### 检测并修正了什么",
    issues.map((issue) => `- ${issue}`).join("\n"),
    "",
    "### 修复后的代码",
    "```qasm",
    corrected || "（没有收到可显示的 QASM）",
    "```",
    "",
    "### 校验状态",
    "这份代码已经通过当前统一入口的 OpenQASM parser/IR 结构校验，并且包含测量语句，可以进入后续运行流程。Fidelity 是否达到题目阈值，还需要运行正式评测或点击 Run Experiment 后结合结果确认。",
    "",
    "### 下一步",
    "先检查右侧 QASM，再点击 Run Experiment；如果评测仍失败，把报错或 Fidelity 数值继续发给我，我会针对失败位置做第二轮修复。",
  ].join("\n");
}

function buildBackendTutorMessage(prompt, generated) {
  const recommendation = generated?.backend_recommendation || {};
  const backends = Array.isArray(generated?.backends) ? generated.backends : [];
  const selected = backends.find((backend) => backend.id === recommendation.backend_id);
  const requirements = Object.entries(recommendation.requirements || {})
    .filter(([, value]) => value !== null && value !== undefined && value !== false && value !== "")
    .map(([key, value]) => `${key}=${value}`)
    .join("、");
  const backendLabel = selected?.name || recommendation.backend_id || "当前没有完全匹配的后端";
  const backendDetails = selected
    ? `${selected.kind_label}，最大 ${selected.max_qubits} 个量子比特，${selected.queue_label}，${selected.cost_label}。`
    : "请查看下方能力表并手动选择一个满足约束的后端。";
  const optionLines = backends.slice(0, 6).map((backend) => (
    `- ${backend.name}（${backend.id}）：${backend.kind_label}，最大 ${backend.max_qubits} 比特，${backend.queue_label}。`
  )).join("\n");
  return [
    "### 后端推荐的具体结论",
    `你的任务是：${prompt || "为当前电路选择合适的后端"}。我根据比特数、是否真机、排队和费用约束检查了能力表。`,
    recommendation.backend_id
      ? `推荐 **${backendLabel}**（规范 backend_id：\`${recommendation.backend_id}\`）。${backendDetails}`
      : "当前没有后端能同时满足全部条件，因此没有伪造一个“完全满足”的答案。",
    `推荐理由：${recommendation.reason || "按当前电路容量和运行约束选择。"}`,
    requirements ? `已识别的约束：${requirements}。` : "未识别到额外约束，默认优先选择无需排队的可用模拟器。",
    "",
    "### 可以怎样操作",
    "你可以在下方展开后端列表核对能力；确认后点击同一个 Run Experiment。若远端凭证没有配置，系统会按架构约定回退到已就绪的本地模拟器，并在结果中明确标记。",
    optionLines ? `\n### 能力表摘要\n${optionLines}` : "",
  ].join("\n");
}

function renderTutorAnswer(content) {
  const lines = String(content ?? "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let codeLines = [];
  let inCode = false;

  const flushCode = () => {
    if (!inCode) return;
    html.push(`<pre class="qa-code"><code>${escapeMarkup(codeLines.join("\n"))}</code></pre>`);
    codeLines = [];
    inCode = false;
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (/^```/.test(trimmed)) {
      if (inCode) flushCode();
      else inCode = true;
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    if (!trimmed) continue;

    const safeLine = renderTutorInline(escapeMarkup(line));
    if (/^#{1,3}\s+/.test(trimmed)) {
      const heading = renderTutorInline(escapeMarkup(trimmed.replace(/^#{1,3}\s+/, "")));
      html.push(`<h4>${heading}</h4>`);
    } else if (/^---+\s*$/.test(trimmed)) {
      html.push("<hr>");
    } else if (/^[-*]\s+/.test(trimmed)) {
      const bullet = renderTutorInline(escapeMarkup(trimmed.replace(/^[-*]\s+/, "")));
      html.push(`<div class="qa-bullet"><span aria-hidden="true">•</span><span>${bullet}</span></div>`);
    } else if (/^\d+\.\s+/.test(trimmed)) {
      const number = trimmed.match(/^(\d+)\.\s+/)[1];
      const item = renderTutorInline(escapeMarkup(trimmed.replace(/^\d+\.\s+/, "")));
      html.push(`<div class="qa-numbered"><span aria-hidden="true">${number}.</span><span>${item}</span></div>`);
    } else {
      html.push(`<p>${safeLine}</p>`);
    }
  }
  flushCode();
  return html.join("");
}

function renderTutorInline(value) {
  return value
    .replace(/\\\\(?=[A-Za-z])/g, "\\")
    .replace(/\\\((.*?)\\\)/g, "$1")
    .replace(/\\\[(.*?)\\\]/g, "$1")
    .replace(/\\text\{([^{}]+)\}/g, "$1")
    .replace(/\\ket\{([^{}]+)\}/g, "|$1⟩")
    .replace(/\\sqrt\{([^{}]+)\}/g, "√($1)")
    .replace(/\\frac\{1\}\{√\(2\)\}/g, "1/√2")
    .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1)/($2)")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>");
}

function buildQuestionContext() {
  const experiment = activeExperiment
    ? {
      title: activeExperiment.title,
      kind: activeExperiment.kind,
      prompt: activeExperiment.prompt,
      qasm: activeExperiment.qasm,
      circuit: {
        num_qubits: activeExperiment.circuit?.num_qubits,
        num_clbits: activeExperiment.circuit?.num_clbits,
        operations: (activeExperiment.circuit?.operations || []).map((operation) => ({
          index: operation.index,
          type: operation.type,
          gate: operation.gate,
          qubits: operation.qubits,
          params: operation.params,
        })),
      },
      steps: (activeExperiment.steps || []).map((step) => ({
        index: step.index,
        title: step.title,
        purpose: step.purpose,
        explanation: step.explanation,
        simple_change: step.simple_change,
        math_note: step.math_detail?.note,
        before_state: step.math_detail?.before_state,
        after_state: step.math_detail?.after_state,
      })),
      result_explanation: activeExperiment.result_explanation,
    }
    : null;
  const run = latestRunResult
    ? {
      backend_name: latestRunResult.backend_name,
      shots: latestRunResult.shots,
      counts: latestRunResult.counts,
      elapsed_seconds: latestRunResult.elapsed_seconds,
    }
    : null;
  elements.qaContext.textContent = experiment
    ? (run ? "会参考当前实验和最新测量结果" : "会参考当前实验与电路步骤")
    : "先生成实验，回答会更具体";
  return { experiment, run };
}

elements.tabs.forEach((tab) => {
  tab.addEventListener("click", () => selectTab(tab.id));
});

elements.backendOptions.addEventListener("change", (event) => {
  const radio = event.target.closest("[data-backend-option]");
  if (!radio || radio.value === selectedBackendId) return;
  selectedBackendId = radio.value;
  renderSelectedBackend();
  clearRunResult();
  setRunState("ready");
});

elements.circuitSvg.addEventListener("pointerover", (event) => {
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement) return;
  const operationIndex = Number(operationElement.dataset.operationIndex);
  if (operationIndex === pinnedOperationIndex) {
    hideQuickGateCard();
    return;
  }
  showQuickGateCard(operationIndex);
});

elements.circuitSvg.addEventListener("pointerout", (event) => {
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement || operationElement.contains(event.relatedTarget)) return;
  hideQuickGateCard();
});

elements.circuitSvg.addEventListener("focusin", (event) => {
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement) return;
  const operationIndex = Number(operationElement.dataset.operationIndex);
  if (operationIndex === pinnedOperationIndex) {
    hideQuickGateCard();
    return;
  }
  showQuickGateCard(operationIndex);
});

elements.circuitSvg.addEventListener("focusout", (event) => {
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement || operationElement.contains(event.relatedTarget)) return;
  hideQuickGateCard();
});

elements.circuitSvg.addEventListener("click", (event) => {
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement) return;
  toggleGateCard(Number(operationElement.dataset.operationIndex));
});

elements.circuitSvg.addEventListener("keydown", (event) => {
  if (!['Enter', ' '].includes(event.key)) return;
  const operationElement = event.target.closest("[data-operation-index]");
  if (!operationElement) return;
  event.preventDefault();
  toggleGateCard(Number(operationElement.dataset.operationIndex));
});

elements.gateCardClose.addEventListener("click", () => {
  pinnedOperationIndex = null;
  hideGateCard();
  hideQuickGateCard();
});

elements.gateReferences.addEventListener("click", (event) => {
  const button = event.target.closest("[data-gate-ref]");
  if (!button) return;
  focusOperation(Number(button.dataset.gateRef));
});

elements.shots.addEventListener("change", normalizeShots);
elements.shots.addEventListener("blur", normalizeShots);

elements.runButton.addEventListener("click", async () => {
  if (!activeExperiment || !["ready", "backend-ready"].includes(generationState) || runState === "running") return;

  const shots = normalizeShots();
  setRunState("running");

  try {
    const result = await runExperiment(activeExperiment.qasm, shots, selectedBackendId);
    renderRunResult(activeExperiment, result);
    setRunState("success");
    elements.results.hidden = false;
    elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setRunState("error", error instanceof Error ? error.message : "实验运行失败，请稍后重试。");
  }
});

function selectTab(tabId) {
  elements.tabs.forEach((tab) => {
    const selected = tab.id === tabId;
    tab.setAttribute("aria-selected", String(selected));
    byId(tab.dataset.panelId).hidden = !selected;
  });
}

function normalizeShots() {
  if (selectedBackendId === "spinq_cloud_qpu") {
    elements.shots.value = "1000";
    return 1000;
  }
  const parsed = Number.parseInt(elements.shots.value, 10);
  const safeValue = Number.isFinite(parsed) ? parsed : 1000;
  const clamped = Math.min(8192, Math.max(100, safeValue));
  elements.shots.value = String(clamped);
  return clamped;
}

function updateDirtyState() {
  if (generationState === "generating") return;
  const prompt = elements.prompt.value.trim();

  if (!prompt && !activeExperiment) {
    setGenerationState("idle");
  } else if (prompt === generatedPrompt && generatedResponseType === "backend_recommendation") {
    setGenerationState("backend-ready", "已完成后端推荐，本次未生成新电路。");
  } else if (activeExperiment && prompt === generatedPrompt) {
    setGenerationState("ready");
  } else {
    setGenerationState("dirty");
  }
}

function setGenerationState(state, message = "") {
  generationState = state;
  elements.promptForm.dataset.state = state;
  elements.promptStatus.classList.remove("is-generating", "is-error");
  elements.workspace.classList.remove("is-stale", "is-generating");
  const generating = state === "generating";
  elements.generateLabel.textContent = generating ? "处理中…" : "发送";

  if (state === "idle") {
    elements.promptStatus.hidden = true;
  } else if (state === "dirty") {
    elements.promptStatus.hidden = false;
    elements.promptStatus.textContent = activeExperiment
      ? "内容已修改，点击「发送」；系统会自动生成实验或解释问题"
      : "内容已准备好，点击「发送」让系统自动判断下一步";
    if (activeExperiment) {
      elements.workspace.classList.add("is-stale");
      elements.workspaceStatus.textContent = "上一版已生成方案";
    }
  } else if (state === "generating") {
    elements.promptStatus.hidden = false;
    elements.promptStatus.classList.add("is-generating");
    elements.promptStatus.textContent = "正在判断意图并处理你的输入…";
    if (activeExperiment) {
      elements.workspace.classList.add("is-generating");
      elements.workspaceStatus.textContent = "正在生成新方案…";
    }
  } else if (state === "ready") {
    elements.promptStatus.hidden = true;
    elements.workspaceStatus.textContent = "真实 L2 方案";
  } else if (state === "backend-ready") {
    elements.promptStatus.hidden = false;
    elements.promptStatus.textContent = message || "已完成后端推荐，本次未生成新电路。";
    elements.workspaceStatus.textContent = activeExperiment ? "上一轮电路 · 本次仅推荐后端" : "本次仅推荐后端";
  } else if (state === "error") {
    elements.promptStatus.hidden = false;
    elements.promptStatus.classList.add("is-error");
    elements.promptStatus.textContent = message;
    if (activeExperiment) {
      elements.workspace.classList.add("is-stale");
      elements.workspaceStatus.textContent = "上一版已生成方案";
    }
  }

  updateControlAvailability();
}

function setQuestionState(state, message = "") {
  questionState = state;
  elements.qaCard.dataset.state = state;
  elements.qaStatus.classList.remove("is-success", "is-error", "is-asking");
  elements.qaStatus.hidden = !message;
  elements.qaStatus.textContent = message;
  if (state === "success") elements.qaStatus.classList.add("is-success");
  if (state === "error") elements.qaStatus.classList.add("is-error");
  if (state === "asking") elements.qaStatus.classList.add("is-asking");
  updateControlAvailability();
}

function setRunState(state, message = "") {
  runState = state;
  elements.workspace.dataset.runState = state;
  elements.runStatus.classList.remove("is-running", "is-error", "is-success");
  elements.runLabel.textContent = state === "running" ? "Running…" : "Run Experiment";
  const selectedBackend = getSelectedBackend();
  const backendName = selectedBackend?.name || "所选后端";
  const runtimeUnavailable = selectedBackend?.runtime_available === false;

  if (state === "idle") {
    elements.runStatus.textContent = "生成实验后即可在所选本地或云端后端运行。";
  } else if (state === "ready") {
    if (runtimeUnavailable) {
      if (selectedBackend.run_mode === "remote") {
        elements.runStatus.textContent = `${selectedBackend.runtime_message || "真机环境未配置。"} 将自动尝试回退到已就绪的本地模拟器。`;
      } else {
        elements.runStatus.classList.add("is-error");
        elements.runStatus.textContent = selectedBackend.runtime_message || "能力支持，但当前 Python 环境缺少运行依赖。";
      }
    } else {
      elements.runStatus.textContent = `QASM 已就绪，可在 ${backendName} 上运行。`;
    }
  } else if (state === "running") {
    elements.runStatus.classList.add("is-running");
    elements.runStatus.textContent = `正在 ${backendName} 上运行…`;
  } else if (state === "success") {
    elements.runStatus.classList.add("is-success");
    elements.runStatus.textContent = "实验运行完成。";
  } else if (state === "error") {
    elements.runStatus.classList.add("is-error");
    elements.runStatus.textContent = message;
  }

  updateControlAvailability();
}

function updateControlAvailability() {
  const locked = generationState === "generating" || runState === "running" || questionState === "asking";
  const apiReady = llmStatus === "connected";
  const apiPending = llmStatus === "loading";
  elements.generateButton.disabled = locked || apiPending;
  elements.generateButton.title = apiReady ? "" : "请先通过右上角连接自己的 LLM API";
  elements.prompt.readOnly = locked;
  elements.examples.querySelectorAll("[data-example]").forEach((button) => { button.disabled = locked; });
  elements.questions.querySelectorAll("[data-question]").forEach((button) => { button.disabled = locked; });
  elements.firstVisit.disabled = locked;
  elements.shots.disabled = runState === "running";
  elements.backendOptions.querySelectorAll("[data-backend-option]").forEach((input) => { input.disabled = locked; });
  const selectedBackend = getSelectedBackend();
  const backendRuntimeReady = selectedBackend?.runtime_available !== false || selectedBackend?.run_mode === "remote";
  elements.runButton.disabled = !["ready", "backend-ready"].includes(generationState) || !activeExperiment || !selectedBackendId || !backendRuntimeReady || runState === "running";
}

function clearRunResult() {
  latestRunResult = null;
  lastRunConversationNoticeKey = null;
  elements.results.hidden = false;
  elements.results.classList.add("is-empty");
  elements.resultsTitle.textContent = "等待运行结果";
  elements.resultStatusText.textContent = "尚未运行实验";
  elements.resultBackend.textContent = "—";
  elements.resultJobId.textContent = "—";
  elements.resultShots.textContent = "—";
  elements.resultElapsed.textContent = "—";
  elements.resultBars.classList.remove("is-dense");
  elements.resultChartTitle.textContent = "测量结果";
  elements.resultBars.innerHTML = '<p class="chart-empty">暂无测量数据</p>';
  elements.rawCounts.textContent = "";
  elements.resultSummary.textContent = "运行后会根据真实 counts 总结测量现象。";
  elements.resultSource.textContent = "生成电路并运行后，结果会显示在这里。";
  elements.resultMeaning.textContent = "这里会把结果与当前电路联系起来。";
  elements.resultWhy.textContent = "";
  elements.resultNext.textContent = "运行后会给出更具体的比较方法。";
  elements.gateReferences.replaceChildren();
  elements.rawCountsDetails.open = false;
  setRunState("idle");
}

function renderRunResult(experiment, result) {
  const observedEntries = Object.entries(result.counts)
    .filter(([, count]) => Number.isFinite(Number(count)))
    .map(([state, count]) => [state, Number(count)])
    .sort(([left], [right]) => left.localeCompare(right));

  if (!observedEntries.length) throw new Error("运行结果中没有有效 counts。");

  latestRunResult = result;

  const countsByState = new Map(observedEntries);
  const displayOrder = experiment.circuit.num_clbits === 2
    ? ["00", "11", "01", "10"]
    : observedEntries.map(([state]) => state);
  const hasHighCardinality = observedEntries.length > 16;
  const weightGroups = hasHighCardinality
    ? observedEntries.reduce((groups, [state, count]) => {
      const ones = [...state].filter((bit) => bit === "1").length;
      groups.set(ones, (groups.get(ones) || 0) + count);
      return groups;
    }, new Map())
    : null;
  const entries = hasHighCardinality
    ? Array.from({ length: experiment.circuit.num_clbits + 1 }, (_, ones) => [ones, weightGroups.get(ones) || 0])
    : displayOrder.map((state) => [state, countsByState.get(state) || 0]);
  const shots = Number(result.shots);
  const highestClassicalBit = Math.max(0, experiment.circuit.num_clbits - 1);
  const bitOrderNote = `结果位序：c${highestClassicalBit}...c0，c0 在最右侧`;
  elements.results.classList.remove("is-empty");
  elements.resultsTitle.textContent = "测量结果";
  elements.resultStatusText.textContent = "实验运行完成";
  const backendName = result.backend_name || getSelectedBackend()?.name || result.backend;
  elements.resultBackend.textContent = backendName;
  elements.resultJobId.textContent = result.job_id || "—";
  const fallbackNotice = result.fallback
    ? ` 未配置 ${result.requested_backend_id}，已回退到本地模拟器。`
    : "";
  elements.resultSource.textContent = `结果来自 ${backendName}。${fallbackNotice}`;
  elements.resultShots.textContent = shots.toLocaleString("zh-CN");
  elements.chartShots.textContent = shots.toLocaleString("zh-CN");
  elements.resultElapsed.textContent = `${Number(result.elapsed_seconds).toFixed(3)} s`;
  elements.resultBitOrder.textContent = hasHighCardinality
    ? `${bitOrderNote} · 状态较多，横轴按每次结果中“1”的数量汇总`
    : bitOrderNote;
  elements.resultChartTitle.textContent = hasHighCardinality ? "测量结果概览 · 1 的数量分布" : "测量结果";
  elements.rawBitOrder.textContent = bitOrderNote;
  elements.rawCounts.textContent = JSON.stringify(result.counts, null, 2);
  elements.resultBars.classList.toggle("is-dense", hasHighCardinality);
  elements.resultChart.setAttribute("aria-label", entries.map(([state, count]) => hasHighCardinality ? `包含 ${state} 个 1 的结果为 ${count} 次` : `${state} 为 ${count} 次`).join("，"));
  elements.resultBars.innerHTML = entries.map(([state, count], index) => {
    const percentage = shots > 0 ? (count / shots) * 100 : 0;
    const tooltip = hasHighCardinality
      ? `包含 ${state} 个 1 · ${count} 次 · ${percentage.toFixed(1)}%`
      : `${state} · ${count} 次 · ${percentage.toFixed(1)}%`;
    return `<div class="bar-item" tabindex="0" data-chart-tooltip="${escapeMarkup(tooltip)}"><strong>${percentage.toFixed(1)}%</strong><div class="bar${index % 2 ? " alt" : ""}" style="--height:${percentage.toFixed(2)}%"></div><span>${escapeMarkup(state)}</span></div>`;
  }).join("");

  const explanation = experiment.result_explanation || {};
  const reading = buildResultExplanation(experiment, observedEntries, shots, explanation);
  elements.resultSummary.textContent = reading.summary;
  elements.resultMeaning.textContent = reading.meaning;
  elements.resultWhy.textContent = reading.why;
  elements.resultNext.textContent = reading.next;
  elements.keyFormulas.hidden = experiment.kind !== "bell";
  const operationsByIndex = new Map(experiment.circuit.operations.map((operation) => [operation.index, operation]));
  elements.gateReferences.innerHTML = (explanation.gate_refs || []).map((index) => {
    const operation = operationsByIndex.get(index);
    if (!operation) return "";
    const label = operation.type === "measure" ? "Measure" : operation.gate.toUpperCase();
    return `<button type="button" data-gate-ref="${index}">回看 ${escapeMarkup(label)}</button>`;
  }).join("");

  const runNoticeKey = [
    result.job_id || "",
    backendName || "",
    shots,
    JSON.stringify(result.counts || {}),
  ].join("|");
  if (runNoticeKey !== lastRunConversationNoticeKey) {
    lastRunConversationNoticeKey = runNoticeKey;
    appendConversationNotice(buildRunTutorMessage(experiment, result, reading, observedEntries));
  }
}

function formatResultPercent(count, total) {
  return `${(total > 0 ? (count / total) * 100 : 0).toFixed(1)}%`;
}

function buildRunTutorMessage(experiment, result, reading, observedEntries) {
  const shots = Number(result.shots) || observedEntries.reduce((sum, [, count]) => sum + count, 0);
  const topResults = [...observedEntries]
    .sort(([, left], [, right]) => right - left)
    .slice(0, 4)
    .map(([state, count]) => `${state}：${count} 次（${formatResultPercent(count, shots)}）`)
    .join("、");
  const fallbackMessage = result.fallback
    ? `未配置 ${result.requested_backend_id || "所选远端后端"}，本次实际回退到了本地模拟器；这个结果可以用于产品演示，但不能冒充真机证据。`
    : "本次没有发生远端回退，以上 counts 就是所选运行后端返回的结果。";
  const jobLine = result.job_id ? `可追踪的 job_id：\`${result.job_id}\`。` : "本次运行没有返回可展示的 job_id。";
  return [
    "### 这次运行的具体结论",
    `运行后端：${result.backend_name || "所选后端"}；采样 ${shots.toLocaleString("zh-CN")} 次。主要结果：${topResults || "没有可读结果"}。`,
    fallbackMessage,
    jobLine,
    "",
    "### 这些 counts 说明什么",
    reading.summary,
    reading.meaning,
    "",
    "### 为什么会得到这个分布",
    reading.why,
    "",
    "### 下一步怎么验证",
    reading.next,
    "你还可以继续问我“逐步解释这条电路”“这个结果和理论概率差多少”，我会基于当前电路和这次真实运行结果回答。",
  ].join("\n");
}

function buildResultExplanation(experiment, observedEntries, shots, explanation) {
  const counts = Object.fromEntries(observedEntries);
  const total = observedEntries.reduce((sum, [, count]) => sum + count, 0);
  const denominator = shots > 0 ? shots : total;
  const ranked = [...observedEntries].sort(([, left], [, right]) => right - left);
  const fallbackMeaning = explanation.meaning || "这些柱子展示不同测量结果在重复运行中的出现频率。";
  const fallbackWhy = explanation.why || "电路中的门依次改变状态，Measure 最后把状态转换成可统计的经典比特。";
  const topLine = ranked.length
    ? ranked.slice(0, 3).map(([state, count]) => `${state} ${count} 次（${formatResultPercent(count, denominator)}）`).join("、")
    : "没有可读的测量结果";

  if (experiment.kind === "coin") {
    const zero = counts["0"] || 0;
    const one = counts["1"] || 0;
    const gap = Math.abs(zero - one);
    const gapPercent = denominator > 0 ? (gap / denominator) * 100 : 0;
    return {
      summary: `本次 ${total.toLocaleString("zh-CN")} 次测量得到 0 ${zero} 次（${formatResultPercent(zero, denominator)}），得到 1 ${one} 次（${formatResultPercent(one, denominator)}）；两者相差 ${gap} 次（${gapPercent.toFixed(1)} 个百分点）。`,
      meaning: gapPercent <= 8
        ? "0 和 1 都出现且接近各占一半，说明这次测量看到了量子硬币的概率分布，而不是每次都固定得到同一个值。"
        : "0 和 1 都出现，但有限次采样让两边暂时不完全相等；应把它理解为概率的估计，不是一次运行就能确定的比例。",
      why: "H 门把 |0⟩ 变成 (|0⟩ + |1⟩) / √2，理想情况下两种结果各约 50%；Measure 会在每次运行时产生一个 0 或 1，并把它写入经典寄存器。",
      next: "把 Shots 调大再运行一次，比较两次百分比是否更接近 50/50；点击“回看 H”可以查看叠加是怎样建立的。",
    };
  }

  if (experiment.kind === "bell" || experiment.kind === "ghz") {
    const qubits = experiment.circuit?.num_clbits || experiment.circuit?.num_qubits || 2;
    const allZero = "0".repeat(qubits);
    const allOne = "1".repeat(qubits);
    const zeroCount = counts[allZero] || 0;
    const oneCount = counts[allOne] || 0;
    const correlated = zeroCount + oneCount;
    const leakage = Math.max(0, total - correlated);
    return {
      summary: `本次结果中 ${allZero} 出现 ${zeroCount} 次（${formatResultPercent(zeroCount, denominator)}），${allOne} 出现 ${oneCount} 次（${formatResultPercent(oneCount, denominator)}）；其它组合合计 ${leakage} 次。`,
      meaning: `重点不是某一个比特单独偏向 0 或 1，而是多个比特是否总是以成组的结果出现。${correlated >= total * 0.8 ? ` 当前 ${formatResultPercent(correlated, denominator)} 的结果落在 ${allZero}/${allOne} 这两种组合，相关性很明显。` : "当前仍有不少其它组合，说明相关性还不够集中。"}`,
      why: "H 门先让控制比特保留多种可能，CX/受控门再把这种可能传播到其它比特；测量后，相关的量子态会表现为少数几种经典比特串。",
      next: `继续观察 ${allZero} 与 ${allOne} 的合计比例，并与其它组合比较；增加 Shots 可以减少统计波动，但不会把错误的电路变成正确的电路。`,
    };
  }

  if (experiment.kind === "phase_interference" || experiment.kind === "qft") {
    return {
      summary: `本次测量最常见的结果是 ${topLine}。柱子之间的高度差，就是不同结果概率被测量出来后的差异。`,
      meaning: "这里要观察的是概率如何被重新分配，而不只是哪个结果最高；相位本身不能直接读出，必须通过干涉转成 counts 的差异。",
      why: "相位门先改变各条路径的相对相位，后续 H 等门让路径发生加强或抵消，最后 Measure 把干涉后的振幅平方转成可统计的概率。",
      next: "修改相位或门的顺序后重新运行，比较柱子的变化；如果只改变 Shots，主要变化应是统计噪声，而不是理论分布。",
    };
  }

  return {
    summary: `本次 ${total.toLocaleString("zh-CN")} 次测量最常见的结果是 ${topLine}。`,
    meaning: fallbackMeaning,
    why: fallbackWhy,
    next: "先点击电路中的量子门查看状态变化，再调整 Shots 或门的顺序重新运行，比较结果是否符合预期。",
  };
}

function renderExperiment(experiment) {
  pinnedOperationIndex = null;
  hideGateCard();
  hideQuickGateCard();
  elements.workspace.classList.remove("is-empty");
  elements.workspaceTitle.textContent = experiment.kind === "bell" ? "Bell 态实验" : experiment.title;
  elements.qasmCode.textContent = experiment.qasm;
  renderBackendChooser(experiment.backends || [], experiment.backend_recommendation || {});
  renderCircuit(experiment, { svg: elements.circuitSvg, stateOrder: elements.stateOrder });
  renderSteps(experiment.steps);
}

function mathExpressionMarkup(value) {
  const source = String(value ?? "")
    .replace(/\\pi/g, "π")
    .replace(/\\theta/g, "θ")
    .replace(/\\ket\{([^{}]+)\}/g, "|$1⟩")
    .replace(/\\sqrt\{([^{}]+)\}/g, "√$1");
  if (!source) return "";

  let markup = escapeMarkup(source)
    .replace(/e\^\(([^()]+)\)/g, '<span class="math-exp">e<sup>$1</sup></span>')
    .replace(/e\^\{([^{}]+)\}/g, '<span class="math-exp">e<sup>$1</sup></span>')
    .replace(/\^\{([^{}]+)\}/g, '<sup>$1</sup>')
    .replace(/([A-Za-z0-9πθ])\^([A-Za-z0-9πθ−+\/-]+)/g, '$1<sup>$2</sup>')
    .replace(/\|([0-9A-Za-z,\s⊕=−+\-]+)(?:⟩|&gt;)/g, "|$1⟩")
    .replace(/(\([^)]*\))\s*\/\s*(√[0-9A-Za-zπθ]+)/g, '<span class="math-fraction"><span class="math-numerator">$1</span><span class="math-denominator">$2</span></span>')
    .replace(/(^|[^\w>])([−+\-]?\d+)\s*\/\s*(√[0-9A-Za-zπθ]+)/g, '$1<span class="math-fraction"><span class="math-numerator">$2</span><span class="math-denominator">$3</span></span>');

  return `<span class="math-expression">${markup}</span>`;
}

function renderBackendChooser(backends, recommendation) {
  availableBackends = backends;
  recommendedBackendId = recommendation.backend_id || null;
  selectedBackendId = recommendedBackendId || backends[0]?.id || null;
  backendRecommendationReason = recommendation.reason || "";
  elements.backendOptions.innerHTML = backends.map((backend) => `
    <label class="backend-option">
      <input type="radio" name="backend" data-backend-option value="${escapeMarkup(backend.id)}"${backend.id === selectedBackendId ? " checked" : ""} />
      <span class="backend-option-copy">
        <strong>${escapeMarkup(backend.name)}</strong>
        <small>${escapeMarkup(backend.kind_label)} · 最大 ${backend.max_qubits} qubits · ${escapeMarkup(backend.queue_label)} · ${escapeMarkup(backend.cost_label)} · ${backend.requires_account ? "需要账号" : "无需账号"}${backend.runtime_available === false ? (backend.run_mode === "remote" ? " · 未配置，运行时回退本地" : " · 当前依赖未就绪") : ""}</small>
      </span>
      ${backend.id === recommendedBackendId ? '<span class="recommend">AI 推荐</span>' : ""}
    </label>
  `).join("");
  elements.backendPicker.open = false;
  elements.backendPicker.hidden = backends.length === 0;
  renderSelectedBackend();
}

function renderSelectedBackend() {
  const backend = getSelectedBackend();
  if (!backend) return;
  const isRecommended = Boolean(recommendedBackendId && backend.id === recommendedBackendId);
  const recommended = availableBackends.find((item) => item.id === recommendedBackendId);
  elements.backendMark.textContent = backend.platform;
  elements.backendTitle.textContent = backend.name;
  elements.backendRecommendBadge.textContent = isRecommended ? "AI 推荐" : (recommendedBackendId ? "手动选择" : "可用后端");
  elements.backendRecommendBadge.classList.toggle("is-manual", !isRecommended);
  const accountLabel = backend.requires_account ? "需要账号" : "无需账号";
  const runtimeLabel = backend.runtime_available === false
    ? (backend.run_mode === "remote" ? " · 未配置，运行时回退本地" : " · 当前不可运行")
    : "";
  elements.backendSummary.textContent = `${backend.kind_label} · ${backend.cost_label} · ${accountLabel} · ${backend.queue_label}${runtimeLabel}`;
  elements.backendCapacity.textContent = `最大 ${backend.max_qubits} 量子比特${backend.notes ? ` · ${backend.notes}` : ""}`;
  elements.backendReason.textContent = isRecommended
    ? backendRecommendationReason
    : (recommendedBackendId
      ? `你已手动选择该后端。AI 推荐仍是 ${recommended?.name || "另一可用后端"}，但不会强制切换。`
      : backendRecommendationReason);
  elements.backendFacts.innerHTML = `
    <div><dt>类型</dt><dd>${escapeMarkup(backend.kind_label)}</dd></div>
    <div><dt>最大量子比特</dt><dd>${backend.max_qubits}</dd></div>
    <div><dt>排队</dt><dd>${escapeMarkup(backend.queue_label)}</dd></div>
    <div><dt>费用</dt><dd>${escapeMarkup(backend.cost_label)}</dd></div>
    <div><dt>账号</dt><dd>${accountLabel}</dd></div>
    <div><dt>运行状态</dt><dd>${backend.runtime_available === false ? (backend.run_mode === "remote" ? "未配置；将回退本地" : "未配置或依赖未就绪") : "已就绪"}</dd></div>
  `;
  normalizeShots();
  if (["ready", "idle"].includes(runState)) setRunState(activeExperiment ? "ready" : "idle");
}

function getSelectedBackend() {
  return availableBackends.find((backend) => backend.id === selectedBackendId) || null;
}

function renderSteps(steps) {
  elements.circuitSteps.innerHTML = steps.map((step) => {
    const operationAttribute = Number.isInteger(step.operation_index)
      ? ` data-step-operation="${step.operation_index}"`
      : "";
    const basisHelp = (step.basis_help || []).length
      ? `<div class="basis-help"><span>这些状态表示</span>${step.basis_help.map((item) => mathExpressionMarkup(item)).join("")}</div>`
      : "";
    const simpleState = step.show_simple_state && step.after_state
      ? step.before_state
        ? `<div class="trace-state-flow"><div><span>这一步之前</span><div class="state-expression">${mathExpressionMarkup(step.before_state)}</div></div><b aria-hidden="true">→</b><div><span>这一步之后</span><div class="state-expression">${mathExpressionMarkup(step.after_state)}</div></div></div>`
        : `<div class="trace-initial-state"><span>当前状态</span><div class="state-expression">${mathExpressionMarkup(step.after_state)}</div></div>`
      : "";
    const measurementContext = step.measurement_analysis
      ? measurementAnalysisMarkup(step.measurement_analysis)
      : "";
    const concreteDetail = `
      <details class="trace-detail">
        <summary>看看具体发生了什么</summary>
        <div class="trace-detail-body">
          <div class="trace-technical"><span>当前操作</span><code>${escapeMarkup(step.technical || step.concept || "")}</code></div>
          <p class="simple-change">${escapeMarkup(step.simple_change || step.change || "")}</p>
          ${measurementContext}
          ${simpleState}
          ${basisHelp}
        </div>
      </details>`;
    const math = step.math_detail;
    const mathStates = math && (math.before_state || math.after_state)
      ? `<div class="trace-math-states">
          ${math.before_state ? `<div><span>完整 statevector · 之前</span><div class="state-expression">${mathExpressionMarkup(math.before_state)}</div></div>` : ""}
          ${math.after_state ? `<div><span>完整 statevector · 之后</span><div class="state-expression">${mathExpressionMarkup(math.after_state)}</div></div>` : ""}
        </div>`
      : "";
    const mathDetail = math
      ? `<details class="trace-detail trace-math-detail">
          <summary>看看数学怎么算</summary>
          <div class="trace-detail-body">
            ${mathStates}
            ${math.gate_math ? gateMathMarkup(math.gate_math) : ""}
            <p class="trace-math-note">${escapeMarkup(math.note || "")}</p>
            ${basisHelp}
          </div>
        </details>`
      : "";

    return `
      <li class="trace-step trace-${escapeMarkup(step.trace_mode || "fallback")}"${operationAttribute}>
        <span class="step-number">${step.index}</span>
        <div class="trace-content">
          <div class="trace-heading"><strong>${escapeMarkup(step.purpose || step.title)}</strong></div>
          <p class="trace-explanation">${escapeMarkup(step.explanation || step.description || "")}</p>
          <div class="intuitive-example"><span>当前实验里的直观例子</span><p>${escapeMarkup(step.intuitive_example || step.simple_change || "")}</p></div>
          <div class="trace-disclosures">${concreteDetail}${mathDetail}</div>
        </div>
      </li>`;
  }).join("");
}

function measurementAnalysisMarkup(analysis) {
  const qubitRows = (analysis.qubits || [])
    .map((row) => `<li>${escapeMarkup(row.text)}</li>`)
    .join("");
  const counts = (analysis.predicted_counts || [])
    .map((item) => `<span><code>${escapeMarkup(item.result)}</code> 约 ${escapeMarkup(item.percent)}</span>`)
    .join("");
  return `
    <div class="measurement-analysis">
      <div class="measurement-orders">
        <span>量子态顺序：<code>${escapeMarkup(analysis.state_order)}</code></span>
        <span>结果位序：<code>${escapeMarkup(analysis.result_order)}</code>，c0 在最右侧</span>
      </div>
      <p>${escapeMarkup(analysis.measured_summary)}</p>
      ${qubitRows ? `<ul>${qubitRows}</ul>` : ""}
      ${counts ? `<div class="predicted-counts"><strong>由测量前 statevector 推得</strong>${counts}</div>` : ""}
    </div>`;
}

function getOperation(operationIndex) {
  return activeExperiment?.circuit.operations.find((item) => item.index === operationIndex);
}

function operationTarget(operation) {
  if (operation.type === "measure") return `q${operation.qubit} → c${operation.cbit}`;
  return operation.qubits.map((qubit) => `q${qubit}`).join(" → ");
}

function highlightOperation(operationIndex) {
  elements.circuitSvg.querySelectorAll("[data-operation-index]").forEach((element) => {
    element.classList.toggle("is-highlighted", Number(element.dataset.operationIndex) === operationIndex);
  });
}

function pinOperation(operationIndex) {
  elements.circuitSvg.querySelectorAll("[data-operation-index]").forEach((element) => {
    const pinned = Number(element.dataset.operationIndex) === operationIndex;
    element.classList.toggle("is-pinned", pinned);
    element.setAttribute("aria-pressed", String(pinned));
  });
}

function showQuickGateCard(operationIndex) {
  const operation = getOperation(operationIndex);
  if (!operation?.gate_card) return;
  const card = operation.gate_card;
  const current = card.current;
  const isCx = operation.type === "gate" && operation.gate === "cx";
  const isBellCx = isCx && activeExperiment?.kind === "bell";
  highlightOperation(operationIndex);
  elements.gateQuickCard.classList.toggle("is-cx", isCx);
  elements.gateQuickTitle.textContent = isCx ? "CX · 受控非门" : card.concept;
  elements.gateQuickTarget.textContent = operationTarget(operation);
  elements.gateQuickChange.innerHTML = mathExpressionMarkup(card.rule);
  elements.gateQuickExample.hidden = !isCx;
  elements.gateQuickExperiment.hidden = !isBellCx || current.mode !== "exact";
  elements.gateQuickExampleText.textContent = isCx ? "00 → 00　　　　　10 → 11" : "";
  elements.gateQuickExperimentText.innerHTML = isBellCx && current.mode === "exact"
    ? mathExpressionMarkup(`${current.before} → ${current.after}`)
    : "";
  elements.gateQuickCard.hidden = false;
}

function hideQuickGateCard() {
  elements.gateQuickCard.hidden = true;
  highlightOperation(-1);
}

function toggleGateCard(operationIndex) {
  if (pinnedOperationIndex === operationIndex) {
    pinnedOperationIndex = null;
    hideGateCard();
    hideQuickGateCard();
    return;
  }
  openGateCard(operationIndex);
}

function openGateCard(operationIndex) {
  const operation = getOperation(operationIndex);
  if (!operation?.gate_card) return;
  pinnedOperationIndex = operationIndex;
  hideQuickGateCard();
  pinOperation(operationIndex);
  const card = operation.gate_card;
  const current = card.current;
  elements.gateCardConcept.textContent = card.concept;
  elements.gateCardTechnical.textContent = card.technical;
  elements.gateCardRule.innerHTML = mathExpressionMarkup(card.rule);
  elements.gateCardTransition.hidden = current.mode !== "exact";
  elements.gateCardBefore.innerHTML = mathExpressionMarkup(current.before || "");
  elements.gateCardAfter.innerHTML = mathExpressionMarkup(current.after || "");
  elements.gateCardCurrent.innerHTML = mathExpressionMarkup(current.explanation);
  elements.gateMathLabel.textContent = card.math.label;
  renderGateMath(card.math);
  renderBlochPanel(current.bloch);
  elements.gateCard.hidden = false;
}

function renderGateMath(math) {
  elements.gateCardMath.innerHTML = gateMathMarkup(math);
}

function formatBlochComponent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0.00";
  const rounded = Math.abs(number) < 0.005 ? 0 : number;
  return rounded.toFixed(2).replace("-0.00", "0.00");
}

function formatPhaseDegrees(value) {
  if (value === null || value === undefined || value === "") return "未定义";
  const number = Number(value);
  if (!Number.isFinite(number)) return "未定义";
  const rounded = Math.abs(number) < 0.05 ? 0 : number;
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}°`;
}

function formatAmplitudeComplex(real, imaginary) {
  const safeReal = Number(real) || 0;
  const safeImaginary = Number(imaginary) || 0;
  const realText = formatBlochComponent(safeReal);
  const imaginaryText = formatBlochComponent(Math.abs(safeImaginary));
  if (Math.abs(safeImaginary) < 0.005) return realText;
  if (Math.abs(safeReal) < 0.005) return `${safeImaginary < 0 ? "−" : ""}${imaginaryText}i`;
  return `${realText} ${safeImaginary < 0 ? "−" : "+"} ${imaginaryText}i`;
}

function amplitudePayload(real, imaginary) {
  const safeReal = Number(real) || 0;
  const safeImaginary = Number(imaginary) || 0;
  const magnitude = Math.hypot(safeReal, safeImaginary);
  const phase = magnitude < 0.005 ? null : Math.atan2(safeImaginary, safeReal) * 180 / Math.PI;
  return {
    real: safeReal,
    imag: safeImaginary,
    text: formatAmplitudeComplex(safeReal, safeImaginary),
    magnitude,
    phase_deg: phase,
  };
}

function blochAmplitudesFromVector(vector) {
  const [x, y, z] = vector.map((value) => Number(value) || 0);
  const purity = x * x + y * y + z * z;
  if (purity < 0.995) {
    return {
      pure: false,
      purity,
      note: "该局部态不是纯态，不能用一组唯一的 α、β 表示。",
    };
  }

  const alphaMagnitude = Math.sqrt(Math.max(0, (1 + z) / 2));
  const alpha = alphaMagnitude > 0.005
    ? amplitudePayload(alphaMagnitude, 0)
    : amplitudePayload(0, 0);
  const beta = alphaMagnitude > 0.005
    ? amplitudePayload(x / (2 * alphaMagnitude), y / (2 * alphaMagnitude))
    : amplitudePayload(0, Math.sqrt(Math.max(0, (1 - z) / 2)));
  const relativePhase = alpha.magnitude > 0.005 && beta.magnitude > 0.005
    ? Math.atan2(beta.imag, beta.real) * 180 / Math.PI
    : null;
  return {
    pure: true,
    purity,
    alpha,
    beta,
    relative_phase_deg: relativePhase,
    note: "α、β 已去除整体相位；相对相位 Δφ = arg(β) − arg(α)。",
  };
}

function amplitudeDetailsMarkup(amplitudes) {
  if (!amplitudes?.pure) {
    return `<p class="bloch-amplitude-note">${escapeMarkup(amplitudes?.note || "α、β 不是唯一的纯态表示")}</p>`;
  }
  const alpha = amplitudes.alpha || amplitudePayload(0, 0);
  const beta = amplitudes.beta || amplitudePayload(0, 0);
  return `
    <div class="bloch-amplitude-grid">
      <div class="bloch-amplitude-cell"><span>α（|0⟩）</span><div class="state-expression">${mathExpressionMarkup(alpha.text)}</div><small>|α| = ${formatBlochComponent(alpha.magnitude)} · 相位 ${formatPhaseDegrees(alpha.phase_deg)}</small></div>
      <div class="bloch-amplitude-cell"><span>β（|1⟩）</span><div class="state-expression">${mathExpressionMarkup(beta.text)}</div><small>|β| = ${formatBlochComponent(beta.magnitude)} · 相位 ${formatPhaseDegrees(beta.phase_deg)}</small></div>
    </div>
    <p class="bloch-relative-phase">相对相位 Δφ = ${formatPhaseDegrees(amplitudes.relative_phase_deg)}</p>
  `;
}

function blochVectorText(vector) {
  return `r⃗ = (${vector.map(formatBlochComponent).join(", ")})`;
}

function blochPoint(vector) {
  const [x, y, z] = vector;
  const cx = 88;
  const cy = 78;
  const radius = 55;
  return {
    x: cx + radius * (0.82 * x + 0.36 * y),
    y: cy - radius * (0.86 * z - 0.2 * y),
  };
}

function blochSphereMarkup(vector, label, key, amplitudes) {
  const [x, y, z] = Array.isArray(vector) ? vector : [0, 0, 1];
  const safe = [x, y, z].map((value) => Math.max(-1, Math.min(1, Number(value) || 0)));
  const [safeX, safeY, safeZ] = safe;
  const cx = 88;
  const cy = 78;
  const radius = 55;
  const point = blochPoint(safe);
  const markerId = `bloch-arrow-${key}`;
  const vectorText = blochVectorText(safe);
  return `
    <article class="bloch-state">
      <div class="bloch-state-heading"><strong>${escapeMarkup(label)}</strong><code data-bloch-vector>${escapeMarkup(vectorText)}</code></div>
      <svg class="bloch-sphere" viewBox="0 0 176 156" role="img" aria-label="${escapeMarkup(label)} Bloch 球向量 ${escapeMarkup(vectorText)}" data-bloch-interactive="true" data-bloch-x="${safeX}" data-bloch-y="${safeY}" data-bloch-z="${safeZ}">
        <title>${escapeMarkup(label)}：拖拽蓝色向量查看 α、β 和相对相位</title>
        <defs><marker id="${markerId}" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" /></marker></defs>
        <circle class="bloch-surface" cx="${cx}" cy="${cy}" r="${radius}" />
        <ellipse class="bloch-grid" cx="${cx}" cy="${cy}" rx="${radius}" ry="18" />
        <ellipse class="bloch-grid" cx="${cx}" cy="${cy}" rx="18" ry="${radius}" />
        <line class="bloch-axis" x1="${cx - radius - 7}" y1="${cy}" x2="${cx + radius + 7}" y2="${cy}" />
        <line class="bloch-axis bloch-axis-depth" x1="${cx - 42}" y1="${cy + 30}" x2="${cx + 42}" y2="${cy - 30}" />
        <line class="bloch-axis" x1="${cx}" y1="${cy - radius - 7}" x2="${cx}" y2="${cy + radius + 7}" />
        <line class="bloch-vector" x1="${cx}" y1="${cy}" x2="${point.x.toFixed(2)}" y2="${point.y.toFixed(2)}" marker-end="url(#${markerId})" />
        <circle class="bloch-point" cx="${point.x.toFixed(2)}" cy="${point.y.toFixed(2)}" r="3.5" />
        <text class="bloch-label bloch-label-x" x="${cx + radius + 7}" y="${cy + 4}">+X</text>
        <text class="bloch-label bloch-label-y" x="${cx + 40}" y="${cy - 34}">+Y</text>
        <text class="bloch-label bloch-label-z" x="${cx + 5}" y="${cy - radius - 10}">+Z</text>
        <text class="bloch-label bloch-label-zero" x="${cx - 5}" y="${cy + radius + 19}">−Z</text>
      </svg>
      <div class="bloch-amplitudes" data-bloch-amplitudes>${amplitudeDetailsMarkup(amplitudes || blochAmplitudesFromVector(safe))}</div>
    </article>
  `;
}

function updateBlochSphere(svg, vector) {
  const safe = vector.map((value) => Math.max(-1, Math.min(1, Number(value) || 0)));
  const point = blochPoint(safe);
  svg.dataset.blochX = String(safe[0]);
  svg.dataset.blochY = String(safe[1]);
  svg.dataset.blochZ = String(safe[2]);
  svg.querySelector(".bloch-vector")?.setAttribute("x2", point.x.toFixed(2));
  svg.querySelector(".bloch-vector")?.setAttribute("y2", point.y.toFixed(2));
  svg.querySelector(".bloch-point")?.setAttribute("cx", point.x.toFixed(2));
  svg.querySelector(".bloch-point")?.setAttribute("cy", point.y.toFixed(2));
  const state = svg.closest(".bloch-state");
  if (!state) return;
  const vectorText = blochVectorText(safe);
  state.querySelector("[data-bloch-vector]").textContent = vectorText;
  state.querySelector("[data-bloch-amplitudes]").innerHTML = amplitudeDetailsMarkup(blochAmplitudesFromVector(safe));
  svg.setAttribute("aria-label", `${state.querySelector(".bloch-state-heading strong").textContent} Bloch 球向量 ${vectorText}`);
}

function rotateBlochVector(vector, deltaX, deltaY) {
  const rawLength = Math.hypot(...vector);
  const length = rawLength > 0.05 ? rawLength : 1;
  const base = rawLength > 0.05 ? vector : [0, 0, 1];
  const azimuth = Math.atan2(base[1], base[0]);
  const polar = Math.acos(Math.max(-1, Math.min(1, base[2] / Math.max(rawLength, 1e-6))));
  const nextAzimuth = azimuth + deltaX * 0.018;
  const nextPolar = Math.max(0.03, Math.min(Math.PI - 0.03, polar - deltaY * 0.018));
  return [
    length * Math.sin(nextPolar) * Math.cos(nextAzimuth),
    length * Math.sin(nextPolar) * Math.sin(nextAzimuth),
    length * Math.cos(nextPolar),
  ];
}

function bindBlochInteractions() {
  elements.gateCardBloch.querySelectorAll(".bloch-sphere[data-bloch-interactive]").forEach((svg) => {
    let drag = null;
    svg.addEventListener("pointerdown", (event) => {
      drag = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        vector: [Number(svg.dataset.blochX), Number(svg.dataset.blochY), Number(svg.dataset.blochZ)],
      };
      try {
        svg.setPointerCapture?.(event.pointerId);
      } catch {
        // Synthetic pointer events used by assistive tooling may not be capturable.
      }
      svg.classList.add("is-dragging");
      event.preventDefault();
    });
    svg.addEventListener("pointermove", (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      updateBlochSphere(svg, rotateBlochVector(drag.vector, event.clientX - drag.startX, event.clientY - drag.startY));
    });
    const stopDragging = (event) => {
      if (!drag || event.pointerId !== drag.pointerId) return;
      drag = null;
      svg.classList.remove("is-dragging");
      try {
        svg.releasePointerCapture?.(event.pointerId);
      } catch {
        // The pointer may already have been released by the browser.
      }
    };
    svg.addEventListener("pointerup", stopDragging);
    svg.addEventListener("pointercancel", stopDragging);
  });
}

function renderBlochPanel(change) {
  if (!change?.qubits?.length) {
    elements.gateBloch.hidden = true;
    elements.gateCardBloch.replaceChildren();
    return;
  }

  elements.gateCardBloch.innerHTML = change.qubits.map((item) => `
    <article class="bloch-track">
      <div class="bloch-track-heading"><strong>q${escapeMarkup(item.qubit)}</strong><span>作用前 → 作用后</span></div>
      <div class="bloch-pair">
        ${blochSphereMarkup(item.before, "作用前", `q${item.qubit}-before`, item.before_amplitudes)}
        <span class="bloch-arrow" aria-hidden="true">→</span>
        ${blochSphereMarkup(item.after, "作用后", `q${item.qubit}-after`, item.after_amplitudes)}
      </div>
    </article>
  `).join("");
  bindBlochInteractions();
  elements.gateBloch.hidden = false;
}

function gateMathMarkup(math) {
  if (math.kind === "matrix" && Array.isArray(math.rows)) {
    const cells = math.rows.flat().map((cell) => `<span>${mathExpressionMarkup(cell)}</span>`).join("");
    const notes = (math.notes || []).map((note) => `<li>${mathExpressionMarkup(note)}</li>`).join("");
    const parameter = math.parameter ? `<p class="math-parameter">当前参数：${mathExpressionMarkup(`θ = ${math.parameter}`)}</p>` : "";
    return `
      ${parameter}
      <div class="math-equation">
        <span class="math-symbol">${escapeMarkup(math.symbol || "U")}</span><span>=</span>
        <span class="matrix-grid">${cells}</span>
      </div>
      ${notes ? `<ul class="math-notes">${notes}</ul>` : ""}
    `;
  }

  const lines = Array.isArray(math.lines)
    ? math.lines
    : String(math.content || "当前没有可可靠展示的数学形式。").split("\n");
  return `<div class="math-rule-lines">${lines.map((line) => mathExpressionMarkup(line)).join("")}</div>`;
}

function hideGateCard() {
  elements.gateCard.hidden = true;
  pinOperation(-1);
  highlightOperation(-1);
}

function focusOperation(operationIndex) {
  elements.workspace.hidden = false;
  selectTab("circuit-tab");
  elements.workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  window.setTimeout(() => {
    const operationElement = elements.circuitSvg.querySelector(`[data-operation-index="${operationIndex}"]`);
    if (!operationElement) return;
    openGateCard(operationIndex);
    operationElement.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    operationElement.focus({ preventScroll: true });
  }, 350);
}
