var __M = window.__M || [];
const dashboardLayoutUrl = __M0__;
const csrfToken = __M1__;
const panelContainer = document.getElementById('doctorPanels');
const settingsList = document.getElementById('dashboardSettingsList');
const saveSettingsBtn = document.getElementById('saveDashboardSettings');

function applyLayout(items) {
    const map = {};
    (items || []).forEach(it => map[it.id] = it);
    const panels = panelContainer.querySelectorAll('.dashboard-panel');
    panels.forEach(panel => {
        const id = panel.getAttribute('data-panel');
        const cfg = map[id];
        if (!cfg) return;
        panel.style.order = cfg.order || 0;
        panel.style.display = cfg.enabled ? '' : 'none';
    });
}

function renderSettings(items) {
    settingsList.innerHTML = '';
    (items || []).sort((a,b) => (a.order || 0) - (b.order || 0)).forEach(item => {
        const row = document.createElement('div');
        row.className = 'd-flex align-items-center justify-content-between border rounded p-2 mb-2';
        row.innerHTML = `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" id="panel_${item.id}" ${item.enabled ? 'checked' : ''}>
                <label class="form-check-label" for="panel_${item.id}">${item.title || item.id}</label>
            </div>
            <input type="number" class="form-control form-control-sm" style="width: 80px;" value="${item.order || 0}" data-panel="${item.id}">
        `;
        settingsList.appendChild(row);
    });
}

async function loadLayout() {
    try {
        const r = await fetch(dashboardLayoutUrl);
        const data = await r.json().catch(() => ({}));
        if (!data || !data.items) return;
        applyLayout(data.items);
        renderSettings(data.items);
    } catch (err) {
        if (window.notify && window.notify.warning) {
            window.notify.warning('تعذّر تحميل إعدادات اللوحة. حاول تحديث الصفحة.');
        }
    }
}

async function saveLayout() {
    const items = [];
    settingsList.querySelectorAll('input[type="number"]').forEach(input => {
        const id = input.getAttribute('data-panel');
        const checkbox = document.getElementById(`panel_${id}`);
        items.push({
            id,
            order: parseInt(input.value || '0', 10),
            enabled: checkbox ? checkbox.checked : true
        });
    });
    try {
        const r = await fetch(dashboardLayoutUrl, {
            method: 'POST',
            headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            body: JSON.stringify({ items })
        });
        const data = await r.json().catch(() => ({}));
        if (data && data.items) {
            applyLayout(data.items);
            renderSettings(data.items);
        }
    } catch (err) {
        if (window.notify && window.notify.error) {
            window.notify.error('تعذّر حفظ إعدادات اللوحة. حاول مرة أخرى.');
        }
    }
}

if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', saveLayout);
}

document.addEventListener('DOMContentLoaded', function() {
    loadLayout();
});

document.addEventListener('keydown', function(e) {
    if (e.target && ['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
    if (e.altKey && e.key.toLowerCase() === 'q') {
        window.location.href = __M2__;
    }
    if (e.altKey && e.key.toLowerCase() === 'p') {
        window.location.href = __M3__;
    }
    if (e.altKey && e.key.toLowerCase() === 'r') {
        window.location.href = __M4__;
    }
    if (e.altKey && e.key.toLowerCase() === 'a') {
        window.location.href = __M5__;
    }
});
