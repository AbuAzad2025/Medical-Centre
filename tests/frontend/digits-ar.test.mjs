import { describe, it, expect } from 'vitest';
import { normalizeArabicDigits } from '../../static/js/digits-ar.js';

describe('normalizeArabicDigits', () => {
  it('converts Arabic digits ٠١٢٣٤٥٦٧٨٩ to 0123456789', () => {
    const textNode = document.createTextNode('٠١٢٣٤٥٦٧٨٩');
    const div = document.createElement('div');
    div.appendChild(textNode);
    document.body.appendChild(div);
    normalizeArabicDigits(div);
    expect(textNode.nodeValue).toBe('0123456789');
  });

  it('does not affect Latin digits', () => {
    const textNode = document.createTextNode('abc123');
    const div = document.createElement('div');
    div.appendChild(textNode);
    document.body.appendChild(div);
    normalizeArabicDigits(div);
    expect(textNode.nodeValue).toBe('abc123');
  });

  it('does nothing for null root', () => {
    expect(() => normalizeArabicDigits(null)).not.toThrow();
  });

  it('does nothing for undefined root', () => {
    expect(() => normalizeArabicDigits(undefined)).not.toThrow();
  });

  it('normalizes mixed text', () => {
    const textNode = document.createTextNode('الرقم ١٢٣');
    const div = document.createElement('div');
    div.appendChild(textNode);
    document.body.appendChild(div);
    normalizeArabicDigits(div);
    expect(textNode.nodeValue).toBe('الرقم 123');
  });
});
