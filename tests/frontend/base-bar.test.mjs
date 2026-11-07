import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeAll(async () => {
  await loadModule('static/js/base.js');
});

beforeEach(() => {
  try { localStorage.clear(); } catch (e) {}
  document.querySelectorAll('body > *:not(#topLoadingBar)').forEach((n) => n.remove());
});

afterEach(() => {
  vi.useRealTimers();
});

describe('base.js top loading bar', () => {
  it('loading bar shows on same-origin link click', () => {
    const link = document.createElement('a');
    link.href = `${window.location.origin}/other-page`;
    link.textContent = 'Go';
    link.addEventListener('click', (e) => e.preventDefault());
    document.body.appendChild(link);
    link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    expect(document.getElementById('topLoadingBar').style.display).toBe('block');
  });

  it('beforeunload shows loading bar', () => {
    window.dispatchEvent(new Event('beforeunload'));
    expect(document.getElementById('topLoadingBar').style.display).toBe('block');
  });
});