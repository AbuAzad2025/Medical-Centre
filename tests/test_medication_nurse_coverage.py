"""Medication + nurse routes coverage boost."""

import pytest


@pytest.fixture()
def _ph(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='ph_cov', role='pharmacist')
    login_test_client(client, u, test_tenant)
    return client


@pytest.fixture()
def _nurse_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='nu_cov', role='nurse')
    login_test_client(client, u, test_tenant)
    return client


class TestMedicationRoutes:
    def test_dashboard(self, _ph):
        assert _ph.get('/medication/dashboard').status_code in (200, 302)

    def test_inventory(self, _ph):
        assert _ph.get('/medication/inventory').status_code in (200, 302)

    def test_suppliers_list(self, _ph):
        assert _ph.get('/medication/suppliers').status_code in (200, 302)

    def test_pos_terminal(self, _ph):
        assert _ph.get('/medication/pos').status_code in (200, 302)

    def test_prescriptions(self, _ph):
        assert _ph.get('/medication/prescriptions').status_code in (200, 302)


class TestNurseRoutes:
    def test_nurse_dashboard(self, _nurse_client):
        assert _nurse_client.get('/nurse/dashboard').status_code in (200, 302)

    def test_nurse_tasks(self, _nurse_client):
        assert _nurse_client.get('/nurse/tasks').status_code in (200, 302)

    def test_nurse_vitals(self, _nurse_client):
        assert _nurse_client.get('/nurse/vitals').status_code in (200, 302)

    def test_nurse_wards(self, _nurse_client):
        assert _nurse_client.get('/nurse/wards').status_code in (200, 302)
