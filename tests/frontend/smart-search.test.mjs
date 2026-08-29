import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ patients: [] }) });
  vi.useFakeTimers();
  loadScript('static/js/smart-search.js');
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function setupSmartSearch() {
  document.body.innerHTML = `
    <div data-smart-search data-api="/api/search/patients" data-min="2">
      <input type="text" data-smart-search-input />
      <div data-smart-search-results class="smart-search-results"></div>
      <input type="hidden" />
    </div>
  `;
  const root = document.querySelector('[data-smart-search]');
  window.initSmartSearch(root);
  return { input: root.querySelector('[data-smart-search-input]'), root };
}

describe('smart-search.js', () => {
  it('debounces search input', () => {
    window.fetch.mockClear();
    const { input } = setupSmartSearch();

    input.value = 'test';
    input.dispatchEvent(new Event('input'));
    input.value = 'testing';
    input.dispatchEvent(new Event('input'));

    vi.advanceTimersByTime(300);
    expect(window.fetch).toHaveBeenCalledTimes(1);
  });

  it('does not search with less than minChars', () => {
    window.fetch.mockClear();
    const { input } = setupSmartSearch();

    input.value = 'a';
    input.dispatchEvent(new Event('input'));
    vi.advanceTimersByTime(300);
    expect(window.fetch).not.toHaveBeenCalled();
  });

  it('sends request on valid input', () => {
    window.fetch.mockClear();
    const { input } = setupSmartSearch();

    input.value = 'ab';
    input.dispatchEvent(new Event('input'));
    vi.advanceTimersByTime(300);
    expect(window.fetch).toHaveBeenCalledTimes(1);
    expect(window.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/search/patients?q='),
      expect.any(Object)
    );
  });
});
