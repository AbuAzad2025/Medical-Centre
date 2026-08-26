var __M = window.__M || [];
const apiUrl = __M0__;
        const clockEl = document.getElementById('live-clock');
        const queueSocket = io('/queue');

        function renderList(el, items, emptyText) {
            el.innerHTML = '';
            if (!items || items.length === 0) {
                const div = document.createElement('div');
                div.className = 'text-muted';
                div.textContent = emptyText;
                el.appendChild(div);
                return;
            }
            items.forEach(it => {
                const card = document.createElement('div');
                card.className = 'p-3 rounded bg-dark-subtle text-dark queue-card-enter';
                if (window.__MOTION_ENABLED__ && !window.__MOTION_ENABLED__()) {
                    card.classList.remove('queue-card-enter');
                }
                card.innerHTML = `
                    <div class="queue-number">${it.queue_number || '-'}</div>
                    <div class="ticker">${window.escHtml(it.department_name || '')}</div>
                    <div class="text-muted">${window.escHtml(it.doctor_name || '')}</div>
                    <div class="text-muted">${it.room_name ? 'غرفة ' + window.escHtml(it.room_name) : ''}</div>
                `;
                el.appendChild(card);
            });
        }

        function markStale() {
            ['current-list', 'called-list', 'waiting-list'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.setAttribute('data-stale', '');
            });
        }

        function refresh() {
            fetch(apiUrl, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
                .then(r => {
                    if (!r.ok) throw new Error(r.status);
                    return r.json();
                })
                .then(data => {
                    if (!data || !data.success) return;
                    ['current-list', 'called-list', 'waiting-list'].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.removeAttribute('data-stale');
                    });
                    renderList(document.getElementById('current-list'), data.current, 'لا يوجد');
                    renderList(document.getElementById('called-list'), data.called, 'لا يوجد');
                    renderList(document.getElementById('waiting-list'), data.waiting, 'لا يوجد');
                })
                .catch(() => {
                    markStale();
                });
        }

        function tickClock() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            clockEl.textContent = `${h}:${m}`;
        }

        tickClock();
        setInterval(tickClock, 60000);
        refresh();
        setInterval(refresh, 8000);

        queueSocket.on('queue_display_waiting', function(data) {
            if (!data) return;
            renderList(document.getElementById('current-list'), data.current, 'لا يوجد');
            renderList(document.getElementById('called-list'), data.called, 'لا يوجد');
            renderList(document.getElementById('waiting-list'), data.waiting, 'لا يوجد');
        });
