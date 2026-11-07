var __M = window.__M || [];

export async function createOrderSet() {
    const name = document.getElementById('orderSetName')?.value;
    if (!name) {
        if (window.showToast) window.showToast('Name is required', 'error');
        return;
    }
    const items = [];
    document.querySelectorAll('.order-set-item').forEach(function(row) {
        items.push({
            item_type: row.querySelector('.item-type')?.value || 'medication',
            item_name: row.querySelector('.item-name')?.value || '',
            item_code: row.querySelector('.item-code')?.value || '',
            default_dosage: row.querySelector('.item-dosage')?.value || '',
            default_quantity: parseInt(row.querySelector('.item-qty')?.value || '1'),
            default_duration: parseInt(row.querySelector('.item-duration')?.value || '7'),
            is_optional: row.querySelector('.item-optional')?.checked || false,
        });
    });
    try {
        const resp = await fetch('/order-sets/api/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.csrfToken || '' },
            credentials: 'same-origin',
            body: JSON.stringify({ name: name, items: items }),
        });
        if (!resp.ok) throw new Error('http_' + resp.status);
        const data = await resp.json();
        if (data.id) {
            if (window.showToast) window.showToast('Order set created', 'success');
            window.location.reload();
        }
    } catch (e) {
        if (window.showToast) window.showToast('Error creating order set', 'error');
    }
}

export async function checkBPA(context) {
    try {
        const resp = await fetch('/order-sets/api/bpa/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.csrfToken || '' },
            credentials: 'same-origin',
            body: JSON.stringify({ context: context }),
        });
        if (!resp.ok) throw new Error('http_' + resp.status);
        const data = await resp.json();
        return data.advisories || [];
    } catch (e) {
        return [];
    }
}

window.createOrderSet = createOrderSet;
window.checkBPA = checkBPA;


// Backward compatibility
if (typeof createOrderSet !== "undefined") window.createOrderSet = createOrderSet;
if (typeof checkBPA !== "undefined") window.checkBPA = checkBPA;
