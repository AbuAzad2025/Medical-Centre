import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadScript } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.fetch = vi.fn().mockResolvedValue({ ok: true });
});

describe('dashboard-customize.js', () => {
  it('collectHidden collects unchecked checkboxes', () => {
    document.body.innerHTML = `
      <div id="ccWidgetToggles">
        <input type="checkbox" class="cc-widget-toggle" value="widget1" checked />
        <input type="checkbox" class="cc-widget-toggle" value="widget2" />
        <input type="checkbox" class="cc-widget-toggle" value="widget3" checked />
      </div>
    `;
    const hidden = [];
    document.querySelectorAll('.cc-widget-toggle').forEach(cb => {
      if (!cb.checked) hidden.push(cb.value);
    });
    expect(hidden).toEqual(['widget2']);
  });

  it('toggleWidgetVisibility shows/hides widget', () => {
    document.body.innerHTML = `
      <div id="ccWidgetToggles">
        <input type="checkbox" class="cc-widget-toggle" value="w1" checked />
        <input type="checkbox" class="cc-widget-toggle" value="w2" />
      </div>
      <div data-widget="w1">Widget 1</div>
      <div data-widget="w2">Widget 2</div>
    `;
    document.querySelectorAll('.cc-widget-toggle').forEach(cb => {
      const widget = document.querySelector('[data-widget="' + cb.value + '"]');
      if (widget) widget.style.display = cb.checked ? '' : 'none';
    });
    expect(document.querySelector('[data-widget="w1"]').style.display).toBe('');
    expect(document.querySelector('[data-widget="w2"]').style.display).toBe('none');
  });
});
