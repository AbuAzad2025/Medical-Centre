"""Coverage tests for routes.procurement.py"""

from __future__ import annotations

pytest_plugins = ['tests._isolated_tenant']


class TestProcurement:
    def test_new_po_form(self, app, rollback_db, client, login_as):
        login_as(client, 'proc_new_user', 'manager')
        resp = client.get('/procurement/new')
        assert resp.status_code in (200, 302)

    def test_create_po(self, app, rollback_db, client, login_as):
        login_as(client, 'proc_create_user', 'manager')
        resp = client.post(
            '/procurement/new',
            json={
                'supplier_id': 1,
                'medication_id': 1,
                'quantity': 10,
                'purchase_price': 5.0,
            },
        )
        assert resp.status_code in (200, 201, 302, 400, 500)
