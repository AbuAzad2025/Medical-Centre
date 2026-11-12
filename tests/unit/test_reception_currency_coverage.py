"""Coverage tests for routes.reception_currency.py"""

from __future__ import annotations

pytest_plugins = ['tests._isolated_tenant']


class TestReceptionCurrency:
    def test_save_manual_rate_missing_fields(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={},
        )
        assert resp.status_code == 400

    def test_save_manual_rate_invalid_rate(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user2', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'rate': 'not-a-number',
            },
        )
        assert resp.status_code == 400

    def test_save_manual_rate_negative(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user3', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'rate': -10,
            },
        )
        assert resp.status_code == 400

    def test_save_manual_rate_zero(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user4', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'rate': 0,
            },
        )
        assert resp.status_code == 400

    def test_save_manual_rate_too_large(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user5', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'rate': 2000000,
            },
        )
        assert resp.status_code == 400

    def test_save_manual_rate_success(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user6', 'manager')
        resp = client.post(
            '/reception/api/save-manual-rate',
            json={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'rate': 3.75,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'rate_id' in data

    def test_check_rate_default(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user7', 'doctor')
        resp = client.get('/reception/api/check-rate')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'available' in data
        assert 'from_currency' in data
        assert 'to_currency' in data

    def test_check_rate_custom(self, app, rollback_db, client, login_as):
        login_as(client, 'curr_user8', 'doctor')
        resp = client.get('/reception/api/check-rate?from=USD&to=EUR')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['from_currency'] == 'USD'
        assert data['to_currency'] == 'EUR'
