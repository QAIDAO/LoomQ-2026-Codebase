// Interactive Bell-circuit tutorial state machine.

const COPY = Object.freeze({
  0: {
    kicker: '先点击 H 门',
    title: '先让两份同等优先的申请机会相等',
    narration: 'q0 代表面向申请人的公示结果。H 门让“匿名申请 A 获得名额”和“匿名申请 B 获得名额”成为概率相同的两种可能。',
    analogy: '在需求确实相同、资源又有限时，公开且不偏向身份的规则，比由某个人凭印象决定更公平。',
    action: '① 点击左侧高亮的 H 门',
  },
  1: {
    kicker: 'q0 已准备好 · 下一步点击 CX 门',
    title: '让公示结果与审计记录保持一致',
    narration: '现在点击电路中高亮的 CX 门，把 q0 的公示结果与 q1 的审计记录关联起来。',
    analogy: '如果公示屏与审计记录各自独立抽签，就可能写下不同答案，审计也失去意义。一次公平抽签，必须对应一份相同记录。',
    action: '② 点击两条线中间高亮的 CX 门',
  },
  2: {
    kicker: '纠缠已建立 · 点击测量',
    title: 'CX 把公示结果与审计记录关联起来',
    narration: 'q0 是控制端，q1 是目标端：q0 为 0 时 q1 保持 0；q0 为 1 时 q1 翻转为 1。现在可以测量 100 次。',
    analogy: 'H 负责“选择时不偏向任何一份匿名申请”，CX 负责“选择后留下相同记录”。',
    action: '③ 点击右侧任意一个高亮的“测量”',
  },
});

export class QuantumLab {
  constructor({ root, results, finishButton, hint }) {
    this.root = root;
    this.results = results;
    this.finishButton = finishButton;
    this.hint = hint;
    this.stage = 0;
  }

  init() {
    this.root.addEventListener('click', (event) => this.handleAction(event));
    document.querySelector('#lab-reset').addEventListener('click', () => this.reset());
  }

  handleAction(event) {
    const action = event.target.closest('[data-lab-action]')?.dataset.labAction;
    if (action === 'h' && this.stage === 0) this.setStage(1);
    if (action === 'cx' && this.stage === 1) this.setStage(2);
    if (action === 'measure' && this.stage === 2) this.measure();
  }

  reset() {
    this.stage = 0;
    this.root.dataset.stage = '0';
    this.setGateAvailability(0);
    this.updateCopy(COPY[0]);
    this.root.querySelectorAll('.bit-state').forEach((bit) => { bit.textContent = '0'; });
    this.results.hidden = true;
    this.finishButton.disabled = true;
    this.hint.textContent = '完成三步互动后，就可以进入 LoomQ 工作台';
  }

  setStage(stage) {
    this.stage = stage;
    this.root.dataset.stage = String(stage);
    this.setGateAvailability(stage);
    this.updateCopy(COPY[stage]);
  }

  measure() {
    this.stage = 3;
    this.root.dataset.stage = '3';
    this.setGateAvailability(3);
    const zeroCount = this.sample(100);
    const oneCount = 100 - zeroCount;
    const finalBit = Math.random() < 0.5 ? '0' : '1';
    this.root.querySelectorAll('.bit-state').forEach((bit) => { bit.textContent = finalBit; });
    this.updateCopy({
      kicker: '测量完成 · 规律出现了',
      title: '选择公平，而且全过程可以核验',
      narration: `这次 100 次实验中，00 出现 ${zeroCount} 次，11 出现 ${oneCount} 次。谁获得名额不可预知，但公示结果与审计记录从未冲突。`,
      analogy: '这个电路只演示同等优先情况下的程序公平。真正的平等权益还需要按需求分配、充足资源、申诉机制与公共监督。',
      action: '完成 · 现在可以进入 LoomQ 工作台',
    });
    this.results.querySelector('#value-00').textContent = `${zeroCount}%`;
    this.results.querySelector('#value-11').textContent = `${oneCount}%`;
    this.results.hidden = false;
    window.requestAnimationFrame(() => {
      this.results.querySelector('#bar-00').style.width = `${zeroCount}%`;
      this.results.querySelector('#bar-11').style.width = `${oneCount}%`;
    });
    this.finishButton.disabled = false;
    this.hint.textContent = '完成！你已经运行并读懂了一个 Bell 纠缠电路';
  }

  sample(shots) {
    let zeroCount = 0;
    for (let shot = 0; shot < shots; shot += 1) {
      if (Math.random() < 0.5) zeroCount += 1;
    }
    return zeroCount;
  }

  setGateAvailability(stage) {
    this.root.querySelector('[data-lab-action="h"]').disabled = stage >= 1;
    this.root.querySelector('[data-lab-action="cx"]').disabled = stage !== 1;
    this.root.querySelectorAll('[data-lab-action="measure"]').forEach((button) => {
      button.disabled = stage !== 2;
    });
  }

  nextActionText() {
    return {
      0: '① 点击左侧高亮的 H 门',
      1: '② 点击两条线中间高亮的 CX 门',
      2: '③ 点击右侧任意一个高亮的“测量”',
      3: '完成 · 现在可以进入 LoomQ 工作台',
    }[this.stage];
  }

  updateCopy(copy) {
    this.root.querySelector('#lab-kicker').textContent = copy.kicker;
    this.root.querySelector('#lab-title').textContent = copy.title;
    this.root.querySelector('#lab-narration').textContent = copy.narration;
    this.root.querySelector('#lab-analogy').textContent = copy.analogy;
    this.root.querySelector('#lab-action-text').textContent = copy.action;
  }
}
