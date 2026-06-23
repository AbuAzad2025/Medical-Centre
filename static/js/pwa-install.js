(function () {
  'use strict';
  var VISIT_KEY = 'azad_pwa_visits';
  var DISMISS_KEY = 'azad_pwa_install_dismissed';
  var deferredPrompt = null;

  function visitCount() {
    try {
      return parseInt(localStorage.getItem(VISIT_KEY) || '0', 10) + 1;
    } catch (e) {
      return 1;
    }
  }

  function bumpVisits() {
    try {
      localStorage.setItem(VISIT_KEY, String(visitCount()));
    } catch (e) {}
  }

  function isIOS() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent);
  }

  function showBanner() {
    if (document.getElementById('pwaInstallBanner')) return;
    try {
      if (localStorage.getItem(DISMISS_KEY) === '1') return;
    } catch (e) {}

    var bar = document.createElement('div');
    bar.id = 'pwaInstallBanner';
    bar.className = 'pwa-install-banner';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'تثبيت التطبيق');
    bar.innerHTML = '<div class="pwa-install-banner__text"><i class="fas fa-download me-2"></i><span id="pwaInstallText">ثبّت التطبيق للوصول السريع</span></div>'
      + '<div class="pwa-install-banner__actions">'
      + '<button type="button" class="btn btn-sm btn-primary" id="pwaInstallBtn">تثبيت</button>'
      + '<button type="button" class="btn btn-sm btn-outline-secondary" id="pwaInstallDismiss">لاحقاً</button>'
      + '</div>';
    document.body.appendChild(bar);

    document.getElementById('pwaInstallDismiss').addEventListener('click', function () {
      try { localStorage.setItem(DISMISS_KEY, '1'); } catch (e) {}
      bar.remove();
    });

    document.getElementById('pwaInstallBtn').addEventListener('click', function () {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
          deferredPrompt = null;
          bar.remove();
        });
        return;
      }
      if (isIOS()) {
        document.getElementById('pwaInstallText').textContent =
          'اضغط مشاركة ثم «إضافة إلى الشاشة الرئيسية»';
      }
    });
  }

  bumpVisits();

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    if (visitCount() >= 2) showBanner();
  });

  if (isIOS() && visitCount() >= 2 && !window.matchMedia('(display-mode: standalone)').matches) {
    showBanner();
  }
})();
