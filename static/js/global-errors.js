(function (global) {
  'use strict';

  function reportError(message, source) {
    var msg = message || 'حدث خطأ غير متوقع';
    if (global.notify && typeof global.notify.error === 'function') {
      global.notify.error(msg);
    } else {
      console.error('[global-errors]', source || '', msg);
    }
    if (window.__ENV === 'production') {
      try {
        var auditLogUrl = (window.API_ROUTES && window.API_ROUTES.audit_log) || '/super-admin/api/audit-log';
        var csrfMeta = document.querySelector('meta[name="csrf-token"]');
        var csrfVal = csrfMeta ? csrfMeta.content : '';
        fetch(auditLogUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfVal, 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ action: 'js_error', message: msg, source: source, url: global.location.href }),
        }).catch(function(){ console.warn('فشل إرسال سجل الخطأ'); });
      } catch (e) {}
    }
  }

  global.onerror = function (msg, source, _lineno, _colno, error) {
    if (source && (String(source).indexOf('.map') !== -1 || String(source).indexOf('favicon') !== -1)) {
      return false;
    }
    var detail = (error && error.message) || msg || 'حدث خطأ غير متوقع';
    reportError(detail, 'onerror');
    return false;
  };

  global.onunhandledrejection = function (event) {
    var reason = event && event.reason;
    var msg = (reason && (reason.message || String(reason))) || 'خطأ في العملية';
    reportError(msg, 'unhandledrejection');
  };

  function showEntitlementLock(payload) {
    if (document.querySelector('.entitlement-lock-overlay')) return;
    var title = (payload && payload.title) || 'الميزة غير متاحة';
    var message = (payload && (payload.message || payload.description || payload.error))
      || 'هذه الميزة غير مفعّلة في باقتك الحالية. تواصل مع مدير المنشأة للترقية.';
    var capability = (payload && (payload.capability_key || payload.capability)) || '';
    var upgradeUrl = (payload && (payload.upgrade_url || payload.upgradeUrl)) || '';

    var overlay = document.createElement('div');
    overlay.className = 'entitlement-lock-overlay';
    overlay.setAttribute('role', 'alertdialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.innerHTML =
      '<div class="entitlement-lock-overlay__backdrop"></div>' +
      '<div class="entitlement-lock-screen entitlement-lock-overlay__panel" data-capability="' +
      global.escHtml(String(capability)) + '">' +
      '<div class="entitlement-lock-screen__icon" aria-hidden="true"><i class="fas fa-lock"></i></div>' +
      '<h5 class="mb-2">' + global.escHtml(String(title)) + '</h5>' +
      '<p class="text-muted mb-3">' + global.escHtml(String(message)) + '</p>' +
      (upgradeUrl
        ? '<a href="' + global.escHtml(String(upgradeUrl)) + '" class="btn btn-primary btn-sm">ترقية الباقة</a>'
        : '<button type="button" class="btn btn-secondary btn-sm" data-dismiss-lock>إغلاق</button>') +
      '</div>';
    document.body.appendChild(overlay);
    var dismiss = overlay.querySelector('[data-dismiss-lock]');
    if (dismiss) {
      dismiss.addEventListener('click', function () { overlay.remove(); });
    }
    if (global.notify && typeof global.notify.warning === 'function') {
      global.notify.warning(message);
    }
  }

  function parseJsonSafe(response) {
    return response.clone().json().catch(function () { return {}; });
  }

  function handleEntitlementStatus(response) {
    if (response.status !== 402 && response.status !== 403) return;
    parseJsonSafe(response).then(function (data) {
      if (data && data.redirect_url) {
        global.location.href = data.redirect_url;
        return;
      }
      showEntitlementLock(data || {});
    });
  }

  function wrapFetchWithEntitlementHandling(fetchFn) {
    return function (input, init) {
      return fetchFn(input, init).then(function (response) {
        handleEntitlementStatus(response);
        return response;
      }).catch(function (err) {
        reportError('فشل الاتصال بالخادم. تحقق من الشبكة.', 'fetch');
        throw err;
      });
    };
  }

  global.__wrapFetchEntitlement = wrapFetchWithEntitlementHandling;
  global.__showEntitlementLock = showEntitlementLock;
})(window);
