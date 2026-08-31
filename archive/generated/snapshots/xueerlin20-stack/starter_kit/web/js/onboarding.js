// First-run configuration, learning profile, and tutorial orchestration.

export class OnboardingController {
  constructor({ api, preferences, quantumLab, conceptBasics, onFinish = () => {} }) {
    this.api = api;
    this.preferences = preferences;
    this.quantumLab = quantumLab;
    this.conceptBasics = conceptBasics;
    this.onFinish = onFinish;
    this.configuration = null;
    this.flow = 'guide';
    this.selectedProfile = preferences.getLearningPreferences().profile;
    this.elements = this.collectElements();
  }

  collectElements() {
    return {
      dialog: document.querySelector('#onboarding'),
      configForm: document.querySelector('#config-form'),
      configFields: document.querySelector('#config-fields'),
      configError: document.querySelector('#config-error'),
      runtimeLabel: document.querySelector('#runtime-label'),
      statusDot: document.querySelector('#status-dot'),
      finish: document.querySelector('#finish-onboarding'),
      saveProfile: document.querySelector('#save-profile'),
      continueBasics: document.querySelector('#continue-basics'),
      primer: document.querySelector('#concept-primer'),
      hint: document.querySelector('#ready-hint'),
    };
  }

  async init() {
    this.bindEvents();
    try {
      this.configuration = await this.api.getConfiguration();
      this.renderConfigFields(this.configuration.fields);
      this.updateRuntimeStatus(this.configuration.ready);
      const requestedStep = new URLSearchParams(window.location.search).get('open');
      if (!this.configuration.ready) {
        this.open('config', true, requestedStep === 'config' ? 'config' : 'guide');
      } else if (requestedStep === 'config') this.open('config', false, 'config');
      else if (requestedStep === 'guide') this.open('profile', false, 'guide');
      else if (!this.preferences.isOnboardingComplete()) this.open('profile', true, 'guide');
    } catch (error) {
      this.updateRuntimeStatus(false, error.message || '配置检查失败');
    }
  }

  isReady() {
    return Boolean(this.configuration?.ready);
  }

  open(step = 'config', required = false, flow = 'guide') {
    this.flow = flow;
    this.elements.dialog.dataset.required = required ? 'true' : 'false';
    this.showStep(step);
    if (!this.elements.dialog.open) this.elements.dialog.showModal();
  }

  showStep(step) {
    this.elements.dialog.dataset.activeStep = step;
    document.querySelectorAll('.onboarding-step').forEach((panel) => {
      panel.hidden = panel.dataset.step !== step;
    });
    if (step === 'profile') this.restoreProfileSelection();
  }

  bindEvents() {
    this.elements.configForm.addEventListener('submit', (event) => this.saveConfiguration(event));
    document.querySelectorAll('[data-profile]').forEach((button) => {
      button.addEventListener('click', () => this.selectProfile(button));
    });
    this.elements.saveProfile.addEventListener('click', () => this.saveProfile());
    this.elements.continueBasics.addEventListener('click', () => this.continueFromBasics());
    this.elements.finish.addEventListener('click', () => this.finish());
    document.querySelectorAll('#open-settings, #open-config').forEach((button) => {
      button.addEventListener('click', () => this.open('config', false, 'config'));
    });
    document.querySelector('#open-guide').addEventListener('click', () => {
      this.open(this.isReady() ? 'profile' : 'config', false, 'guide');
    });
    document.querySelector('#close-onboarding').addEventListener('click', () => {
      if (this.elements.dialog.dataset.required !== 'true') this.elements.dialog.close();
    });
    document.querySelectorAll('[data-back]').forEach((button) => {
      button.addEventListener('click', () => this.showStep(button.dataset.back));
    });
    this.elements.dialog.addEventListener('cancel', (event) => {
      if (this.elements.dialog.dataset.required === 'true') event.preventDefault();
    });
  }

  async saveConfiguration(event) {
    event.preventDefault();
    const submit = this.elements.configForm.querySelector('[type="submit"]');
    this.elements.configError.textContent = '';
    submit.disabled = true;
    submit.firstChild.textContent = '正在保存… ';
    try {
      const payload = Object.fromEntries(new FormData(this.elements.configForm).entries());
      this.configuration = await this.api.saveConfiguration(payload);
      this.renderConfigFields(this.configuration.fields);
      this.updateRuntimeStatus(this.configuration.ready);
      if (this.flow === 'config') {
        this.elements.dialog.dataset.required = 'false';
        this.elements.dialog.close();
      } else {
        this.showStep('profile');
      }
    } catch (error) {
      this.elements.configError.textContent = error.message || '配置保存失败，请检查后重试。';
    } finally {
      submit.disabled = false;
      submit.firstChild.textContent = '保存并继续 ';
    }
  }

  selectProfile(button) {
    this.selectedProfile = button.dataset.profile;
    document.querySelectorAll('[data-profile]').forEach((option) => {
      option.classList.toggle('is-selected', option === button);
    });
    this.elements.saveProfile.disabled = false;
  }

  restoreProfileSelection() {
    const { profile } = this.preferences.getLearningPreferences();
    if (profile) this.selectedProfile = profile;
    if (!this.selectedProfile) return;
    document.querySelectorAll('[data-profile]').forEach((option) => {
      option.classList.toggle('is-selected', option.dataset.profile === this.selectedProfile);
    });
    this.elements.saveProfile.disabled = false;
  }

  saveProfile() {
    if (!this.selectedProfile) return;
    const modules = this.preferences.saveLearningPreferences(this.selectedProfile);
    this.pendingExampleCircuit = modules.exampleCircuit;
    if (modules.conceptBasics) {
      this.conceptBasics.reset();
      this.showStep('basics');
      return;
    }
    if (modules.exampleCircuit) this.prepareReadyStep(true);
    else this.finish();
  }

  continueFromBasics() {
    this.prepareReadyStep(this.pendingExampleCircuit);
  }

  prepareReadyStep(showPrimer) {
    this.elements.primer.hidden = !showPrimer;
    this.elements.finish.disabled = showPrimer;
    this.elements.hint.textContent = showPrimer
      ? '完成三步互动后，就可以进入 LoomQ 工作台'
      : '示例电路互动已跳过，你可以直接进入工作台';
    if (showPrimer) this.quantumLab.reset();
    this.showStep('ready');
  }

  finish() {
    this.preferences.markOnboardingComplete();
    this.elements.dialog.dataset.required = 'false';
    this.elements.dialog.close();
    this.onFinish();
  }

  renderConfigFields(fields) {
    this.elements.configFields.replaceChildren();
    fields.forEach((field) => this.elements.configFields.append(this.createConfigField(field)));
  }

  createConfigField(field) {
    const wrapper = document.createElement('label');
    wrapper.className = `config-field${field.configured ? ' is-valid' : ''}`;
    const head = document.createElement('span');
    head.className = 'field-head';
    const label = document.createElement('strong');
    label.textContent = field.label;
    const state = document.createElement('small');
    state.textContent = field.configured ? '已配置 ✓' : '需要配置';
    head.append(label, state);
    const input = document.createElement('input');
    input.name = field.name;
    input.type = field.secret ? 'password' : (field.name.endsWith('TIMEOUT_SECONDS') ? 'number' : 'text');
    input.autocomplete = field.secret ? 'new-password' : 'off';
    input.placeholder = field.secret && field.configured ? '已保存；留空则保持不变' : field.description;
    input.value = field.secret ? '' : (field.value || field.default || '');
    if (field.name.endsWith('TIMEOUT_SECONDS')) {
      input.min = '1';
      input.max = '3600';
    }
    const help = document.createElement('span');
    help.className = 'field-help';
    help.textContent = field.description;
    wrapper.append(head, input, help);
    return wrapper;
  }

  updateRuntimeStatus(ready, label) {
    this.elements.statusDot.classList.toggle('is-offline', !ready);
    this.elements.runtimeLabel.textContent = label || (ready ? '模型已连接 · 本地模拟器就绪' : '需要完成运行配置');
  }
}
