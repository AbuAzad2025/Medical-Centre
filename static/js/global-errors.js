'use strict';

// Standalone-safe escaping and URL validation. window.escHtml comes from base.js,
// but this module also runs on minimal shells; never depend on load order.
function esc(v) {
  if (typeof window !== 'undefined' && typeof window.escHtml === 'function') {
    return window.escHtml(v);
  }
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function safeSameOriginUrl(raw) {
  // Only root-relative or same-origin absolute URLs are allowed back into
  // location.href / <a href>. Server-controlled redirect_url must never be
  // able to smuggle javascript: or external-origin payloads.
  if (!raw || typeof raw !== 'string') return '';
  var url = raw.trim();
  if (!url) return '';
  if (url.indexOf('/') === 0) {
    if (url.indexOf('//') === 0) return ''; // protocol-relative: outside origin
    return url;
  }
  try {
    var loc = window.location || {};
    var origin = loc.origin;
    if (!origin && loc.href) {
      try { origin = new URL(loc.href).origin; } catch (_ignored) { origin = ''; }
    }
    if (!origin) return ''; // cannot determine same-origin: refuse
    var parsed = new URL(url, origin);
    return parsed.origin === origin ? parsed.href : '';
  } catch (e) {
    return '';
  }
}

export function reportError(message, source) {
  var msg = message || 'حدث خطأ غير متوقع';
  if (window.notify && typeof window.notify.error === 'function') {
    window.notify.error(msg);
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
        body: JSON.stringify({ action: 'js_error', message: msg, source: source, url: window.location.href }),
      }).catch(function(){ console.warn('فشل إرسال سجل الخطأ'); });
    } catch (e) {}
  }
}

window.onerror = function (msg, source, _lineno, _colno, error) {
  if (source && (String(source).indexOf('.map') !== -1 || String(source).indexOf('favicon') !== -1)) {
    return false;
  }
  var detail = (error && error.message) || msg || 'حدث خطأ غير متوقع';
  reportError(detail, 'onerror');
  return false;
};

window.onunhandledrejection = function (event) {
  var reason = event && event.reason;
  var msg = (reason && (reason.message || String(reason))) || 'خطأ في العملية';
  reportError(msg, 'unhandledrejection');
};

export function showEntitlementLock(payload) {
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
    esc(String(capability)) + '">' +
    '<div class="entitlement-lock-screen__icon" aria-hidden="true"><i class="fas fa-lock"></i></div>' +
    '<h5 class="mb-2">' + esc(String(title)) + '</h5>' +
    '<p class="text-muted mb-3">' + esc(String(message)) + '</p>' +
    (safeSameOriginUrl(upgradeUrl)
      ? '<a href="' + esc(safeSameOriginUrl(upgradeUrl)) + '" class="btn btn-primary btn-sm">ترقية الباقة</a>'
      : '<button type="button" class="btn btn-secondary btn-sm" data-dismiss-lock>إغلاق</button>') +
    '</div>';
  document.body.appendChild(overlay);
  var dismiss = overlay.querySelector('[data-dismiss-lock]');
  if (dismiss) {
    dismiss.addEventListener('click', function () { overlay.remove(); });
  }
  if (window.notify && typeof window.notify.warning === 'function') {
    window.notify.warning(message);
  }
}

export function parseJsonSafe(response) {
  return response.clone().json().catch(function () { return {}; });
}

export function handleEntitlementStatus(response) {
  if (response.status !== 402 && response.status !== 403) return;
  parseJsonSafe(response).then(function (data) {
    if (data && data.redirect_url) {
      var safe = safeSameOriginUrl(data.redirect_url);
      if (safe) {
        window.location.href = safe;
        return;
      }
      // Unsafe redirect target: show the lock dialog instead of navigating.
      showEntitlementLock(data || {});
      return;
    }
    showEntitlementLock(data || {});
  });
}

export function wrapFetchWithEntitlementHandling(fetchFn) {
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

window.__wrapFetchEntitlement = wrapFetchWithEntitlementHandling;
window.__showEntitlementLock = showEntitlementLock;

// Backward compatibility
if (typeof reportError !== 'undefined') window.reportError = reportError;
if (typeof showEntitlementLock !== 'undefined') window.showEntitlementLock = showEntitlementLock;
if (typeof parseJsonSafe !== 'undefined') window.parseJsonSafe = parseJsonSafe;
if (typeof handleEntitlementStatus !== 'undefined') window.handleEntitlementStatus = handleEntitlementStatus;
if (typeof wrapFetchWithEntitlementHandling !== 'undefined') window.wrapFetchWithEntitlementHandling = wrapFetchWithEntitlementHandling;
if (typeof safeSameOriginUrl !== 'undefined') window.safeSameOriginUrl = safeSameOriginUrl;