(function () {
  'use strict';
  var coarse = window.matchMedia('(pointer: coarse)').matches;
  var kiosk = new URLSearchParams(window.location.search).has('kiosk');
  document.body.dataset.touch = coarse || kiosk ? 'coarse' : 'fine';
  if (kiosk) document.body.dataset.kiosk = 'true';
})();
