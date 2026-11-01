/* Form stepper - TypeScript */
class FormStepper {
  private currentStep: number = 0;
  private steps: HTMLElement[];
  private totalSteps: number;

  constructor(container: HTMLElement) {
    this.steps = Array.from(container.querySelectorAll('.step'));
    this.totalSteps = this.steps.length;
    this.showStep(0);
  }

  showStep(index: number): void {
    this.steps.forEach((step, i) => {
      step.classList.toggle('active', i === index);
      step.classList.toggle('completed', i < index);
    });
    this.currentStep = index;
  }

  next(): void {
    if (this.currentStep < this.totalSteps - 1) {
      this.showStep(this.currentStep + 1);
    }
  }

  prev(): void {
    if (this.currentStep > 0) {
      this.showStep(this.currentStep - 1);
    }
  }

  goTo(index: number): void {
    if (index >= 0 && index < this.totalSteps) {
      this.showStep(index);
    }
  }
}

(window as any).FormStepper = FormStepper;