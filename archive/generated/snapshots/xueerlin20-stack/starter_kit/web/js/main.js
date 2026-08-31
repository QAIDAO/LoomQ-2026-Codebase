// Main-page composition root: configuration and beginner guidance only.

import { api } from './api.js';
import { ConceptBasics } from './concept-basics.js';
import { OnboardingController } from './onboarding.js';
import { PreferenceStore } from './preferences.js';
import { QuantumLab } from './quantum-lab.js';

const preferences = new PreferenceStore();
const conceptBasics = new ConceptBasics(document.querySelector('#concept-basics'));
const finishButton = document.querySelector('#finish-onboarding');
const readyHint = document.querySelector('#ready-hint');
const quantumLab = new QuantumLab({
  root: document.querySelector('#circuit-lab'),
  results: document.querySelector('#measurement-results'),
  finishButton,
  hint: readyHint,
});

const onboarding = new OnboardingController({
  api,
  preferences,
  conceptBasics,
  quantumLab,
  onFinish: () => window.location.assign('/workspace.html'),
});

quantumLab.init();
conceptBasics.init();
onboarding.init();
