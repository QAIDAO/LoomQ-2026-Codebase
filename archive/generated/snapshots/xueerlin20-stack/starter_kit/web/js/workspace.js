// Workspace composition root: conversation, circuit context, and config gate.

import { api } from './api.js';
import { ChatController } from './chat.js';
import { CircuitRunner } from './circuit-runner.js';
import { CircuitVisualizer } from './circuit-visualizer.js';
import { ConversationSession } from './conversation-session.js';
import { JourneyProgress } from './journey.js';
import { PreferenceStore } from './preferences.js';

const preferences = new PreferenceStore();
const conversationSession = new ConversationSession();
const journey = new JourneyProgress();
const circuitVisualizer = new CircuitVisualizer(document.querySelector('#circuit-panel'));
const circuitRunner = new CircuitRunner({
  root: document.querySelector('#circuit-panel'),
  api,
  conversationSession,
});

const configurationGate = {
  ready: false,
  isReady() {
    return this.ready;
  },
  open() {
    window.location.assign('/?open=config');
  },
};

async function startWorkspace() {
  try {
    const configuration = await api.getConfiguration();
    if (!configuration.ready) {
      window.location.replace('/?open=config');
      return;
    }
    configurationGate.ready = true;
  } catch (_error) {
    window.location.replace('/?open=config');
    return;
  }

  const chat = new ChatController({
    api,
    preferences,
    onboarding: configurationGate,
    journey,
    conversationSession,
    circuitVisualizer,
  });
  circuitRunner.init();
  chat.init();
  chat.focus();
}

startWorkspace();
