import { vi } from 'vitest';

global.window = globalThis;
window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.HTMLElement.prototype.scrollIntoViewIfNeeded = vi.fn();

if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addListener: vi.fn(),
    removeListener: vi.fn(),
  });
}

Element.prototype.closest = Element.prototype.closest || function(selector) {
  let el = this;
  while (el && el !== document) {
    if (el.matches(selector)) return el;
    el = el.parentElement;
  }
  return null;
};

if (!Element.prototype.matches) {
  Element.prototype.matches = Element.prototype.msMatchesSelector || Element.prototype.webkitMatchesSelector;
}

window.Swal = {
  fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
};

window.Toast = {
  fire: vi.fn(),
};

window.__ENV = 'testing';
window.csrfToken = 'test-csrf-token';
