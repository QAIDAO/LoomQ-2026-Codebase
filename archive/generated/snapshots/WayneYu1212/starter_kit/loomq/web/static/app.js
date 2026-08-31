(function () {
  'use strict';

  var form = document.querySelector('#experiment-form');
  var promptField = document.querySelector('#prompt');
  var targetField = document.querySelector('#target');
  var shotsField = document.querySelector('#shots');
  var runButton = document.querySelector('#run-button');
  var formStatus = document.querySelector('#form-status');
  var launchNotice = document.querySelector('#launch-notice');
  var runtimeStatus = document.querySelector('#runtime-status');
  var runtimeStatusCopy = document.querySelector('#runtime-status-copy');
  var backendAvailabilityCopy = document.querySelector('#backend-availability-copy');
  var hSingleRun = document.querySelector('#h-single-run');
  var hShotsRun = document.querySelector('#h-shots-run');
  var hSingleResult = document.querySelector('#h-single-result');
  var hZeroBar = document.querySelector('#h-zero-bar');
  var hOneBar = document.querySelector('#h-one-bar');
  var hZeroCount = document.querySelector('#h-zero-count');
  var hOneCount = document.querySelector('#h-one-count');
  var cnotRuleChoices = [].slice.call(document.querySelectorAll('.cnot-rule-choice'));
  var cnotRuleResult = document.querySelector('#cnot-rule-result');
  var cnotControlState = document.querySelector('#cnot-control-state');
  var cnotTargetState = document.querySelector('#cnot-target-state');
  var bellOneShot = document.querySelector('#bell-one-shot');
  var bellAutoShots = document.querySelector('#bell-auto-shots');
  var bellShotResult = document.querySelector('#bell-shot-result');
  var bellZeroBar = document.querySelector('#bell-zero-bar');
  var bellOneBar = document.querySelector('#bell-one-bar');
  var bellZeroCount = document.querySelector('#bell-zero-count');
  var bellOneCount = document.querySelector('#bell-one-count');
  var outcomeDelightStats = [].slice.call(document.querySelectorAll('[data-outcome-delight]'));
  var circuitInspectSteps = [].slice.call(document.querySelectorAll('.circuit-inspect-step'));
  var circuitInspectState = document.querySelector('#circuit-inspect-state');
  var circuitInspectCopy = document.querySelector('#circuit-inspect-copy');
  var workspace = document.querySelector('#workspace');
  var resultPanel = document.querySelector('#result-panel');
  var verificationPanel = document.querySelector('#verification-panel');
  var circuitPanel = document.querySelector('#circuit-panel');
  var qasmDisclosure = document.querySelector('#qasm-disclosure');
  var circuitView = document.querySelector('#circuit-view');
  var circuitNote = document.querySelector('#circuit-note');
  var verificationWrap = document.querySelector('.verification-wrap');
  var verificationList = document.querySelector('#verification-list');
  var countsChart = document.querySelector('#counts-chart');
  var countsTableBody = document.querySelector('#counts-table-body');
  var resultTotal = document.querySelector('#result-total');
  var explanation = document.querySelector('#explanation');
  var recommendation = document.querySelector('#recommendation');
  var qasmCode = document.querySelector('#qasm-code');
  var runMeta = document.querySelector('#run-meta');
  var resultBoundaryCopy = document.querySelector('#result-boundary-copy');
  var qubitStoryLine = document.querySelector('#qubit-story-line');
  var bellStoryLine = document.querySelector('#bell-story-line');
  var quickActionButtons = [].slice.call(document.querySelectorAll('.quick-action'));
  var agentPromptCards = [].slice.call(document.querySelectorAll('.agent-prompt-card'));
  var focusBackendAction = document.querySelector('#focus-backend-action');
  var scrollTutorials = [].slice.call(document.querySelectorAll('.scroll-tutorial'));
  var stepperSteps = [].slice.call(document.querySelectorAll('.stepper-step'));
  var stepperLabel = document.querySelector('#stepper-label');
  var stepperTitle = document.querySelector('#stepper-title');
  var stepperDescription = document.querySelector('#stepper-description');
  var stepperProgressFill = document.querySelector('#stepper-progress-fill');
  var stepperPrev = document.querySelector('#stepper-prev');
  var stepperNext = document.querySelector('#stepper-next');
  var stepperFinish = document.querySelector('#stepper-finish');
  var lineSidebar = document.querySelector('.line-sidebar');
  var lineSidebarItems = [].slice.call(document.querySelectorAll('.line-sidebar__item'));
  var languageToggle = document.querySelector('#language-toggle');
  var scrollFloatHeadings = [].slice.call(document.querySelectorAll('[data-scroll-float]'));
  var strokeTextSvg = document.querySelector('.stroke-text__svg');
  var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  var isReduced = motionQuery.matches;
  var isStaticFile = window.location.protocol === 'file:';
  var localServiceUrl = 'http:' + '//127.0.0.1:8765/';
  var backendAvailabilityReady = isStaticFile;
  var lastBackendAvailability = null;
  var hAnimationCancel = null;
  var bellAnimationCancel = null;
  var selectedExample = null;
  var scrollFrameId = 0;
  var stepIndex = 0;
  var currentLanguage = 'zh';
  var activePinnedHelp = null;
  var activeHelpTrigger = null;
  var helpCloseTimer = 0;
  var tutorialGeometry = new WeakMap();
  var predictionChoices = [].slice.call(document.querySelectorAll('.prediction-choice'));
  var predictionFeedback = document.querySelector('#prediction-feedback');
  var pauliTabs = [].slice.call(document.querySelectorAll('.pauli-tab'));
  var pauliPanel = document.querySelector('#pauli-panel');
  var pauliBasisLabel = document.querySelector('.pauli-basis-label');
  var pauliBasisCopy = null;
  var pauliRelation = document.querySelector('.pauli-relation');
  var pauliValue = document.querySelector('.pauli-value');
  var pauliDescription = document.querySelector('.pauli-description');
  var pauliPanelData = {
    z: {
      zh: { basis: 'Z 方向', relation: '两个量子比特几乎总是同向变化', value: 'Czz = 0.99955', description: '相关系数接近 +1，表示高度同向。' },
      en: { basis: 'Z basis · closest to the view you just saw', relation: 'The two qubits tend to move together', value: 'Czz = 0.99955', description: 'A correlation close to +1 means the two readings move together.' }
    },
    x: {
      zh: { basis: 'X 方向', relation: '两个量子比特仍然几乎同向变化', value: 'Cxx = 0.99956', description: '换一个方向后，两边仍然高度同向。' },
      en: { basis: 'X basis · a different measurement view', relation: 'The two qubits still tend to move together', value: 'Cxx = 0.99956', description: 'From this different basis, the two readings still move together.' }
    },
    y: {
      zh: { basis: 'Y 方向', relation: '两个量子比特几乎总是反向变化', value: 'Cyy = -0.99865', description: '相关系数接近 −1，表示高度反向。' },
      en: { basis: 'Y basis · one more measurement view', relation: 'The two qubits tend to move in opposite directions', value: 'Cyy = -0.99865', description: 'A correlation close to −1 means the two readings move in opposite directions.' }
    }
  };
  var currentPauliBasis = 'z';
  var qubitStoryState = '';
  var bellStoryState = '';
  var lastExperimentData = null;

  var TERM_HELP_COPY = {
    'quantum-computing': { labelZh: '量子计算', labelEn: 'quantum computing', zh: '一种利用量子系统来处理信息的计算方式。你现在不需要先学量子力学；这页只带你看懂一个最小实验。', en: 'A way of processing information using quantum systems. You do not need quantum mechanics to follow this page—we are only unpacking one small experiment.' },
    'bit': { labelZh: 'bit', labelEn: 'bit', zh: '普通计算机最基本的信息单位，通常用 0 或 1 表示。', en: 'The basic unit of information in an ordinary computer, usually represented as 0 or 1.' },
    'qubit': { labelZh: '量子比特 · qubit', labelEn: 'qubit', zh: '量子计算里的基本信息单位。测量后会读到 0 或 1；测量前，它可以处在不同的量子状态。', en: 'The basic unit of quantum information. A measurement returns 0 or 1, while before measurement the qubit can occupy different quantum states.' },
    'ket-zero': { labelZh: '|0⟩', labelEn: '|0⟩', zh: '读作 “ket zero”。这里你先把它理解成：这个量子比特从 0 状态开始。', en: 'Read “ket zero.” For this page, just think of it as: this qubit starts in the 0 state.' },
    'h-gate': { labelZh: 'H · Hadamard', labelEn: 'H · Hadamard', zh: '一种作用在单个量子比特上的量子操作。对这页从 |0⟩ 开始的实验，它会让重复测量时 0 和 1 各出现大约一半。', en: 'A one-qubit operation. In this experiment, starting from |0⟩, it leads to roughly half 0s and half 1s when the same circuit is measured many times.' },
    'quantum-gate': { labelZh: '量子门', labelEn: 'quantum gate', zh: '对量子比特执行的一种基本操作。你可以先把它理解成“改变量子状态的一步”。', en: 'A basic operation applied to one or more qubits.' },
    'measurement': { labelZh: '测量 · M', labelEn: 'measurement · M', zh: '把量子状态读成经典结果。在这页里，每次测量最终会得到 0 或 1。', en: 'The step that turns a quantum state into a classical outcome. Here, each measurement returns 0 or 1.' },
    'cnot': { labelZh: 'CNOT', labelEn: 'CNOT', zh: '一种作用在两个量子比特上的量子门。看最简单的 0 / 1 输入时：控制位为 0，目标位不变；控制位为 1，目标位翻转。', en: 'A two-qubit gate. For simple 0/1 inputs, the target stays unchanged when the control is 0 and flips when the control is 1.' },
    'control-qubit': { labelZh: '控制位', labelEn: 'control qubit', zh: 'CNOT 里的第一个量子比特。它的 0 / 1 状态决定目标位是否翻转。', en: 'The first qubit in a CNOT. Its 0/1 value determines whether the target flips.' },
    'target-qubit': { labelZh: '目标位', labelEn: 'target qubit', zh: 'CNOT 里的第二个量子比特。控制位为 1 时，它会翻转；控制位为 0 时保持不变。', en: 'The second qubit in a CNOT. It flips when the control is 1.' },
    'bell-state': { labelZh: 'Bell 实验 / Bell 态', labelEn: 'Bell experiment / Bell state', zh: '这里是一个两量子比特的 Bell 态入门实验：先用 H 和 CNOT 准备 Bell 态，再观察重复测量得到的结果分布。', en: 'A small two-qubit Bell-state experiment: prepare the state with H and CNOT, then inspect the distribution from repeated measurements.' },
    'bell-phi-plus': { labelZh: 'Bell Φ+', labelEn: 'Bell Φ+', zh: '一个标准的两量子比特纠缠态。理想情况下，在计算基测量时，结果主要是 00 和 11，而且各约一半。', en: 'A standard two-qubit entangled state. For Bell Φ+, an ideal computational-basis measurement returns mostly 00 and 11, about half each.' },
    'entanglement': { labelZh: '纠缠', labelEn: 'entanglement', zh: '两个量子比特之间的一种联合量子关系。描述它们时，不能只把两个量子比特各自独立地说完就结束。', en: 'A joint quantum relationship between multiple qubits that cannot be fully described by treating each qubit independently.' },
    'shots': { labelZh: 'shots · 重复次数', labelEn: 'shots · repetitions', zh: '把同一份电路重复运行并测量很多次。一次测量只给一个结果，所以要靠多次统计才能看出分布。', en: 'Repeated runs of the same circuit. One measurement gives one outcome, so many shots reveal the distribution.' },
    'backend': { labelZh: '运行后端 · backend', labelEn: 'backend', zh: '真正执行这份量子电路的地方。可以是本地模拟器，也可以是真实量子平台。', en: 'The system that actually executes the circuit—either a local simulator or a quantum hardware service.' },
    'simulator': { labelZh: '模拟器', labelEn: 'simulator', zh: '用普通计算机模拟量子电路行为的软件。它方便、快速，适合先验证实验流程。', en: 'Software on a classical computer that imitates the behavior of a quantum circuit.' },
    'quantum-hardware': { labelZh: '真实量子机器', labelEn: 'quantum hardware', zh: '真正的量子硬件设备。它会受到噪声、校准状态和设备条件影响，所以结果通常不会像理想模拟那样完美。', en: 'A physical quantum processor. Real hardware is noisy, so results are usually less ideal than a simulator.' },
    'openqasm': { labelZh: 'OpenQASM', labelEn: 'OpenQASM', zh: '一种描述量子电路的程序文本。你可以把它理解成“把量子实验写成程序”。', en: 'A text language for describing quantum circuits—roughly, a way to write the experiment as a program.' },
    'xyz': { labelZh: 'X / Y / Z 测量方向', labelEn: 'X / Y / Z measurement settings', zh: '三种不同的量子测量设置。可以把它理解成：用不同方式观察同一个量子状态，从而获得不同的信息。', en: 'Different ways of measuring the same quantum state. Each setting reveals a different piece of information.' },
    'correlation': { labelZh: '相关系数 Cxx / Cyy / Czz', labelEn: 'correlation coefficient', zh: '用一个数描述两个量子比特在某个测量方向上的关联趋势。接近 +1 表示高度同向，接近 −1 表示高度反向。', en: 'A number that summarizes how strongly two qubits move together in one measurement setting. Near +1 means strongly aligned; near −1 means strongly anti-aligned.' },
    'tomography': { labelZh: '量子态层析 · tomography', labelEn: 'tomography', zh: '从多个测量方向收集信息，再把这些结果合起来，重建一个更完整的量子状态描述。', en: 'A method that combines measurements from multiple settings to reconstruct a fuller description of a quantum state.' },
    'density-matrix': { labelZh: '密度矩阵 · density matrix', labelEn: 'density matrix', zh: '一种记录量子状态统计信息的数学表示。读懂这一页，不需要先会矩阵运算。', en: 'A mathematical representation that stores the statistical information of a quantum state. You do not need matrix algebra to follow this page.' },
    'fidelity': { labelZh: 'fidelity · 接近程度', labelEn: 'fidelity', zh: '这里可以先读作“接近程度”。数值越接近 1，表示重建状态越接近目标 Bell Φ+。', en: 'A measure of closeness. Here, values nearer 1 mean the reconstructed state is closer to the target Bell Φ+ state.' },
    'ppt': { labelZh: 'PPT 纠缠判据', labelEn: 'PPT criterion', zh: '一种检查两比特量子态是否纠缠的数学方法。对这里的 2×2 系统，部分转置出现负本征值意味着这个重建状态满足 PPT 纠缠判据。', en: 'A mathematical test for two-qubit entanglement. In this 2×2 case, a negative partial-transpose eigenvalue signals entanglement under the PPT criterion.' },
    'api-key': { labelZh: 'API Key', labelEn: 'API Key', zh: '连接外部 AI 模型服务时使用的私密凭证。体验现成 Bell 实验不需要它，也不要把自己的 Key 发给别人。', en: 'A private credential used to connect an external AI model service. You do not need one to run the built-in Bell experiment.' }
  };

  var stepData = [
    {
      zh: { label: '第一步', title: '说出你想做什么', description: '可以直接说：“帮我做一次 Bell 实验。”' },
      en: { label: 'Step one', title: 'State what you want to do', description: 'You can simply say: “Run a Bell experiment for me.”' }
    },
    {
      zh: { label: '第二步', title: '写成一份电路', description: 'LoomQ 把你的意图整理成标准 OpenQASM 程序。' },
      en: { label: 'Step two', title: 'Turn it into a circuit', description: 'LoomQ turns your intent into a standard OpenQASM program.' }
    },
    {
      zh: { label: '第三步', title: '先检查再执行', description: '程序写法和这台机器能否运行它，会在执行以前检查。' },
      en: { label: 'Step three', title: 'Check before running', description: 'The program and the selected backend are checked before execution.' }
    },
    {
      zh: { label: '第四步', title: '交给运行后端', description: '同一份电路可以交给 SpinQ、OriginQ 或 Braket 的后端。' },
      en: { label: 'Step four', title: 'Send it to a backend', description: 'The same circuit can run through a SpinQ, OriginQ, or Braket backend.' }
    },
    {
      zh: { label: '第五步', title: '把返回结果讲清楚', description: '你会看到测量分布、电路、验证信息，以及这次实验支持的判断。' },
      en: { label: 'Step five', title: 'Explain what came back', description: 'See the measurements, circuit, verification, and the conclusions this run supports.' }
    }
  ];

  function pick(zh, en) {
    return currentLanguage === 'zh' ? zh : en;
  }

  function setBilingualText(element, zh, en) {
    if (!element) return;
    element.dataset.zh = zh;
    element.dataset.en = en;
    element.textContent = pick(zh, en);
  }

  function makeBilingualNode(tag, className, zh, en) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    setBilingualText(element, zh, en);
    return element;
  }

  function makeTermHelpNode(termKey, id) {
    var copy = TERM_HELP_COPY[termKey];
    if (!copy) return document.createDocumentFragment();
    var anchor = makeEl('span', 'term-help-anchor');
    var trigger = makeEl('button', 'term-help-trigger');
    trigger.type = 'button';
    trigger.dataset.helpTarget = id;
    trigger.dataset.termKey = termKey;
    trigger.dataset.ariaLabelZh = '解释：' + copy.labelZh;
    trigger.dataset.ariaLabelEn = 'Explain: ' + copy.labelEn;
    trigger.setAttribute('aria-label', trigger.dataset.ariaLabelZh);
    trigger.setAttribute('aria-expanded', 'false');
    var icon = makeEl('span', '', '?');
    icon.setAttribute('aria-hidden', 'true');
    trigger.appendChild(icon);
    var tooltip = makeEl('span', 'term-help');
    tooltip.id = id;
    tooltip.setAttribute('role', 'tooltip');
    tooltip.hidden = true;
    tooltip.appendChild(makeBilingualNode('strong', 'term-help-title', copy.labelZh, copy.labelEn));
    tooltip.appendChild(makeBilingualNode('span', 'term-help-copy', copy.zh, copy.en));
    anchor.appendChild(trigger);
    anchor.appendChild(tooltip);
    return anchor;
  }

  function makeDisclosureSummary(zh, en) {
    var summary = document.createElement('summary');
    summary.className = 'disclosure-summary';
    var marker = document.createElement('span');
    marker.className = 'disclosure-marker';
    marker.setAttribute('aria-hidden', 'true');
    marker.textContent = '▸';
    summary.appendChild(marker);
    summary.appendChild(makeBilingualNode('span', 'disclosure-label', zh, en));
    return summary;
  }

  function initV71PublicExperience() {
    var evidence = document.querySelector('#evidence');
    var contentWidth = evidence ? evidence.querySelector('.content-width') : null;
    var oldTechnicalLadder = document.querySelector('#judge-evidence');
    if (!contentWidth || !oldTechnicalLadder) return;

    oldTechnicalLadder.hidden = true;
    oldTechnicalLadder.setAttribute('aria-hidden', 'true');

    var publicSection = document.createElement('section');
    publicSection.className = 'public-hardware-section';
    publicSection.id = 'public-hardware';
    publicSection.setAttribute('aria-labelledby', 'public-hardware-title');
    var publicCard = document.createElement('div');
    publicCard.className = 'public-hardware-card white-card';
    var publicTitle = makeBilingualNode('h3', 'sr-only', '真实机器上的运行记录', 'Run records from real machines');
    publicTitle.id = 'public-hardware-title';
    publicCard.appendChild(publicTitle);
    var platformGrid = document.createElement('div');
    platformGrid.className = 'hardware-platforms';
    ['SpinQ', 'OriginQ'].forEach(function (name) {
      var fact = document.createElement('article');
      fact.className = 'hardware-fact';
      fact.appendChild(makeBilingualNode('h4', '', name, name));
      fact.appendChild(makeBilingualNode('p', '', '真实任务记录 · 实际 QASM · 原始返回结果', 'Real task record · actual QASM · raw returned result'));
      platformGrid.appendChild(fact);
    });
    publicCard.appendChild(platformGrid);
    publicCard.appendChild(makeBilingualNode('p', 'hardware-summary centered-copy v71-copy', '这些记录已经归档，页面这里只把最重要的信息讲给你看。', 'These records are archived; this page keeps only the most important part in view.'));
    publicCard.appendChild(makeBilingualNode('p', 'hardware-next centered-copy v71-copy', '刚才的测量只用了一种方式。\n这三组归档数据来自独立的重复实验：每次重新准备同一目标状态，再换一种测量方向。', 'The earlier run used one measurement view.\nThese three archived records are independent repeats: each prepares the target state again, then changes the measurement direction.'));
    var returnLink = document.createElement('a');
    returnLink.className = 'text-link public-return-link';
    returnLink.href = '#experiment';
    returnLink.appendChild(makeBilingualNode('span', '', '想自己问一个量子问题？回到实验区 ↑', 'Want to ask a quantum question? Return to the lab ↑'));
    publicCard.appendChild(returnLink);
    publicSection.appendChild(publicCard);
    contentWidth.insertBefore(publicSection, oldTechnicalLadder);

    var disclosure = document.createElement('details');
    disclosure.className = 'technical-disclosure white-card';
    disclosure.id = 'technical-disclosure-v71';
    disclosure.appendChild(makeDisclosureSummary('想看技术与来源？', 'Technical details and sources'));
    disclosure.appendChild(makeBilingualNode('p', 'technical-disclosure-copy', '这里可以查看证据路径、验证说明、Agent / L3 / Custom RISC-V 技术文档与 Judge Guide。归档 provenance 说明也只放在这里。CNOT 的控制位规则只针对 0 / 1 基态输入；对叠加输入，它作为相干门作用于整个两比特状态，不会先测量控制位。X / Y / Z 来自三次独立归档作业，不是同一份量子副本同时测量。', 'This optional layer contains evidence paths, validation notes, Agent / L3 / Custom RISC-V documentation, and the Judge Guide. The archived provenance note lives here too. The CNOT control rule is for 0 / 1 basis inputs; on a superposition it acts coherently on the whole two-qubit state and does not measure the control first. X / Y / Z come from three independent archived jobs, not simultaneous measurements of one copy.'));
    disclosure.appendChild(makeBilingualNode('p', 'technical-disclosure-paths', '技术路径：evidence/README.md · JUDGE_GUIDE.md · 归档哈希说明。', 'Technical paths: evidence/README.md · JUDGE_GUIDE.md · archived hash note.'));
    contentWidth.insertBefore(disclosure, oldTechnicalLadder);

    var analogy = contentWidth.querySelector('.analogy-strip');
    if (analogy) {
      analogy.hidden = true;
      var diagram = document.createElement('div');
      diagram.className = 'multi-view-diagram';
      diagram.setAttribute('role', 'img');
      diagram.setAttribute('aria-label', pick('三个测量方向汇合成更完整的描述', 'Three measurement views combine into a fuller description'));
      var steps = document.createElement('div');
      steps.className = 'multi-view-steps';
      ['正面|Front', '侧面|Side', '斜侧|Angle'].forEach(function (label) {
        var parts = label.split('|');
        steps.appendChild(makeBilingualNode('span', '', parts[0], parts[1]));
      });
      diagram.appendChild(steps);
      var arrows = document.createElement('div');
      arrows.className = 'multi-view-arrows';
      arrows.setAttribute('aria-hidden', 'true');
      arrows.textContent = '↘  ↓  ↙';
      diagram.appendChild(arrows);
      diagram.appendChild(makeBilingualNode('p', 'multi-view-caption centered-copy v71-copy', '更多观察方向 → 更完整的状态描述', 'More views → a fuller description of the state'));
      analogy.parentNode.insertBefore(diagram, analogy);
    }

    var evidenceTitle = document.querySelector('#evidence-title');
    setBilingualText(document.querySelector('#evidence .eyebrow'), '真实机器也跑过', 'Real machines have run it too');
    setBilingualText(evidenceTitle, '同一类电路，也交给了真实量子机器', 'The same kind of circuit also ran on real quantum machines');
    var evidenceDeck = document.querySelector('#evidence .section-deck');
    if (evidenceDeck) {
      evidenceDeck.classList.add('centered-copy', 'v71-copy');
      setBilingualText(evidenceDeck, '前面你亲手运行的是本地模拟。\nLoomQ 也保存了真实量子平台上的运行记录。', 'You just ran a local simulation.\nLoomQ also keeps run records from real quantum platforms.');
    }

    var qubitDeck = document.querySelector('#qubit .section-deck');
    if (qubitDeck) {
      qubitDeck.classList.add('centered-copy', 'v71-copy');
      setBilingualText(qubitDeck, '普通电脑把信息写成 0 和 1。\n量子电脑也会读出 0 或 1，但读取之前，量子比特可以处在不同的量子状态。\n我们先从最简单的 |0⟩ 开始。', 'Ordinary computers write information as 0 and 1.\nQuantum computers also read 0 or 1, but before reading, a qubit can be in different quantum states.\nWe will start with the simplest |0⟩.');
    }
    var openerCue = document.querySelector('#qubit .opener-cue span');
    setBilingualText(openerCue, '↓ 接下来加入一个叫 H 的操作，先看它怎样改变状态', '↓ Next, add an operation called H and see how it changes the state');
    setBilingualText(document.querySelector('#qubit-science-title'), 'H 改变了状态，重复测量显出了分布。', 'H changes the state; repeated measurements reveal a distribution.');
    var hNarrative = document.querySelector('.h-narrative-copy');
    var hSentences = hNarrative ? hNarrative.querySelectorAll('.sentence-line') : [];
    var hZh = [
      '把同一份电路重复很多次，0 和 1 会各出现大约一半。',
      '这种准备方式会得到一种均匀叠加状态。',
      '每次测量仍然只留下一个结果。'
    ];
    var hEn = [
      'Repeat the same circuit many times, and 0 and 1 each appear about half the time.',
      'This preparation produces an equal superposition state.',
      'Each measurement still leaves one result.'
    ];
    [].slice.call(hSentences).forEach(function (sentence, index) {
      setBilingualText(sentence, hZh[index], hEn[index]);
    });
    if (hNarrative) hNarrative.classList.add('v71-copy');

    var bellDeck = document.querySelector('#bell .section-deck');
    if (bellDeck) {
      bellDeck.classList.add('centered-copy', 'v71-copy');
      setBilingualText(bellDeck, '这一章会把 H 和 CNOT 串起来：先认识规则，再看 Bell 结果。', 'This chapter connects H and CNOT: learn the rule first, then inspect the Bell result.');
    }
    var bellHeading = document.querySelector('#bell .section-heading');
    if (bellHeading && !bellHeading.querySelector('.cnot-intro')) {
      var cnotIntro = makeEl('p', 'sentence-line cnot-intro');
      cnotIntro.appendChild(makeBilingualNode('span', '', 'CNOT 是一种作用在两个量子比特上的操作。\n第一个量子比特叫控制位，第二个叫目标位。', 'CNOT is an operation on two qubits.\nThe first qubit is the control; the second is the target.'));
      cnotIntro.appendChild(makeTermHelpNode('cnot', 'bell-cnot-help'));
      bellHeading.appendChild(cnotIntro);
    }
    var cnotRule = document.querySelector('.cnot-rule');
    if (cnotRule) {
      var cnotResultCopy = cnotRule.querySelector('.cnot-rule-result-copy');
      if (cnotResultCopy) setBilingualText(cnotResultCopy, '控制位是 0：目标位不变。', 'Control is 0: the target stays unchanged.');
      else {
        var cnotParagraphs = cnotRule.querySelectorAll('p');
        if (cnotParagraphs.length) setBilingualText(cnotParagraphs[cnotParagraphs.length - 1], '控制位是 0：目标位不变。', 'Control is 0: the target stays unchanged.');
      }
    }
    var climax = document.querySelector('.narrative-climax');
    if (climax) {
      var climaxParagraphs = climax.querySelectorAll('p');
      if (climaxParagraphs.length) {
        climaxParagraphs[0].classList.add('bell-reveal-line');
        setBilingualText(climaxParagraphs[0], '理想 Bell 电路最后主要留下 00 和 11，各约一半。', 'An ideal Bell circuit mainly leaves 00 and 11, about half each.');
      }
      if (climaxParagraphs.length > 1) setBilingualText(climaxParagraphs[climaxParagraphs.length - 1], '也就是说，在这种测量方式下，两个量子比特通常一起读成 0，或者一起读成 1。', 'In this measurement, the two qubits usually read as 0 together or 1 together.');
    }
    var bellExplanation = document.querySelector('.bell-explanation');
    if (bellExplanation) {
      var bellParagraphs = bellExplanation.querySelectorAll('p');
      if (bellParagraphs.length > 0) setBilingualText(bellParagraphs[0], '这个联合量子状态叫 Bell Φ+。', 'This joint quantum state is called Bell Φ+.');
      if (bellParagraphs.length > 1) setBilingualText(bellParagraphs[1], 'Bell Φ+ 是一个纠缠态。', 'Bell Φ+ is an entangled state.');
    }

    var flowDeck = document.querySelector('#flow .section-deck');
    if (flowDeck) {
      flowDeck.classList.add('centered-copy', 'v71-copy');
      setBilingualText(flowDeck, '你只需要说清楚想做什么。\nLoomQ 把它写成电路，先检查，再交给运行机器。\n机器返回结果以后，LoomQ 再把它讲回人话。', 'You only need to state what you want.\nLoomQ writes it as a circuit, checks it, and sends it to a backend.\nAfter the machine returns a result, LoomQ explains it in plain language.');
    }
    setBilingualText(document.querySelector('#agent-tasks'), '如果暂时没有配置模型，也可以直接运行现成的 Bell 实验和本地模拟。', 'If you have not configured a model yet, you can still run the ready-made Bell experiment and the local simulator.');

    var tomographyDeck = document.querySelector('#tomography .section-deck');
    if (tomographyDeck) {
      tomographyDeck.classList.add('centered-copy', 'v71-copy');
      setBilingualText(tomographyDeck, '刚才的测量只从一个方向看这个状态。\n每个测量方向都只告诉我们一部分信息。\n我们重复准备同一状态，再在不同设置下测量。\n把多个方向的结果合起来，就能重建这个量子状态的更完整描述。\n这种方法叫量子态层析，也叫 tomography。', 'The earlier measurement looked at this state from only one direction.\nEach measurement direction tells us only part of the story.\nWe prepare the same state again, then measure it with different settings.\nCombine several directions to reconstruct a fuller description of the state.\nThis method is called quantum state tomography.');
    }
    setBilingualText(document.querySelector('.archive-label'), '归档真机数据 · Origin Wukong 180-2。页面只展示已经保存的结果。', 'Archived hardware data · Origin Wukong 180-2. This page shows saved results only.');
    var tomographyStats = document.querySelectorAll('.tomography-stats > div');
    if (tomographyStats.length > 0) {
      setBilingualText(tomographyStats[0].querySelector('p:not(.technical-note)'), 'Fidelity 可以先读作“接近程度”。\n越接近 1，重建出的状态就越接近目标 Bell Φ+。', 'Fidelity can first be read as “how close it is.”\nCloser to 1 means the reconstructed state is closer to target Bell Φ+.');
    }
    if (tomographyStats.length > 1) {
      setBilingualText(tomographyStats[1].querySelector('span'), 'PPT 纠缠检验', 'PPT entanglement check');
      setBilingualText(tomographyStats[1].querySelector('p'), '这是一个用来检查两比特纠缠的数学检验。\n这里得到负值，因此这个重建状态通过了 PPT 纠缠判据。', 'This is a mathematical check for two-qubit entanglement.\nThe value is negative, so this reconstructed state passes the PPT entanglement criterion.');
    }
    var claims = document.querySelector('.tomography-claims');
    if (claims && claims.parentNode && !claims.closest('details')) {
      var boundaryDetails = document.createElement('details');
      boundaryDetails.className = 'science-boundary-disclosure';
      boundaryDetails.appendChild(makeDisclosureSummary('科学边界', 'Science boundary'));
      claims.parentNode.insertBefore(boundaryDetails, claims);
      boundaryDetails.appendChild(claims);
    }
    var footerQuote = document.querySelector('.footer-inner blockquote');
    if (footerQuote) footerQuote.textContent = '“If you wish to make an apple pie from scratch, you must first invent the universe.”';
  }

  function initV72PublicCopy() {
    var evidenceDeck = document.querySelector('#evidence .section-deck');
    if (evidenceDeck) setBilingualText(evidenceDeck, '前面你亲手运行的是本地模拟。\nLoomQ 也保存了真实量子平台上的运行记录。\n这里不要求你读懂全部原始文件，我们只把最重要的信息讲给你看。', 'You just ran a local simulation.\nLoomQ also keeps run records from real quantum platforms.\nYou do not need to read every raw file here; we keep the most important information in view.');
    var hardwareSummary = null;
    var evidenceParagraphs = document.querySelector('#evidence') ? document.querySelector('#evidence').querySelectorAll('p') : [];
    [].slice.call(evidenceParagraphs).some(function (paragraph) {
      if (!paragraph.classList.contains('hardware-summary')) return false;
      hardwareSummary = paragraph;
      return true;
    });
    if (hardwareSummary) setBilingualText(hardwareSummary, 'LoomQ 也保存了真实量子平台上的运行记录。这里不要求你读懂全部原始文件，我们只把最重要的信息讲给你看。', 'LoomQ also keeps run records from real quantum platforms. You do not need to read every raw file here; we keep the most important information in view.');
    var hVisualCopy = document.querySelector('#qubit .qubit-visual > p');
    if (hVisualCopy) setBilingualText(hVisualCopy, '接下来加入一个叫 H 的操作。它作用在一个量子比特上。先看它造成的变化。', 'Next, add an operation called H. It acts on one qubit. First, look at the change it causes.');
    var qubitTutorialBody = document.querySelector('#qubit .tutorial-body:not(.tutorial-body--state)');
    if (qubitTutorialBody) setBilingualText(qubitTutorialBody, '我们先让一个量子比特从 |0⟩ 开始。|0⟩ 可以先理解成：这个量子比特从 0 状态出发。如果现在立刻测量，结果会是 0。', 'We start one qubit in |0⟩. For now, understand |0⟩ as this qubit starting from the 0 state. If we measure it immediately, the result is 0.');
    var modelLabel = document.querySelector('#model-disclosure .disclosure-label');
    var modelBody = document.querySelector('.model-disclosure-body');
    if (modelLabel) setBilingualText(modelLabel, '进阶功能：让 LoomQ 理解你自己的问题（可选）', 'Advanced: let LoomQ understand your own questions (optional)');
    if (modelBody) {
      var modelParagraphs = modelBody.querySelectorAll('p');
      if (modelParagraphs.length > 0) setBilingualText(modelParagraphs[0], '第一次体验这页，不需要配置这里。', 'For your first experience, you do not need to configure this section.');
      if (modelParagraphs.length > 1 && !modelBody.querySelector('.model-optional-explanation')) {
        var optionalExplanation = makeBilingualNode('p', 'model-optional-explanation', '只有当你想让 LoomQ 根据你自己的自然语言问题生成、修复或解释量子电路时，才需要连接一个兼容的 AI 模型服务。', 'Only connect a compatible AI model service when you want LoomQ to generate, repair, or explain a quantum circuit from your own natural-language question.');
        modelBody.insertBefore(optionalExplanation, modelParagraphs[1]);
      }
      var evaluatorNote = modelBody.querySelector('.model-evaluator-note');
      if (evaluatorNote) setBilingualText(evaluatorNote, '模型配置只影响“自己的问题”功能；现成 Bell 实验不受影响。普通用户无需为第一次体验配置它。', 'Model configuration only affects the “your own question” feature; the built-in Bell experiment is unaffected. Ordinary users do not need to configure it for a first experience.');
    }
    if (formStatus) setBilingualText(formStatus, '第一次体验 LoomQ，不需要 API Key；你可以直接运行现成的 Bell 实验。', 'You do not need an API key for your first LoomQ experience; run the built-in Bell experiment directly.');
    var bellActionDescription = document.querySelector('.quick-action--primary .quick-action-description');
    if (bellActionDescription) setBilingualText(bellActionDescription, '直接运行 H + CNOT，不需要连接 AI 模型。', 'Run H + CNOT directly; no AI model connection is needed.');

    var backendHelp = document.querySelector('#backend-help');
    if (backendHelp) {
      setBilingualText(backendHelp.querySelector('strong'), '运行后端 · backend', 'backend');
      setBilingualText(backendHelp.querySelector('p'), TERM_HELP_COPY.backend.zh, TERM_HELP_COPY.backend.en);
    }
    var shotsHelp = document.querySelector('#shots-help');
    if (shotsHelp) {
      setBilingualText(shotsHelp.querySelector('strong'), TERM_HELP_COPY.shots.labelZh, TERM_HELP_COPY.shots.labelEn);
      setBilingualText(shotsHelp.querySelector('p'), TERM_HELP_COPY.shots.zh, TERM_HELP_COPY.shots.en);
    }

    if (pauliBasisLabel && !pauliBasisCopy) {
      pauliBasisLabel.removeAttribute('data-zh');
      pauliBasisLabel.removeAttribute('data-en');
      pauliBasisCopy = makeEl('span', 'pauli-basis-copy');
      pauliBasisLabel.textContent = '';
      pauliBasisLabel.appendChild(pauliBasisCopy);
      pauliBasisLabel.appendChild(makeTermHelpNode('xyz', 'pauli-xyz-help'));
      var correlationHelp = makeTermHelpNode('correlation', 'pauli-correlation-help');
      if (pauliValue && pauliValue.parentNode) pauliValue.parentNode.insertBefore(correlationHelp, pauliDescription);
      renderPauli(currentPauliBasis);
    }

    var tomographyStats = document.querySelectorAll('.tomography-stats > div');
    if (tomographyStats.length > 0 && !tomographyStats[0].querySelector('[data-term-key="fidelity"]')) {
      tomographyStats[0].insertBefore(makeTermHelpNode('fidelity', 'tomography-fidelity-help'), tomographyStats[0].querySelector('strong'));
    }
    if (tomographyStats.length > 1 && !tomographyStats[1].querySelector('[data-term-key="ppt"]')) {
      tomographyStats[1].insertBefore(makeTermHelpNode('ppt', 'tomography-ppt-help'), tomographyStats[1].querySelector('strong'));
    }
    var densityHelp = document.querySelector('.density-help');
    if (densityHelp && !densityHelp.querySelector('[data-term-key="density-matrix"]')) {
      var densityTerm = makeEl('p', 'density-term-help-line');
      densityTerm.appendChild(makeBilingualNode('span', '', '密度矩阵 · density matrix', 'density matrix'));
      densityTerm.appendChild(makeTermHelpNode('density-matrix', 'density-matrix-help'));
      densityHelp.insertBefore(densityTerm, densityHelp.querySelector('p'));
    }
  }

  function initV724Copy() {
    var qubitOpenerCue = document.querySelector('#qubit .opener-cue span');
    if (qubitOpenerCue) setBilingualText(qubitOpenerCue, '↓ 接着加入 H，看看状态怎么变', '↓ Add H next and watch the state change');
    var hVisualCopy = document.querySelector('#qubit .qubit-visual > p');
    if (hVisualCopy) setBilingualText(hVisualCopy, '接着加入 H。先看它带来的变化。', 'Next, add H. Watch the change it brings.');
    var qubitStart = document.querySelector('#qubit .tutorial-body:not(.tutorial-body--state)');
    if (qubitStart) {
      qubitStart.classList.add('v71-copy');
      setBilingualText(qubitStart, '先从 |0⟩ 出发。\n现在立刻测量，结果会是 0。', 'Start with |0⟩.\nMeasure it now, and the result is 0.');
    }
    var qubitH = document.querySelector('#qubit .tutorial-body--definition');
    if (qubitH) {
      qubitH.classList.add('v71-copy');
      setBilingualText(qubitH, '接着加入 H。\n先别急着记定义，先看它带来的变化。\n重复测量以后，0 和 1 都会出现。', 'Next, add H.\nDo not worry about the definition yet; watch the change first.\nAfter repeated measurements, both 0 and 1 appear.');
    }
    if (qubitStoryLine) setBilingualText(qubitStoryLine, '现在，测量会得到 0。', 'A measurement now returns 0.');
    var qubitAnimationNote = document.querySelector('#qubit .animation-note');
    if (qubitAnimationNote) setBilingualText(qubitAnimationNote, '先看变化，滚到底时会接近各一半。', 'Watch the change; by the end, they approach half each.');

    var bellDefinition = document.querySelector('#bell .cnot-definition');
    if (bellDefinition) {
      bellDefinition.classList.add('v71-copy');
      setBilingualText(bellDefinition, 'CNOT 先记一条规则：控制位为 0，目标位不变；控制位为 1，目标位翻转。', 'Start with one CNOT rule: control 0 leaves the target unchanged; control 1 flips it.');
    }
    var bellAnimationNote = document.querySelector('#bell .animation-note');
    if (bellAnimationNote) setBilingualText(bellAnimationNote, '继续向下，00 和 11 会各接近一半。', 'Keep going; 00 and 11 approach half each.');

    var quantumHelp = document.querySelector('#onboarding-quantum-computing-help');
    if (quantumHelp) setBilingualText(quantumHelp.querySelector('p'), '这页只用一个最小 Bell 实验，带你走过准备、操作和测量。', 'This page follows one small Bell experiment through preparation, operations, and measurement.');

    var modelBody = document.querySelector('.model-disclosure-body');
    if (modelBody) {
      var modelParagraphs = modelBody.querySelectorAll('p');
      if (modelParagraphs.length > 0) setBilingualText(modelParagraphs[0], '第一次先用现成的 Bell 例子就行，不用配 API Key。', 'Start with the built-in Bell example; no API key is needed.');
      var optionalExplanation = modelBody.querySelector('.model-optional-explanation');
      if (optionalExplanation) setBilingualText(optionalExplanation, '想让 LoomQ 帮你生成、修改或解释自己的电路时，再连接模型。', 'Connect a model when you want LoomQ to generate, modify, or explain your own circuit.');
      var evaluatorNote = modelBody.querySelector('.model-evaluator-note');
      if (evaluatorNote) setBilingualText(evaluatorNote, '需要处理自己的问题时，再连接模型；现成 Bell 例子不受影响。', 'Connect a model when you want to handle your own question; the built-in Bell example is unaffected.');
    }
    if (formStatus) setBilingualText(formStatus, '第一次先用现成的 Bell 例子就行，不用配 API Key。', 'Start with the built-in Bell example; no API key is needed.');
    var apiOptionalLead = document.querySelector('.api-optional-lead span[data-zh]');
    if (apiOptionalLead) setBilingualText(apiOptionalLead, '第一次先用现成的 Bell 例子就行，不用配 API Key。', 'Start with the built-in Bell example; no API key is needed.');
    var agentCapabilityNote = document.querySelector('.agent-capability-note');
    if (agentCapabilityNote) setBilingualText(agentCapabilityNote, '想让 LoomQ 帮你生成、修改或解释自己的电路时，再连接模型。', 'Connect a model when you want LoomQ to generate, modify, or explain your own circuit.');
  }

  function initAnchorFocus() {
    [].slice.call(document.querySelectorAll('a[href^="#"]')).forEach(function (link) {
      link.addEventListener('click', function (event) {
        var href = link.getAttribute('href');
        var target = href && document.querySelector(href);
        if (!target || target.hidden) return;
        event.preventDefault();
        target.scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth', block: 'start' });
        if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
        window.setTimeout(function () { target.focus({ preventScroll: true }); }, isReduced ? 0 : 450);
      });
    });
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function makeEl(tag, className, text) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function clear(element) {
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function makeSvgEl(tag, className, text) {
    var element = document.createElementNS('http:' + '//www.w3.org/2000/svg', tag);
    if (className) element.setAttribute('class', className);
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function updateStrokeViewport() {
    strokeTextSvg.setAttribute('viewBox', window.innerWidth <= 767 ? '320 0 360 128' : '0 0 1000 128');
  }

  function prepareScrollFloats() {
    scrollFloatHeadings.forEach(function (heading) {
      var lines = [].slice.call(heading.querySelectorAll('.scroll-float-line'));
      heading.setAttribute('aria-label', lines.map(function (line) { return line.textContent; }).join(''));
      lines.forEach(function (line) {
        var text = line.textContent;
        clear(line);
        line.setAttribute('aria-hidden', 'true');
        var revealUnits = currentLanguage === 'en' ? [text] : Array.from(text);
        revealUnits.forEach(function (character, index) {
          var span = makeEl('span', 'scroll-float-char', character === ' ' ? '\u00a0' : character);
          span.dataset.floatIndex = String(index);
          line.appendChild(span);
        });
      });
      if (isReduced || heading.dataset.revealed === 'true') heading.classList.add('is-visible');
    });
  }

  function initTitleReveals() {
    if (isReduced || !('IntersectionObserver' in window)) {
      scrollFloatHeadings.forEach(function (heading) {
        heading.dataset.revealed = 'true';
        heading.classList.add('is-visible');
      });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.dataset.revealed = 'true';
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -22% 0px', threshold: 0 });
    scrollFloatHeadings.forEach(function (heading) { observer.observe(heading); });
  }

  function applyLocalizedAttributes() {
    [].slice.call(document.querySelectorAll('[data-aria-label-zh][data-aria-label-en]')).forEach(function (element) {
      element.setAttribute('aria-label', currentLanguage === 'zh' ? element.dataset.ariaLabelZh : element.dataset.ariaLabelEn);
    });
    document.querySelectorAll('[data-aria-description-zh][data-aria-description-en]').forEach(function (element) {
      element.setAttribute('aria-description', currentLanguage === 'zh' ? element.dataset.ariaDescriptionZh : element.dataset.ariaDescriptionEn);
    });
  }

  function renderPauli(basis) {
    if (!pauliPanel || !pauliBasisLabel) return;
    currentPauliBasis = pauliPanelData[basis] ? basis : 'z';
    var copy = pauliPanelData[currentPauliBasis][currentLanguage];
    pauliPanel.dataset.basis = currentPauliBasis;
    pauliPanel.setAttribute('aria-labelledby', 'tab-' + currentPauliBasis);
    if (pauliBasisCopy) pauliBasisCopy.textContent = copy.basis;
    else pauliBasisLabel.textContent = copy.basis;
    pauliRelation.textContent = copy.relation;
    pauliValue.textContent = copy.value;
    pauliDescription.textContent = copy.description;
    pauliTabs.forEach(function (tab) {
      var selected = tab.dataset.basis === currentPauliBasis;
      tab.setAttribute('aria-selected', selected ? 'true' : 'false');
      tab.tabIndex = selected ? 0 : -1;
    });
  }

  function initPauliTabs() {
    pauliTabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () { renderPauli(tab.dataset.basis); });
      tab.addEventListener('keydown', function (event) {
        var nextIndex = index;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (index + 1) % pauliTabs.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (index - 1 + pauliTabs.length) % pauliTabs.length;
        if (event.key === 'Home') nextIndex = 0;
        if (event.key === 'End') nextIndex = pauliTabs.length - 1;
        if (nextIndex === index) return;
        event.preventDefault();
        pauliTabs[nextIndex].focus();
        renderPauli(pauliTabs[nextIndex].dataset.basis);
      });
    });
    renderPauli('z');
  }

  function initPrediction() {
    predictionChoices.forEach(function (choice) {
      choice.setAttribute('aria-pressed', 'false');
      choice.addEventListener('click', function () {
        predictionChoices.forEach(function (item) { item.setAttribute('aria-pressed', item === choice ? 'true' : 'false'); });
        predictionFeedback.textContent = pick('记下你的猜测；答案就在下一段。', 'Your guess is noted; the answer is in the next section.');
      });
    });
  }

  function runTeachingAnimation(duration, update, complete) {
    var frameId = 0;
    var startTime = 0;
    if (isReduced) {
      update(1);
      if (complete) complete();
      return function () {};
    }
    function frame(now) {
      if (!startTime) startTime = now;
      var progress = clamp((now - startTime) / duration, 0, 1);
      update(progress);
      if (progress >= 1) {
        frameId = 0;
        if (complete) complete();
        return;
      }
      frameId = window.requestAnimationFrame(frame);
    }
    frameId = window.requestAnimationFrame(frame);
    return function () {
      if (frameId) window.cancelAnimationFrame(frameId);
      frameId = 0;
    };
  }

  function renderHTeachingCounts(zeroCount, oneCount) {
    var total = Math.max(zeroCount + oneCount, 1);
    var zeroShare = (zeroCount / total) * 100;
    var oneShare = (oneCount / total) * 100;
    if (hZeroBar) hZeroBar.style.width = zeroShare.toFixed(2) + '%';
    if (hOneBar) hOneBar.style.width = oneShare.toFixed(2) + '%';
    if (hZeroCount) hZeroCount.textContent = String(zeroCount);
    if (hOneCount) hOneCount.textContent = String(oneCount);
  }

  function initOutcomeDelight() {
    outcomeDelightStats.forEach(function (stat) {
      var timer = 0;
      stat.addEventListener('click', function () {
        stat.classList.remove('is-delighted');
        void stat.offsetWidth;
        stat.classList.add('is-delighted');
        window.clearTimeout(timer);
        timer = window.setTimeout(function () { stat.classList.remove('is-delighted'); }, 520);
      });
    });
  }

  function initV725GoldenRestore() {
    var title = document.querySelector('#page-title');
    var titleMotion = title ? title.querySelector('.hero-title-motion') : null;
    var strokeText = titleMotion ? titleMotion.querySelector('[data-stroke-text]') : null;
    var heroContent = document.querySelector('.hero-content');
    if (!title || !heroContent) return;

    title.classList.remove('hero-title--question', 'hero-title--restored');
    title.classList.add('hero-title--golden');
    clear(title);
    if (titleMotion) {
      titleMotion.hidden = false;
      titleMotion.removeAttribute('aria-hidden');
      titleMotion.classList.add('hero-golden-line');
      titleMotion.querySelectorAll('[data-stroke-lang]').forEach(function (group) {
        var value = group.dataset.strokeLang === 'en' ? 'See a result first' : '先看见一个结果';
        group.querySelectorAll('tspan').forEach(function (tspan) { tspan.textContent = value; });
      });
      if (strokeText) {
        strokeText.dataset.ariaLabelZh = '先看见一个结果';
        strokeText.dataset.ariaLabelEn = 'See a result first';
        strokeText.setAttribute('aria-label', pick(strokeText.dataset.ariaLabelZh, strokeText.dataset.ariaLabelEn));
      }
      title.appendChild(titleMotion);
    } else {
      title.appendChild(makeBilingualNode('span', 'hero-golden-line hero-title-solid', '先看见一个结果', 'See a result first'));
    }
    title.appendChild(makeBilingualNode('span', 'hero-golden-line hero-title-solid', '再走进量子世界', 'Then step into the quantum world'));

    var primary = document.querySelector('#hero-see-result');
    if (primary) {
      setBilingualText(primary.querySelector('[data-zh][data-en]'), '先看结果 ↓', 'See the result ↓');
      primary.setAttribute('href', '#outcome-first');
    }

    var intro = heroContent.querySelector('.hero-intro');
    var mystery = heroContent.querySelector('.hero-mystery');
    if (!mystery) {
      mystery = makeEl('div', 'hero-mystery');
      heroContent.insertBefore(mystery, intro || null);
    }
    clear(mystery);
    mystery.appendChild(makeBilingualNode('p', 'hero-question', '为什么这份只有两个量子比特的电路，反复运行时，答案会集中在 00 和 11？', 'Why does a two-qubit circuit keep returning mostly 00 and 11 when we run it again and again?'));
    var preview = makeEl('div', 'hero-preview');
    preview.dataset.ariaLabelZh = '00 和 11 结果预览';
    preview.dataset.ariaLabelEn = 'Preview of 00 and 11';
    preview.setAttribute('aria-label', pick(preview.dataset.ariaLabelZh, preview.dataset.ariaLabelEn));
    [['00', '72%'], ['11', '68%']].forEach(function (item) {
      var row = makeEl('div');
      row.appendChild(makeBilingualNode('span', '', item[0], item[0]));
      var bar = makeEl('i');
      bar.style.setProperty('--preview-size', item[1]);
      row.appendChild(bar);
      preview.appendChild(row);
    });
    mystery.appendChild(preview);
    var supportLine = heroContent.querySelector('.hero-support-line');
    if (supportLine) setBilingualText(supportLine, '不懂量子也可以。先跑一次，再看发生了什么。', 'You do not need quantum background. Run it once, then see what happens.');
    var productLine = heroContent.querySelector('.hero-product-line');
    if (productLine) setBilingualText(productLine, 'LoomQ 会把你的自然语言变成量子电路、检查它、选择后端并把结果翻译成人话。', 'LoomQ turns plain language into a quantum circuit, checks it, chooses a backend, and explains the result.');
  }

  function initHInteraction() {
    if (!hSingleRun || !hShotsRun) return;
    var zeroCount = 0;
    var oneCount = 0;
    var oneShotIndex = 0;
    var oneShotSequence = [0, 1, 0, 1];
    renderHTeachingCounts(zeroCount, oneCount);
    hSingleRun.addEventListener('click', function () {
      if (hAnimationCancel) hAnimationCancel();
      var value = oneShotSequence[oneShotIndex % oneShotSequence.length];
      oneShotIndex += 1;
      if (value === 0) zeroCount += 1;
      else oneCount += 1;
      renderHTeachingCounts(zeroCount, oneCount);
      setBilingualText(hSingleResult, value === 0 ? '这一次测量读到 0。一次结果只有一个值。' : '这一次测量读到 1。一次结果只有一个值。', value === 0 ? 'This measurement returned 0. One shot has one outcome.' : 'This measurement returned 1. One shot has one outcome.');
    });
    hShotsRun.addEventListener('click', function () {
      if (hAnimationCancel) hAnimationCancel();
      var startZero = zeroCount;
      var startOne = oneCount;
      hAnimationCancel = runTeachingAnimation(700, function (progress) {
        zeroCount = Math.round(startZero + ((50 - startZero) * progress));
        oneCount = Math.round(startOne + ((50 - startOne) * progress));
        renderHTeachingCounts(zeroCount, oneCount);
      }, function () {
        zeroCount = 50;
        oneCount = 50;
        renderHTeachingCounts(zeroCount, oneCount);
        setBilingualText(hSingleResult, '100 次测量后，0 和 1 各出现约一半。', 'After 100 measurements, 0 and 1 each appear about half the time.');
      });
    });
  }

  function initCnotInteraction() {
    if (!cnotRuleChoices.length || !cnotRuleResult) return;
    var resultCopy = cnotRuleResult.querySelector('.cnot-rule-result-copy');
    function chooseCnot(choice) {
      var input = choice.dataset.input || '00';
      var output = choice.dataset.output || input;
      var control = input.charAt(0);
      var targetBefore = input.charAt(1);
      var targetAfter = output.charAt(1);
      cnotRuleChoices.forEach(function (item) { item.setAttribute('aria-pressed', item === choice ? 'true' : 'false'); });
      if (resultCopy) {
        setBilingualText(
          resultCopy,
          control === '0' ? '控制位是 0：目标位不变。' : '控制位是 1：目标位翻转。',
          control === '0' ? 'Control is 0: the target stays unchanged.' : 'Control is 1: the target flips.'
        );
      }
      setBilingualText(cnotControlState, 'q0 = ' + control + ' · 控制位', 'q0 = ' + control + ' · control');
      setBilingualText(cnotTargetState, 'q1：' + targetBefore + ' → ' + targetAfter + ' · 目标位', 'q1: ' + targetBefore + ' → ' + targetAfter + ' · target');
      if (cnotTargetState) {
        cnotTargetState.classList.remove('is-flipping');
        if (control === '1') {
          window.requestAnimationFrame(function () { cnotTargetState.classList.add('is-flipping'); });
        }
      }
    }
    cnotRuleChoices.forEach(function (choice) { choice.addEventListener('click', function () { chooseCnot(choice); }); });
    chooseCnot(cnotRuleChoices[0]);
  }

  function initCircuitInspect() {
    if (!circuitInspectSteps.length || !circuitInspectState || !circuitInspectCopy) return;
    var steps = [
      { state: '|00⟩', zh: '两个量子比特都从 0 状态开始。', en: 'Both qubits start in the 0 state.' },
      { state: '(|00⟩ + |10⟩) / √2', zh: 'H 作用在 q0 上；在测量前，状态用两个基态的叠加来描述。', en: 'H acts on q0; before measurement, the state is described as a superposition of two basis states.' },
      { state: '(|00⟩ + |11⟩) / √2', zh: 'CNOT 让 q0 的控制规则作用到 q1，得到这里的 Bell Φ+ 准备。', en: 'CNOT applies the q0 control rule to q1, giving the Bell Φ+ preparation shown here.' },
      { state: '00 或 11', zh: '每次测量只读出一个结果；重复很多次，00 和 11 各约一半。', en: 'Each measurement returns one result; repeated many times, 00 and 11 appear about half each.' }
    ];
    function chooseStep(button) {
      var index = Number(button.dataset.circuitStep || 0);
      var step = steps[index] || steps[0];
      circuitInspectSteps.forEach(function (item) { item.setAttribute('aria-pressed', item === button ? 'true' : 'false'); item.classList.toggle('is-selected', item === button); });
      circuitInspectState.textContent = step.state;
      setBilingualText(circuitInspectCopy, step.zh, step.en);
    }
    circuitInspectSteps.forEach(function (button) { button.addEventListener('click', function () { chooseStep(button); }); });
    chooseStep(circuitInspectSteps[0]);
  }

  function renderBellTeachingCounts(zeroShare, oneShare) {
    if (bellZeroBar) bellZeroBar.style.width = zeroShare.toFixed(2) + '%';
    if (bellOneBar) bellOneBar.style.width = oneShare.toFixed(2) + '%';
    if (bellZeroCount) bellZeroCount.textContent = zeroShare.toFixed(0) + '%';
    if (bellOneCount) bellOneCount.textContent = oneShare.toFixed(0) + '%';
  }

  function initBellShotAccumulator() {
    if (!bellOneShot || !bellAutoShots) return;
    var oneShotIndex = 0;
    var oneShotSequence = ['00', '11', '00', '11'];
    var zeroShare = 0;
    var oneShare = 0;
    renderBellTeachingCounts(zeroShare, oneShare);
    bellOneShot.addEventListener('click', function () {
      if (bellAnimationCancel) bellAnimationCancel();
      var result = oneShotSequence[oneShotIndex % oneShotSequence.length];
      oneShotIndex += 1;
      setBilingualText(bellShotResult, '这一次测量读到 ' + result + '。一次测量看不出分布；shots 是把同一份电路重新准备并测量很多次。', 'This measurement returned ' + result + '. One measurement cannot show a distribution; shots means preparing the same circuit and measuring it many times.');
    });
    bellAutoShots.addEventListener('click', function () {
      if (bellAnimationCancel) bellAnimationCancel();
      bellAnimationCancel = runTeachingAnimation(800, function (progress) {
        zeroShare = 50 * progress;
        oneShare = 50 * progress;
        renderBellTeachingCounts(zeroShare, oneShare);
      }, function () {
        zeroShare = 50;
        oneShare = 50;
        renderBellTeachingCounts(zeroShare, oneShare);
        setBilingualText(bellShotResult, '100 次测量后，00 和 11 各约 50%。一次测量看不出分布；shots 是把同一份电路重新准备并测量很多次。', 'After 100 measurements, 00 and 11 are about 50% each. One measurement cannot show a distribution; shots means preparing the same circuit and measuring it many times.');
      });
    });
  }

  function initAgentPromptCards() {
    if (!agentPromptCards.length || !promptField) return;
    agentPromptCards.forEach(function (card) {
      card.addEventListener('click', function () {
        promptField.value = card.dataset.agentPrompt || '';
        selectedExample = null;
        quickActionButtons.forEach(function (button) { button.classList.remove('is-selected'); });
        var experiment = document.querySelector('#experiment');
        if (experiment) experiment.scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth', block: 'start' });
        window.setTimeout(function () { promptField.focus(); }, isReduced ? 0 : 450);
      });
    });
  }

  function applyLanguage(language) {
    currentLanguage = language === 'en' ? 'en' : 'zh';
    document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
    [].slice.call(document.querySelectorAll('[data-zh][data-en]')).forEach(function (element) {
      element.textContent = currentLanguage === 'zh' ? element.dataset.zh : element.dataset.en;
    });
    [].slice.call(document.querySelectorAll('[data-placeholder-zh][data-placeholder-en]')).forEach(function (element) {
      element.placeholder = currentLanguage === 'zh' ? element.dataset.placeholderZh : element.dataset.placeholderEn;
    });
    [].slice.call(document.querySelectorAll('[data-stroke-lang]')).forEach(function (group) {
      group.toggleAttribute('hidden', group.dataset.strokeLang !== currentLanguage);
    });
    var localizedStrokeText = document.querySelector('[data-stroke-text]');
    if (localizedStrokeText) localizedStrokeText.setAttribute('aria-label', pick('先看见一个结果', 'See a result first'));
    languageToggle.setAttribute('aria-pressed', currentLanguage === 'en' ? 'true' : 'false');
    languageToggle.setAttribute('aria-label', pick('切换到英文', 'Switch to Chinese'));
    document.querySelector('[data-language-label]').textContent = '中 / EN';
    applyLocalizedAttributes();
    updateStrokeViewport();
    prepareScrollFloats();
    renderStepper();
    qubitStoryState = null;
    bellStoryState = null;
    updateScrollTutorials();
    renderPauli(currentPauliBasis);
    if (lastBackendAvailability) renderBackendAvailability(lastBackendAvailability);
    if (lastExperimentData) {
      if (lastExperimentData.kind === 'recommendation') showRecommendationWorkspace(lastExperimentData);
      else showCircuitWorkspace(lastExperimentData);
      formStatus.textContent = lastExperimentData.mode === 'local_example'
        ? pick('本地 Bell 示例完成：没有调用模型；电路已检查并由 SDK 执行。', 'Local Bell experiment complete: no model was called; the circuit was checked and run through the SDK.')
        : pick('你的描述已整理成电路，检查后由 SDK 执行。', 'Your description became a circuit, passed checks, and ran through the SDK.');
    }
    scheduleScrollUpdate();
  }

  function setRuntimeStatus(message, state) {
    runtimeStatusCopy.textContent = message;
    runtimeStatus.dataset.state = state || '';
  }

  function renderBackendAvailability(backends) {
    lastBackendAvailability = backends || {};
    var availableKeys = [];
    var optionLabels = [];
    if (targetField) {
      [].slice.call(targetField.options).forEach(function (option) {
        var key = option.value;
        var detail = lastBackendAvailability[key] || {};
        var available = detail.available === true;
        var baseLabel = option.dataset.labelZh || option.dataset.labelEn || option.textContent.replace(/\s+·.*$/, '');
        option.dataset.labelZh = option.dataset.labelZh || baseLabel;
        option.dataset.labelEn = option.dataset.labelEn || baseLabel;
        option.disabled = !available;
        option.textContent = currentLanguage === 'zh'
          ? option.dataset.labelZh + (available ? '' : ' · SDK 不可用')
          : option.dataset.labelEn + (available ? '' : ' · SDK unavailable');
        if (available) {
          availableKeys.push(key);
          optionLabels.push(currentLanguage === 'zh' ? option.dataset.labelZh : option.dataset.labelEn);
        }
      });
      if (availableKeys.indexOf(targetField.value) === -1) targetField.value = availableKeys[0] || '';
      targetField.disabled = availableKeys.length === 0;
    }
    backendAvailabilityReady = availableKeys.length > 0;
    if (backendAvailabilityCopy) {
      if (availableKeys.length) {
        setBilingualText(
          backendAvailabilityCopy,
          '可用本地后端：' + optionLabels.join('、') + '。现成 Bell 实验可以直接运行。',
          'Available local backends: ' + optionLabels.join(', ') + '. The ready-made Bell experiment can run directly.'
        );
        backendAvailabilityCopy.classList.remove('is-error');
      } else {
        setBilingualText(
          backendAvailabilityCopy,
          '没有检测到可用的本地 SDK。请运行 .\\starter_kit\\scripts\\setup.ps1 后再启动 .\\starter_kit\\scripts\\run_web.ps1。',
          'No local SDK backend is available. Run .\\starter_kit\\scripts\\setup.ps1, then start .\\starter_kit\\scripts\\run_web.ps1.'
        );
        backendAvailabilityCopy.classList.add('is-error');
      }
    }
    return availableKeys.length > 0;
  }

  function loadRuntimeStatus() {
    if (isStaticFile) {
      launchNotice.hidden = false;
      setRuntimeStatus(pick('实验接口未启动 · 请通过 LoomQ 本地服务打开', 'Experiment service offline · open LoomQ through the local service'), 'offline');
      return;
    }
    backendAvailabilityReady = false;
    if (targetField) targetField.disabled = true;
    fetch('/api/health', { headers: { 'Accept': 'application/json' } })
      .then(function (response) {
        if (!response.ok) throw new Error('health endpoint unavailable');
        return response.json();
      })
      .then(function (health) {
        var hasAvailableBackend = renderBackendAvailability(health.backends || {});
        if (health.llm_configured) {
          setRuntimeStatus(
            hasAvailableBackend
              ? pick('模型服务已连接 · Bell 实验和自己的问题都可以运行', 'Model service connected · Bell and your own question can run')
              : pick('模型服务已连接 · 但本地 SDK 后端不可用', 'Model service connected · but no local SDK backend is available'),
            hasAvailableBackend ? 'connected' : 'offline'
          );
        } else {
          setRuntimeStatus(
            hasAvailableBackend
              ? pick('还没有连接模型 · 现成的 Bell 实验仍可直接运行', 'No model connected yet · the Bell experiment still runs directly')
              : pick('本地 SDK 后端不可用 · 请先完成本地设置', 'Local SDK backend unavailable · complete the local setup first'),
            hasAvailableBackend ? 'local' : 'offline'
          );
        }
      })
      .catch(function () {
        backendAvailabilityReady = false;
        if (targetField) targetField.disabled = true;
        if (backendAvailabilityCopy) setBilingualText(backendAvailabilityCopy, '无法读取本地 SDK 状态，请确认服务仍在运行。', 'Could not read local SDK status; check that the service is running.');
        setRuntimeStatus(pick('本地服务暂时不可用 · 请确认 Python 服务仍在运行', 'Local service unavailable · check that the Python service is running'), 'offline');
      });
  }

  function apiError(code, message) {
    var error = new Error(message || '实验未完成');
    error.code = code || '';
    return error;
  }

  function failureMessage(error) {
    if (isStaticFile) {
      return pick('当前打开的是静态页面，所以实验按钮暂时无法连接本地接口。运行 LoomQ 本地服务后，再从浏览器打开：', 'This is a static page, so the experiment button cannot reach the local service yet. Start the LoomQ local service, then open: ') + localServiceUrl;
    }
    if (error.code === 'agent_unavailable') return error.message;
    if (error.code === 'backend_unavailable') return error.message;
    if (error.code === 'invalid_request') return pick('请检查你的描述或实验设置：', 'Input validation failed: ') + error.message;
    if (error.code === 'execution_failed') return pick('这次实验没有完成：', 'The quantum SDK did not complete the run: ') + error.message;
    if (error instanceof TypeError || error.code === 'network_unavailable') {
      return pick('无法连接 LoomQ 本地服务。请确认 Python 服务已启动，并访问 ', 'Cannot reach the LoomQ local service. Start the Python service and visit ') + localServiceUrl + (currentLanguage === 'zh' ? '。' : '.');
    }
    return pick('这次实验没有完成：', 'The experiment did not complete: ') + error.message;
  }

  function tutorialProgress(section) {
    var stage = section.querySelector('.tutorial-story-stage');
    var frame = section.querySelector('.tutorial-story-frame');
    if (!stage || !frame) return 0;
    var stageRect = stage.getBoundingClientRect();
    var sectionRect = section.getBoundingClientRect();
    var stickyTop = parseFloat(window.getComputedStyle(stage).top);
    if (!Number.isFinite(stickyTop)) stickyTop = window.innerWidth <= 767 ? 62 : 68;
    var isSticky = window.getComputedStyle(stage).position === 'sticky';
    if (!isSticky) {
      var naturalTravel = Math.max(section.offsetHeight - window.innerHeight + stickyTop, 1);
      return clamp((stickyTop - sectionRect.top) / naturalTravel, 0, 1);
    }

    var geometry = tutorialGeometry.get(section);
    var frameRect = frame.getBoundingClientRect();
    if (!geometry) {
      var naturalStageRect = stageRect;
      if (stageRect.top <= stickyTop + 1) {
        var previousPosition = stage.style.position;
        var previousTop = stage.style.top;
        stage.style.position = 'static';
        stage.style.top = 'auto';
        naturalStageRect = stage.getBoundingClientRect();
        stage.style.position = previousPosition;
        stage.style.top = previousTop;
      }
      geometry = { stageOffsetInFrame: naturalStageRect.top - frameRect.top };
      tutorialGeometry.set(section, geometry);
    }
    var frameDocumentTop = frameRect.top + window.scrollY;
    var stageDocumentTop = frameDocumentTop + geometry.stageOffsetInFrame;
    var frameDocumentBottom = frameDocumentTop + frame.offsetHeight;
    var stickyStart = stageDocumentTop - stickyTop;
    var stickyEnd = frameDocumentBottom - stage.offsetHeight - stickyTop;
    var stickyTravel = Math.max(stickyEnd - stickyStart, 1);
    return clamp((window.scrollY - stickyStart) / stickyTravel, 0, 1);
  }

  function updateScrollTutorials() {
    if (!scrollTutorials.length) return;
    var qubitCard = scrollTutorials[0].querySelector('.tutorial-card');
    var qubitProgress = isReduced ? 1 : tutorialProgress(scrollTutorials[0]);
    qubitCard.style.setProperty('--progress', qubitProgress.toFixed(4));
    var zeroProbability = 100 - (qubitProgress * 50);
    var oneProbability = qubitProgress * 50;
    qubitCard.querySelector('.state-fill-zero').style.width = zeroProbability.toFixed(2) + '%';
    qubitCard.querySelector('.state-fill-one').style.width = oneProbability.toFixed(2) + '%';
    qubitCard.querySelector('.state-value-zero').textContent = zeroProbability.toFixed(0) + '%';
    qubitCard.querySelector('.state-value-one').textContent = oneProbability.toFixed(0) + '%';
    var singleGate = qubitCard.querySelector('.qubit-gate');
    singleGate.style.opacity = clamp(qubitProgress * 1.4, 0, 1).toFixed(3);
    singleGate.style.transform = 'translateX(' + ((1 - qubitProgress) * 14).toFixed(2) + 'px)';
    var nextQubitStoryState = qubitProgress < 0.34 ? 'before' : (qubitProgress < 0.7 ? 'gate' : 'distribution');
    if (nextQubitStoryState !== qubitStoryState) {
      qubitStoryState = nextQubitStoryState;
      qubitStoryLine.textContent = nextQubitStoryState === 'before'
        ? pick('现在，测量会得到 0。', 'A measurement now returns 0.')
        : (nextQubitStoryState === 'gate'
          ? pick('接着加入 H。先看它带来的变化。', 'Next, add H. Watch the change first.')
          : pick('重复测量以后，0 和 1 会各出现约一半。', 'After repeated measurements, 0 and 1 each appear about half.'));
    }

    var bellCard = scrollTutorials[1].querySelector('.tutorial-card');
    var bellProgress = isReduced ? 1 : tutorialProgress(scrollTutorials[1]);
    bellCard.style.setProperty('--progress', bellProgress.toFixed(4));
    var gateProgress = clamp(bellProgress / 0.3, 0, 1);
    var connectorProgress = clamp((bellProgress - 0.25) / 0.4, 0, 1);
    var resultProgress = clamp((bellProgress - 0.55) / 0.45, 0, 1);
    bellCard.querySelector('.bell-h').style.opacity = gateProgress.toFixed(3);
    bellCard.querySelector('.bell-h').style.transform = 'translateX(' + ((1 - gateProgress) * 14).toFixed(2) + 'px)';
    bellCard.querySelector('.bell-control').style.opacity = connectorProgress.toFixed(3);
    bellCard.querySelector('.bell-target').style.opacity = connectorProgress.toFixed(3);
    bellCard.querySelector('.bell-connector').style.opacity = connectorProgress.toFixed(3);
    bellCard.querySelector('.bell-connector').style.transform = 'scaleY(' + connectorProgress.toFixed(3) + ')';
    var resultPercentage = resultProgress * 50;
    bellCard.querySelector('.distribution-fill-zero').style.width = resultPercentage.toFixed(2) + '%';
    bellCard.querySelector('.distribution-fill-one').style.width = resultPercentage.toFixed(2) + '%';
    bellCard.querySelector('.distribution-value-zero').textContent = resultPercentage.toFixed(0) + '%';
    bellCard.querySelector('.distribution-value-one').textContent = resultPercentage.toFixed(0) + '%';
    var nextBellStoryState = bellProgress < 0.2 ? 'start' : (bellProgress < 0.48 ? 'h' : (bellProgress < 0.78 ? 'cnot' : 'result'));
    if (nextBellStoryState !== bellStoryState) {
      bellStoryState = nextBellStoryState;
      bellStoryLine.textContent = nextBellStoryState === 'start'
        ? pick('两个量子比特都从 0 开始。', 'Both qubits begin at 0.')
        : (nextBellStoryState === 'h'
          ? pick('先让 q0 经过 H。', 'First, send q0 through H.')
          : (nextBellStoryState === 'cnot'
            ? pick('加入 CNOT：q0 控制 q1。', 'Add CNOT: q0 controls q1.')
            : pick('最后主要留下 00 和 11，各约一半。', 'The result settles near half 00 and half 11.')));
    }
  }

  function scheduleScrollUpdate() {
    if (isReduced || scrollFrameId) return;
    scrollFrameId = window.requestAnimationFrame(function () {
      scrollFrameId = 0;
      updateScrollTutorials();
    });
  }

  function renderStepper() {
    var content = stepData[stepIndex][currentLanguage];
    stepperSteps.forEach(function (step, index) {
      if (index === stepIndex) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
    stepperLabel.textContent = content.label;
    stepperTitle.textContent = content.title;
    stepperDescription.textContent = content.description;
    stepperProgressFill.style.width = ((stepIndex + 1) * 20) + '%';
    stepperPrev.disabled = stepIndex === 0;
    stepperNext.hidden = stepIndex === stepData.length - 1;
    stepperFinish.hidden = false;
  }

  function initStepper() {
    stepperPrev.addEventListener('click', function () {
      stepIndex = clamp(stepIndex - 1, 0, stepData.length - 1);
      renderStepper();
    });
    stepperNext.addEventListener('click', function () {
      stepIndex = clamp(stepIndex + 1, 0, stepData.length - 1);
      renderStepper();
    });
    stepperFinish.addEventListener('click', function () {
      document.querySelector('#experiment').scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth', block: 'start' });
    });
    renderStepper();
  }

  function setSpotlightPosition(card, clientX, clientY) {
    var rect = card.getBoundingClientRect();
    var x = clamp(clientX - rect.left, 0, rect.width);
    var y = clamp(clientY - rect.top, 0, rect.height);
    card.style.setProperty('--mouse-x', x.toFixed(1) + 'px');
    card.style.setProperty('--mouse-y', y.toFixed(1) + 'px');
    card.style.setProperty('--spotlight-color', 'rgba(0, 113, 227, 0.14)');
  }

  function initSpotlightCards() {
    [].slice.call(document.querySelectorAll('.spotlight-card')).forEach(function (card) {
      var pointerFrame = 0;
      var pendingPointer = null;
      card.addEventListener('pointermove', function (event) {
        if (event.pointerType === 'touch') return;
        pendingPointer = { x: event.clientX, y: event.clientY };
        if (pointerFrame) return;
        pointerFrame = window.requestAnimationFrame(function () {
          pointerFrame = 0;
          if (pendingPointer) setSpotlightPosition(card, pendingPointer.x, pendingPointer.y);
        });
      }, { passive: true });
      card.addEventListener('pointerleave', function () {
        pendingPointer = null;
        if (pointerFrame) {
          window.cancelAnimationFrame(pointerFrame);
          pointerFrame = 0;
        }
      }, { passive: true });
      card.addEventListener('focus', function () {
        var rect = card.getBoundingClientRect();
        setSpotlightPosition(card, rect.left + (rect.width / 2), rect.top + (rect.height / 2));
      });
    });
  }

  function helpTargetFor(trigger) {
    return trigger && trigger.dataset.helpTarget ? document.getElementById(trigger.dataset.helpTarget) : null;
  }

  function cancelHelpClose() {
    if (!helpCloseTimer) return;
    window.clearTimeout(helpCloseTimer);
    helpCloseTimer = 0;
  }

  function positionHelp(trigger, target) {
    if (!trigger || !target || target.hidden) return;
    var triggerRect = trigger.getBoundingClientRect();
    var margin = 16;
    target.style.visibility = 'hidden';
    target.style.left = margin + 'px';
    target.style.top = margin + 'px';
    var targetRect = target.getBoundingClientRect();
    var left = triggerRect.left + (triggerRect.width / 2) - (targetRect.width / 2);
    var top = triggerRect.bottom + 10;
    if (left + targetRect.width > window.innerWidth - margin) left = window.innerWidth - targetRect.width - margin;
    if (left < margin) left = margin;
    if (top + targetRect.height > window.innerHeight - margin) top = triggerRect.top - targetRect.height - 10;
    if (top < margin) top = margin;
    target.style.left = Math.round(left) + 'px';
    target.style.top = Math.round(top) + 'px';
    target.classList.toggle('term-help--above', top < triggerRect.top);
    target.style.visibility = '';
  }

  function hideHelp(trigger) {
    if (!trigger) trigger = activeHelpTrigger || activePinnedHelp;
    if (!trigger) return;
    var target = helpTargetFor(trigger);
    if (target) {
      target.hidden = true;
      target.style.left = '';
      target.style.top = '';
      target.style.visibility = '';
    }
    trigger.setAttribute('aria-expanded', 'false');
    if (activePinnedHelp === trigger) activePinnedHelp = null;
    if (activeHelpTrigger === trigger) activeHelpTrigger = null;
  }

  function scheduleHideHelp(trigger) {
    if (activePinnedHelp === trigger) return;
    cancelHelpClose();
    helpCloseTimer = window.setTimeout(function () {
      helpCloseTimer = 0;
      if (activePinnedHelp !== trigger) hideHelp(trigger);
    }, 90);
  }

  function showHelp(trigger, pinned) {
    var target = helpTargetFor(trigger);
    if (!target) return;
    cancelHelpClose();
    if (activeHelpTrigger && activeHelpTrigger !== trigger) hideHelp(activeHelpTrigger);
    if (activePinnedHelp && activePinnedHelp !== trigger) hideHelp(activePinnedHelp);
    activeHelpTrigger = trigger;
    if (pinned) activePinnedHelp = trigger;
    target.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    trigger.setAttribute('aria-controls', target.id);
    trigger.setAttribute('aria-describedby', target.id);
    window.requestAnimationFrame(function () { positionHelp(trigger, target); });
  }

  function repairStaticTermHelpMarkup() {
    var onboardingGrid = document.querySelector('#onboarding .onboarding-grid');
    var onboardingFooter = onboardingGrid ? onboardingGrid.querySelector('.onboarding-footer-note') : null;
    if (onboardingGrid && onboardingFooter && onboardingFooter.tagName === 'P') {
      var footerReplacement = document.createElement('div');
      [].slice.call(onboardingFooter.attributes).forEach(function (attribute) { footerReplacement.setAttribute(attribute.name, attribute.value); });
      while (onboardingFooter.firstChild) footerReplacement.appendChild(onboardingFooter.firstChild);
      onboardingFooter.parentNode.replaceChild(footerReplacement, onboardingFooter);
      onboardingFooter = footerReplacement;
    }
    if (onboardingGrid && onboardingFooter) {
      [].slice.call(onboardingGrid.children).forEach(function (child) {
        if (child.classList.contains('term-help-anchor')) onboardingFooter.appendChild(child);
      });
    }
    [].slice.call(document.querySelectorAll('.term-help')).forEach(function (target) {
      if (target.querySelector('p, .term-help-copy')) return;
      var anchor = target.parentElement;
      var owner = anchor;
      var orphan = owner ? owner.nextElementSibling : null;
      while (owner && owner.parentElement && (!orphan || !(orphan.tagName === 'P' && orphan.hasAttribute('data-zh')))) {
        owner = owner.parentElement;
        orphan = owner.nextElementSibling;
      }
      if (!orphan || orphan.tagName !== 'P' || !orphan.hasAttribute('data-zh')) return;
      target.appendChild(orphan);
      var emptyParagraph = owner.nextElementSibling;
      if (emptyParagraph && emptyParagraph.tagName === 'P' && !emptyParagraph.textContent.trim()) emptyParagraph.remove();
    });
  }

  function initTermHelp() {
    var triggers = [].slice.call(document.querySelectorAll('.term-help-trigger, .help-button'));
    triggers.forEach(function (trigger) {
      var target = helpTargetFor(trigger);
      if (!target) return;
      trigger.setAttribute('aria-controls', target.id);
      trigger.setAttribute('aria-describedby', target.id);
      trigger.addEventListener('pointerenter', function (event) {
        if (event.pointerType === 'touch') return;
        showHelp(trigger, false);
      });
      trigger.addEventListener('pointerleave', function () { scheduleHideHelp(trigger); });
      trigger.addEventListener('focus', function () { showHelp(trigger, false); });
      trigger.addEventListener('blur', function () { scheduleHideHelp(trigger); });
      trigger.addEventListener('click', function (event) {
        event.stopPropagation();
        if (activePinnedHelp === trigger) {
          hideHelp(trigger);
          return;
        }
        if (activePinnedHelp) hideHelp(activePinnedHelp);
        showHelp(trigger, true);
      });
      trigger.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        event.preventDefault();
        hideHelp(trigger);
        trigger.focus();
      });
      target.addEventListener('pointerenter', function (event) {
        if (event.pointerType !== 'touch') cancelHelpClose();
      });
      target.addEventListener('pointerleave', function (event) {
        if (event.pointerType !== 'touch') scheduleHideHelp(trigger);
      });
    });
    document.addEventListener('click', function (event) {
      if (!activeHelpTrigger) return;
      var target = helpTargetFor(activeHelpTrigger);
      if (activeHelpTrigger.contains(event.target) || (target && target.contains(event.target))) return;
      hideHelp(activeHelpTrigger);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !activeHelpTrigger) return;
      var trigger = activeHelpTrigger;
      hideHelp(trigger);
      trigger.focus();
    });
    window.addEventListener('scroll', function () {
      if (activeHelpTrigger) positionHelp(activeHelpTrigger, helpTargetFor(activeHelpTrigger));
    }, { passive: true });
    window.addEventListener('resize', function () {
      if (activeHelpTrigger) positionHelp(activeHelpTrigger, helpTargetFor(activeHelpTrigger));
    });
  }

  function setSidebarRest() {
    lineSidebarItems.forEach(function (item) { item.style.setProperty('--proximity', '0'); });
  }

  function updateSidebarProximity(event) {
    var rect = lineSidebar.getBoundingClientRect();
    var localY = event.clientY - rect.top;
    lineSidebarItems.forEach(function (item) {
      var center = item.offsetTop + (item.offsetHeight / 2);
      var proximity = clamp(1 - (Math.abs(localY - center) / 120), 0, 1);
      item.style.setProperty('--proximity', proximity.toFixed(3));
    });
  }

  function initLineSidebar() {
    if (!lineSidebar) return;
    lineSidebar.addEventListener('pointerenter', updateSidebarProximity, { passive: true });
    lineSidebar.addEventListener('pointermove', updateSidebarProximity, { passive: true });
    lineSidebar.addEventListener('pointerleave', setSidebarRest);
    lineSidebarItems.forEach(function (item) {
      item.addEventListener('focus', function () { item.style.setProperty('--proximity', '1'); });
      item.addEventListener('blur', function () { item.style.setProperty('--proximity', '0'); });
    });
    setSidebarRest();

    if (!('IntersectionObserver' in window)) return;
    var trackedSections = [].slice.call(document.querySelectorAll('.tracked-section'));
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var sectionId = entry.target.dataset.section;
        lineSidebarItems.forEach(function (item) {
          if (item.getAttribute('href') === '#' + sectionId) item.setAttribute('aria-current', 'location');
          else item.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-38% 0px -48% 0px', threshold: 0 });
    trackedSections.forEach(function (section) { observer.observe(section); });
  }

  function setBusy(busy) {
    runButton.disabled = busy;
    runButton.setAttribute('aria-busy', busy ? 'true' : 'false');
    runButton.querySelector('.run-label').textContent = busy
      ? pick('正在执行…', 'Running…')
      : pick('执行这个实验', 'Run this experiment');
    if (busy) {
      formStatus.classList.remove('is-error');
      formStatus.textContent = pick(
        '正在准备、检查并运行这次实验；状态来自真实返回。',
        'LoomQ is preparing, checking, and running the experiment; this status comes from the real response.'
      );
    }
  }

  function groupCircuitColumns(operations) {
    var columns = [];
    operations.forEach(function (operation) {
      var previous = columns[columns.length - 1];
      var isMeasurement = operation.type === 'measurement';
      var previousIsMeasurementColumn = previous && previous.every(function (item) { return item.type === 'measurement'; });
      if (isMeasurement && previousIsMeasurementColumn) previous.push(operation);
      else columns.push([operation]);
    });
    return columns;
  }

  function renderCircuit(circuit) {
    clear(circuitView);
    var operations = circuit.operations || [];
    var columns = groupCircuitColumns(operations);
    var qubitCount = circuit.qubit_count || 0;
    var layout = makeEl('div', 'circuit-layout');
    var width = Math.max(420, (Math.max(columns.length, 1) * 118) + 92);
    var height = Math.max(150, (Math.max(qubitCount, 1) * 58) + 48);
    var svg = makeSvgEl('svg', 'quantum-circuit-svg');
    var railLeft = 42;
    var railRight = width - 28;
    var yStart = 38;
    var rowGap = qubitCount > 1 ? Math.min(66, (height - 58) / (qubitCount - 1)) : 0;
    var columnStep = columns.length > 1 ? (railRight - 72) / (columns.length - 1) : 0;
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('width', '100%');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', currentLanguage === 'zh' ? '量子电路图' : 'Quantum circuit diagram');
    var title = makeSvgEl('title', '', currentLanguage === 'zh' ? '量子电路：H、CNOT，然后测量' : 'Quantum circuit: H, CNOT, then measurement');
    svg.appendChild(title);
    for (var q = 0; q < qubitCount; q += 1) {
      var y = yStart + (rowGap * q);
      var rail = makeSvgEl('line', 'circuit-rail');
      rail.setAttribute('x1', railLeft);
      rail.setAttribute('x2', railRight);
      rail.setAttribute('y1', y);
      rail.setAttribute('y2', y);
      rail.setAttribute('data-role', 'rail');
      rail.setAttribute('data-qubit', 'q' + q);
      svg.appendChild(rail);
      var label = makeSvgEl('text', 'circuit-label-svg', 'q' + q);
      label.setAttribute('x', 10);
      label.setAttribute('y', y);
      label.setAttribute('dominant-baseline', 'central');
      label.setAttribute('aria-hidden', 'true');
      svg.appendChild(label);
    }
    columns.forEach(function (column, columnIndex) {
      var operation = column.filter(function (item) { return item.type === 'gate' && item.qubits && item.qubits.length > 1; })[0] || null;
      var measurementByQubit = {};
      column.forEach(function (item) {
        if (item.type === 'measurement') measurementByQubit[item.qubit] = item;
      });
      var x = columns.length > 1 ? 72 + (columnStep * columnIndex) : ((railLeft + railRight) / 2);
      if (operation) {
        var controlQubit = operation.qubits[0];
        var targetQubit = operation.qubits[1];
        var connector = makeSvgEl('line', 'circuit-connector-svg');
        connector.setAttribute('x1', x);
        connector.setAttribute('x2', x);
        connector.setAttribute('y1', yStart + (rowGap * controlQubit));
        connector.setAttribute('y2', yStart + (rowGap * targetQubit));
        connector.setAttribute('data-role', 'connector');
        connector.setAttribute('aria-hidden', 'true');
        svg.appendChild(connector);
      }
      for (var row = 0; row < qubitCount; row += 1) {
        var rowY = yStart + (rowGap * row);
        if (measurementByQubit[row]) {
          var measurementGlyph = makeSvgEl('g', 'measurement-glyph-svg');
          measurementGlyph.setAttribute('data-role', 'measurement');
          measurementGlyph.setAttribute('aria-label', pick('测量 q' + row, 'Measure q' + row));
          var measurementBox = makeSvgEl('rect', 'measurement-box-svg');
          measurementBox.setAttribute('x', x - 18);
          measurementBox.setAttribute('y', rowY - 18);
          measurementBox.setAttribute('width', 36);
          measurementBox.setAttribute('height', 36);
          measurementGlyph.appendChild(measurementBox);
          var measurementLabel = makeSvgEl('text', 'measurement-label-svg', 'M');
          measurementLabel.setAttribute('x', x);
          measurementLabel.setAttribute('y', rowY + 1);
          measurementLabel.setAttribute('text-anchor', 'middle');
          measurementLabel.setAttribute('dominant-baseline', 'central');
          measurementGlyph.appendChild(measurementLabel);
          svg.appendChild(measurementGlyph);
        } else if (operation && operation.qubits.indexOf(row) !== -1) {
          var operationName = String(operation.name || '').toLowerCase();
          var controlQubit = operation.qubits[0];
          var targetQubit = operation.qubits[1];
          if (row === controlQubit) {
            var controlGlyph = makeSvgEl('circle', 'circuit-control-svg');
            controlGlyph.setAttribute('cx', x);
            controlGlyph.setAttribute('cy', rowY);
            controlGlyph.setAttribute('r', 7);
            controlGlyph.setAttribute('data-role', 'control');
            controlGlyph.setAttribute('aria-label', controlQubit === 0 ? pick('控制位 q0', 'control q0') : pick('控制位 q' + controlQubit, 'control q' + controlQubit));
            svg.appendChild(controlGlyph);
          } else if (row === targetQubit && (operationName === 'cx' || operationName === 'cnot')) {
            var targetGlyph = makeSvgEl('g', 'circuit-target-svg');
            targetGlyph.setAttribute('data-role', 'target');
            targetGlyph.setAttribute('aria-label', targetQubit === 1 ? pick('目标位 q1', 'target q1') : pick('目标位 q' + targetQubit, 'target q' + targetQubit));
            var targetCircle = makeSvgEl('circle', 'circuit-target-ring');
            targetCircle.setAttribute('cx', x);
            targetCircle.setAttribute('cy', rowY);
            targetCircle.setAttribute('r', 17);
            targetGlyph.appendChild(targetCircle);
            var targetCrossA = makeSvgEl('line', 'circuit-target-cross');
            targetCrossA.setAttribute('x1', x - 11);
            targetCrossA.setAttribute('y1', rowY);
            targetCrossA.setAttribute('x2', x + 11);
            targetCrossA.setAttribute('y2', rowY);
            targetGlyph.appendChild(targetCrossA);
            var targetCrossB = makeSvgEl('line', 'circuit-target-cross');
            targetCrossB.setAttribute('x1', x);
            targetCrossB.setAttribute('y1', rowY - 11);
            targetCrossB.setAttribute('x2', x);
            targetCrossB.setAttribute('y2', rowY + 11);
            targetGlyph.appendChild(targetCrossB);
            svg.appendChild(targetGlyph);
          } else {
            var multiLabel = String(operation.name || 'gate').toUpperCase();
            var multiText = makeSvgEl('text', 'circuit-gate-label-svg', multiLabel);
            multiText.setAttribute('x', x);
            multiText.setAttribute('y', rowY + 1);
            multiText.setAttribute('text-anchor', 'middle');
            multiText.setAttribute('dominant-baseline', 'central');
            svg.appendChild(multiText);
          }
        } else {
          var singleOperation = column.filter(function (item) { return item.type === 'gate' && item.qubits && item.qubits.indexOf(row) !== -1; })[0];
          if (singleOperation) {
            var singleLabel = String(singleOperation.name || 'gate').toUpperCase();
            if (singleOperation.params && singleOperation.params.length) singleLabel += '(' + Number(singleOperation.params[0]).toFixed(2) + ')';
            var gateGroup = makeSvgEl('g', 'circuit-gate-svg');
            gateGroup.setAttribute('data-role', 'gate');
            gateGroup.setAttribute('aria-label', pick(singleLabel + ' q' + row, singleLabel + ' q' + row));
            var gateBox = makeSvgEl('rect', 'circuit-gate-box');
            gateBox.setAttribute('x', x - 18);
            gateBox.setAttribute('y', rowY - 18);
            gateBox.setAttribute('width', 36);
            gateBox.setAttribute('height', 36);
            gateGroup.appendChild(gateBox);
            var gateText = makeSvgEl('text', 'circuit-gate-label-svg', singleLabel);
            gateText.setAttribute('x', x);
            gateText.setAttribute('y', rowY + 1);
            gateText.setAttribute('text-anchor', 'middle');
            gateText.setAttribute('dominant-baseline', 'central');
            gateGroup.appendChild(gateText);
            svg.appendChild(gateGroup);
          }
        }
      }
    });
    layout.appendChild(svg);
    circuitView.appendChild(layout);
    var metrics = circuit.metrics || {};
    circuitNote.textContent = currentLanguage === 'zh'
      ? qubitCount + ' 个量子比特 · ' + (metrics.transpiled_gates || 0) + ' 个门 · 深度 ' + (metrics.depth || 0)
      : qubitCount + ' qubits · ' + (metrics.transpiled_gates || 0) + ' gates · depth ' + (metrics.depth || 0);
    circuitView.setAttribute('aria-label', currentLanguage === 'zh'
      ? qubitCount + ' 比特量子电路，包含 ' + operations.length + ' 个操作'
      : qubitCount + '-qubit circuit with ' + operations.length + ' operations');
  }

  function renderVerification(verification) {
    clear(verificationList);
    var checks = verification && verification.checks ? verification.checks : [];
    checks.forEach(function (check) {
      var item = makeEl('li');
      item.appendChild(makeEl('span', 'check-dot'));
      var label = check.label || '';
      if (currentLanguage === 'en') {
        label = {
          'OpenQASM 2.0 语法': 'OpenQASM 2.0 syntax',
          '官方 12 门边界': 'Official 12-gate boundary',
          '本地无噪声模拟': 'Local noiseless simulation'
        }[label] || label.replace('真实本地后端完成：', 'Real local backend completed: ');
      }
      item.appendChild(makeEl('span', '', label));
      item.appendChild(makeEl('small', '', check.status === 'passed' ? 'PASS' : (currentLanguage === 'en' ? 'REVIEW' : 'REVIEW')));
      verificationList.appendChild(item);
    });
  }

  function renderCounts(result) {
    clear(countsChart);
    clear(countsTableBody);
    var counts = result.counts || {};
    var entries = Object.keys(counts).map(function (state) { return [state, Number(counts[state])]; });
    entries.sort(function (a, b) { return b[1] - a[1]; });
    entries.forEach(function (entry) {
      var state = entry[0];
      var count = entry[1];
      var ratio = result.shots ? count / result.shots : 0;
      var row = makeEl('div', 'count-row');
      row.tabIndex = 0;
      var tooltipCopy = currentLanguage === 'zh'
        ? state + ' · ' + count + ' / ' + result.shots + ' · ' + (ratio * 100).toFixed(1) + '%'
        : state + ' · ' + count + ' / ' + result.shots + ' · ' + (ratio * 100).toFixed(1) + '%';
      row.setAttribute('aria-label', tooltipCopy);
      row.appendChild(makeEl('span', 'count-state', state));
      var track = makeEl('div', 'bar-track');
      var fill = makeEl('div', 'bar-fill');
      fill.style.width = Math.max(ratio * 100, ratio > 0 ? 0.6 : 0).toFixed(2) + '%';
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(makeEl('span', 'count-value', (ratio * 100).toFixed(1) + '%'));
      row.appendChild(makeEl('span', 'count-tooltip', tooltipCopy));
      countsChart.appendChild(row);
      var tableRow = document.createElement('tr');
      tableRow.appendChild(makeEl('td', '', state));
      tableRow.appendChild(makeEl('td', '', String(count)));
      tableRow.appendChild(makeEl('td', '', (ratio * 100).toFixed(2) + '%'));
      countsTableBody.appendChild(tableRow);
    });
    var total = entries.reduce(function (sum, entry) { return sum + entry[1]; }, 0);
    resultTotal.textContent = currentLanguage === 'zh'
      ? '共 ' + result.shots + ' 次重复 · 已返回 ' + total + ' 次结果'
      : Number(result.shots).toLocaleString('en-US') + ' repetitions · ' + Number(total).toLocaleString('en-US') + ' results returned';
  }

  function showCircuitWorkspace(data) {
    workspace.classList.remove('is-recommendation');
    resultPanel.hidden = false;
    circuitPanel.hidden = false;
    qasmDisclosure.hidden = false;
    verificationList.hidden = false;
    verificationWrap.hidden = false;
    recommendation.hidden = true;
    explanation.hidden = data.mode === 'local_example';
    renderCircuit(data.circuit);
    renderVerification(data.verification);
    renderCounts(data.result);
    explanation.textContent = data.explanation || pick('这次实验完成了，结果已经返回。', 'The experiment is complete and the result has been returned.');
    resultBoundaryCopy.textContent = data.mode === 'local_example'
      ? pick(
        '这是一种测量方向看到的结果。继续向下，看看已归档真机数据在 X、Y、Z 方向怎样描述同一个状态。',
        'This is one measurement view. Continue to see how archived hardware data describes the same state in X, Y, and Z.'
      )
      : pick(
        '这次返回说明所选后端得到了这份电路的结果。更强的判断需要与问题匹配的额外实验和证据。',
        'This return reports what the selected backend produced. Stronger conclusions need additional experiments and evidence matched to the question.'
      );
    qasmCode.textContent = data.qasm || '';
    qasmDisclosure.open = true;
    runMeta.textContent = currentLanguage === 'zh'
      ? data.result.backend + ' · ' + data.result.shots + ' 次重复 · 位序：' + (data.result.bit_order === 'little' ? '低位在前（little-endian）' : data.result.bit_order)
      : data.result.backend + ' · ' + data.result.shots + ' repetitions · bit order: ' + (data.result.bit_order === 'little' ? 'little-endian' : data.result.bit_order);
  }

  function showRecommendationWorkspace(data) {
    workspace.classList.add('is-recommendation');
    resultPanel.hidden = true;
    circuitPanel.hidden = true;
    qasmDisclosure.hidden = true;
    verificationList.hidden = true;
    verificationWrap.hidden = true;
    explanation.hidden = false;
    explanation.textContent = pick('这是后端能力筛选与推荐。', 'This is a backend capability recommendation.');
    recommendation.hidden = false;
    recommendation.textContent = data.reply || data.explanation || '当前请求返回了后端能力推荐。';
    runMeta.textContent = pick('后端能力表 · 程序化筛选', 'Backend capability table · programmatic filter');
  }

  function renderExperiment(data) {
    workspace.hidden = false;
    if (data.kind === 'recommendation') showRecommendationWorkspace(data);
    else showCircuitWorkspace(data);
    formStatus.textContent = data.mode === 'local_example'
      ? pick('本地 Bell 示例完成：没有调用模型；电路已检查并由 SDK 执行。', 'Local Bell experiment complete: no model was called; the circuit was checked and run through the SDK.')
      : pick('你的描述已整理成电路，检查后由 SDK 执行。', 'Your description became a circuit, passed checks, and ran through the SDK.');
    workspace.scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth', block: 'start' });
  }

  quickActionButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      if (button === focusBackendAction) {
        var settings = document.querySelector('#experiment-settings');
        settings.open = true;
        targetField.focus();
        targetField.scrollIntoView({ behavior: isReduced ? 'auto' : 'smooth', block: 'center' });
        return;
      }
      promptField.value = button.dataset.prompt || '';
      selectedExample = button.dataset.example || null;
      quickActionButtons.forEach(function (item) { item.classList.toggle('is-selected', item === button); });
      promptField.focus();
    });
  });

  promptField.addEventListener('input', function () {
    var activeButton = quickActionButtons.filter(function (button) { return button.classList.contains('is-selected'); })[0];
    if (!activeButton || promptField.value !== activeButton.dataset.prompt) {
      selectedExample = null;
      quickActionButtons.forEach(function (button) { button.classList.remove('is-selected'); });
    }
  });

  languageToggle.addEventListener('click', function () {
    applyLanguage(currentLanguage === 'zh' ? 'en' : 'zh');
    loadRuntimeStatus();
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (isStaticFile) {
      launchNotice.hidden = false;
      formStatus.textContent = failureMessage(apiError('network_unavailable', ''));
      formStatus.classList.add('is-error');
      launchNotice.focus({ preventScroll: true });
      return;
    }
    if (!backendAvailabilityReady || !targetField || targetField.disabled || !targetField.value) {
      formStatus.textContent = pick(
        '当前没有可用的本地 SDK 后端。请先运行 .\\starter_kit\\scripts\\setup.ps1，再用 .\\starter_kit\\scripts\\run_web.ps1 启动。',
        'No local SDK backend is available. Run .\\starter_kit\\scripts\\setup.ps1, then start .\\starter_kit\\scripts\\run_web.ps1.'
      );
      formStatus.classList.add('is-error');
      if (backendAvailabilityCopy) backendAvailabilityCopy.focus({ preventScroll: true });
      return;
    }
    var prompt = promptField.value.trim();
    var shots = Number(shotsField.value);
    if (!prompt) {
      formStatus.textContent = pick('请先描述你想尝试的实验。', 'Describe the experiment you want to try first.');
      formStatus.classList.add('is-error');
      promptField.focus();
      return;
    }
    if (!Number.isInteger(shots) || shots < 1 || shots > 8192) {
      formStatus.textContent = pick('重复次数需要是 1 到 8192 之间的整数。', 'Repetitions must be a whole number from 1 to 8,192.');
      formStatus.classList.add('is-error');
      shotsField.focus();
      return;
    }
    setBusy(true);
    var payload = { prompt: prompt, target: targetField.value, shots: shots };
    if (selectedExample) payload.example = selectedExample;
    fetch('/api/experiment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok) {
          var detail = result.data && result.data.error ? result.data.error : {};
          throw apiError(detail.code, detail.message);
        }
        lastExperimentData = result.data;
        renderExperiment(result.data);
      })
      .catch(function (error) {
        formStatus.textContent = failureMessage(error);
        formStatus.classList.add('is-error');
      })
      .then(function () {
        setBusy(false);
        if (workspace.hidden) runButton.focus();
        else workspace.focus({ preventScroll: true });
      });
  });

  window.addEventListener('scroll', scheduleScrollUpdate, { passive: true });
  window.addEventListener('resize', function () {
    tutorialGeometry = new WeakMap();
    updateStrokeViewport();
    scheduleScrollUpdate();
  });
  motionQuery.addEventListener('change', function (event) {
    isReduced = event.matches;
    if (isReduced && scrollFrameId) {
      window.cancelAnimationFrame(scrollFrameId);
      scrollFrameId = 0;
    }
    updateScrollTutorials();
  });

  initStepper();
  initSpotlightCards();
  initLineSidebar();
  initTitleReveals();
  initPrediction();
  initPauliTabs();
  initV71PublicExperience();
  initV72PublicCopy();
  initV725GoldenRestore();
  initV724Copy();
  initHInteraction();
  initCnotInteraction();
  initOutcomeDelight();
  initCircuitInspect();
  initBellShotAccumulator();
  initAgentPromptCards();
  repairStaticTermHelpMarkup();
  initTermHelp();
  initAnchorFocus();
  applyLanguage('zh');
  loadRuntimeStatus();
})();
