const screens = [...document.querySelectorAll("[data-screen]")];
const liveStatus = document.querySelector("#liveStatus");
const startButton = document.querySelector("#startButton");
const customIdeaButton = document.querySelector("#customIdeaButton");
const studioNavButtons = [...document.querySelectorAll("[data-studio-nav]")];
const brandHome = document.querySelector("#brandHome");
const themeToggle = document.querySelector("#themeToggle");
const playgroundForm = document.querySelector("#playgroundForm");
const playgroundPrompt = document.querySelector("#playgroundPrompt");
const playgroundRun = document.querySelector("#playgroundRun");
const playgroundOutput = document.querySelector("#playgroundOutput");
const playgroundReset = document.querySelector("#playgroundReset");
const agentStatus = document.querySelector("#agentStatus");
const agentError = document.querySelector("#agentError");
const agentResultContent = document.querySelector("#agentResultContent");
const agentResultTitle = document.querySelector("#agentResultTitle");
const agentAnswer = document.querySelector("#agentAnswer");
const agentAnswerTitle = document.querySelector("#agentAnswerTitle");
const agentCodeBlock = document.querySelector("#agentCodeBlock");
const agentQasm = document.querySelector("#agentQasm");
const agentCopy = document.querySelector("#agentCopy");
const agentRetry = document.querySelector("#agentRetry");
const agentProposal = document.querySelector("#agentProposal");
const agentProposalSummary = document.querySelector("#agentProposalSummary");
const agentProposalChecks = document.querySelector("#agentProposalChecks");
const agentAdopt = document.querySelector("#agentAdopt");
const courseList = document.querySelector("#courseList");
const courseSidebar = document.querySelector("#courseSidebar");
const courseSidebarList = document.querySelector("#courseSidebarList");
const courseMap = document.querySelector("#courseMap");
const courseStatus = document.querySelector("#courseStatus");
const courseOrder = document.querySelector("#courseOrder");
const courseTitle = document.querySelector("#courseTitle");
const courseSummary = document.querySelector("#courseSummary");
const courseHook = document.querySelector("#courseHook");
const courseGoal = document.querySelector("#courseGoal");
const courseConcepts = document.querySelector("#courseConcepts");
const courseExperiment = document.querySelector("#courseExperiment");
const courseExperimentCards = document.querySelector("#courseExperimentCards");
const courseError = document.querySelector("#courseError");
const courseResult = document.querySelector("#courseResult");
const courseCounts = document.querySelector("#courseCounts");
const courseProbabilities = document.querySelector("#courseProbabilities");
const courseExplanation = document.querySelector("#courseExplanation");
const courseResultStatus = document.querySelector("#courseResultStatus");
const courseAnimationStage = document.querySelector("#courseAnimationStage");
const courseAnimate = document.querySelector("#courseAnimate");
const courseStepBack = document.querySelector("#courseStepBack");
const courseStepNext = document.querySelector("#courseStepNext");
const courseStepCount = document.querySelector("#courseStepCount");
const courseStepTitle = document.querySelector("#courseStepTitle");
const courseStepExplanation = document.querySelector("#courseStepExplanation");
const courseStepDots = document.querySelector("#courseStepDots");
const courseBack = document.querySelector("#courseBack");
const courseNext = document.querySelector("#courseNext");
const courseBackToTop = document.querySelector("#courseBackToTop");
const playgroundPromptEditor = document.querySelector("#playgroundPromptEditor");
const playgroundPromptLabel = document.querySelector("#playgroundPromptLabel");
const promptSuggestions = document.querySelector("#promptSuggestions");
const repairEditor = document.querySelector("#repairEditor");
const repairQasmLabel = document.querySelector("#repairQasmLabel");
const repairQasm = document.querySelector("#repairQasm");
const environmentChooser = document.querySelector("#environmentChooser");
const environmentList = document.querySelector("#environmentList");
const environmentStatus = document.querySelector("#environmentStatus");
const environmentRun = document.querySelector("#environmentRun");
const environmentRefresh = document.querySelector("#environmentRefresh");
const environmentResult = document.querySelector("#environmentResult");
const environmentResultBadge = document.querySelector("#environmentResultBadge");
const environmentCounts = document.querySelector("#environmentCounts");
const environmentProvenance = document.querySelector("#environmentProvenance");
const hardwareConfig = document.querySelector("#hardwareConfig");
const hardwareLabel = document.querySelector("#hardwareLabel");
const hardwarePlatform = document.querySelector("#hardwarePlatform");
const originqFields = document.querySelector("#originqFields");
const originqToken = document.querySelector("#originqToken");
const originqBackend = document.querySelector("#originqBackend");
const spinqFields = document.querySelector("#spinqFields");
const spinqUsername = document.querySelector("#spinqUsername");
const spinqPrivateKey = document.querySelector("#spinqPrivateKey");
const spinqHost = document.querySelector("#spinqHost");
const spinqPlatformCode = document.querySelector("#spinqPlatformCode");
const hardwareSave = document.querySelector("#hardwareSave");
const hardwareConfigStatus = document.querySelector("#hardwareConfigStatus");
const hardwareProfiles = document.querySelector("#hardwareProfiles");
const hardwareProfileCount = document.querySelector("#hardwareProfileCount");
const hardwareProfileList = document.querySelector("#hardwareProfileList");
const hardwareConfirm = document.querySelector("#hardwareConfirm");
const hardwareConfirmPlatform = document.querySelector("#hardwareConfirmPlatform");
const hardwareCurrent = document.querySelector("#hardwareCurrent");
const hardwareCurrentState = document.querySelector("#hardwareCurrentState");
const hardwareCurrentTaskId = document.querySelector("#hardwareCurrentTaskId");
const hardwareCurrentProviderId = document.querySelector("#hardwareCurrentProviderId");
const hardwareCurrentStage = document.querySelector("#hardwareCurrentStage");
const hardwareCurrentElapsed = document.querySelector("#hardwareCurrentElapsed");
const hardwareHistoryList = document.querySelector("#hardwareHistoryList");
const hardwareHistoryRefresh = document.querySelector("#hardwareHistoryRefresh");

let currentScreen = "welcome";
let lastAgentRequest = null;
let courseCatalog = [];
let activeCourseIndex = 0;
let courseRunCount = 0;
let environmentCatalog = { environments: [], unavailable: [] };
let hardwareProfileCatalog = [];
let hardwareEvidenceCache = null;
let activeCourseStep = 0;
let courseStepTimer = null;
let pendingHardwareEnvironment = null;
let hardwarePollTimer = null;
let hardwareElapsedTimer = null;
let activeHardwareJob = null;
const sessionNonce = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${performance.now()}`;

const CONCEPT_EXPLANATIONS = {
  bit: "只能保存 0 或 1 的经典信息单位。",
  qubit: "用振幅描述测量前状态的量子信息单位。",
  "振幅": "带有大小和相位的数值，决定路径如何组合。",
  "X 门": "把 |0⟩ 与 |1⟩ 相互翻转。",
  "H 门": "建立等大的 |0⟩ 和 |1⟩ 振幅。",
  "测量": "把量子状态读成经典的 0 或 1。",
  shots: "同一电路独立制备并测量的次数。",
  counts: "多次测量后各输出出现次数的汇总。",
  "概率": "大量重复测量时，各结果所占的预期比例。",
  "CX 门": "依据控制 qubit 的状态翻转目标 qubit。",
  "Bell 态": "两枚 qubit 形成强关联的两体量子状态。",
  "纠缠": "整体状态无法拆成各部分独立状态的关联。",
  "联合分布": "同时观察多枚 qubit 后得到的结果分布。",
  "相位": "振幅的方向信息，影响路径相加或抵消。",
  "RZ 门": "绕 Z 轴旋转相位而不直接改变测量概率。",
  "干涉": "不同路径的振幅相加或相消。",
  "相对相位": "两条路径相位之间的差值。",
  "GHZ 态": "三枚以上 qubit 共同关联的代表性状态。",
  "多体纠缠": "三个或更多量子系统之间不可拆分的关联。",
  "支持集": "理论上具有非零概率的输出集合。",
  "噪声": "真实设备让结果偏离理想计算的误差来源。",
  "保真度": "实际状态或操作接近理想目标的程度。",
  "模拟基线": "用于对照真机结果的理想模拟结果。",
  job_id: "量子平台为一次运行分配的可追溯编号。",
  "实验留证": "保存电路、结果和来源以便复核。",
};

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    if (error instanceof TypeError) {
      const serviceAddress = globalThis.location?.origin || "当前页面地址";
      throw new Error(`无法连接 LoomQ 本地服务（${serviceAddress}），请刷新页面后重试`);
    }
    throw error;
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`本地服务返回了无法读取的响应（HTTP ${response.status}）`);
  }
  if (!response.ok) {
    const serverMessage = typeof payload?.error === "string" ? payload.error : payload?.error?.message;
    throw new Error(serverMessage || `服务请求失败（HTTP ${response.status}）`);
  }
  return payload;
}

async function simulateExperiment(lessonId, experimentId, shots, nonce) {
  return requestJson("/api/simulate", {
    method: "POST",
    body: JSON.stringify({
      lesson_id: lessonId,
      experiment_id: experimentId,
      shots,
      nonce,
    }),
  });
}

function formatNumber(value, digits = 4) {
  const rounded = Number(value.toFixed(digits));
  return Object.is(rounded, -0) ? "0" : String(rounded);
}

function miniCircuitMarkup(experimentId) {
  const threeQubits = ["ghz-3", "ideal-ghz-baseline"].includes(experimentId);
  const phase = ["phase-zero", "phase-half", "phase-flip"].includes(experimentId);
  const pair = ["bell-state", "bell-2-baseline", "independent-pair", "ideal-bell-baseline", "ideal-ghz-baseline"].includes(experimentId);
  const firstGate = experimentId === "x-flip" || experimentId === "deterministic-baseline" ? "X" : "H";
  const rows = Array.from({length: threeQubits ? 3 : pair ? 2 : 1}, (_, index) => 14 + index * 16);
  const wires = rows.map((y) => `<path d="M8 ${y}H112" />`).join("");
  const gates = `<rect x="26" y="${rows[0] - 8}" width="16" height="16" rx="2" /><text x="34" y="${rows[0] + 3}" text-anchor="middle">${firstGate}</text>${phase ? `<rect x="57" y="${rows[0] - 8}" width="22" height="16" rx="2" /><text x="68" y="${rows[0] + 3}" text-anchor="middle">Rz</text><rect x="88" y="${rows[0] - 8}" width="16" height="16" rx="2" /><text x="96" y="${rows[0] + 3}" text-anchor="middle">H</text>` : ""}${pair ? `<path class="mini-circuit__link" d="M65 ${rows[0]}V${rows.at(-1)}" /><circle cx="65" cy="${rows[0]}" r="3" /><circle cx="65" cy="${rows.at(-1)}" r="7" />` : ""}`;
  return `<svg class="mini-circuit" viewBox="0 0 120 ${rows.at(-1) + 14}" aria-hidden="true">${wires}${gates}<path class="mini-circuit__measure" d="M108 ${rows[0]}h7" /></svg>`;
}

function renderCourseCatalog() {
  courseList.replaceChildren(...courseCatalog.map((lesson, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const order = document.createElement("b");
    const copy = document.createElement("span");
    const detail = document.createElement("small");
    const visual = document.createElement("span");
    visual.className = "course-card-visual";
    visual.innerHTML = miniCircuitMarkup(lesson.experiments[0]?.id || "hadamard-measure");
    button.type = "button";
    order.textContent = String(lesson.order).padStart(2, "0");
    copy.textContent = lesson.title;
    detail.textContent = lesson.summary;
    copy.append(detail);
    button.append(order, visual, copy);
    button.addEventListener("click", () => openCourse(index));
    item.append(button);
    return item;
  }));
  courseSidebarList.replaceChildren(...courseCatalog.map((lesson, index) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    const order = document.createElement("span");
    const title = document.createElement("strong");
    button.type = "button";
    order.textContent = String(lesson.order).padStart(2, "0");
    title.textContent = lesson.title;
    button.append(order, title);
    button.addEventListener("click", () => openCourse(index));
    item.append(button);
    return item;
  }));
}

function activeLesson() {
  return courseCatalog[activeCourseIndex];
}

function activeCourseExperiment() {
  return activeLesson()?.experiments.find((item) => item.id === courseExperiment.value);
}

function renderExperimentCards() {
  const lesson = activeLesson();
  if (!lesson) return;
  courseExperimentCards.replaceChildren(
    Object.assign(document.createElement("legend"), {textContent: "实验情景", className: "sr-only"}),
    ...lesson.experiments.map((experiment) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      const prompt = document.createElement("small");
      input.type = "radio";
      input.name = "course-experiment-card";
      input.value = experiment.id;
      input.checked = experiment.id === courseExperiment.value;
      title.textContent = experiment.plain_title;
      prompt.textContent = experiment.plain_prompt;
      copy.append(title, prompt);
      label.append(input, copy);
      input.addEventListener("change", () => {
        if (!input.checked) return;
        courseExperiment.value = experiment.id;
        updateCourseExperimentCopy({autoRun: true});
      });
      return label;
    }),
  );
}

const COURSE_STEPS = {
  paths: [
    {title: "从 0 出发", explanation: "每次实验先把 qubit 准备为 0。图中只显示起点，门操作还没有发生。"},
    {title: "让门处理信息", explanation: "X 把 0 确定地翻成 1；H 则建立通往 0 与 1 的两条测量前路线。"},
    {title: "检查门后的状态", explanation: "门已经生效，但还没有测量。两条路线表示两份振幅，不是已经得到两个答案。"},
    {title: "测量一次", explanation: "探测器每次只登记一个结果：0 或 1。"},
    {title: "比较两种计算方式", explanation: "X 沿一条确定路线改变 bit；H 利用多条带振幅的路线描述 qubit。"},
  ],
  shots: [
    {title: "准备第 1 次实验", explanation: "一个 shot 从重新准备 qubit 开始；两个计票桶现在都是空的。"},
    {title: "运行一次电路", explanation: "门操作处理这次新准备的 qubit，此时还没有给 counts 加票。"},
    {title: "测量并投下一票", explanation: "一次运行只产生一个结果，只能投进 0 或 1 的一个桶。"},
    {title: "重新开始下一次", explanation: "下一票来自一次全新的准备、运行和测量，不是重复读取上一枚 qubit。"},
    {title: "累计成 counts", explanation: "counts 是许多次单次结果的累计直方图。"},
    {title: "比较确定与随机", explanation: "X 的票全部落向 1；H 的票会分散到 0 和 1。shots 只增加样本数。"},
  ],
  pair: [
    {title: "准备两枚 qubit", explanation: "两枚 qubit 都从确定的 0 开始，尚未制造随机性或关联。"},
    {title: "分别制造随机性", explanation: "H 让每一枚单独看都像一枚随机硬币。"},
    {title: "决定是否用 CX 连接", explanation: "独立实验不连接；Bell 实验用 CX 把第二枚的变化关联到第一枚。"},
    {title: "查看四种联合结果", explanation: "把两枚结果合在一起统计，才能分辨独立与关联。"},
    {title: "识别 Bell 关联", explanation: "独立时 00/01/10/11 都可能；理想 Bell 主要只留下 00 和 11。"},
  ],
  phase: [
    {title: "把一条路线分成两条", explanation: "第一个 H 建立两条等大的测量前路线。"},
    {title: "用箭头表示振幅", explanation: "箭头长度表示大小，方向表示相位；箭头是计算模型，不是测量结果。"},
    {title: "转动其中一支箭头", explanation: "RZ 改变路线 B 的相对方向：0、π/2 或 π。"},
    {title: "把两条路线重新合成", explanation: "第二个 H 让同向部分相加、反向部分抵消。"},
    {title: "读取干涉后的概率", explanation: "相位差会改变 0 与 1 的测量概率；π 时 0 路线完全抵消。"},
  ],
  chain: [
    {title: "全部从 0 开始", explanation: "Bell 使用两枚、GHZ 使用三枚；所有 qubit 起初都是 0。"},
    {title: "H 建立两个候选分支", explanation: "第一枚 qubit 形成“全为 0”与“全为 1”两个分支的起点。"},
    {title: "第一次 CX 连接第二枚", explanation: "分支关系传给第二枚，得到 00 与 11。"},
    {title: "第二次 CX 连接第三枚", explanation: "只有 GHZ-3 继续把关联传给第三枚；Bell-2 在上一步已经完成。"},
    {title: "测量联合结果", explanation: "Bell 支持集是 00/11；GHZ-3 支持集是 000/111。"},
  ],
  noise: [
    {title: "建立理想基线", explanation: "先看算法希望得到的 Bell counts：00 与 11 是两个主峰。"},
    {title: "同一电路运行在真实芯片", explanation: "真实门、状态保持与读出都可能引入小误差。"},
    {title: "用共同刻度比较 counts", explanation: "三组柱图共享相同纵轴，才能公平比较主峰与误差结果。"},
    {title: "解释 01 与 10", explanation: "少量误差结果不等于实验失败；关键是 00/11 是否仍占主导。"},
    {title: "核对可追溯证据", explanation: "job_id 与时间戳用于回到平台核验；查看图解不会创建新真机任务。"},
  ],
};

const COURSE_STEP_OVERRIDES = {
  "bell-state": [
    {title: "准备两枚 qubit", explanation: "两枚都从确定的 0 开始，尚未制造随机性或关联。"},
    {title: "先让第一枚产生随机分支", explanation: "只对 q0 使用 H；q1 此刻仍是 0，等待下一步的 CX。"},
    {title: "用 CX 建立连接", explanation: "CX 把 q0 的分支关系传给 q1；从这一步起，两枚单独看都随机。"},
    {title: "查看四种联合结果", explanation: "把两枚结果合在一起统计，才能看见 00/11 的关联。"},
    {title: "识别 Bell 关联", explanation: "单独看各约一半；合起来看，理想电路只留下 00 和 11。"},
  ],
  "independent-pair": [
    {title: "准备两枚 qubit", explanation: "两枚都从确定的 0 开始，尚未制造随机性。"},
    {title: "分别制造随机性", explanation: "对 q0、q1 各使用一个 H，让每一枚单独看都像随机硬币。"},
    {title: "保持两条线路不连接", explanation: "没有 CX，两次随机不会互相传递信息。"},
    {title: "查看四种联合结果", explanation: "00、01、10、11 都会出现，并且长期比例都接近四分之一。"},
    {title: "确认相互独立", explanation: "知道 q0 的结果仍不能预测 q1；四种组合都保留。"},
  ],
  "bell-2-baseline": [
    {title: "两枚都从 0 开始", explanation: "Bell 实验只使用 q0 和 q1，两枚起初都是确定的 0。"},
    {title: "q0 产生两个候选分支", explanation: "H 建立 0 分支与 1 分支的起点。"},
    {title: "CX 把分支传给 q1", explanation: "第一次也是唯一一次 CX 建立两枚关联，得到 00/11。"},
    {title: "确认 Bell-2 已经完成", explanation: "这个实验没有第三枚 qubit，因此不会执行第二个 CX。"},
    {title: "测量两枚的联合结果", explanation: "理想 Bell 电路的主导支持集是 00 和 11。"},
  ],
  "ideal-ghz-baseline": [
    {title: "建立理想 GHZ 基线", explanation: "理想 GHZ-3 只保留 000 和 111；这还不是真机结果。"},
    {title: "查看更长的电路", explanation: "GHZ 比 Bell 多一枚 qubit 和一次 CX，状态还要保持到最终测量。"},
    {title: "定位三类误差机会", explanation: "门误差、退相干和读出误差都可能随电路过程累积。"},
    {title: "正确理解“更容易出错”", explanation: "误差机会增加不等于实验必然失败，也不能据此猜测具体 counts。"},
  ],
};

function activeCourseSteps() {
  return COURSE_STEP_OVERRIDES[activeCourseExperiment()?.id]
    || COURSE_STEPS[activeLesson()?.animation]
    || COURSE_STEPS.paths;
}

function stopCourseStepAutoplay() {
  if (courseStepTimer) globalThis.clearInterval(courseStepTimer);
  courseStepTimer = null;
  courseAnimate.textContent = "自动演示";
  courseAnimate.setAttribute("aria-pressed", "false");
}

function renderCourseStep(index, {focus = false} = {}) {
  const steps = activeCourseSteps();
  activeCourseStep = Math.max(0, Math.min(steps.length - 1, index));
  const step = steps[activeCourseStep];
  courseStepCount.textContent = `第 ${activeCourseStep + 1} / ${steps.length} 步`;
  courseStepTitle.textContent = step.title;
  courseStepExplanation.textContent = step.explanation;
  courseStepBack.disabled = activeCourseStep === 0;
  courseStepNext.disabled = activeCourseStep === steps.length - 1;
  courseStepDots.replaceChildren(...steps.map((item, dotIndex) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = dotIndex === activeCourseStep ? "is-active" : "";
    dot.setAttribute("aria-label", `查看第 ${dotIndex + 1} 步：${item.title}`);
    dot.setAttribute("aria-current", dotIndex === activeCourseStep ? "step" : "false");
    dot.addEventListener("click", () => {
      stopCourseStepAutoplay();
      renderCourseStep(dotIndex, {focus: true});
    });
    return dot;
  }));
  const shell = courseAnimationStage.querySelector(".remotion-shell");
  if (shell) globalThis.LoomQMotion?.setStep?.(shell, activeCourseStep);
  if (focus) courseStepTitle.focus({preventScroll: true});
}

function renderCourseAnimation() {
  const lesson = activeLesson();
  const experiment = activeCourseExperiment();
  if (!lesson || !experiment) return;
  stopCourseStepAutoplay();
  activeCourseStep = 0;
  courseAnimationStage.className = "animation-stage";
  const shell = document.createElement("div");
  shell.className = "remotion-shell";
  courseAnimationStage.replaceChildren(shell);
  courseAnimationStage.setAttribute("aria-label", `${lesson.title}：${experiment.plain_title} 的分步过程图`);
  const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
  const compact = globalThis.matchMedia?.("(max-width: 600px)")?.matches ?? false;
  const mount = (evidence = null) => {
    if (!globalThis.LoomQMotion?.mount) {
      shell.innerHTML = '<div class="motion-fallback"><strong>步骤图暂时没有加载</strong><small>课程实验和 L1 计算仍可正常使用。</small></div>';
      return;
    }
    globalThis.LoomQMotion.mount(shell, {experimentId: experiment.id, evidence, reducedMotion, compact, stepIndex: 0});
    globalThis.setTimeout(() => renderCourseStep(0), 0);
  };
  if (lesson.animation !== "noise") {
    mount();
    return;
  }
  requestJson("/api/evidence/hardware/bell", {headers: {}})
    .then((evidence) => {
      hardwareEvidenceCache = evidence;
      if (activeCourseExperiment()?.id === experiment.id) mount(evidence);
    })
    .catch(() => mount(hardwareEvidenceCache));
}

async function runCourseSimulation() {
  const lesson = activeLesson();
  const experiment = activeCourseExperiment();
  if (!lesson || !experiment) return;
  const requestedExperimentId = experiment.id;
  courseError.hidden = true;
  courseResult.setAttribute("aria-busy", "true");
  courseResultStatus.textContent = "正在运行…";
  courseRunCount += 1;
  try {
    const payload = await simulateExperiment(
      lesson.id,
      requestedExperimentId,
      experiment.default_shots,
      `${sessionNonce}-course-${lesson.id}-${courseRunCount}`,
    );
    if (activeCourseExperiment()?.id !== requestedExperimentId) return;
    renderCourseResult(payload);
  } catch (error) {
    if (activeCourseExperiment()?.id !== requestedExperimentId) return;
    courseError.textContent = `实验没有运行成功：${error.message}`;
    courseError.hidden = false;
    courseResultStatus.textContent = "自动运行失败";
  } finally {
    if (activeCourseExperiment()?.id === requestedExperimentId) courseResult.setAttribute("aria-busy", "false");
  }
}

function updateCourseExperimentCopy({autoRun = true} = {}) {
  const lesson = activeLesson();
  const experiment = lesson?.experiments.find((item) => item.id === courseExperiment.value);
  if (!experiment) return;
  courseError.hidden = true;
  renderExperimentCards();
  renderCourseAnimation();
  if (autoRun) runCourseSimulation();
}

function openCourse(index) {
  if (!courseCatalog[index]) return;
  activeCourseIndex = index;
  const lesson = activeLesson();
  courseOrder.textContent = `系统实验 ${lesson.order} / ${courseCatalog.length} · 约 ${lesson.duration_minutes} 分钟`;
  courseTitle.textContent = lesson.title;
  courseSummary.textContent = lesson.summary;
  courseHook.textContent = lesson.hook;
  courseGoal.textContent = lesson.plain_goal;
  courseConcepts.replaceChildren(...lesson.concepts.map((concept) => {
    const item = document.createElement("span");
    const term = document.createElement("strong");
    const explanation = document.createElement("small");
    term.textContent = concept;
    explanation.textContent = CONCEPT_EXPLANATIONS[concept] || "本节使用的量子计算概念。";
    item.append(term, explanation);
    return item;
  }));
  courseExperiment.replaceChildren(...lesson.experiments.map((experiment) => {
    const option = document.createElement("option");
    option.value = experiment.id;
    option.textContent = experiment.plain_title;
    return option;
  }));
  courseExperiment.value = lesson.experiments[0].id;
  courseBack.disabled = index === 0;
  courseSidebarList.querySelectorAll("button").forEach((button, sidebarIndex) => {
    if (sidebarIndex === index) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  courseNext.textContent = index === courseCatalog.length - 1 ? "完成系统实验，返回首页" : "下一节实验";
  updateCourseExperimentCopy();
  showScreen("course", `已进入第 ${lesson.order} 个可操作实验：${lesson.title}`);
}

function renderCourseResult(payload, {scroll = false} = {}) {
  const entries = Object.entries(payload.result.counts).sort(([left], [right]) => left.localeCompare(right));
  const maximum = Math.max(...entries.map(([, count]) => count), 1);
  courseCounts.replaceChildren(...entries.map(([basis, count]) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    const track = document.createElement("i");
    const value = document.createElement("strong");
    label.textContent = basis;
    track.style.setProperty("--agent-size", `${Math.max((count / maximum) * 100, 1)}%`);
    value.textContent = String(count);
    row.append(label, track, value);
    return row;
  }));
  courseCounts.setAttribute("aria-label", entries.map(([basis, count]) => `${basis} 为 ${count} 次`).join("，"));
  courseProbabilities.replaceChildren(...payload.statevector.map((item) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    term.textContent = `|${item.basis}⟩`;
    value.textContent = `${formatNumber(item.probability * 100, 2)}%`;
    row.append(term, value);
    return row;
  }));
  courseExplanation.textContent = payload.experiment.result_hint;
  courseResult.hidden = false;
  courseResultStatus.textContent = "L1 模拟完成";
  if (scroll) courseResult.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function loadCourseCatalog() {
  try {
    const catalog = await requestJson("/api/lessons", { headers: {} });
    courseCatalog = catalog.lessons;
    renderCourseCatalog();
    courseList.setAttribute("aria-busy", "false");
    courseStatus.hidden = true;
  } catch {
    courseList.replaceChildren();
    courseList.setAttribute("aria-busy", "false");
    courseStatus.textContent = "L1 服务未连接：课程与模拟结果均不会使用伪造的替代数据。";
    courseStatus.hidden = false;
  }
}

function updateCourseBackToTop() {
  const visible = currentScreen === "course" && globalThis.scrollY > 640;
  courseBackToTop.classList.toggle("is-visible", visible);
  courseBackToTop.tabIndex = visible ? 0 : -1;
}

function showScreen(name, announcement, {scroll = true} = {}) {
  if (currentScreen === "course" && name !== "course") {
    stopCourseStepAutoplay();
    const shell = courseAnimationStage.querySelector(".remotion-shell");
    if (shell) globalThis.LoomQMotion?.pause?.(shell);
  }
  currentScreen = name;
  courseSidebar.hidden = name !== "course";
  courseBackToTop.hidden = name !== "course";
  screens.forEach((screen) => {
    const active = screen.dataset.screen === name;
    screen.hidden = !active;
    screen.classList.toggle("is-active", active);
  });
  const activeStudioScene = name === "course"
    ? "learn"
    : name === "playground"
      ? "create"
      : name === "history"
        ? "history"
        : "home";
  studioNavButtons.forEach((button) => {
    if (button.dataset.studioNav === activeStudioScene) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const heading = document.querySelector(`[data-screen="${name}"] h1`);
  if (heading) {
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
    heading.removeAttribute("tabindex");
  }
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
  globalThis.dispatchEvent(new CustomEvent("loomq:screen-change", {detail: {name}}));
  liveStatus.textContent = announcement || `已进入${heading?.textContent || "下一步"}`;
  updateCourseBackToTop();
}

function selectedValue(name) {
  return document.querySelector(`input[name="${name}"]:checked`)?.value;
}

function selectPlaygroundMode(mode, prompt = "") {
  const radio = document.querySelector(`input[name="playgroundMode"][value="${mode}"]`);
  if (radio) radio.checked = true;
  if (prompt) playgroundPrompt.value = prompt;
  if (mode === "repair" && !repairQasm.value.trim()) {
    repairQasm.value = `OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];`;
  }
  updatePlaygroundMode();
  clearAgentResult();
  showScreen("playground", "已进入自由实验室，可以从想法生成实验或修复已有实验");
  playgroundPrompt.focus();
}

function playgroundActionLabel(mode = selectedValue("playgroundMode") || "generate") {
  if (mode === "repair") return "让智能体修复并验证";
  if (mode === "execute") return "验证代码并选择运行环境";
  return "让智能体规划并验证";
}

function updatePlaygroundSubmitAvailability() {
  const mode = selectedValue("playgroundMode") || "generate";
  const hasPrompt = playgroundPrompt.value.trim().length > 0;
  const hasQasm = repairQasm.value.trim().length > 0;
  playgroundRun.disabled = mode === "execute"
    ? !hasQasm
    : !hasPrompt || (mode === "repair" && !hasQasm);
  playgroundRun.textContent = playgroundActionLabel(mode);
}

function updatePlaygroundMode() {
  const mode = selectedValue("playgroundMode") || "generate";
  const repairing = mode === "repair";
  const executing = mode === "execute";
  playgroundPromptEditor.hidden = executing;
  promptSuggestions.hidden = mode !== "generate";
  repairEditor.hidden = !(repairing || executing);
  repairQasmLabel.textContent = executing
    ? "粘贴需要执行的 OpenQASM 2.0"
    : "粘贴需要修复的 OpenQASM 2.0";
  playgroundPromptLabel.textContent = repairing
    ? "原本希望这个实验实现什么？"
    : "你希望实验表现出什么现象？";
  playgroundPrompt.placeholder = repairing
    ? "例如：我想保留两枚 qubit 的 Bell 关联，并正确测量它们"
    : "例如：我想让三枚量子硬币每次随机，但测量后总是一起得到 000 或 111";
  updatePlaygroundSubmitAvailability();
}

function profileDetail(profile) {
  const metadata = profile.metadata || {};
  const destination = metadata.backend || metadata.platform_code || metadata.host || "";
  const provider = profile.provider === "originq" ? "本源悟空" : "SpinQ";
  return [provider, destination, profile.source === "system" ? "系统配置" : "用户配置"]
    .filter(Boolean)
    .join(" · ");
}

function qasmQubitWidth(qasm) {
  const match = /\bqreg\s+[A-Za-z_][A-Za-z0-9_]*\s*\[\s*(\d+)\s*\]\s*;/i.exec(qasm);
  return match ? Number.parseInt(match[1], 10) : 0;
}

function renderHardwareProfiles(managing) {
  hardwareProfiles.hidden = false;
  hardwareProfileCount.textContent = `${hardwareProfileCatalog.length} 项`;
  if (!hardwareProfileCatalog.length) {
    const empty = document.createElement("p");
    empty.textContent = "还没有我的真机配置。请先选择“配置我的真机”。";
    hardwareProfileList.replaceChildren(empty);
    return;
  }
  hardwareProfileList.replaceChildren(...hardwareProfileCatalog.map((profile, index) => {
    const card = document.createElement(managing ? "article" : "label");
    card.className = "hardware-profile";
    if (!managing) {
      const radio = document.createElement("input");
      radio.type = "radio";
      radio.name = "hardwareProfile";
      radio.value = profile.id;
      radio.checked = index === 0;
      card.append(radio);
    }
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    const detail = document.createElement("small");
    const badge = document.createElement("span");
    title.textContent = profile.label;
    detail.textContent = profileDetail(profile);
    badge.className = "environment-badge";
    badge.textContent = profile.source === "system" ? "只读" : "可管理";
    copy.append(title, detail);
    card.append(copy, badge);
    if (managing) {
      const actions = document.createElement("span");
      actions.className = "hardware-profile-actions";
      const availableActions = profile.source === "user"
        ? [["view", "查看"], ["delete", "删除"]]
        : [["view", "查看"]];
      for (const [action, text] of availableActions) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button button-quiet";
        button.dataset.profileAction = action;
        button.dataset.profileId = profile.id;
        button.textContent = text;
        actions.append(button);
      }
      card.append(actions);
      const metadata = document.createElement("dl");
      metadata.className = "hardware-profile-metadata";
      metadata.hidden = true;
      const safeFields = [
        ["backend", "后端"],
        ["host", "服务地址"],
        ["platform_code", "平台代码"],
        ["username", "账号"],
      ];
      for (const [key, label] of safeFields) {
        if (!profile.metadata?.[key]) continue;
        const row = document.createElement("div");
        const term = document.createElement("dt");
        const value = document.createElement("dd");
        term.textContent = label;
        value.textContent = profile.metadata[key];
        row.append(term, value);
        metadata.append(row);
      }
      card.append(metadata);
    }
    return card;
  }));
}

function renderEnvironmentCatalog() {
  const requestedKind = selectedValue("executionKind") || "simulator";
  const configuring = requestedKind === "custom";
  const selectingHardware = requestedKind === "qpu";
  hardwareConfig.hidden = !configuring;
  environmentList.hidden = configuring || selectingHardware;
  hardwareProfiles.hidden = !(configuring || selectingHardware);
  if (configuring || selectingHardware) {
    renderHardwareProfiles(configuring);
    environmentResult.hidden = true;
    environmentRun.disabled = configuring || !hardwareProfileCatalog.length;
    environmentRun.textContent = configuring ? "选择“使用已配置真机”后运行" : "提交到所选真机";
    return;
  }
  const available = environmentCatalog.environments.filter((item) => item.kind === "simulator");
  if (!available.length) {
    environmentList.replaceChildren();
    const empty = document.createElement("p");
    empty.textContent = "没有可用的本地模拟环境。";
    environmentList.append(empty);
  } else {
    environmentList.replaceChildren(...available.map((environment, index) => {
      const label = document.createElement("label");
      label.className = "environment-option";
      const radio = document.createElement("input");
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      const detail = document.createElement("small");
      const badge = document.createElement("span");
      radio.type = "radio";
      radio.name = "availableEnvironment";
      radio.value = environment.id;
      radio.checked = index === 0;
      name.textContent = environment.name;
      detail.textContent = `${environment.detail} ${environment.queue} · ${environment.cost}`;
      badge.className = "environment-badge";
      badge.textContent = "本地可用";
      copy.append(name, detail);
      label.append(radio, copy, badge);
      return label;
    }));
  }
  environmentResult.hidden = true;
  environmentRun.disabled = !available.length;
  environmentRun.textContent = "在所选环境运行";
}

async function loadEnvironments() {
  environmentStatus.textContent = "正在从本地服务检查 SDK 和凭据状态…";
  try {
    [environmentCatalog, hardwareProfileCatalog] = await Promise.all([
      requestJson("/api/environments", { headers: {} }),
      requestJson("/api/hardware/profiles", { headers: {} }),
    ]);
    if (!Array.isArray(hardwareProfileCatalog)) {
      hardwareProfileCatalog = hardwareProfileCatalog.profiles || [];
    }
    renderEnvironmentCatalog();
    environmentStatus.textContent = `已发现 ${hardwareProfileCatalog.length} 份真机配置；密钥没有发送到浏览器。`;
  } catch (error) {
    environmentList.replaceChildren();
    environmentStatus.textContent = `无法读取本机环境：${error.message}`;
  }
  await loadHardwareHistory();
}

function renderEnvironmentCounts(payload) {
  const result = payload.result || payload;
  const entries = Object.entries(result.counts)
    .sort(([left], [right]) => left.localeCompare(right));
  const maximum = Math.max(...entries.map(([, count]) => count), 1);
  environmentCounts.replaceChildren(...entries.map(([basis, count]) => {
    const item = document.createElement("div");
    const label = document.createElement("span");
    const track = document.createElement("i");
    const value = document.createElement("strong");
    label.textContent = basis;
    track.style.setProperty("--agent-size", `${Math.max((count / maximum) * 100, 1)}%`);
    value.textContent = String(count);
    item.append(label, track, value);
    return item;
  }));
  const environmentName = payload.environment?.name || payload.platform || "所选真机";
  environmentCounts.setAttribute(
    "aria-label",
    `${environmentName}：${entries.map(([basis, count]) => `${basis} 为 ${count} 次`).join("，")}`,
  );
  environmentResultBadge.textContent = payload.environment?.kind === "simulator" ? "本地结果" : "真机结果";
  environmentProvenance.textContent = `${payload.engine || payload.backend} · ${result.job_id}`;
  environmentResult.hidden = false;
}

const HARDWARE_STATUS_LABELS = {
  pending: "等待启动",
  running: "执行中",
  completed: "已完成",
  failed: "失败",
  interrupted: "本地轮询中断",
};

function elapsedText(timestamp, endTimestamp = "") {
  const started = Date.parse(timestamp || "");
  if (!Number.isFinite(started)) return "—";
  const parsedEnd = Date.parse(endTimestamp || "");
  const ended = Number.isFinite(parsedEnd) ? parsedEnd : Date.now();
  const seconds = Math.max(0, Math.floor((ended - started) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours
    ? `${hours} 小时 ${minutes} 分`
    : minutes
      ? `${minutes} 分 ${remainder} 秒`
      : `${remainder} 秒`;
}

function renderActiveHardwareJob(job) {
  activeHardwareJob = job;
  hardwareCurrent.hidden = false;
  hardwareCurrentState.textContent = HARDWARE_STATUS_LABELS[job.status] || job.status;
  hardwareCurrentTaskId.textContent = job.task_id;
  hardwareCurrentProviderId.textContent = job.provider_job_id || "等待平台返回";
  hardwareCurrentStage.textContent = job.stage_message || "正在读取任务状态。";
  hardwareCurrentElapsed.textContent = elapsedText(
    job.started_at || job.created_at,
    job.completed_at,
  );
  environmentStatus.textContent = job.status === "running" || job.status === "pending"
    ? `${job.stage_message || "真机任务处理中。"} 已等待 ${hardwareCurrentElapsed.textContent}。`
    : job.stage_message || "";
  globalThis.clearInterval(hardwareElapsedTimer);
  if (job.status === "running" || job.status === "pending") {
    hardwareElapsedTimer = globalThis.setInterval(() => {
      if (!activeHardwareJob) return;
      hardwareCurrentElapsed.textContent = elapsedText(
        activeHardwareJob.started_at || activeHardwareJob.created_at,
      );
      environmentStatus.textContent = `${activeHardwareJob.stage_message || "真机任务处理中。"} 已等待 ${hardwareCurrentElapsed.textContent}。`;
    }, 1000);
  }
}

function appendTaskFact(list, label, value, code = false) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  const content = code ? document.createElement("code") : document.createElement("span");
  content.textContent = value || "—";
  detail.append(content);
  row.append(term, detail);
  list.append(row);
}

function renderHardwareHistory(jobs) {
  if (!jobs.length) {
    const empty = document.createElement("p");
    empty.textContent = "暂无真机执行记录。";
    hardwareHistoryList.replaceChildren(empty);
    return;
  }
  hardwareHistoryList.replaceChildren(...jobs.map((job) => {
    const card = document.createElement("article");
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const badge = document.createElement("span");
    const meta = document.createElement("small");
    const facts = document.createElement("dl");
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const body = document.createElement("div");
    card.className = "hardware-history-item";
    heading.className = "hardware-history-heading";
    badge.className = `hardware-history-status is-${job.status}`;
    facts.className = "hardware-task-facts";
    details.dataset.taskId = job.task_id;
    body.className = "hardware-history-detail";
    title.textContent = job.profile_label;
    badge.textContent = HARDWARE_STATUS_LABELS[job.status] || job.status;
    meta.textContent = new Date(job.created_at).toLocaleString("zh-CN", {hour12: false});
    summary.textContent = "查看代码与结果";
    body.textContent = "正在读取记录…";
    appendTaskFact(facts, "平台任务 ID", job.provider_job_id, true);
    appendTaskFact(facts, "阶段", job.stage_message);
    appendTaskFact(
      facts,
      "耗时",
      elapsedText(job.started_at || job.created_at, job.completed_at),
    );
    heading.append(title, badge);
    details.append(summary, body);
    card.append(heading, meta, facts, details);
    return card;
  }));
}

async function loadHardwareHistory() {
  hardwareHistoryRefresh.disabled = true;
  try {
    const payload = await requestJson("/api/hardware/jobs", {headers: {}});
    renderHardwareHistory(Array.isArray(payload.jobs) ? payload.jobs : []);
  } catch (error) {
    const message = document.createElement("p");
    message.className = "feedback";
    message.textContent = `无法读取真机记录：${error.message}`;
    hardwareHistoryList.replaceChildren(message);
  } finally {
    hardwareHistoryRefresh.disabled = false;
  }
}

function hardwareCountSeries(job) {
  const counts = job.result?.counts || {};
  const observed = Object.keys(counts);
  const width = Number(job.qubits) || Math.max(0, ...observed.map((basis) => basis.length));
  const basisStates = width > 0 && width <= 5
    ? Array.from({length: 2 ** width}, (_, index) => index.toString(2).padStart(width, "0"))
    : observed.sort();
  return basisStates.map((basis) => ({
    basis,
    count: Number(counts[basis] || 0),
  }));
}

function appendResultMetric(list, label, value) {
  const metric = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value;
  metric.append(term, detail);
  list.append(metric);
}

function renderHardwareResult(job) {
  const panel = document.createElement("section");
  const heading = document.createElement("div");
  const title = document.createElement("h4");
  const summary = document.createElement("dl");
  const chart = document.createElement("div");
  const grid = document.createElement("span");
  const bars = document.createElement("div");
  const series = hardwareCountSeries(job);
  const total = series.reduce((sum, item) => sum + item.count, 0);
  const maximum = Math.max(1, ...series.map((item) => item.count));
  const dominant = series.reduce(
    (best, item) => item.count > best.count ? item : best,
    {basis: "—", count: -1},
  );
  panel.className = "hardware-result-panel";
  heading.className = "hardware-result-heading";
  summary.className = "hardware-result-summary";
  chart.className = "hardware-result-chart";
  grid.className = "hardware-result-grid";
  bars.className = "hardware-result-bars";
  bars.style.setProperty("--column-count", String(Math.max(1, series.length)));
  title.textContent = "运行结果";
  appendResultMetric(summary, "测量次数", String(job.result?.shots || job.shots || total));
  appendResultMetric(summary, "有效输出", `${series.filter((item) => item.count > 0).length} / ${series.length}`);
  appendResultMetric(summary, "主导态", dominant.count >= 0 ? `|${dominant.basis}⟩` : "—");
  for (const item of series) {
    const column = document.createElement("div");
    const count = document.createElement("strong");
    const track = document.createElement("span");
    const bar = document.createElement("i");
    const basis = document.createElement("code");
    const percent = document.createElement("small");
    const ratio = item.count / maximum;
    column.className = "hardware-result-column";
    track.className = "hardware-result-track";
    bar.style.setProperty("--bar-height", `${ratio * 100}%`);
    count.textContent = String(item.count);
    basis.textContent = `|${item.basis}⟩`;
    percent.textContent = total ? `${formatNumber((item.count / total) * 100, 1)}%` : "0%";
    track.append(bar);
    column.append(count, track, basis, percent);
    bars.append(column);
  }
  chart.setAttribute("role", "img");
  chart.setAttribute(
    "aria-label",
    series.map((item) => `${item.basis} 为 ${item.count} 次`).join("，"),
  );
  chart.append(grid, bars);
  heading.append(title, summary);
  panel.append(heading, chart);
  return panel;
}

async function hydrateHardwareHistory(details) {
  if (details.dataset.loaded === "true" || !details.open) return;
  const body = details.querySelector(".hardware-history-detail");
  try {
    const job = await requestJson(
      `/api/hardware/jobs/${encodeURIComponent(details.dataset.taskId)}`,
      {headers: {}},
    );
    const fragments = [];
    if (job.result?.counts) {
      fragments.push(renderHardwareResult(job));
    } else if (job.error) {
      const error = document.createElement("p");
      error.className = "feedback";
      error.textContent = job.error;
      fragments.push(error);
    }
    const codeHeading = document.createElement("h4");
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    codeHeading.textContent = "执行代码";
    code.textContent = job.qasm || "未保存执行代码";
    pre.append(code);
    fragments.push(codeHeading, pre);
    body.replaceChildren(...fragments);
    details.dataset.loaded = "true";
  } catch (error) {
    body.textContent = `无法读取记录：${error.message}`;
  }
}

async function configureHardware(event) {
  event.preventDefault();
  const platform = hardwarePlatform.value;
  const credentials = platform === "originq"
    ? {token: originqToken.value, backend: originqBackend.value}
    : {
        username: spinqUsername.value,
        private_key: spinqPrivateKey.files[0] ? await spinqPrivateKey.files[0].text() : "",
        host: spinqHost.value,
        platform_code: spinqPlatformCode.value,
      };
  if (!hardwareLabel.value.trim()) {
    hardwareConfigStatus.textContent = "请先填写配置名称。";
    hardwareLabel.focus();
    return;
  }
  if (!Object.values(credentials).every(Boolean)) {
    hardwareConfigStatus.textContent = "新建配置需要完整凭据。";
    return;
  }
  hardwareSave.disabled = true;
  hardwareConfigStatus.textContent = "正在创建本次服务会话配置…";
  try {
    const body = {
      label: hardwareLabel.value.trim(),
      provider: platform,
      credentials,
    };
    await requestJson("/api/hardware/profiles", {
      method: "POST",
      body: JSON.stringify(body),
    });
    resetHardwareForm();
    hardwareConfigStatus.textContent = "配置仅在本次服务会话中可用；密钥不会写入磁盘。";
    await loadEnvironments();
  } catch (error) {
    hardwareConfigStatus.textContent = `配置失败：${error.message}`;
  } finally {
    hardwareSave.disabled = false;
  }
}

function resetHardwareForm() {
  hardwareLabel.value = "";
  originqToken.value = "";
  originqBackend.value = "WK_C180_2";
  spinqUsername.value = "";
  spinqPrivateKey.value = "";
  spinqHost.value = "";
  spinqPlatformCode.value = "";
  updateHardwarePlatformFields();
}

async function deleteHardwareProfile(profileId) {
  const profile = hardwareProfileCatalog.find((item) => item.id === profileId);
  if (!profile || profile.source !== "user") return;
  if (!globalThis.confirm(`删除配置“${profile.label}”？此操作不会取消已提交的真机任务。`)) return;
  hardwareConfigStatus.textContent = "正在删除配置…";
  try {
    await requestJson(`/api/hardware/profiles/${encodeURIComponent(profileId)}`, {
      method: "DELETE",
    });
    resetHardwareForm();
    hardwareConfigStatus.textContent = "配置已删除。";
    await loadEnvironments();
  } catch (error) {
    hardwareConfigStatus.textContent = `删除失败：${error.message}`;
  }
}

function updateHardwarePlatformFields() {
  const originq = hardwarePlatform.value === "originq";
  originqFields.hidden = !originq;
  spinqFields.hidden = originq;
}

async function pollHardwareJob(taskId) {
  globalThis.clearTimeout(hardwarePollTimer);
  try {
    const payload = await requestJson(`/api/hardware/jobs/${encodeURIComponent(taskId)}`, {headers: {}});
    renderActiveHardwareJob(payload);
    if (payload.status === "completed") {
      renderEnvironmentCounts(payload.result || payload);
      environmentStatus.textContent = "真机任务已完成。";
      environmentRun.disabled = false;
      await loadHardwareHistory();
      return;
    }
    if (payload.status === "failed") {
      environmentStatus.textContent = `真机任务失败：${payload.error || "平台未返回结果"}`;
      environmentRun.disabled = false;
      await loadHardwareHistory();
      return;
    }
    if (payload.status === "interrupted") {
      environmentStatus.textContent = payload.stage_message;
      environmentRun.disabled = false;
      await loadHardwareHistory();
      return;
    }
    hardwarePollTimer = globalThis.setTimeout(() => pollHardwareJob(taskId), 5000);
  } catch (error) {
    environmentStatus.textContent = `无法读取真机任务状态：${error.message}`;
    environmentRun.disabled = false;
  }
}

async function submitHardwareJob() {
  const selected = pendingHardwareEnvironment;
  const qasm = agentQasm.textContent.trim();
  pendingHardwareEnvironment = null;
  if (!selected || !qasm) return;
  environmentRun.disabled = true;
  environmentResult.hidden = true;
  environmentStatus.textContent = `正在向 ${selected.name} 提交任务…`;
  try {
    const payload = await requestJson("/api/hardware/jobs", {
      method: "POST",
      body: JSON.stringify({
        environment_id: selected.id,
        profile_id: selected.profileId,
        qasm,
        shots: 1024,
        confirm: true,
        confirmation_token: selected.id === "originq_wukong"
          ? "ORIGINQ_WUKONG_180_REAL_QPU"
          : "SPINQ_REAL_QPU",
      }),
    });
    renderActiveHardwareJob(payload);
    await loadHardwareHistory();
    await pollHardwareJob(payload.task_id);
  } catch (error) {
    environmentStatus.textContent = `真机提交失败：${error.message}`;
    environmentRun.disabled = false;
  }
}

async function runSelectedEnvironment() {
  const requestedKind = selectedValue("executionKind") || "simulator";
  const selectedId = requestedKind === "qpu"
    ? selectedValue("hardwareProfile")
    : selectedValue("availableEnvironment");
  if (!selectedId) {
    environmentStatus.textContent = "当前没有可运行的环境。";
    return;
  }
  if (requestedKind === "qpu") {
    const profile = hardwareProfileCatalog.find((item) => item.id === selectedId);
    if (!profile) {
      environmentStatus.textContent = "请选择一份真机配置。";
      return;
    }
    const qasm = agentQasm.textContent.trim();
    if (!qasm) {
      environmentStatus.textContent = "请先生成或粘贴代码，并通过 L1 验证后再提交真机。";
      playgroundPrompt.focus();
      return;
    }
    const qubitWidth = qasmQubitWidth(qasm);
    if (
      profile.provider === "spinq"
      && profile.metadata?.platform_code === "gemini_vp"
      && qubitWidth > 2
    ) {
      environmentStatus.textContent = `当前电路需要 ${qubitWidth} qubit，但 SpinQ gemini_vp 真机最多支持 2 qubit。`;
      return;
    }
    pendingHardwareEnvironment = {
      id: profile.environment_id,
      name: profile.label,
      profileId: profile.id,
    };
    hardwareConfirmPlatform.textContent = `${profile.label} · ${profileDetail(profile)}`;
    hardwareConfirm.showModal();
    return;
  }
  const selected = environmentCatalog.environments.find((item) => item.id === selectedId);
  const qasm = agentQasm.textContent.trim();
  if (!qasm) {
    environmentStatus.textContent = "请先生成或粘贴代码，并通过 L1 验证后再选择环境运行。";
    playgroundPrompt.focus();
    return;
  }
  environmentRun.disabled = true;
  environmentResult.hidden = true;
  environmentStatus.textContent = `正在 ${selected.name} 上运行当前电路…`;
  try {
    const payload = await requestJson("/api/run-environment", {
      method: "POST",
      body: JSON.stringify({
        environment_id: selectedId,
        qasm,
        shots: 1024,
      }),
    });
    renderEnvironmentCounts(payload);
    environmentStatus.textContent = `${selected.name} 已完成 1024 shots。`;
  } catch (error) {
    environmentStatus.textContent = `运行失败：${error.message}`;
  } finally {
    environmentRun.disabled = false;
  }
}

function openCourseCatalog() {
  showScreen("welcome", "已打开课程目录", {scroll: false});
  courseMap.open = true;
  courseMap.scrollIntoView({behavior: "smooth", block: "start"});
  courseMap.querySelector("summary")?.focus({preventScroll: true});
}

studioNavButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const destination = button.dataset.studioNav;
    if (destination === "home") showScreen("welcome", "回到 LoomQ Studio 首页");
    if (destination === "learn" && courseCatalog.length) openCourse(activeCourseIndex);
    if (destination === "create") selectPlaygroundMode("generate");
    if (destination === "history") {
      showScreen("history", "已打开本机真机执行记录");
      loadHardwareHistory();
    }
  });
});

startButton.addEventListener("click", openCourseCatalog);

customIdeaButton.addEventListener("click", () => selectPlaygroundMode("generate"));

courseExperiment.addEventListener("change", () => updateCourseExperimentCopy({autoRun: true}));
courseAnimate.addEventListener("click", () => {
  if (courseStepTimer) {
    stopCourseStepAutoplay();
    return;
  }
  if (activeCourseStep === activeCourseSteps().length - 1) renderCourseStep(0);
  courseAnimate.textContent = "暂停演示";
  courseAnimate.setAttribute("aria-pressed", "true");
  courseStepTimer = globalThis.setInterval(() => {
    if (activeCourseStep >= activeCourseSteps().length - 1) {
      stopCourseStepAutoplay();
      return;
    }
    renderCourseStep(activeCourseStep + 1);
  }, 2600);
});
courseStepBack.addEventListener("click", () => {
  stopCourseStepAutoplay();
  renderCourseStep(activeCourseStep - 1, {focus: true});
});
courseStepNext.addEventListener("click", () => {
  stopCourseStepAutoplay();
  renderCourseStep(activeCourseStep + 1, {focus: true});
});

courseBack.addEventListener("click", () => {
  if (activeCourseIndex > 0) openCourse(activeCourseIndex - 1);
});
courseNext.addEventListener("click", () => {
  if (activeCourseIndex >= courseCatalog.length - 1) openCourseCatalog();
  else openCourse(activeCourseIndex + 1);
});
courseBackToTop.addEventListener("click", () => {
  globalThis.scrollTo({top: 0, behavior: "smooth"});
});
globalThis.addEventListener("scroll", updateCourseBackToTop, {passive: true});

document.querySelectorAll("input[name='playgroundMode']").forEach((input) => {
  input.addEventListener("change", () => {
    lastAgentRequest = null;
    updatePlaygroundMode();
    clearAgentResult();
  });
});

document.querySelectorAll("[data-suggestion]").forEach((button) => {
  button.addEventListener("click", () => {
    selectPlaygroundMode(button.dataset.suggestionMode || "generate", button.dataset.suggestion);
  });
});

playgroundPrompt.addEventListener("input", () => {
  updatePlaygroundSubmitAvailability();
  agentError.hidden = true;
});

repairQasm.addEventListener("input", () => {
  updatePlaygroundSubmitAvailability();
  agentError.hidden = true;
});

playgroundForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = selectedValue("playgroundMode") || "generate";
  if (mode === "execute") {
    await runExistingQasm(repairQasm.value);
    return;
  }
  let prompt = playgroundPrompt.value;
  if (mode === "repair") {
    if (!repairQasm.value.trim()) {
      agentError.textContent = "请粘贴需要修复的 OpenQASM 2.0 代码。";
      agentError.hidden = false;
      playgroundOutput.hidden = false;
      repairQasm.focus();
      return;
    }
    prompt = `${prompt.trim()}\n\n需要修复的 OpenQASM 2.0：\n${repairQasm.value.trim()}`;
  }
  await runAgentTask(mode, prompt);
});

playgroundReset.addEventListener("click", () => {
  document.querySelector("input[name='playgroundMode'][value='generate']").checked = true;
  playgroundPrompt.value = "";
  repairQasm.value = "";
  updatePlaygroundMode();
  lastAgentRequest = null;
  clearAgentResult();
  playgroundPrompt.focus();
});

document.querySelectorAll("input[name='executionKind']").forEach((input) => {
  input.addEventListener("change", () => {
    renderEnvironmentCatalog();
    environmentStatus.textContent = input.value === "qpu"
      ? ""
      : "已按你的用途更新可选环境。";
  });
});

environmentRefresh.addEventListener("click", loadEnvironments);
environmentRun.addEventListener("click", runSelectedEnvironment);
hardwareHistoryRefresh.addEventListener("click", loadHardwareHistory);
hardwareHistoryList.addEventListener("toggle", (event) => {
  if (event.target instanceof HTMLDetailsElement) hydrateHardwareHistory(event.target);
}, true);
hardwareConfig.addEventListener("submit", configureHardware);
hardwarePlatform.addEventListener("change", updateHardwarePlatformFields);
hardwareProfileList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-profile-action]");
  if (!button) return;
  if (button.dataset.profileAction === "view") {
    const metadata = button.closest(".hardware-profile")?.querySelector(".hardware-profile-metadata");
    if (metadata) {
      metadata.hidden = !metadata.hidden;
      button.textContent = metadata.hidden ? "查看" : "收起";
    }
  }
  if (button.dataset.profileAction === "delete") deleteHardwareProfile(button.dataset.profileId);
});
hardwareConfirm.addEventListener("close", () => {
  if (hardwareConfirm.returnValue === "confirm") submitHardwareJob();
  else pendingHardwareEnvironment = null;
});

agentRetry.addEventListener("click", async () => {
  if (!lastAgentRequest) return;
  if (lastAgentRequest.mode === "execute") await runExistingQasm(lastAgentRequest.qasm);
  else await runAgentTask(lastAgentRequest.mode, lastAgentRequest.prompt);
});

function adoptAgentProposal() {
  if (!agentQasm.textContent.trim()) return;
  document.querySelector('input[name="playgroundMode"][value="repair"]').checked = true;
  repairQasm.value = agentQasm.textContent;
  playgroundPrompt.value = "保留这份已验证电路的目标，帮我继续解释或修改。";
  updatePlaygroundMode();
  playgroundRun.disabled = false;
  repairEditor.scrollIntoView({ behavior: "smooth", block: "center" });
  repairQasm.focus();
  agentStatus.textContent = "已采用为草稿，尚未重新运行";
  agentAdopt.hidden = true;
}

agentAdopt.addEventListener("click", adoptAgentProposal);

agentCopy.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(agentQasm.textContent);
    agentCopy.textContent = "已复制";
    window.setTimeout(() => { agentCopy.textContent = "复制代码"; }, 1200);
  } catch {
    agentError.textContent = "浏览器未允许复制。代码仍保留在页面中，可以手动选择。";
    agentError.hidden = false;
  }
});

async function runExistingQasm(qasm) {
  const value = qasm.trim();
  if (!value) {
    agentError.textContent = "请粘贴需要执行的 OpenQASM 2.0 代码。";
    agentError.hidden = false;
    playgroundOutput.hidden = false;
    repairQasm.focus();
    return;
  }
  lastAgentRequest = {mode: "execute", qasm: value};
  environmentChooser.hidden = true;
  environmentResult.hidden = true;
  environmentStatus.textContent = "";
  playgroundOutput.hidden = false;
  agentError.hidden = true;
  agentResultContent.hidden = true;
  agentResultTitle.textContent = "代码验证结果";
  agentStatus.textContent = "L1 正在解析";
  playgroundRun.disabled = true;
  agentRetry.disabled = true;
  playgroundRun.textContent = "正在验证代码…";
  try {
    const payload = await requestJson("/api/validate-qasm", {
      method: "POST",
      body: JSON.stringify({qasm: value}),
    });
    const validation = payload.validation;
    agentResultContent.hidden = false;
    agentProposal.hidden = true;
    agentAdopt.hidden = true;
    agentProposalChecks.replaceChildren();
    agentAnswerTitle.textContent = "L1 验证";
    agentAnswer.textContent = `${validation.qubits} qubit · ${validation.operations} 个操作 · ${validation.measurements} 个测量`;
    agentCodeBlock.hidden = false;
    agentQasm.textContent = payload.qasm;
    agentStatus.textContent = "OpenQASM 2.0 已解析 · L1 验证通过";
    environmentChooser.hidden = false;
    playgroundOutput.scrollIntoView({behavior: "smooth", block: "nearest"});
  } catch (error) {
    agentStatus.textContent = "代码未通过验证";
    agentError.textContent = `${error.message} 已保留代码，可修改后重试。`;
    agentError.hidden = false;
  } finally {
    agentRetry.disabled = false;
    updatePlaygroundSubmitAvailability();
  }
}

async function runAgentTask(mode, prompt) {
  const value = prompt.trim();
  if (!value) {
    agentError.textContent = "请先描述目标；也可以选择上方任一示例。";
    agentError.hidden = false;
    playgroundOutput.hidden = false;
    playgroundPrompt.focus();
    return;
  }
  lastAgentRequest = { mode, prompt: value };
  environmentChooser.hidden = true;
  environmentResult.hidden = true;
  environmentStatus.textContent = "";
  playgroundOutput.hidden = false;
  agentError.hidden = true;
  agentResultContent.hidden = true;
  agentResultTitle.textContent = "智能体生成结果";
  agentStatus.textContent = "智能体分析中";
  playgroundRun.disabled = true;
  agentRetry.disabled = true;
  playgroundRun.textContent = "分析并验证中…";
  try {
    const payload = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({ mode, prompt: value }),
    });
    renderAgentResult(payload);
    const modelLabel = payload.model || "配置的 LLM";
    agentStatus.textContent = payload.simulation
      ? `${modelLabel} 生成 · L1 验证通过`
      : `${modelLabel} · 约束筛选完成`;
    playgroundOutput.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    agentStatus.textContent = "需要处理";
    agentError.textContent = `${friendlyAgentError(error.message)} 已保留你的输入，可检查配置后重试。`;
    agentError.hidden = false;
  } finally {
    agentRetry.disabled = false;
    updatePlaygroundSubmitAvailability();
  }
}

function friendlyAgentError(message) {
  if (message.includes("missing required LoomQ L2 environment variable")) {
    return "模型服务尚未连接。请在服务端配置 LOOMQ_LLM_BASE_URL、LOOMQ_LLM_API_KEY 和 LOOMQ_LLM_MODEL。";
  }
  if (message.includes("timeout")) {
    return "模型服务响应超时，本次没有提交任何真机任务。";
  }
  return message;
}

function renderAgentResult(payload) {
  agentResultContent.hidden = false;
  agentResultTitle.textContent = "智能体生成结果";
  agentAnswerTitle.textContent = "结论";
  const hasProposal = Boolean(payload.qasm);
  const modelLabel = payload.model || "配置的 LLM";
  agentProposal.hidden = !hasProposal;
  agentAdopt.hidden = !hasProposal;
  agentProposalSummary.textContent = hasProposal
    ? `${modelLabel} 给出电路草稿，随后由 L1 解析并模拟验证。`
    : `${modelLabel} 完成了这次约束分析。`;
  agentProposalChecks.replaceChildren(...(hasProposal ? ["OpenQASM 2.0 已解析", payload.simulation ? "L1 模拟与 counts 已生成" : "本次不需要模拟"] : []).map((text) => { const item = document.createElement("li"); item.textContent = text; return item; }));
  agentAnswer.textContent = payload.answer;
  agentCodeBlock.hidden = !payload.qasm;
  agentQasm.textContent = payload.qasm || "";
  environmentChooser.hidden = !(payload.qasm && payload.simulation);
}

function clearAgentResult() {
  playgroundOutput.hidden = true;
  agentError.hidden = true;
  agentResultContent.hidden = true;
  agentStatus.textContent = "等待任务";
  agentResultTitle.textContent = "智能体生成结果";
  agentAnswerTitle.textContent = "结论";
  agentAnswer.textContent = "";
  agentQasm.textContent = "";
  agentCodeBlock.hidden = true;
  agentProposal.hidden = true;
  agentAdopt.hidden = true;
  agentRetry.disabled = !lastAgentRequest;
  environmentChooser.hidden = true;
  environmentResult.hidden = true;
  hardwareCurrent.hidden = true;
  environmentStatus.textContent = "";
  pendingHardwareEnvironment = null;
}

document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => showScreen(button.dataset.back, "已返回上一步，之前的选择仍保留"));
});

brandHome.addEventListener("click", (event) => {
  event.preventDefault();
  if (currentScreen === "welcome") return;
  showScreen("welcome", "已返回开始页，当前选择仍保留");
});

function setTheme(theme, persist = true) {
  const nextTheme = theme === "light" ? "light" : "dark";
  const isLight = nextTheme === "light";
  document.documentElement.dataset.theme = nextTheme;
  themeToggle.setAttribute("aria-pressed", String(isLight));
  themeToggle.setAttribute("aria-label", isLight ? "切换到深色模式" : "切换到浅色模式");
  themeToggle.querySelector("span").textContent = isLight ? "☾" : "☼";
  themeToggle.querySelector("b").textContent = isLight ? "深色模式" : "浅色模式";
  if (persist) globalThis.localStorage?.setItem("loomq-theme", nextTheme);
}

themeToggle.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  setTheme(nextTheme);
  liveStatus.textContent = `已切换到${nextTheme === "light" ? "浅色" : "深色"}模式`;
});

setTheme(document.documentElement.dataset.theme, false);
loadCourseCatalog();
loadEnvironments();
