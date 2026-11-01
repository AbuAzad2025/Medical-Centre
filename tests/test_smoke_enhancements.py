import pytest


def _login(client, db, tenant, username, role):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, tenant, username=username, role=role)
    login_test_client(client, u, tenant)
    return u


@pytest.mark.parametrize('path', [
    '/finance/payment-plans',
    '/finance/billing-summary',
    '/finance/insurance-claims',
    '/medication/api/stock/alerts',
    '/medication/api/expiry',
    '/medication/refills',
    '/reception/appointments/waitlist',
    '/reception/appointments/reminders',
    '/reception/appointments/no-shows',
    '/booking/waitlist',
    '/booking/appointment-reminders',
    '/lab/result-templates',
    '/lab/critical-alerts',
])
def test_get_endpoints(app, client, db, test_tenant, path):
    role = 'accountant'
    if path.startswith('/medication'):
        role = 'pharmacist'
    if path.startswith('/reception') or path.startswith('/booking'):
        role = 'reception'
    if path.startswith('/lab'):
        role = 'lab'
    _login(client, db, test_tenant, f'smoke_{role}', role)
    resp = client.get(path)
    assert resp.status_code < 500, (path, resp.status_code, resp.get_data(as_text=True)[:200])


def test_post_endpoints(app, client, db, test_tenant):
    _login(client, db, test_tenant, 'smoke_acct2', 'accountant')
    r = client.post('/finance/payment-plans', json={'total_amount': 100, 'installments': 2})
    assert r.status_code < 500
    _login(client, db, test_tenant, 'smoke_ph2', 'pharmacist')
    r = client.post('/medication/api/interactions/check', json={'medication_ids': [1, 2]})
    assert r.status_code < 500
    r = client.post('/medication/prescriptions/1/refill', json={'quantity': 5})
    # prescription may not exist -> 404 acceptable
    assert r.status_code < 500
    _login(client, db, test_tenant, 'smoke_rc2', 'reception')
    r = client.post('/reception/appointments/recurring', json={'patient_id': 1, 'starts_at': '2026-01-01T10:00:00'})
    assert r.status_code < 500
    r = client.post('/reception/appointments/waitlist', json={'patient_id': 1})
    assert r.status_code < 500
    r = client.post('/reception/appointments/reminders')
    assert r.status_code < 500
    _login(client, db, test_tenant, 'smoke_lab2', 'lab')
    r = client.post('/lab/result-templates', json={'name': 't', 'test_code': 'CBC'})
    assert r.status_code < 500
    r = client.post('/lab/derived-values', json={'formula': 'bmi', 'values': {'weight': 70, 'height': 175}})
    assert r.status_code < 500
    r = client.post('/lab/results/1/history', json={'value': '5'})
    assert r.status_code < 500
