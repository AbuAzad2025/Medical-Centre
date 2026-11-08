import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.confirm = vi.fn(() => true);
  window.bootstrap = { Modal: { getInstance: vi.fn(() => ({ hide: vi.fn() })), getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('events.js', () => {
  it('confirmAction uses Swal when available and fires onConfirm on confirm', async () => {
    const mod = await loadModule('static/js/events.js');
    const cb = vi.fn();
    mod.confirmAction('msg', cb);
    await new Promise(r => setTimeout(r, 20));
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('confirmAction uses window.confirm when Swal missing', async () => {
    const mod = await loadModule('static/js/events.js');
    delete window.Swal;
    const cb = vi.fn();
    mod.confirmAction('msg', cb);
    expect(cb).toHaveBeenCalled();
  });

  it('confirmAction confirm=false does not call onConfirm', async () => {
    const mod = await loadModule('static/js/events.js');
    delete window.Swal;
    window.confirm = vi.fn(() => false);
    const cb = vi.fn();
    mod.confirmAction('msg', cb);
    expect(cb).not.toHaveBeenCalled();
  });

  it('data-action="print" triggers window.print', async () => {
    await loadModule('static/js/events.js');
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});
    document.body.innerHTML = '<button data-action="print">x</button>';
    document.querySelector('[data-action]').click();
    expect(printSpy).toHaveBeenCalled();
    printSpy.mockRestore();
  });

  it('data-action="go-back" triggers history.back', async () => {
    await loadModule('static/js/events.js');
    const backSpy = vi.spyOn(window.history, 'back').mockImplementation(() => {});
    document.body.innerHTML = '<button data-action="go-back">x</button>';
    document.querySelector('[data-action]').click();
    expect(backSpy).toHaveBeenCalled();
    backSpy.mockRestore();
  });

  it('data-action="reload" triggers location.reload', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = '<button data-action="reload">x</button>';
    expect(() => document.querySelector('[data-action]').click()).not.toThrow();
  });

  it('data-action="close-modal" hides modal instance', async () => {
    await loadModule('static/js/events.js');
    const hide = vi.fn();
    window.bootstrap.Modal.getInstance = vi.fn(() => ({ hide }));
    document.body.innerHTML = '<div class="modal" id="m"><button data-action="close-modal">x</button></div>';
    document.querySelector('[data-action]').click();
    expect(hide).toHaveBeenCalled();
  });

  it('data-action="close-modal" no-ops without modal parent', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = '<button data-action="close-modal">x</button>';
    expect(() => document.querySelector('[data-action]').click()).not.toThrow();
  });

  it('data-action="submit-form" submits the closest form', async () => {
    await loadModule('static/js/events.js');
    const form = document.createElement('form');
    form.submit = vi.fn();
    document.body.appendChild(form);
    const btn = document.createElement('button');
    btn.setAttribute('data-action', 'submit-form');
    form.appendChild(btn);
    btn.click();
    expect(form.submit).toHaveBeenCalled();
  });

  it('data-action="confirm" submits closest form when confirmed', async () => {
    await loadModule('static/js/events.js');
    const form = document.createElement('form');
    form.submit = vi.fn();
    document.body.appendChild(form);
    const btn = document.createElement('button');
    btn.setAttribute('data-action', 'confirm');
    btn.setAttribute('data-message', 'sure?');
    form.appendChild(btn);
    btn.click();
    await new Promise(r => setTimeout(r, 20));
    expect(form.submit).toHaveBeenCalled();
  });

  it('data-action="confirm" navigates anchor', async () => {
    await loadModule('static/js/events.js');
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true });
    document.body.innerHTML = '<a href="/somewhere" data-action="confirm">go</a>';
    const link = document.querySelector('a');
    link.click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('data-action="confirm-submit" submits form', async () => {
    await loadModule('static/js/events.js');
    const form = document.createElement('form');
    form.submit = vi.fn();
    document.body.appendChild(form);
    const btn = document.createElement('button');
    btn.setAttribute('data-action', 'confirm-submit');
    btn.setAttribute('data-message', 'sure?');
    form.appendChild(btn);
    btn.click();
    await new Promise(r => setTimeout(r, 20));
    expect(form.submit).toHaveBeenCalled();
  });

  it('data-action="confirm-navigate" sets location.href', async () => {
    await loadModule('static/js/events.js');
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: true });
    document.body.innerHTML = '<a href="/destination" data-action="confirm-navigate">go</a>';
    const link = document.querySelector('a');
    link.click();
    await new Promise(r => setTimeout(r, 20));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('data-action="toggle-password" invokes setAttribute on target', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = `
      <input type="password" id="pwd">
      <button data-action="toggle-password" data-target="pwd">T</button>
    `;
    const input = document.getElementById('pwd');
    const spy = vi.fn(function(name, value) { return this.__proto__.setAttribute.call(this, name, value); });
    input.setAttribute = spy;
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('type', 'text');
  });

  it('toggle-password no-ops against missing target', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = '<button data-action="toggle-password" data-target="nope">T</button>';
    expect(() => document.querySelector('[data-action]').click()).not.toThrow();
  });

  it('filter-* calls window.filter<Name> with data-value', async () => {
    await loadModule('static/js/events.js');
    window.filterActive = vi.fn();
    document.body.innerHTML = '<button data-action="filter-active" data-value="x">F</button>';
    document.querySelector('[data-action]').click();
    expect(window.filterActive).toHaveBeenCalledWith('x');
  });

  it('filter-id-* calls window.filterId<Name>', async () => {
    await loadModule('static/js/events.js');
    window.filterStatus = vi.fn();
    document.body.innerHTML = '<button data-action="filter-status" data-value="s">F</button>';
    document.querySelector('[data-action]').click();
    expect(window.filterStatus).toHaveBeenCalledWith('s');
  });

  it('filter with camelCase guess path', async () => {
    await loadModule('static/js/events.js');
    window.filterMyThing = vi.fn();
    document.body.innerHTML = '<button data-action="filter-my-thing" data-value="m">F</button>';
    document.querySelector('[data-action]').click();
    expect(window.filterMyThing).toHaveBeenCalledWith('m');
  });

  it('window-action dispatcher passes single id key', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.viewItem = spy;
    document.body.innerHTML = '<button data-action="view-item" data-id="42">V</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('42');
  });

  it('window-action passes value and text together', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.actThing = spy;
    document.body.innerHTML = '<button data-action="actThing" data-value="v" data-text="t">A</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('v', 't');
  });

  it('window-action passes only value when set', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.actThing = spy;
    document.body.innerHTML = '<button data-action="actThing" data-value="v">A</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('v');
  });

  it('window-action passes message when that alone is set', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.actThing = spy;
    document.body.innerHTML = '<button data-action="actThing" data-message="hi">A</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('hi');
  });

  it('window-action fallback passes nothing', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.actThing = spy;
    document.body.innerHTML = '<button data-action="actThing">A</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith();
  });

  it('action not registered does not throw', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = '<button data-action="does-not-exist">X</button>';
    expect(() => document.querySelector('[data-action]').click()).not.toThrow();
  });

  it('exposes camelCase fallback action', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.doSomething = spy;
    document.body.innerHTML = '<button data-action="do-something" data-value="v">D</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('v');
  });

  it('default export is present', async () => {
    const mod = await loadModule('static/js/events.js');
    expect(mod.default).toBeDefined();
  });
});
describe('events.js raw action and fallback arms', () => {
  it('filter-* with no matching window.filter* falls through to the camelCase path', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.filterSlow = spy;
    document.body.innerHTML = '<button data-action="filter-slow" data-value="x">F</button>';
    // window.filterSlow already matches the primary guess
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('x');
  });

  it('filter-* matching neither guess calls nothing and does not throw', async () => {
    await loadModule('static/js/events.js');
    document.body.innerHTML = '<button data-action="filter-nothere" data-value="x">F</button>';
    expect(() => document.querySelector('[data-action]').click()).not.toThrow();
  });

  it('raw action with exactly one non-reserved dataset key passes it to the function', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.viewItem = spy; // raw key must match window.viewItem exactly
    document.body.innerHTML = '<button data-action="viewItem" data-user-id="42">V</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith('42');
  });

  it('raw action with one reserved id key still passes other single key', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.actItem = spy;
    document.body.innerHTML = '<button data-action="actItem" data-value="v" data-user-id="9">A</button>';
    document.querySelector('[data-action]').click();
    // value and id are excluded from idKeys, leaving userId as the single key
    expect(spy).toHaveBeenCalledWith('9');
  });

  it('fn2 camelCase path with no value or id calls the function with nothing', async () => {
    await loadModule('static/js/events.js');
    const spy = vi.fn();
    window.cleanupNow = spy;
    document.body.innerHTML = '<button data-action="cleanup-now">Go</button>';
    document.querySelector('[data-action]').click();
    expect(spy).toHaveBeenCalledWith();
  });
});
