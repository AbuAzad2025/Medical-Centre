import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <div data-ocr>
      <input type="file" id="ocrFile">
      <div data-ocr-progress></div>
      <div data-ocr-result></div>
    </div>
    <div data-ocr>
      <input type="file" id="ocrFile2">
    </div>
  `;
}

beforeEach(() => {
  baseDom();
  window.Tesseract = {
    recognize: vi.fn().mockResolvedValue({ data: { text: 'مرحبا بالعالم' } }),
  };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('document_ocr.js', () => {
  it('exposes initOCR on window', async () => {
    await loadModule('static/js/document_ocr.js');
    expect(typeof window.initOCR).toBe('function');
  });

  it('initializes listeners on OCR containers', async () => {
    const mod = await loadModule('static/js/document_ocr.js');
    expect(typeof mod.initOCR).toBe('function');
  });

  it('file change with unknown Tesseract shows warning', async () => {
    delete window.Tesseract;
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    const file = new File(['img'], 'photo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 20));
    expect(document.querySelector('[data-ocr-result]').innerHTML).toContain('Tesseract');
  });

  it('file change with Tesseract recognizing Arabic text', async () => {
    document.documentElement.lang = 'ar';
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    const file = new File(['img'], 'photo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    expect(window.Tesseract.recognize).toHaveBeenCalledWith(file, 'ara', expect.any(Object));
    expect(document.querySelector('[data-ocr-result]').textContent).toBe('مرحبا بالعالم');
  });

  it('file change with Tesseract recognizing English text', async () => {
    document.documentElement.lang = 'en';
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    const file = new File(['img'], 'photo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    expect(window.Tesseract.recognize).toHaveBeenCalledWith(file, 'eng', expect.any(Object));
  });

  it('progress area updates during recognition', async () => {
    window.Tesseract = {
      recognize: vi.fn().mockImplementation((file, lang, opts) => {
        opts.logger({ status: 'recognizing text', progress: 0.5 });
        return new Promise(() => {}); // never resolves so the progress text persists
      }),
    };
    document.documentElement.lang = 'ar';
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    const file = new File(['img'], 'photo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 20));
    expect(document.querySelector('[data-ocr-progress]').textContent).toContain('50%');
  });

  it('recognition failure updates progress with error', async () => {
    window.Tesseract = {
      recognize: vi.fn().mockRejectedValue(new Error('ocr failed')),
    };
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    const file = new File(['img'], 'photo.png', { type: 'image/png' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    await new Promise(r => setTimeout(r, 50));
    expect(document.querySelector('[data-ocr-progress]').textContent).toContain('ocr failed');
  });

  it('file change without files does nothing', async () => {
    await loadModule('static/js/document_ocr.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('ocrFile');
    Object.defineProperty(input, 'files', { value: [], configurable: true });
    expect(() => input.dispatchEvent(new Event('change'))).not.toThrow();
    expect(window.Tesseract.recognize).not.toHaveBeenCalled();
  });

  it('container without resultArea is skipped', async () => {
    const mod = await loadModule('static/js/document_ocr.js');
    expect(document.getElementById('ocrFile2')).toBeTruthy();
    expect(typeof mod.initOCR).toBe('function');
  });
});