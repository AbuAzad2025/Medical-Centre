/* Touch mode detection - TypeScript */
(function(): void {
  'use strict';

  function isTouchDevice(): boolean {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  }

  if (isTouchDevice()) {
    document.documentElement.classList.add('touch-device');
  }

  (window as any).isTouchDevice = isTouchDevice;
})();