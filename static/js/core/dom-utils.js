export function escHtml(v) {
  if (v === null || v === undefined) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function debounce(fn, waitMs) {
  let timer = null;
  return function debounced(...args) {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, waitMs);
  };
}

export function digitsOnly(s, max4 = 4) {
  if (s === null || s === undefined) return '';
  const stripped = String(s).replace(/\D/g, '');
  const cap = Number.isInteger(max4) && max4 > 0 ? max4 : 4;
  return stripped.slice(0, cap);
}

export function formatMoney(n) {
  const num = Number(n);
  if (!Number.isFinite(num)) return '0.00';
  return num.toFixed(2);
}
