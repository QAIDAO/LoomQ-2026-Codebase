// Device-local onboarding and explanation preferences.

const KEYS = Object.freeze({
  profile: 'loomq.quantumProfile',
  explainConcepts: 'loomq.explainConcepts',
  onboardingComplete: 'loomq.onboardingComplete',
});

const PROFILE_MODULES = Object.freeze({
  new: Object.freeze({ conceptBasics: true, exampleCircuit: true }),
  some: Object.freeze({ conceptBasics: false, exampleCircuit: true }),
  expert: Object.freeze({ conceptBasics: false, exampleCircuit: false }),
});

export class PreferenceStore {
  constructor(storage = window.localStorage) {
    this.storage = storage;
  }

  getLearningPreferences() {
    const profile = this.get(KEYS.profile) || '';
    const modules = this.modulesForProfile(profile);
    return {
      profile,
      explainConcepts: modules.conceptBasics,
      ...modules,
    };
  }

  modulesForProfile(profile) {
    return PROFILE_MODULES[profile] || { conceptBasics: false, exampleCircuit: false };
  }

  saveLearningPreferences(profile) {
    const modules = this.modulesForProfile(profile);
    this.set(KEYS.profile, profile);
    this.set(KEYS.explainConcepts, String(modules.conceptBasics));
    return modules;
  }

  isOnboardingComplete() {
    return this.get(KEYS.onboardingComplete) === 'true';
  }

  markOnboardingComplete() {
    this.set(KEYS.onboardingComplete, 'true');
  }

  get(key) {
    try {
      return this.storage.getItem(key);
    } catch (_error) {
      return null;
    }
  }

  set(key, value) {
    try {
      this.storage.setItem(key, value);
    } catch (_error) {
      // Preferences are optional; the app remains usable without browser storage.
    }
  }
}
