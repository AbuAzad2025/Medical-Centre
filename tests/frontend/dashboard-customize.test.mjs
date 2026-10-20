import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

/**
 * These cases used to re-implement the logic they asserted on: the test
 * declared its own collectHidden and its own toggleWidgetVisibility and
 * checked those. The production script was never loaded, so
 * static/js/dashboard-customize.js had no coverage, and the cases could not
 * fail however the real script behaved.
 *
 * The script attaches to DOMContentLoaded, so it is loaded here and the
 * event dispatched - the assertions then run against the real behaviour.
 */
beforeEach(async () => {
  document.body.innerHTML = '';
  window.API_ROUTES = {};
  window.UIPreferences = { persist: vi.fn().mockResolvedValue(undefined) };
  window.notifications = { show: vi.fn() };
  window.fetch = vi.fn().mockResolvedValue({ ok: true });

  document.body.innerHTML = `
    <div id="ccWidgetToggles">
      <input type="checkbox" class="cc-widget-toggle" value="widget1" checked />
      <input type="checkbox" class="cc-widget-toggle" value="widget2" />
      <input type="checkbox" class="cc-widget-toggle" value="widget3" checked />
    </div>
    <div data-widget="widget1"></div>
    <div data-widget="widget2"></div>
    <div data-widget="widget3"></div>
  `;

  await loadModule('static/js/dashboard-customize.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('dashboard-customize.js', () => {
  it('hides the widget of an unchecked toggle', () => {
    const toggle = document.querySelector('.cc-widget-toggle[value="widget2"]');
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change', { bubbles: true }));

    expect(document.querySelector('[data-widget="widget2"]').style.display).toBe('none');
  });

  it('shows the widget of a checked toggle', () => {
    const widget = document.querySelector('[data-widget="widget2"]');
    widget.style.display = 'none';

    const toggle = document.querySelector('.cc-widget-toggle[value="widget2"]');
    toggle.checked = true;
    toggle.dispatchEvent(new Event('change', { bubbles: true }));

    expect(widget.style.display).toBe('');
  });

  it('leaves a checked widget alone', () => {
    const toggle = document.querySelector('.cc-widget-toggle[value="widget1"]');
    toggle.dispatchEvent(new Event('change', { bubbles: true }));

    expect(document.querySelector('[data-widget="widget1"]').style.display).toBe('');
  });

  it('persists the hidden widgets', () => {
    const toggle = document.querySelector('.cc-widget-toggle[value="widget2"]');
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change', { bubbles: true }));

    expect(window.UIPreferences.persist).toHaveBeenCalledWith({
      dashboard: { hidden_widgets: ['widget2'] },
    });
  });

  it('reports the change to the user', async () => {
    const toggle = document.querySelector('.cc-widget-toggle[value="widget2"]');
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change', { bubbles: true }));
    await vi.waitFor(() => {
      expect(window.notifications.show).toHaveBeenCalled();
    });
  });
});
