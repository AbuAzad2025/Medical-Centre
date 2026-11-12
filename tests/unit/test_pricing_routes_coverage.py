"""Coverage tests for routes.manager.pricing.py"""

from __future__ import annotations

pytest_plugins = ['tests._isolated_tenant']


class TestPricingRoutes:
    def test_pricing_page(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_user', 'manager')
        resp = client.get('/manager/pricing')
        assert resp.status_code in (200, 302)

    def test_get_services_api_empty(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_api_user', 'manager')
        resp = client.get('/manager/api/pricing/services')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'data' in data

    def test_add_service_api_missing_fields(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_add_user', 'manager')
        resp = client.post(
            '/manager/api/pricing/services',
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_add_service_api_success(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_add_success', 'manager')
        resp = client.post(
            '/manager/api/pricing/services',
            json={
                'code': 'SVC-001',
                'name': 'Test Service',
                'name_ar': 'خدمة اختبار',
                'category': 'consultation',
                'base_price': 100.0,
                'currency': 'USD',
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'id' in data

    def test_add_service_api_duplicate_code(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_dup', 'manager')
        # First add
        client.post(
            '/manager/api/pricing/services',
            json={
                'code': 'SVC-DUP',
                'name': 'First Service',
                'category': 'consultation',
                'base_price': 50.0,
            },
        )
        # Try to add duplicate
        resp = client.post(
            '/manager/api/pricing/services',
            json={
                'code': 'SVC-DUP',
                'name': 'Second Service',
                'category': 'consultation',
                'base_price': 75.0,
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_update_service_api_not_found(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_update_nf', 'manager')
        resp = client.put(
            '/manager/api/pricing/services/99999',
            json={'name': 'Updated'},
        )
        assert resp.status_code == 404

    def test_update_service_api_success(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_update_ok', 'manager')
        # First add a service
        resp = client.post(
            '/manager/api/pricing/services',
            json={
                'code': 'SVC-UPD',
                'name': 'Original Name',
                'category': 'consultation',
                'base_price': 50.0,
            },
        )
        data = resp.get_json()
        service_id = data['id']

        # Then update it
        resp = client.put(
            f'/manager/api/pricing/services/{service_id}',
            json={'name': 'Updated Name', 'base_price': 75.0},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_service_api_not_found(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_del_nf', 'manager')
        resp = client.delete('/manager/api/pricing/services/99999')
        assert resp.status_code == 404

    def test_delete_service_api_success(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_del_ok', 'manager')
        # First add a service
        resp = client.post(
            '/manager/api/pricing/services',
            json={
                'code': 'SVC-DEL',
                'name': 'To Delete',
                'category': 'consultation',
                'base_price': 30.0,
            },
        )
        data = resp.get_json()
        service_id = data['id']

        # Then delete it
        resp = client.delete(f'/manager/api/pricing/services/{service_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_seed_pricing(self, app, rollback_db, client, login_as):
        login_as(client, 'pricing_seed', 'manager')
        resp = client.post('/manager/seed-pricing')
        assert resp.status_code in (200, 400, 500)
        data = resp.get_json()
        assert 'success' in data
