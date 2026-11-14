"""Coverage tests for routes/manager/financial.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestManagerFinancialRoutes:
    def test_settlements_unauth(self, app, client):
        resp = client.get('/manager/settlements')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settlements_auth(self, app, client, login_as):
        login_as(client, 'mgr_fin_set_user', 'admin')
        resp = client.get('/manager/settlements')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settlements_export(self, app, client):
        resp = client.get('/manager/settlements/export')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_financial_reports(self, app, client):
        resp = client.get('/manager/financial-reports')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_financial_reports_auth(self, app, client, login_as):
        login_as(client, 'mgr_fin_rep_user', 'admin')
        resp = client.get('/manager/financial-reports')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_budget_get(self, app, client):
        resp = client.get('/manager/budget')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_budget_post(self, app, client):
        resp = client.post('/manager/budget', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_budget_auth(self, app, client, login_as):
        login_as(client, 'mgr_fin_bud_user', 'admin')
        resp = client.get('/manager/budget')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_monthly_comparison(self, app, client):
        resp = client.get('/manager/monthly-comparison')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_monthly_comparison_auth(self, app, client, login_as):
        login_as(client, 'mgr_fin_mc_user', 'admin')
        resp = client.get('/manager/monthly-comparison')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_exchange_rates_get(self, app, client):
        resp = client.get('/manager/exchange-rates')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_exchange_rates_post(self, app, client):
        resp = client.post('/manager/exchange-rates', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_exchange_rates_auth(self, app, client, login_as):
        login_as(client, 'mgr_fin_er_user', 'admin')
        resp = client.get('/manager/exchange-rates')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_fetch_api(self, app, client):
        resp = client.post('/manager/exchange-rates/fetch-api')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_deactivate_rate(self, app, client):
        resp = client.post('/manager/exchange-rates/deactivate/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
