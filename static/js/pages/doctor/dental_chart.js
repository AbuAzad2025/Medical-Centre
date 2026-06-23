var __M = window.__M || [];
const STATES = __M0__;
let selectedFdi = null;
let teethData = __M1__;

function openToothModal(fdi) {
    selectedFdi = fdi;
    document.getElementById('selectedFdi').textContent = fdi;
    const tooth = teethData[fdi] || {state:'sound', surfaces:{}, notes:''};
    document.getElementById('toothStateSelect').value = tooth.state;
    document.getElementById('toothNotes').value = tooth.notes || '';
    ['occlusal','buccal','lingual','mesial','distal'].forEach(s => {
        document.getElementById('s_' + s).checked = !!(tooth.surfaces && tooth.surfaces[s]);
    });
    document.getElementById('toothEditor').style.display = 'block';
    document.getElementById('toothEditorEmpty').style.display = 'none';
}

function applyToothState() {
    if (!selectedFdi) return;
    const state = document.getElementById('toothStateSelect').value;
    const notes = document.getElementById('toothNotes').value;
    const surfaces = {};
    ['occlusal','buccal','lingual','mesial','distal'].forEach(s => {
        if (document.getElementById('s_' + s).checked) surfaces[s] = state;
    });
    teethData[selectedFdi] = {state, surfaces, notes};
    updateSvgTooth(selectedFdi, state);
    updateSummary();
}

function updateSvgTooth(fdi, state) {
    const group = document.querySelector(`.tooth-group[data-fdi="${fdi}"]`);
    if (!group) return;
    const rect = group.querySelector('rect');
    const dot = group.querySelector('circle');
    const color = STATES[state]?.color || '#10b981';
    rect.setAttribute('fill', color);
    if (state === 'sound') {
        if (dot) dot.remove();
    } else {
        if (!dot) {
            const c = document.createElementNS('http://www.w3.org/2000/svg','circle');
            c.setAttribute('cx','28'); c.setAttribute('cy','4'); c.setAttribute('r','3');
            c.setAttribute('fill','white');
            group.appendChild(c);
        }
    }
}

function updateSummary() {
    const counts = {};
    Object.values(teethData).forEach(t => { counts[t.state] = (counts[t.state]||0)+1; });
    const list = document.getElementById('summaryList');
    list.innerHTML = '';
    for (const [key, info] of Object.entries(STATES)) {
        const cnt = counts[key] || 0;
        if (cnt > 0) {
            list.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center">
                <span><span class="badge me-1" style="background:${info.color}">&nbsp;</span>${info.label}</span>
                <span class="badge bg-secondary">${cnt}</span>
            </li>`;
        }
    }
    if (list.innerHTML === '') list.innerHTML = '<li class="list-group-item text-muted">لا يوجد أسنان معدلة</li>';
}

function saveChart() {
    fetch(__M2__, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': __M3__},
        body: JSON.stringify({patient_id: __M4__, visit_id: __M5__, teeth: teethData, notes: ''})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) window.notify.success('تم الحفظ');
        else window.notify.error('خطأ: ' + data.message);
    })
    .catch(() => window.notify.error('خطأ في الاتصال'));
}

updateSummary();
