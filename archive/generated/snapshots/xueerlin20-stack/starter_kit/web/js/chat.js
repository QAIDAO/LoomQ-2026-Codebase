// Conversation composer, request lifecycle, and result presentation.

import { renderAgentResult, renderUserMessage } from './results.js';

export class ChatController {
  constructor({ api, preferences, onboarding, journey, conversationSession, circuitVisualizer }) {
    this.api = api;
    this.preferences = preferences;
    this.onboarding = onboarding;
    this.journey = journey;
    this.conversationSession = conversationSession;
    this.circuitVisualizer = circuitVisualizer;
    this.conversation = document.querySelector('#conversation');
    this.composer = document.querySelector('#composer');
    this.promptInput = document.querySelector('#prompt');
    this.sendButton = document.querySelector('#send');
    this.loadingTemplate = document.querySelector('#loading-template');
    this.contextBar = document.querySelector('#conversation-context');
    this.contextLabel = document.querySelector('#conversation-context-label');
    this.starterPrompts = document.querySelector('.composer-prompts');
    this.clearContextButton = document.querySelector('#clear-conversation');
    this.introMessage = this.conversation.querySelector('.intro-message').cloneNode(true);
  }

  init() {
    document.querySelectorAll('[data-prompt]').forEach((button) => {
      button.addEventListener('click', () => this.useStarterPrompt(button.dataset.prompt));
    });
    this.promptInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        this.composer.requestSubmit();
      }
    });
    this.composer.addEventListener('submit', (event) => this.submit(event));
    this.clearContextButton.addEventListener('click', () => this.clearConversation());
    this.renderContext();
  }

  focus() {
    this.promptInput.focus();
  }

  useStarterPrompt(prompt) {
    this.promptInput.value = prompt;
    this.focus();
    document.querySelector('.workspace').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  async submit(event) {
    event.preventDefault();
    const prompt = this.promptInput.value.trim();
    if (!prompt || this.sendButton.disabled) return;
    if (!this.onboarding.isReady()) {
      this.onboarding.open('config', true);
      return;
    }

    this.conversation.append(renderUserMessage(prompt));
    this.starterPrompts.hidden = true;
    this.journey.setActive(1);
    this.promptInput.value = '';
    this.setBusy(true);
    const loading = this.loadingTemplate.content.firstElementChild.cloneNode(true);
    this.conversation.append(loading);
    this.scrollConversation();
    const runStageTimer = window.setTimeout(() => this.journey.setActive(2), 500);

    try {
      const learning = this.preferences.getLearningPreferences();
      const data = await this.api.sendChat({
        prompt,
        quantum_profile: learning.profile || undefined,
        explain_concepts: learning.explainConcepts,
        ...this.conversationSession.requestContext(),
      });
      loading.remove();
      this.conversationSession.update(data);
      if (data.qasm) {
        this.circuitVisualizer?.render(data.qasm, data.active_artifact || {});
      }
      this.conversation.append(renderAgentResult(data, {
        onSuggestion: (suggestion) => this.useStarterPrompt(suggestion),
      }));
      this.renderContext();
      this.journey.setActive(3);
    } catch (error) {
      loading.remove();
      const message = error.message || '暂时无法连接 LoomQ Agent，请稍后再试。';
      this.conversation.append(renderAgentResult({
        ok: false,
        display_text: '连接或运行遇到问题。',
        message,
      }));
      if (/鉴权失败|HTTP 401/.test(message)) {
        this.onboarding.open('config', true);
      }
    } finally {
      window.clearTimeout(runStageTimer);
      this.setBusy(false);
      this.focus();
      this.scrollConversation();
    }
  }

  setBusy(busy) {
    this.sendButton.disabled = busy;
    this.promptInput.disabled = busy;
    this.sendButton.querySelector('span:first-child').textContent = busy ? '实验进行中…' : '开始实验';
  }

  scrollConversation() {
    this.conversation.scrollTo({ top: this.conversation.scrollHeight, behavior: 'smooth' });
  }

  async clearConversation() {
    const conversationId = this.conversationSession.state.conversationId;
    this.clearContextButton.disabled = true;
    try {
      if (conversationId) await this.api.resetConversation(conversationId);
      this.conversationSession.clear();
      this.circuitVisualizer?.clear();
      this.conversation.replaceChildren(this.introMessage.cloneNode(true));
      this.renderContext();
      this.promptInput.value = '';
      this.promptInput.placeholder = '例如：生成一个 3 比特 GHZ 态并测量全部量子比特…';
      this.starterPrompts.hidden = false;
      this.journey.setActive(0);
    } catch (error) {
      this.conversation.append(renderAgentResult({
        ok: false,
        display_text: '暂时无法清空当前讨论。',
        message: error.message || '请稍后重试。',
      }));
    } finally {
      this.clearContextButton.disabled = false;
      this.focus();
      this.scrollConversation();
    }
  }

  renderContext() {
    const artifact = this.conversationSession.state.artifact;
    this.contextBar.hidden = !artifact;
    if (!artifact) return;
    const goal = artifact.goal || '当前电路';
    this.contextLabel.textContent = `正在继续：${goal} · v${artifact.version}`;
    this.promptInput.placeholder = '继续追问，例如：为什么先使用 H 门？或把它改成 5 比特…';
  }
}
