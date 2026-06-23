/**
 * Pharmacy POS page logic (§35.4).
 */
(function () {
    const cfg = window.__PHARMACY_POS__ || {};
    let cart = [];
    let posChargeData = null;

    function cartTotal() {
        return cart.reduce(function (sum, item) {
            return sum + item.price * item.qty;
        }, 0);
    }

    function selectedPaymentMethod() {
        const checked = document.querySelector('input[name="paymentMethod"]:checked');
        return checked ? checked.value : 'cash';
    }

    function updateCheckoutLabel() {
        const label = document.getElementById('checkoutBtnLabel');
        if (!label) return;
        const method = selectedPaymentMethod();
        label.textContent = method === 'card' ? 'إتمام البيع (بطاقة)' : 'إتمام البيع (نقداً)';
    }

    function toggleCardBlock() {
        const block = document.getElementById('cardChargeBlock');
        if (!block) return;
        const isCard = selectedPaymentMethod() === 'card';
        block.classList.toggle('d-none', !isCard);
        if (!isCard) {
            posChargeData = null;
            const txn = document.getElementById('pharmacyTransactionId');
            const digits = document.getElementById('pharmacyCardLastDigits');
            if (txn) txn.value = '';
            if (digits) digits.value = '';
        }
        updateCheckoutLabel();
    }

    function renderCart() {
        const container = document.getElementById('cartItems');
        const totalEl = document.getElementById('cartTotal');
        const checkoutBtn = document.getElementById('checkoutBtn');
        if (cart.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5" id="emptyCart">السلة فارغة</div>';
            totalEl.textContent = '0.00 ₪';
            checkoutBtn.disabled = true;
            return;
        }
        let html = '<table class="table table-sm mb-0"><thead><tr><th>الاسم</th><th>السعر</th><th>الكمية</th><th>المجموع</th><th></th></tr></thead><tbody>';
        let total = 0;
        cart.forEach(function (item, idx) {
            const subtotal = item.price * item.qty;
            total += subtotal;
            html += '<tr>' +
                '<td>' + item.name + '</td>' +
                '<td>' + item.price.toFixed(2) + '</td>' +
                '<td><input type="number" class="form-control form-control-sm qty-input" style="width:70px" value="' + item.qty + '" min="1" max="' + item.stock + '" data-index="' + idx + '"></td>' +
                '<td>' + subtotal.toFixed(2) + '</td>' +
                '<td><button class="btn btn-sm btn-outline-danger remove-item" data-index="' + idx + '"><i class="fas fa-times"></i></button></td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
        totalEl.textContent = total.toFixed(2) + ' ₪';
        checkoutBtn.disabled = false;
    }

    function addToCart(id, name, price, stock) {
        const existing = cart.findIndex(function (c) { return String(c.id) === String(id); });
        if (existing >= 0) {
            cart[existing].qty += 1;
        } else {
            cart.push({ id: id, name: name, price: parseFloat(price), qty: 1, stock: parseInt(stock, 10) });
        }
        renderCart();
    }

    document.addEventListener('click', function (e) {
        if (e.target.closest('.quick-add')) {
            const btn = e.target.closest('.quick-add');
            addToCart(btn.dataset.id, btn.dataset.name, btn.dataset.price, btn.dataset.stock);
        }
        if (e.target.closest('.remove-item')) {
            const idx = parseInt(e.target.closest('.remove-item').dataset.index, 10);
            cart.splice(idx, 1);
            renderCart();
        }
    });

    document.addEventListener('change', function (e) {
        if (e.target.classList.contains('qty-input')) {
            const idx = parseInt(e.target.dataset.index, 10);
            const val = parseInt(e.target.value, 10) || 1;
            cart[idx].qty = Math.max(1, Math.min(val, cart[idx].stock));
            renderCart();
        }
        if (e.target.name === 'paymentMethod') {
            toggleCardBlock();
        }
    });

    document.getElementById('clearCart').addEventListener('click', function () {
        cart = [];
        renderCart();
    });

    if (cfg.posEnabled && typeof initPosCharge === 'function') {
        initPosCharge({
            button: 'pharmacyPosChargeBtn',
            statusElement: 'pharmacyPosStatus',
            chargeUrl: cfg.chargeUrl,
            getAmount: cartTotal,
            onSuccess: function (d) {
                posChargeData = d;
                const txn = document.getElementById('pharmacyTransactionId');
                const digits = document.getElementById('pharmacyCardLastDigits');
                if (txn) txn.value = d.transaction_id || d.approval_code || '';
                if (digits && d.card_last_digits) digits.value = d.card_last_digits;
            },
        });
    }

    document.getElementById('checkoutBtn').addEventListener('click', function () {
        if (cart.length === 0) return;
        const btn = this;
        const method = selectedPaymentMethod();
        if (method === 'card' && cfg.posEnabled) {
            const txn = document.getElementById('pharmacyTransactionId');
            if (!txn || !txn.value) {
                showApiWarning('تنبيه', 'يرجى تحصيل المبلغ عبر جهاز البطاقة أولاً');
                return;
            }
        }
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin ms-1"></i>جاري المعالجة...';
        const payload = {
            items: cart.map(function (c) {
                return { medication_id: c.id, quantity: c.qty, unit_price: c.price };
            }),
            customer_name: document.getElementById('customerName').value,
            payment_method: method,
        };
        if (method === 'card' && posChargeData) {
            payload.transaction_id = posChargeData.transaction_id || posChargeData.approval_code;
            payload.card_last_digits = posChargeData.card_last_digits;
        }
        fetch(cfg.sellUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    window.location.href = cfg.receiptUrl.replace('0', String(data.sale_id));
                } else {
                    showApiError('تعذّر البيع', data.message || 'تعذّر إتمام البيع');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-check ms-1"></i><span id="checkoutBtnLabel">' +
                        (method === 'card' ? 'إتمام البيع (بطاقة)' : 'إتمام البيع (نقداً)') + '</span>';
                }
            })
            .catch(function () {
                showApiError('خطأ', 'تعذّر الاتصال بالخادم. حاول مرة أخرى.');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-check ms-1"></i><span id="checkoutBtnLabel">' +
                    (method === 'card' ? 'إتمام البيع (بطاقة)' : 'إتمام البيع (نقداً)') + '</span>';
            });
    });

    let searchTimeout;
    document.getElementById('medSearch').addEventListener('input', function () {
        clearTimeout(searchTimeout);
        const q = this.value.trim();
        if (q.length < 1) {
            document.getElementById('medResults').innerHTML = '';
            document.getElementById('noResults').classList.add('d-none');
            return;
        }
        searchTimeout = setTimeout(function () {
            fetch(cfg.searchUrl + '?q=' + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    const tbody = document.getElementById('medResults');
                    const noRes = document.getElementById('noResults');
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        noRes.classList.remove('d-none');
                        return;
                    }
                    noRes.classList.add('d-none');
                    data.forEach(function (m) {
                        tbody.innerHTML += '<tr>' +
                            '<td>' + m.trade_name + '</td>' +
                            '<td>' + (m.price || 0).toFixed(2) + ' ₪</td>' +
                            '<td>' + (m.stock || 0) + '</td>' +
                            '<td><button class="btn btn-sm btn-success quick-add" data-id="' + m.id + '" data-name="' + m.trade_name + '" data-price="' + (m.price || 0) + '" data-stock="' + (m.stock || 0) + '"><i class="fas fa-plus"></i></button></td>' +
                            '</tr>';
                    });
                });
        }, 300);
    });

    toggleCardBlock();
})();
