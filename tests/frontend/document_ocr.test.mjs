import { describe, it, expect, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(async () => {
  document.body.innerHTML = '';
  await loadModule('static/js/document_ocr.js');
});

describe('document_ocr.js', () => {
  it('loads without error', () => {
    expect(true).toBe(true);
  });
});
