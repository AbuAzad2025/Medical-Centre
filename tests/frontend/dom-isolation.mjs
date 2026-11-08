/**
 * Capture DOMContentLoaded listeners registered during a test and remove them
 * afterwards, so listeners attached by a freshly imported module do not leak
 * into the next test's dispatch.
 */
export function isolateDomContentLoaded() {
  const state = { listeners: [] };
  const origAdd = document.addEventListener.bind(document);
  const origRemove = document.removeEventListener.bind(document);

  return {
    install() {
      state.listeners = [];
      document.addEventListener = (type, listener, ...rest) => {
        if (type === 'DOMContentLoaded') state.listeners.push(listener);
        origAdd(type, listener, ...rest);
      };
    },
    cleanup() {
      for (const listener of state.listeners) origRemove('DOMContentLoaded', listener);
      state.listeners = [];
      document.addEventListener = origAdd;
    },
    dispatchAndSettle: async () => {
      document.dispatchEvent(new Event('DOMContentLoaded'));
      await new Promise(r => setTimeout(r, 80));
    },
  };
}
