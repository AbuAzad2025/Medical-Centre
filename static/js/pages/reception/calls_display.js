var __M = window.__M || [];
const apiUrl = window.__M0__;

// Standalone template: base.js is not loaded on this page, so EscHtml does not
// exist yet. Use it when present, otherwise a local equivalent — never trust
// server data raw into innerHTML.
const escHtml = window.escHtml || function (v) {
    return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};
        const grid = document.getElementById('calls-grid');
        const clockEl = document.getElementById('live-clock');
        // Socket.io may be blocked/unavailable (kiosk offline); degrade to polling.
        const queueSocket = (typeof io === 'function') ? io('/queue') : { on: function () {} };

        function render(items) {
            if (!grid) return;
            grid.innerHTML = '';
            if (!items || items.length === 0) {
                const div = document.createElement('div');
                div.className = 'text-center text-muted';
                div.textContent = 'لا يوجد نداءات حالياً';
                grid.appendChild(div);
                return;
            }
            items.forEach(it => {
                const col = document.createElement('div');
                col.className = 'col-12 col-md-6 col-lg-4';
                col.innerHTML = `
                    <div class="call-card p-4 rounded">
                        <div class="queue-number text-warning">${escHtml(it.queue_number == null ? '-' : it.queue_number)}</div>
                        <div class="fs-5">${escHtml(it.department_name || '')}</div>
                        <div class="text-muted">${escHtml(it.doctor_name || '')}</div>
                        <div class="text-muted">${it.room_name ? 'غرفة ' + escHtml(it.room_name) : ''}</div>
                        <div class="text-muted">${escHtml(it.status || '')}</div>
                    </div>
                `;
                grid.appendChild(col);
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
                    grid.removeAttribute('data-stale');
                    render(data.items || []);
                })
                .catch(() => {
                    grid.setAttribute('data-stale', '');
                });
        }

        function tickClock() {
            if (!clockEl) return;
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            clockEl.textContent = `${h}:${m}`;
        }

        tickClock();
        setInterval(tickClock, 60000);
        refresh();
        setInterval(refresh, 6000);

        queueSocket.on('queue_display_calls', function(data) {
            if (!data) return;
            render(data.items || []);
        });

export {};
