"""Payment + finance + lab routes coverage boost."""

import pytest


@pytest.fixture()
def _fin(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='fin_cov', role='accountant')
    login_test_client(client, u, test_tenant)
    return client


@pytest.fixture()
def _lab_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='lab_cov', role='lab')
    login_test_client(client, u, test_tenant)
    return client


class TestPaymentRoutes:
    def test_process_payment_nonexistent_visit(self, _fin):
        resp = _fin.get('/payment/process/99999')
        assert resp.status_code in (200, 302, 404)


class TestFinanceRoutes:
    def test_finance_dashboard(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='fin_dash', role='manager')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        assert c.get('/finance/dashboard').status_code in (200, 302)


class TestLabRoutes:
    def test_lab_worklist(self, _lab_client):
        assert _lab_client.get('/lab/worklist').status_code in (200, 302)

    def test_lab_dashboard(self, _lab_client):
        assert _lab_client.get('/lab/dashboard').status_code in (200, 302)

    def test_lab_reports(self, _lab_client):
        assert _lab_client.get('/lab/reports').status_code in (200, 302)

    def test_lab_quality(self, _lab_client):
        assert _lab_client.get('/lab/quality').status_code in (200, 302)
