var __M = window.__M || [];
const baseCurrency = __M0__;
  const currencySelect = document.getElementById('paymentCurrencySelect');
  const rateInfo = document.getElementById('exchangeRateInfo');
  const remainingDisplay = document.getElementById('remainingDisplay');
  const baseLabel = document.getElementById('baseCurrencyLabel');

  async function checkRate() {
    const from = currencySelect.value;
    if (from === baseCurrency) {
      rateInfo.classList.add('d-none');
      baseLabel.textContent = baseCurrency;
      return;
    }
    try {
      const r = await fetch(`/reception/api/check-rate?from=${from}&to=${baseCurrency}`);
      const d = await r.json();
      if (d.available) {
        rateInfo.classList.remove('d-none');
        rateInfo.innerHTML = `<i class="fas fa-check text-success me-1"></i>سعر الصرف: 1 ${from} = ${d.rate.toFixed(4)} ${baseCurrency}`;
      } else {
        rateInfo.classList.remove('d-none');
        rateInfo.innerHTML = `<i class="fas fa-exclamation-triangle text-warning me-1"></i>سعر الصرف غير متوفر — سيتم طلبه عند التأكيد`;
      }
    } catch(e) { rateInfo.classList.add('d-none'); }
  }

  currencySelect.addEventListener('change', checkRate);
  checkRate();
