// Visual narrative progress for an Agent request.

export class JourneyProgress {
  constructor(root = document) {
    this.steps = root.querySelectorAll('[data-journey-step]');
    this.progress = root.querySelector('.journey-line span');
  }

  setActive(activeIndex) {
    this.steps.forEach((step) => {
      const index = Number(step.dataset.journeyStep);
      step.classList.toggle('is-active', index === activeIndex);
      step.classList.toggle('is-complete', index < activeIndex);
    });
    if (this.progress && this.steps.length > 1) {
      const percent = Math.max(0, activeIndex / (this.steps.length - 1)) * 100;
      this.progress.style.width = `${percent}%`;
    }
  }
}
