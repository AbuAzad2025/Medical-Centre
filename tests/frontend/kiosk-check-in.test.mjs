import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = `
    <input id="nationalId" />
    <div id="kioskKeypad"></div>
    <button id="kioskSubmit">Submit</button>
    <div id="kioskResult"></div>
  `;
  window.__M = [];
  await loadModule('static/js/pages/kiosk/check_in.js');
});

describe('kiosk/check_in.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});