var __M = window.__M || [];

function aiMessagesEl() {
    return document.getElementById('aiMessages');
}

function appendBubble(text, role) {
    const container = aiMessagesEl();
    if (!container) return;
    const bubble = document.createElement('div');
    bubble.className = 'ai-message ' + role;
    const content = document.createElement('div');
    content.className = 'message-content';
    if (role === 'assistant') {
        const strong = document.createElement('strong');
        strong.textContent = 'المساعد الذكي';
        const p = document.createElement('p');
        p.textContent = text;
        content.appendChild(strong);
        content.appendChild(p);
    } else {
        const p = document.createElement('p');
        p.textContent = text;
        content.appendChild(p);
    }
    bubble.appendChild(content);
    container.appendChild(bubble);
    bubble.scrollIntoView({ block: 'nearest' });
}

function csrfToken() {
    return (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
}

export function askAiAssistant(message) {
    const trimmed = (message || '').trim();
    if (!trimmed) return;
    appendBubble(trimmed, 'user');
    const endpoint = (window.API_ROUTES && window.API_ROUTES.ai_assistant) || '/super-admin/api/ai-assistant';
    fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ message: trimmed }),
    })
    .then(r => r.json().then(d => ({ ok: r.ok, d })))
    .then(({ ok, d }) => {
        if (ok && d && d.success && d.response) {
            appendBubble(d.response, 'assistant');
        } else {
            appendBubble((d && d.response) || 'تعذر معالجة طلبك حالياً', 'assistant');
        }
    })
    .catch(() => appendBubble('تعذر معالجة طلبك حالياً، يرجى المحاولة مرة أخرى', 'assistant'));
}

const QUICK_COMMAND_PROMPTS = {
    analyze: 'حلل أداء النظام',
    report: 'أنشئ تقرير ملخص',
    optimize: 'اقتراحات تحسين النظام',
    backup: 'أخبرني عن النسخ الاحتياطية',
};

export function exportSystemData() {
    const doExport = () => {
        Swal.fire({
            title: 'جارٍ التصدير...',
            allowOutsideClick: false,
            didOpen: function () { Swal.showLoading(); },
        });
        const endpoint = (window.API_ROUTES && window.API_ROUTES.export_system_data) || '/super-admin/export-data';
        fetch(endpoint, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
        })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (ok && d && d.success && d.download_url) {
                const a = document.createElement('a');
                a.href = d.download_url;
                a.setAttribute('download', '');
                document.body.appendChild(a);
                a.click();
                a.remove();
                Swal.fire({ title: 'تم', text: d.message || 'تم تصدير البيانات', icon: 'success' });
            } else {
                Swal.fire({ title: 'خطأ', text: (d && d.message) || 'تعذر تصدير البيانات', icon: 'error' });
            }
        })
        .catch(() => Swal.fire({ title: 'خطأ', text: 'فشل الاتصال بالخادم', icon: 'error' }));
    };

    Swal.fire({
        title: 'تأكيد التصدير',
        text: 'سيتم تصدير نسخة كاملة من بيانات النظام (المستخدمين، المرضى، الزيارات) في ملف JSON. الملف يحتوي على بيانات حساسة، تأكد من حفظه في مكان آمن. هل تريد المتابعة؟',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'نعم، صدّر',
        cancelButtonText: 'إلغاء',
    }).then(function (result) {
        if (result.isConfirmed) doExport();
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('aiInput');
    const sendBtn = document.getElementById('sendBtn');
    if (input && sendBtn) {
        sendBtn.addEventListener('click', function () {
            askAiAssistant(input.value);
            input.value = '';
            input.focus();
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                askAiAssistant(input.value);
                input.value = '';
            }
        });
    }
    document.querySelectorAll('.quick-command').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const prompt = QUICK_COMMAND_PROMPTS[btn.dataset.command];
            if (prompt) askAiAssistant(prompt);
        });
    });
});

// Backward compatibility
if (typeof askAiAssistant !== "undefined") window.askAiAssistant = askAiAssistant;
if (typeof exportSystemData !== "undefined") window.exportSystemData = exportSystemData;

export {};
