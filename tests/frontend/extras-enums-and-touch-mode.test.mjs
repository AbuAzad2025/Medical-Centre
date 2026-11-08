import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  delete window.ENUMS;
});

describe('enums.js', () => {
  it('creates window.ENUMS when absent', async () => {
    await loadModule('static/js/enums.js');
    expect(window.ENUMS).toBeDefined();
    expect(window.ENUMS.COLORS.OPEN).toBe('info');
    expect(window.ENUMS.LABELS.EMERGENCY).toBeDefined();
  });

  it('preserves the window.ENUMS reference', async () => {
    const preset = { COLORS: { OPEN: 'custom' }, LABELS: {} };
    window.ENUMS = preset;
    await loadModule('static/js/enums.js');
    expect(window.ENUMS).toBe(preset);
    expect(window.ENUMS.COLORS.OPEN).toBe('info');
    expect(window.ENUMS.LABELS.PENDING).toBeDefined();
  });
});

describe('touch-mode.js', () => {
  it('sets data-touch=coarse when matchMedia matches', async () => {
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    window.location = { search: '' };
    await loadModule('static/js/touch-mode.js');
    expect(document.body.dataset.touch).toBe('coarse');
  });

  it('sets data-touch=fine when matchMedia does not match', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    window.location = { search: '' };
    await loadModule('static/js/touch-mode.js');
    expect(document.body.dataset.touch).toBe('fine');
  });

  it('kiosk query param sets data-touch=coarse regardless of matchMedia', async () => {
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    window.location = { search: '?kiosk&other=1' };
    await loadModule('static/js/touch-mode.js');
    expect(document.body.dataset.touch).toBe('coarse');
    expect(document.body.dataset.kiosk).toBe('true');
  });

  it('non-kiosk url does not set data-kiosk', async () => {
    delete document.body.dataset.kiosk;
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    window.location = { search: '?x=1' };
    await loadModule('static/js/touch-mode.js');
    expect(document.body.dataset.kiosk).toBeUndefined();
  });
});