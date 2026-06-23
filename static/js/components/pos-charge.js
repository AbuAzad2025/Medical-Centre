/**
 * Shared POS terminal charge button (reception + pharmacy — §35.6).
 */
(function (global) {
    function initPosCharge(opts) {
        const btn = typeof opts.button === 'string'
            ? document.getElementById(opts.button)
            : opts.button;
        if (!btn) return;

        const amountEl = typeof opts.amountInput === 'string'
            ? document.getElementById(opts.amountInput)
            : opts.amountInput;
        const statusEl = opts.statusElement
            ? (typeof opts.statusElement === 'string'
                ? document.getElementById(opts.statusElement)
                : opts.statusElement)
            : null;
        const chargeUrl = opts.chargeUrl || btn.dataset.chargeUrl;
        const amountFallback = opts.amountFallback;

        btn.addEventListener('click', function () {
            let amount = 0;
            if (typeof opts.getAmount === 'function') {
                amount = parseFloat(opts.getAmount()) || 0;
            } else if (amountEl) {
                amount = parseFloat(amountEl.value || '0');
            }
            if ((!amount || amount <= 0) && amountFallback) {
                const fb = document.getElementById(amountFallback);
                if (fb) amount = parseFloat(fb.value || '0');
            }
            if (statusEl) {
                statusEl.textContent = '';
                statusEl.className = 'text-muted ms-2';
            }
            if (!amount || amount <= 0) {
                if (global.showApiWarning) {
                    global.showApiWarning('تنبيه', 'يرجى تحديد المبلغ المراد تحصيله');
                }
                return;
            }
            btn.disabled = true;
            fetch(chargeUrl, {
                method: 'POST',
                headers: { 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ amount: String(amount) }),
            })
                .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
                .then(function (res) {
                    const d = res.data || {};
                    if (d.success) {
                        if (opts.cardLastDigitsId && d.card_last_digits) {
                            const el = document.getElementById(opts.cardLastDigitsId);
                            if (el) el.value = d.card_last_digits;
                        }
                        if (opts.cardHolderId && d.card_holder_name) {
                            const el = document.getElementById(opts.cardHolderId);
                            if (el) el.value = d.card_holder_name;
                        }
                        if (amountEl && typeof d.amount !== 'undefined') {
                            amountEl.value = d.amount;
                        }
                        if (statusEl) {
                            statusEl.textContent = 'تم التحصيل: ' + (d.transaction_id || d.approval_code || 'نجاح');
                            statusEl.className = 'text-success ms-2';
                        }
                        if (typeof opts.onSuccess === 'function') {
                            opts.onSuccess(d);
                        }
                    } else {
                        const msg = d.message || 'لم تتم عملية البطاقة';
                        if (statusEl) {
                            statusEl.textContent = msg;
                            statusEl.className = 'text-danger ms-2';
                        }
                        if (global.showApiError) {
                            global.showApiError('فشل التحصيل', msg);
                        }
                    }
                })
                .catch(function () {
                    const msg = 'تعذّر الاتصال بجهاز البطاقة. تأكد أن الجهاز يعمل وحاول مرة أخرى.';
                    if (statusEl) {
                        statusEl.textContent = msg;
                        statusEl.className = 'text-danger ms-2';
                    }
                    if (global.showApiError) {
                        global.showApiError('خطأ', msg);
                    }
                })
                .finally(function () {
                    btn.disabled = false;
                });
        });
    }

    global.initPosCharge = initPosCharge;
})(window);
