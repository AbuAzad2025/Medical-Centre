"""Owner routes — massive coverage boost (was 40%, 1050 missed lines)."""

import pytest


@pytest.fixture()
def _own(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='owner_cov', role='owner')
    login_test_client(client, u, test_tenant)
    return client


class TestOwnerDashboard:
    def test_dashboard(self, _own):
        assert _own.get('/owner/dashboard').status_code in (200, 302)


class TestOwnerTenantManagement:
    def test_tenants_list(self, _own):
        assert _own.get('/owner/tenants').status_code in (200, 302)

    def test_tenant_detail(self, _own):
        assert _own.get('/owner/tenants/1').status_code in (200, 302, 404)


class TestOwnerUsers:
    def test_users_list(self, _own):
        assert _own.get('/owner/users').status_code in (200, 302)

    def test_user_create_get(self, _own):
        assert _own.get('/owner/users/create').status_code in (200, 302)


class TestOwnerBundles:
    def test_bundles_list(self, _own):
        assert _own.get('/owner/bundles').status_code in (200, 302)

    def test_bundle_api_list(self, _own):
        resp = _own.get('/owner/api/bundles')
        assert resp.status_code == 200


class TestOwnerSubscriptions:
    def test_subscriptions_list(self, _own):
        assert _own.get('/owner/subscriptions').status_code in (200, 302)


class TestOwnerPlans:
    def test_plans_list(self, _own):
        assert _own.get('/owner/plans').status_code in (200, 302)


class TestOwnerPackages:
    def test_packages_list(self, _own):
        assert _own.get('/owner/packages').status_code in (200, 302)

    def test_package_versions(self, _own):
        resp = _own.get('/owner/packages/1/versions')
        assert resp.status_code in (200, 302, 404)


class TestOwnerSystemConfig:
    def test_system_config(self, _own):
        assert _own.get('/owner/system-config').status_code in (200, 302)

    def test_announcements(self, _own):
        assert _own.get('/owner/announcements').status_code in (200, 302)


class TestOwnerIntegrations:
    def test_integrations(self, _own):
        assert _own.get('/owner/integrations').status_code in (200, 302)

    def test_webhooks(self, _own):
        assert _own.get('/owner/webhooks').status_code in (200, 302)

    def test_api_keys(self, _own):
        assert _own.get('/owner/api-keys').status_code in (200, 302)


class TestOwnerThemes:
    def test_themes(self, _own):
        assert _own.get('/owner/themes').status_code in (200, 302)


class TestOwnerEmergencySwitches:
    def test_emergency_switches(self, _own):
        assert _own.get('/owner/emergency-switches').status_code in (200, 302)


class TestOwnerNotifications:
    def test_notification_rules(self, _own):
        assert _own.get('/owner/notification-rules').status_code in (200, 302)
