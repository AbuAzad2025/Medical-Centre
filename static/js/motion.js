(function () {
  'use strict';

  function motionEnabled() {
    var reduced = false;
    try {
      reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {}
    var userMotion = (window.__USER_PREFS__ && window.__USER_PREFS__.ui && window.__USER_PREFS__.ui.motion) || null;
    return !reduced && userMotion !== 'reduced';
  }

  window.__MOTION_ENABLED__ = motionEnabled;

  function runEntranceAnimations() {
    if (!motionEnabled() || typeof gsap === 'undefined') return;
    var items = document.querySelectorAll('.animate-in');
    if (!items.length) return;
    gsap.from(items, {
      y: 12,
      opacity: 0,
      duration: 0.35,
      stagger: 0.05,
      ease: 'power2.out',
      clearProps: 'transform',
    });
  }

  window.addEventListener('load', runEntranceAnimations);
})();
