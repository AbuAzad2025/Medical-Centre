var __M = window.__M || [];

function csvCell(value) {
    const s = String(value == null ? '' : value);
    // Spreadsheet formula-injection guard
    const guarded = /^[=+\-@\t]/.test(s) ? "'" + s : s;
    return '"' + guarded.replace(/"/g, '""') + '"';
}

export function exportUsers() {
    const rows = document.querySelectorAll('#usersTable tbody tr');
    const lines = [['الاسم', 'اسم المستخدم', 'البريد الإلكتروني', 'الدور', 'القسم', 'الحالة', 'آخر دخول']];
    rows.forEach(function (row) {
        const cells = row.querySelectorAll('td');
        if (cells.length < 7) return;
        const vals = [];
        for (let i = 0; i < 7; i++) {
            vals.push(csvCell((cells[i].textContent || '').trim()));
        }
        lines.push(vals);
    });
    const csv = lines.map(function (row) { return row.join(','); }).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'users_' + new Date().toISOString().split('T')[0] + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

export function filterUsers(filter, e) {
    const rows = document.querySelectorAll('#usersTable tbody tr');

    rows.forEach(row => {
        if (filter === 'all') {
            row.style.display = '';
        } else if (filter === 'active') {
            row.style.display = row.dataset.status === 'active' ? '' : 'none';
        } else if (filter === 'inactive') {
            row.style.display = row.dataset.status === 'inactive' ? '' : 'none';
        } else if (filter === 'admin') {
            row.style.display = row.dataset.admin === 'admin' ? '' : 'none';
        }
    });

    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-info').forEach(btn => {
        btn.classList.remove('active');
    });

    if (e) e.target.classList.add('active');
}

export function viewUser(userId) {
    // Show the real, already-rendered row data for this user — no server round-trip, no invented fields.
    // Only allow simple ids into the selector (numbers and word chars).
    const safeId = String(userId == null ? '' : userId).replace(/[^\w-]/g, '');
    const row = safeId ? document.querySelector('#usersTable tbody tr[data-user-id="' + safeId + '"]') : null;
    if (!row) {
        Swal.fire({ title: 'تفاصيل المستخدم', text: 'لم يتم العثور على المستخدم', icon: 'info' });
        return;
    }
    const cells = row.querySelectorAll('td');
    const cellText = (i) => (cells[i] ? cells[i].textContent.trim() : '');
    Swal.fire({
        title: cellText(0).replace(/\s+/g, ' ') || 'تفاصيل المستخدم',
        html:
            '<div class="text-start">'
            + '<p class="mb-1"><strong>اسم المستخدم:</strong> ' + escapeHtml(cellText(1)) + '</p>'
            + '<p class="mb-1"><strong>البريد:</strong> ' + escapeHtml(cellText(2)) + '</p>'
            + '<p class="mb-1"><strong>الدور:</strong> ' + escapeHtml(cellText(3)) + '</p>'
            + '<p class="mb-1"><strong>القسم:</strong> ' + escapeHtml(cellText(4)) + '</p>'
            + '<p class="mb-1"><strong>الحالة:</strong> ' + escapeHtml(cellText(5)) + '</p>'
            + '<p class="mb-0"><strong>آخر دخول:</strong> ' + escapeHtml(cellText(6)) + '</p>'
            + '</div>',
        icon: 'info',
    });
}

function escapeHtml(v) {
    return String(v == null ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

document.addEventListener('DOMContentLoaded', function() {
    const rows = document.querySelectorAll('#usersTable tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
});

// Backward compatibility
if (typeof filterUsers !== "undefined") window.filterUsers = filterUsers;
if (typeof exportUsers !== "undefined") window.exportUsers = exportUsers;
if (typeof viewUser !== "undefined") window.viewUser = viewUser;

export {};
