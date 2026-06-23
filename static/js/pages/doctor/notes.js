var __M = window.__M || [];
const noteTextEl = document.getElementById('medical_notes');
const tplSelectEl = document.getElementById('note_template_select');
const applyTplBtn = document.getElementById('apply_note_template_btn');
const templatesModalEl = document.getElementById('doctorNoteTemplatesModal');
const dntForm = document.getElementById('doctorNoteTemplateForm');
const dntTableBody = document.getElementById('dnt_table_body');
const dntRefreshBtn = document.getElementById('dnt_refresh_btn');
const dntResetBtn = document.getElementById('dnt_reset_btn');
const dntIdEl = document.getElementById('dnt_id');
const dntNameEl = document.getElementById('dnt_name');
const dntTextEl = document.getElementById('dnt_text');
const dntActiveEl = document.getElementById('dnt_active');
const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
let templatesCache = [];

function autoResize() {
    if (!noteTextEl) return;
    noteTextEl.style.height = 'auto';
    noteTextEl.style.height = noteTextEl.scrollHeight + 'px';
}

async function fetchTemplates() {
    try {
        const r = await fetch(__M0__, { method: 'GET' });
        const data = await r.json().catch(() => ({}));
        const arr = data && data.templates ? data.templates : [];
        templatesCache = Array.isArray(arr) ? arr : [];
        return templatesCache;
    } catch (err) {
        console.error('خطأ في الاتصال:', err);
    }
}

function fillTemplateSelect(templates) {
    if (!tplSelectEl) return;
    const selected = tplSelectEl.value || '';
    tplSelectEl.innerHTML = '<option value="">اختر</option>';
    const active = templates.filter(t => t && t.is_active !== false);
    active.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name || '';
        tplSelectEl.appendChild(opt);
    });
    if (selected) tplSelectEl.value = selected;
}

function resetTemplateForm() {
    dntIdEl.value = '';
    dntNameEl.value = '';
    dntTextEl.value = '';
    dntActiveEl.checked = true;
}

function renderTemplatesTable() {
    if (!dntTableBody) return;
    dntTableBody.innerHTML = '';
    templatesCache.forEach(t => {
        if (!t || !t.id) return;
        const active = t.is_active !== false;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${String(t.name || '')}</td>
            <td>${active ? '<span class="badge bg-success">نعم</span>' : '<span class="badge bg-secondary">لا</span>'}</td>
            <td class="text-end">
                <button type="button" class="btn btn-sm btn-outline-primary me-1" data-action="edit" data-id="${t.id}">تعديل</button>
                <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${t.id}">حذف</button>
            </td>
        `;
        dntTableBody.appendChild(tr);
    });
}

async function refreshTemplatesUI() {
    await fetchTemplates();
    fillTemplateSelect(templatesCache);
    renderTemplatesTable();
}

if (noteTextEl) {
    noteTextEl.addEventListener('input', function() { autoResize(); });
}

let autoSaveTimeout;
if (noteTextEl) {
    noteTextEl.addEventListener('input', function() {
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(function() {
            localStorage.setItem('medical_notes_draft', noteTextEl.value);
        }, 1000);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const draft = localStorage.getItem('medical_notes_draft');
    if (draft && noteTextEl) {
        noteTextEl.value = draft;
        autoResize();
    }
    refreshTemplatesUI();
});

document.querySelector('form').addEventListener('submit', function() {
    localStorage.removeItem('medical_notes_draft');
});

if (applyTplBtn) {
    applyTplBtn.addEventListener('click', function() {
        const id = tplSelectEl ? tplSelectEl.value : '';
        if (!id || !noteTextEl) return;
        const t = templatesCache.find(x => x && x.id === id);
        if (!t) return;
        const current = noteTextEl.value ? String(noteTextEl.value) : '';
        const insert = String(t.text || '');
        noteTextEl.value = current ? (current + "\n" + insert) : insert;
        autoResize();
    });
}

if (templatesModalEl) {
    templatesModalEl.addEventListener('show.bs.modal', function () {
        resetTemplateForm();
        refreshTemplatesUI();
    });
}
if (dntRefreshBtn) {
    dntRefreshBtn.addEventListener('click', function () {
        refreshTemplatesUI();
    });
}
if (dntResetBtn) {
    dntResetBtn.addEventListener('click', function () {
        resetTemplateForm();
    });
}
if (dntForm) {
    dntForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const payload = {
            id: dntIdEl.value || undefined,
            name: dntNameEl.value || '',
            text: dntTextEl.value || '',
            is_active: dntActiveEl.checked
        };
        try {
            const r = await fetch(__M1__, {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                body: JSON.stringify(payload)
            });
            if (!r.ok) {
                window.notify.error('فشل الحفظ');
                return;
            }
            resetTemplateForm();
            await refreshTemplatesUI();
        } catch (err) {
            console.error('خطأ في الاتصال:', err);
        }
    });
}
if (dntTableBody) {
    dntTableBody.addEventListener('click', async function (e) {
        const btn = e.target && e.target.closest ? e.target.closest('button[data-action]') : null;
        if (!btn) return;
        const action = btn.getAttribute('data-action');
        const id = btn.getAttribute('data-id');
        const t = templatesCache.find(x => x && x.id === id);
        if (!t) return;
        if (action === 'edit') {
            dntIdEl.value = t.id;
            dntNameEl.value = t.name || '';
            dntTextEl.value = t.text || '';
            dntActiveEl.checked = t.is_active !== false;
        } else if (action === 'delete') {
            const ok = window.confirm('حذف القالب؟');
            if (!ok) return;
            try {
                const r = await fetch(`__M2__`.replace('__T__', encodeURIComponent(id)), {
                    method: 'POST',
                    headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {}
                });
                if (!r.ok) {
                    window.notify.error('فشل الحذف');
                    return;
                }
                await refreshTemplatesUI();
            } catch (err) {
                console.error('خطأ في الاتصال:', err);
            }
        }
    });
}
