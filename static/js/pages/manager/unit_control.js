function refreshUnits() {
    location.reload();
}

function exportUnitsReport() {
    var rows = document.querySelectorAll('#unitsTable tbody tr');
    var csv = "\u0627\u0633\u0645 \u0627\u0644\u0648\u062d\u062f\u0629,\u0627\u0644\u0646\u0648\u0639,\u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645\u064a\u0646,\u0627\u0644\u062d\u0627\u0644\u0629\n";
    rows.forEach(function(r) {
        var cells = r.querySelectorAll('td');
        if (cells.length < 4) return;
        var name = cells[0] ? cells[0].textContent.trim() : '';
        var type = cells[1] ? cells[1].textContent.trim() : '';
        var users = cells[2] ? cells[2].textContent.trim() : '';
        var status = cells[3] ? cells[3].textContent.trim() : '';
        csv += '"' + name + '","' + type + '","' + users + '","' + status + '"\n';
    });
    var blob = new Blob(["\ufeff" + csv], { type: 'text/csv;charset=utf-8;' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'units_report_' + new Date().toISOString().split('T')[0] + '.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
}

function toggleUnit(moduleName, btn) {
    var arName = btn ? btn.getAttribute('data-name-ar') || moduleName : moduleName;
    Swal.fire({
        title: '\u062a\u0623\u0643\u064a\u062f',
        text: '\u0647\u0644 \u062a\u0631\u064a\u062f \u062a\u063a\u064a\u064a\u0631 \u062d\u0627\u0644\u0629 \u0648\u062d\u062f\u0629 ' + arName + '\u061f',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '\u0646\u0639\u0645',
        cancelButtonText: '\u0625\u0644\u063a\u0627\u0621'
    }).then(function(r) {
        if (!r.isConfirmed) return;
        var formData = new FormData();
        formData.append('module_name', moduleName);
        fetch('/manager/api/units/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
            body: JSON.stringify({ module_name: moduleName })
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            if (data.success) {
                Swal.fire({ title: '\u062a\u0645', text: data.message, icon: 'success', timer: 1500, showConfirmButton: false })
                    .then(function() { location.reload(); });
            } else {
                Swal.fire({ title: '\u062e\u0637\u0623', text: data.message || '\u062d\u062f\u062b \u062e\u0637\u0623', icon: 'error' });
            }
        })
        .catch(function() {
            Swal.fire({ title: '\u062e\u0637\u0623', text: '\u062d\u062f\u062b \u062e\u0637\u0623 \u0641\u064a \u0627\u0644\u0627\u062a\u0635\u0627\u0644', icon: 'error' });
        });
    });
}

function bulkActivate() {
    Swal.fire({
        title: '\u062a\u0623\u0643\u064a\u062f',
        text: '\u0647\u0644 \u062a\u0631\u064a\u062f \u062a\u0641\u0639\u064a\u0644 \u062c\u0645\u064a\u0639 \u0627\u0644\u0648\u062d\u062f\u0627\u062a\u061f',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '\u0646\u0639\u0645',
        cancelButtonText: '\u0625\u0644\u063a\u0627\u0621'
    }).then(function(r) {
        if (!r.isConfirmed) return;
        var cards = document.querySelectorAll('#unitsTable tbody tr');
        var promises = [];
        cards.forEach(function(row) {
            var toggleBtn = row.querySelector('[data-action="toggleUnit"]');
            if (!toggleBtn) return;
            var mod = toggleBtn.getAttribute('data-module');
            if (!mod) return;
            var statusCell = row.querySelector('td:nth-child(4) .badge');
            if (statusCell && statusCell.textContent.trim() === '\u0646\u0634\u0637') return;
            promises.push(
                fetch('/manager/api/units/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    body: JSON.stringify({ module_name: mod })
                }).then(function(res) { return res.json(); })
            );
        });
        Promise.all(promises).then(function() {
            Swal.fire({ title: '\u062a\u0645', text: '\u062a\u0645 \u062a\u0641\u0639\u064a\u0644 \u062c\u0645\u064a\u0639 \u0627\u0644\u0648\u062d\u062f\u0627\u062a', icon: 'success', timer: 1500, showConfirmButton: false })
                .then(function() { location.reload(); });
        }).catch(function() {
            Swal.fire({ title: '\u062e\u0637\u0623', text: '\u062d\u062f\u062b \u062e\u0637\u0623', icon: 'error' });
        });
    });
}

function bulkDeactivate() {
    Swal.fire({
        title: '\u062a\u0623\u0643\u064a\u062f',
        text: '\u0647\u0644 \u062a\u0631\u064a\u062f \u062a\u0639\u0637\u064a\u0644 \u062c\u0645\u064a\u0639 \u0627\u0644\u0648\u062d\u062f\u0627\u062a\u061f',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '\u0646\u0639\u0645',
        cancelButtonText: '\u0625\u0644\u063a\u0627\u0621'
    }).then(function(r) {
        if (!r.isConfirmed) return;
        var cards = document.querySelectorAll('#unitsTable tbody tr');
        var promises = [];
        cards.forEach(function(row) {
            var toggleBtn = row.querySelector('[data-action="toggleUnit"]');
            if (!toggleBtn) return;
            var mod = toggleBtn.getAttribute('data-module');
            if (!mod) return;
            var statusCell = row.querySelector('td:nth-child(4) .badge');
            if (statusCell && statusCell.textContent.trim() === '\u0645\u0639\u0637\u0644') return;
            promises.push(
                fetch('/manager/api/units/toggle', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
                    body: JSON.stringify({ module_name: mod })
                }).then(function(res) { return res.json(); })
            );
        });
        Promise.all(promises).then(function() {
            Swal.fire({ title: '\u062a\u0645', text: '\u062a\u0645 \u062a\u0639\u0637\u064a\u0644 \u062c\u0645\u064a\u0639 \u0627\u0644\u0648\u062d\u062f\u0627\u062a', icon: 'success', timer: 1500, showConfirmButton: false })
                .then(function() { location.reload(); });
        }).catch(function() {
            Swal.fire({ title: '\u062e\u0637\u0623', text: '\u062d\u062f\u062b \u062e\u0637\u0623', icon: 'error' });
        });
    });
}

function bulkRestart() {
    Swal.fire({
        title: '\u062a\u0623\u0643\u064a\u062f',
        text: '\u0647\u0644 \u062a\u0631\u064a\u062f \u0625\u0639\u0627\u062f\u0629 \u062a\u0634\u063a\u064a\u0644 \u062c\u0645\u064a\u0639 \u0627\u0644\u0648\u062d\u062f\u0627\u062a\u061f',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '\u0646\u0639\u0645',
        cancelButtonText: '\u0625\u0644\u063a\u0627\u0621'
    }).then(function(r) {
        if (!r.isConfirmed) return;
        bulkActivate();
    });
}

function bulkExport() {
    exportUnitsReport();
}

function filterUnits(status) {
    var rows = document.querySelectorAll('#unitsTable tbody tr');
    rows.forEach(function(row) {
        if (status === 'all' || row.dataset.status === status) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
    document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-danger').forEach(function(btn) {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-action="toggleUnit"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            toggleUnit(this.getAttribute('data-module'), this);
        });
    });
    document.querySelectorAll('[data-action="bulk-activate"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            bulkActivate();
        });
    });
    document.querySelectorAll('[data-action="bulk-deactivate"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            bulkDeactivate();
        });
    });
    document.querySelectorAll('[data-action="bulk-restart"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            bulkRestart();
        });
    });
    document.querySelectorAll('[data-action="bulk-export"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            bulkExport();
        });
    });
    document.querySelectorAll('[data-action="export-units-report"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            exportUnitsReport();
        });
    });
    document.querySelectorAll('[data-action="refresh-units"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            refreshUnits();
        });
    });
    document.querySelectorAll('[data-action="filter-units"]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            filterUnits(this.getAttribute('data-value'));
        });
    });
});
