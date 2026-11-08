/**
 * Capture DOMContentLoaded and beforeunload listeners registered during a
 * test and remove them afterwards, so listeners attached by a freshly
 * imported module do not leak into the next test's dispatch (shared jsdom
 * windows accumulate handlers across tests).
 */
export function isolateDomContentLoaded() {
  const state = { before: [], domContent: [] };
  const origAdd = document.addEventListener.bind(document);
  const origAddWindow = window.addEventListener.bind(window);
  const origRemove = document.removeEventListener.bind(document);
  const origRemoveWindow = window.removeEventListener.bind(window);

  return {
    install() {
      state.before = [];
      state.domContent = [];
      document.addEventListener = (type, listener, ...rest) => {
        if (type === 'DOMContentLoaded') state.domContent.push(listener);
        origAdd(type, listener, ...rest);
      };
      window.addEventListener = (type, listener, ...rest) => {
        if (type === 'beforeunload') state.before.push(listener);
        origAddWindow(type, listener, ...rest);
      };
    },
    cleanup() {
      for (const listener of state.domContent) origRemove('DOMContentLoaded', listener);
      for (const listener of state.before) origRemoveWindow('beforeunload', listener);
      state.domContent = [];
      state.before = [];
      document.addEventListener = origAdd;
      window.addEventListener = origAddWindow;
    },
    dispatchAndSettle: async () => {
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 80));
    },
  };
}
