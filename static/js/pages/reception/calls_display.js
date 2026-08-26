var __M = window.__M || [];
const apiUrl = __M0__;
        const grid = document.getElementById('calls-grid');
        const clockEl = document.getElementById('live-clock');
        const queueSocket = io('/queue');

        function render(items) {
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
                        <div class="queue-number text-warning">${it.queue_number || '-'}</div>
                        <div class="fs-5">${window.escHtml(it.department_name || '')}</div>
                        <div class="text-muted">${window.escHtml(it.doctor_name || '')}</div>
                        <div class="text-muted">${it.room_name ? 'غرفة ' + window.escHtml(it.room_name) : ''}</div>
                        <div class="text-muted">${window.escHtml(it.status || '')}</div>
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
