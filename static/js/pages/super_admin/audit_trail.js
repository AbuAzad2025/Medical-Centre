var __M = window.__M || [];

function dateStamp() {
    return new Date().toISOString().split('T')[0];
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function csvCell(value) {
    const s = String(value == null ? '' : value);
    // Spreadsheet formula-injection guard: leading = + - @ or tab would be
    // interpreted as a formula by Excel/LibreOffice.
    const guarded = /^[=+\-@\t]/.test(s) ? "'" + s : s;
    return '"' + guarded.replace(/"/g, '""') + '"';
}

export function refreshAuditLogs() {
    location.reload();
}

export function exportAuditLogs(format) {
    format = (format || 'csv').toLowerCase();
    const logs = Array.isArray(window.__M0__) ? window.__M0__ : [];

    if (format === 'json') {
        const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
        downloadBlob(blob, 'audit_logs_' + dateStamp() + '.json');
        return 'json';
    }

    // 'csv' and 'excel' both produce a UTF-8 (BOM) CSV, which Excel opens
    // natively; there is no server-side spreadsheet renderer, so this is the
    // honest Excel-compatible export.
    const headers = ['Timestamp', 'User', 'Action', 'Target Model', 'Target ID', 'IP Address', 'Details', 'Request ID'];
    const lines = [headers];
    logs.forEach(function (log) {
        lines.push([
            log.timestamp || '',
            (log.actor && log.actor.full_name) || 'غير محدد',
            log.action || '',
            log.target_model || '',
            log.target_id == null ? '' : log.target_id,
            log.ip_address || '',
            log.description || (log.changes ? JSON.stringify(log.changes) : ''),
            log.request_id || '',
        ]);
    });
    const csv = lines.map(function (row) { return row.map(csvCell).join(','); }).join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    downloadBlob(blob, 'audit_logs_' + dateStamp() + '.csv');
    return 'csv';
}

export function exportAllLogs() {
    return exportAuditLogs('csv');
}

function openModal(modalId, contentId, text) {
    const el = document.getElementById(contentId);
    if (el) el.textContent = text;
    if (window.bootstrap && window.bootstrap.Modal) {
        const modalEl = document.getElementById(modalId);
        if (modalEl) new window.bootstrap.Modal(modalEl).show();
    }
}

export function showChangesModal(changes) {
    const text = typeof changes === 'string' ? changes : JSON.stringify(changes, null, 2);
    openModal('changesModal', 'changes-content', text);
}

export function showLogDetails(log) {
    openModal('detailsModal', 'details-content', JSON.stringify(log, null, 2));
}

// Backward compatibility: only the functions the page actually uses.
if (typeof refreshAuditLogs !== "undefined") window.refreshAuditLogs = refreshAuditLogs;
if (typeof exportAuditLogs !== "undefined") window.exportAuditLogs = exportAuditLogs;
if (typeof exportAllLogs !== "undefined") window.exportAllLogs = exportAllLogs;
if (typeof showChangesModal !== "undefined") window.showChangesModal = showChangesModal;
if (typeof showLogDetails !== "undefined") window.showLogDetails = showLogDetails;

export {};
