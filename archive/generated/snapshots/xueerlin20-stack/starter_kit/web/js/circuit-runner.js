// Local measurement controls and distribution chart for the active circuit.

export class CircuitRunner {
  constructor({ root, api, conversationSession }) {
    this.root = root;
    this.api = api;
    this.conversationSession = conversationSession;
    this.button = root.querySelector('#run-current-circuit');
    this.shots = root.querySelector('#circuit-shots');
    this.status = root.querySelector('#circuit-runner-status');
    this.results = root.querySelector('#circuit-runner-results');
  }

  init() {
    this.button.addEventListener('click', () => this.run());
    this.root.addEventListener('loomq:circuit-ready', () => this.reset());
    this.root.addEventListener('loomq:circuit-clear', () => this.clear());
  }

  async run() {
    if (this.button.disabled) return;
    const context = this.conversationSession.requestContext();
    if (!context.active_artifact_id) {
      this.showError('当前没有可运行的电路。');
      return;
    }
    this.setBusy(true);
    this.results.hidden = true;
    this.status.classList.remove('is-error');
    this.status.textContent = '正在本地模拟并采样测量结果…';
    try {
      const data = await this.api.runCurrentCircuit({
        ...context,
        shots: Number(this.shots.value),
      });
      this.render(data);
    } catch (error) {
      this.showError(error.message || '本地模拟运行失败，请检查当前电路。');
    } finally {
      this.setBusy(false);
    }
  }

  render(data) {
    const entries = Object.entries(data.counts || {})
      .sort(([left], [right]) => left.localeCompare(right));
    this.results.replaceChildren(...entries.map(([state, count]) => {
      const percent = data.shots ? (count / data.shots) * 100 : 0;
      const row = document.createElement('div');
      row.className = 'circuit-result-row';
      const label = document.createElement('span');
      label.textContent = `|${state}⟩`;
      label.title = state;
      const track = document.createElement('i');
      track.className = 'circuit-result-track';
      const fill = document.createElement('i');
      fill.className = 'circuit-result-fill';
      fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
      track.append(fill);
      const value = document.createElement('strong');
      value.textContent = `${count} · ${percent.toFixed(1)}%`;
      row.append(label, track, value);
      return row;
    }));
    this.results.hidden = false;
    this.status.classList.remove('is-error');
    this.status.textContent = `SpinQ 本地模拟完成 · ${data.shots} shots · ${entries.length} 种结果`;
  }

  reset() {
    this.results.replaceChildren();
    this.results.hidden = true;
    this.status.classList.remove('is-error');
    this.status.textContent = '使用 SpinQ 本地模拟器，不会提交到量子真机。';
  }

  clear() {
    this.reset();
    this.setBusy(false);
  }

  showError(message) {
    this.results.hidden = true;
    this.status.classList.add('is-error');
    this.status.textContent = message;
  }

  setBusy(busy) {
    this.button.disabled = busy;
    this.shots.disabled = busy;
    this.button.firstChild.textContent = busy ? '运行中 ' : '运行测量 ';
  }
}
