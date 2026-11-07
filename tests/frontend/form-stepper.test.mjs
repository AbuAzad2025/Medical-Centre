import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function stepDom() {
  return `
    <form id="visitForm">
      <div class="form-step-panel"></div>
      <div class="form-step-panel"></div>
      <div class="form-step-panel"></div>
    </form>
    <div id="stepper" data-form-stepper>
      <div class="form-stepper-item"></div>
      <div class="form-stepper-item"></div>
      <div class="form-stepper-item"></div>
      <button data-stepper-prev>Prev</button>
      <button data-stepper-next>Next</button>
      <button data-step-go="2">Go2</button>
    </div>
  `;
}

describe('form-stepper.js', () => {
  it('initializes first step and shows/hides panels', async () => {
    document.body.innerHTML = stepDom();
    const { initStepper } = await loadModule('static/js/form-stepper.js');
    const root = document.getElementById('stepper');
    initStepper(root);
    const panels = document.querySelectorAll('.form-step-panel');
    expect(panels[0].classList.contains('d-none')).toBe(false);
    expect(panels[1].classList.contains('d-none')).toBe(true);
    expect(document.querySelector('[data-stepper-prev]').disabled).toBe(true);
  });

  it('next/prev navigate between steps', async () => {
    document.body.innerHTML = stepDom();
    const { initStepper } = await loadModule('static/js/form-stepper.js');
    initStepper(document.getElementById('stepper'));
    document.querySelector('[data-stepper-next]').click();
    expect(document.querySelectorAll('.form-step-panel')[1].classList.contains('d-none')).toBe(false);
    document.querySelector('[data-stepper-prev]').click();
    expect(document.querySelectorAll('.form-step-panel')[0].classList.contains('d-none')).toBe(false);
  });

  it('data-step-go jumps to index', async () => {
    document.body.innerHTML = stepDom();
    const { initStepper } = await loadModule('static/js/form-stepper.js');
    initStepper(document.getElementById('stepper'));
    document.querySelector('[data-step-go]').click();
    expect(document.querySelectorAll('.form-step-panel')[2].classList.contains('d-none')).toBe(false);
  });

  it('next at final step keeps button label review', async () => {
    document.body.innerHTML = stepDom();
    const { initStepper } = await loadModule('static/js/form-stepper.js');
    initStepper(document.getElementById('stepper'));
    const next = document.querySelector('[data-stepper-next]');
    next.click();
    next.click();
    expect(next.textContent).toBe('مراجعة');
  });

  it('returns early when root has no closest form', async () => {
    document.body.innerHTML = '<div id="orphan"><div class="form-step-panel"></div></div>';
    const { initStepper } = await loadModule('static/js/form-stepper.js');
    expect(() => initStepper(document.getElementById('orphan'))).not.toThrow();
  });
});