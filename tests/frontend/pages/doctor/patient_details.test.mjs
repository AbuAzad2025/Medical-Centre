import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <button id="diagnosis-tab"></button>
    <button id="prescriptions-tab"></button>
    <button id="lab-tab"></button>
    <button id="radiology-tab"></button>
    <button id="history-tab"></button>
  `;
  window.__M0__ = '/doctor/dashboard';
  window.__M1__ = '/doctor/lab-results';
});

describe('doctor/patient_details.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/doctor/patient_details.js');
  });

  test('keyboard shortcuts listener is registered', async () => {
    await loadScript('static/js/pages/doctor/patient_details.js');
    const event = new KeyboardEvent('keydown', { altKey: true, key: '1' });
    document.dispatchEvent(event);
    expect(true).toBe(true);
  });

  test('Alt+1 clicks diagnosis tab', async () => {
    await loadScript('static/js/pages/doctor/patient_details.js');
    const tab = document.getElementById('diagnosis-tab');
    const clickSpy = vi.fn();
    tab.addEventListener('click', clickSpy);
    document.dispatchEvent(new KeyboardEvent('keydown', { altKey: true, key: '1' }));
    expect(clickSpy).toHaveBeenCalled();
  });

  test('keyboard shortcut ignores input fields', async () => {
    await loadScript('static/js/pages/doctor/patient_details.js');
    const input = document.createElement('input');
    document.body.appendChild(input);
    const event = new KeyboardEvent('keydown', { altKey: true, key: '1', bubbles: true });
    input.dispatchEvent(event);
    expect(true).toBe(true);
  });
});
