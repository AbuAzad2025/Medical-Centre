"""Super_admin + emergency deep coverage. All tests assert status < 500."""

import pytest


@pytest.fixture()
def _sa(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='sa_deep2', role='super_admin')
    login_test_client(client, u, test_tenant)
    return client


@pytest.fixture()
def _emg(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='emg_deep2', role='emergency')
    login_test_client(client, u, test_tenant)
    return client


class TestSuperAdminDeep:
    def test_sa_analytics(self, _sa):
        assert _sa.get('/super-admin/analytics').status_code < 500

    def test_sa_backup_dashboard(self, _sa):
        assert _sa.get('/super-admin/backup').status_code < 500

    def test_sa_branding(self, _sa):
        assert _sa.get('/super-admin/branding').status_code < 500

    def test_sa_data_management(self, _sa):
        assert _sa.get('/super-admin/data').status_code < 500

    def test_sa_system_config(self, _sa):
        assert _sa.get('/super-admin/system-config').status_code < 500


class TestEmergencyDeep:
    def test_emergency_patients(self, _emg):
        assert _emg.get('/emergency/patients').status_code < 500

    def test_emergency_queue(self, _emg):
        assert _emg.get('/emergency/queue').status_code < 500

    def test_emergency_reports(self, _emg):
        assert _emg.get('/emergency/reports').status_code < 500

    def test_emergency_orders(self, _emg):
        assert _emg.get('/emergency/orders').status_code < 500
