(function () {
  function maskNationalId(value) {
    if (!value) return '';
    const cleaned = value.replace(/[^0-9X]/g, '');
    if (cleaned.length <= 4) return 'XXXX';
    return cleaned.slice(0, 3) + 'X'.repeat(cleaned.length - 4) + cleaned.slice(-1);
  }

  function maskPhone(value) {
    if (!value) return '';
    const digits = value.replace(/[^0-9+\-() ]/g, '');
    if (digits.length <= 3) return 'XXX';
    const lastFour = digits.slice(-4);
    const prefix = digits.slice(0, digits.length - 4).replace(/[0-9]/g, 'X');
    return prefix + lastFour;
  }

  function maskName(value) {
    if (!value) return '';
    const parts = value.trim().split(/\s+/);
    if (parts.length === 1) return parts[0][0] + 'X'.repeat(Math.max(0, parts[0].length - 1));
    return parts[0][0] + 'X'.repeat(Math.max(0, parts[0].length - 1)) + ' ' + parts[parts.length - 1];
  }

  function maskEmail(value) {
    if (!value || !value.includes('@')) return value || '';
    const [local, domain] = value.split('@');
    if (local.length <= 2) return local[0] + '***@' + domain;
    return local[0] + '***' + local[local.length - 1] + '@' + domain;
  }

  function toggleReveal(btn, value) {
    const span = btn.parentElement.querySelector('.pii-visible');
    if (!span) return;
    const isMasked = span.getAttribute('data-masked') === 'true';
    if (isMasked) {
      span.textContent = value;
      span.setAttribute('data-masked', 'false');
      btn.textContent = 'إخفاء';
    } else {
      span.textContent = maskNationalId(value);
      span.setAttribute('data-masked', 'true');
      btn.textContent = 'إظهار';
    }
  }

  window.PiiMask = {
    nationalId: maskNationalId,
    phone: maskPhone,
    name: maskName,
    email: maskEmail,
    toggleReveal: toggleReveal,
  };
})();