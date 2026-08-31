// Focused concept explorer: sidebar navigation and one explanation at a time.

const CONCEPTS = [
  { id: 'qubit', next: '量子门' },
  { id: 'gate', next: '量子电路' },
  { id: 'circuit', next: '测量' },
  { id: 'measurement', next: null },
];

export class ConceptBasics {
  constructor(root) {
    this.root = root;
    this.activeIndex = 0;
    this.selectedGate = null;
    this.gateRunResult = null;
    this.cxHasRun = false;
    this.measurementMode = 'single';
    this.measurements = { zero: 0, one: 0 };
  }

  init() {
    this.root.querySelectorAll('[data-concept-target]').forEach((button) => {
      button.addEventListener('click', () => this.selectConcept(button.dataset.conceptTarget));
    });
    this.root.querySelector('[data-basic-action="measure"]').addEventListener('click', () => {
      this.runMeasurements();
    });
    this.root.querySelectorAll('[data-basic-gate-action]').forEach((button) => {
      button.addEventListener('click', () => this.loadGate(button.dataset.basicGateAction));
    });
    this.root.querySelector('[data-basic-gate-run="h"]').addEventListener('click', () => this.runHGate());
    this.root.querySelector('[data-basic-gate-run="cx"]').addEventListener('click', () => this.runCxGate());
    this.root.querySelector('#reset-basic-gates').addEventListener('click', () => this.resetGateLesson());
    this.root.querySelector('#next-concept').addEventListener('click', () => {
      if (this.activeIndex < CONCEPTS.length - 1) {
        this.selectConcept(CONCEPTS[this.activeIndex + 1].id);
      }
    });
    this.reset();
  }

  reset() {
    this.selectedGate = null;
    this.gateRunResult = null;
    this.cxHasRun = false;
    this.measurementMode = 'single';
    this.measurements = { zero: 0, one: 0 };
    this.renderGateLesson();
    this.renderMeasurements(null);
    this.selectConcept('qubit');
  }

  selectConcept(conceptId) {
    const nextIndex = CONCEPTS.findIndex((concept) => concept.id === conceptId);
    if (nextIndex < 0) return;
    this.activeIndex = nextIndex;
    this.root.dataset.activeConcept = conceptId;

    this.root.querySelectorAll('[data-concept-target]').forEach((button) => {
      if (button.dataset.conceptTarget === conceptId) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    this.root.querySelectorAll('[data-concept-panel]').forEach((panel) => {
      const active = panel.dataset.conceptPanel === conceptId;
      panel.hidden = !active;
      panel.classList.toggle('is-active', active);
    });

    const concept = CONCEPTS[nextIndex];
    this.root.querySelector('#concept-position').textContent = `概念 ${nextIndex + 1} / ${CONCEPTS.length}`;
    const nextButton = this.root.querySelector('#next-concept');
    nextButton.hidden = !concept.next;
    nextButton.textContent = concept.next ? `下一个：${concept.next} →` : '';
  }

  loadGate(action) {
    if (!['h', 'cx'].includes(action)) return;
    this.selectedGate = action;
    this.gateRunResult = null;
    this.cxHasRun = false;
    this.renderGateLesson();
  }

  resetGateLesson() {
    this.selectedGate = null;
    this.gateRunResult = null;
    this.cxHasRun = false;
    this.renderGateLesson();
  }

  runHGate() {
    if (this.selectedGate !== 'h') return;
    this.gateRunResult = Math.random() < 0.5 ? '0' : '1';
    const output = this.root.querySelector('#basic-h-output');
    output.textContent = this.gateRunResult;
    output.dataset.result = this.gateRunResult;
    this.root.querySelector('#basic-gate-narration').innerHTML =
      `<b>运行完成：测得 ${this.gateRunResult}。</b>每次点击都会重新准备 <code>|0⟩</code>、经过 H 门并测量，所以再次运行可能得到另一个结果。`;
  }

  runCxGate() {
    if (this.selectedGate !== 'cx' || this.cxHasRun) return;
    this.cxHasRun = true;
    const outputs = [
      this.root.querySelector('#basic-cx-output-zero'),
      this.root.querySelector('#basic-cx-output-one'),
    ];
    outputs.forEach((output) => { output.dataset.result = '1'; });
    outputs[0].textContent = '1';
    outputs[1].textContent = '1';
    const cxRunButton = this.root.querySelector('[data-basic-gate-run="cx"]');
    cxRunButton.disabled = true;
    cxRunButton.setAttribute('aria-label', 'CX 门已运行');
    this.root.querySelector('#basic-cx-action').textContent = '已运行';
    this.root.querySelector('#basic-gate-narration').innerHTML =
      '<b>运行完成：测得 11。</b>控制位 q0 是 1，所以 CX 保持 q0 为 1，并把目标位 q1 从 0 翻转为 1。';
  }

  renderGateLesson() {
    const gate = this.selectedGate || 'empty';
    const explanations = {
      empty: '<b>还没有加载门。</b>先选择 H 或 CX；演示区一次只显示一个门。',
      h: '<b>H 门：</b>把确定的 <code>|0⟩</code> 变成测得 0、1 机会各一半的状态。现在点击线路中的 H 门，运行并测量一次。',
      cx: '<b>CX 门：</b>这里准备 q0 为 <code>|1⟩</code>、q1 为 <code>|0⟩</code>。点击线路中的 CX 门，观察目标位怎样翻转并测量。',
    };

    this.root.querySelector('#basic-gate-demo').dataset.gate = gate;
    this.root.querySelectorAll('[data-gate-view]').forEach((view) => {
      view.hidden = view.dataset.gateView !== gate;
    });
    this.root.querySelectorAll('[data-basic-gate-action]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.basicGateAction === this.selectedGate ? 'true' : 'false');
    });
    const hOutput = this.root.querySelector('#basic-h-output');
    hOutput.textContent = this.gateRunResult ?? '等待';
    hOutput.dataset.result = this.gateRunResult ?? 'waiting';
    const cxOutputs = [
      this.root.querySelector('#basic-cx-output-zero'),
      this.root.querySelector('#basic-cx-output-one'),
    ];
    cxOutputs.forEach((output) => {
      output.textContent = this.cxHasRun ? '1' : '等待';
      output.dataset.result = this.cxHasRun ? '1' : 'waiting';
    });
    const cxRunButton = this.root.querySelector('[data-basic-gate-run="cx"]');
    cxRunButton.disabled = this.cxHasRun;
    cxRunButton.setAttribute('aria-label', this.cxHasRun ? 'CX 门已运行' : '点击 CX 门，运行并测量一次');
    this.root.querySelector('#basic-cx-action').textContent = this.cxHasRun ? '已运行' : '点击运行';
    this.root.querySelector('#basic-gate-narration').innerHTML = explanations[gate];
  }

  runMeasurements() {
    const shots = this.measurementMode === 'single' ? 1 : 100;
    this.measurements = { zero: 0, one: 0 };
    let lastResult = null;
    for (let shot = 0; shot < shots; shot += 1) {
      lastResult = Math.random() < 0.5 ? 'zero' : 'one';
      this.measurements[lastResult] += 1;
    }
    if (this.measurementMode === 'single') this.measurementMode = 'batch';
    this.renderMeasurements(lastResult, shots);
  }

  renderMeasurements(result, shots = 0) {
    const total = this.measurements.zero + this.measurements.one;
    const resultLabel = this.root.querySelector('#basic-measure-result');
    resultLabel.textContent = result === null
      ? '还没有测量'
      : shots === 1
        ? `这一次得到 ${result === 'zero' ? '0' : '1'}`
        : `100 次测量完成：0 和 1 都出现了`;
    resultLabel.dataset.result = result || 'waiting';
    this.root.querySelector('#basic-measure-counts').textContent = result === null
      ? '先运行一次，看看单次测量会发生什么。'
      : shots === 1
        ? '一次只能看到一个答案。现在用 100 次测量观察比例。'
        : `相同电路重复运行 ${total} 次，结果会接近各占一半。`;

    const zeroPercent = total ? Math.round((this.measurements.zero / total) * 100) : 0;
    const onePercent = total ? 100 - zeroPercent : 0;
    this.root.querySelector('#basic-zero-count').textContent = `${this.measurements.zero} 次`;
    this.root.querySelector('#basic-one-count').textContent = `${this.measurements.one} 次`;
    this.root.querySelector('#basic-zero-percent').textContent = `${zeroPercent}%`;
    this.root.querySelector('#basic-one-percent').textContent = `${onePercent}%`;
    this.root.querySelector('#basic-zero-bar').style.width = `${zeroPercent}%`;
    this.root.querySelector('#basic-one-bar').style.width = `${onePercent}%`;
    this.root.querySelector('#basic-measure-button').innerHTML = this.measurementMode === 'single'
      ? '先测量一次 <span>⌁</span>'
      : '测量 100 次 <span>⌁</span>';
    this.root.querySelector('#basic-measure-explanation').textContent = result === null
      ? '一次测量只会得到一个答案；完成后，再用 100 次观察整体比例。'
      : shots === 1
        ? '刚才只出现一个结果，不代表另一个结果不可能。点击“测量 100 次”继续。'
        : '柱状图不是固定答案；再次测量 100 次，具体次数会变化，但通常接近 50% / 50%。';
  }
}
