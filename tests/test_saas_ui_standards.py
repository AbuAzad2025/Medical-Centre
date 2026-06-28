"""Phase 5 UI standards — template render smoke tests."""

from flask import render_template_string


def test_entitlement_lock_partial_renders(app):
    with app.app_context():
        html = render_template_string(
            "{% include 'partials/_entitlement_lock.html' %}",
            capability_key='lab.order',
            title='المختبر',
            message='الباقة لا تشمل المختبر',
        )
    assert 'entitlement-lock-screen' in html
    assert 'lab.order' in html
    assert 'المختبر' in html


def test_reception_visits_dashboard_renders(manager_auth_client):
    resp = manager_auth_client.get('/reception/visits')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'visitsTable' in body
    assert 'table-medical-responsive' in body


def test_finance_dashboard_renders(manager_auth_client):
    resp = manager_auth_client.get('/finance/dashboard')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'clinical-table' in body or 'dashboard-table-wrap' in body
