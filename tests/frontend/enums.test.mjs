import { describe, it, expect, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  window.ENUMS = {};
  loadScript('static/js/enums.js');
});

describe('enums.js', () => {
  it('loads ENUMS.COLORS with expected keys', () => {
    expect(window.ENUMS.COLORS).toBeDefined();
    expect(window.ENUMS.COLORS.OPEN).toBe('info');
    expect(window.ENUMS.COLORS.COMPLETED).toBe('success');
    expect(window.ENUMS.COLORS.CANCELLED).toBe('danger');
  });

  it('loads ENUMS.LABELS with expected keys', () => {
    expect(window.ENUMS.LABELS).toBeDefined();
    expect(window.ENUMS.LABELS.OPEN).toBe('مفتوحة');
    expect(window.ENUMS.LABELS.COMPLETED).toBe('مكتملة');
  });

  it('all COLORS values are non-empty strings', () => {
    for (const [, val] of Object.entries(window.ENUMS.COLORS)) {
      expect(typeof val).toBe('string');
      expect(val.length).toBeGreaterThan(0);
    }
  });

  it('all LABELS values are non-empty strings', () => {
    for (const [, val] of Object.entries(window.ENUMS.LABELS)) {
      expect(typeof val).toBe('string');
      expect(val.length).toBeGreaterThan(0);
    }
  });
});
