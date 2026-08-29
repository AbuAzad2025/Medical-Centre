"""HTTP route tests for the owner blueprint (app.modules.owner)."""

import types
import uuid

import pytest

from models.user import User


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )


@pytest.fixture
def ctx(app, db, test_tenant):
    tenant_id = test_tenant.id

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'مستخدم'),
            role=role,
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
        return u

    return types.SimpleNamespace(db=db, tenant_id=tenant_id, user=_user)


def _make_owner(login_as, client, ctx):
    u = ctx.user(role='owner')
    login_as(client, u.username, 'owner')
    return u


class TestOwnerDashboard:
    def test_dashboard_renders(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/dashboard')
        assert resp.status_code in (200, 302)

    def test_control_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/control')
        assert resp.status_code in (200, 302)

    def test_system_stats(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/system-stats')
        assert resp.status_code in (200, 302)


class TestOwnerTenants:
    def test_tenants_list(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/tenants/')
        assert resp.status_code in (200, 302)

    def test_tenants_create_get(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/tenants/create')
        assert resp.status_code in (200, 302)

    def test_tenants_create_post(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(
            '/owner/tenants/create',
            data={
                'slug': f'tenant_{uuid.uuid4().hex[:6]}',
                'name': 'مستأجر اختبار',
                'contact_email': f'{uuid.uuid4().hex[:8]}@test.local',
                'product_profile_code': 'multi_department_center',
            },
        )
        assert resp.status_code in (302, 200)

    def test_api_tenants(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get(
            '/owner/api/tenants',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    @pytest.mark.skip(reason='owner templates require csrf() global not registered in test env')
    def test_tenant_activate_modules(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(f'/owner/tenants/{ctx.tenant_id}/activate-modules')
        assert resp.status_code in (302, 200)

    @pytest.mark.skip(reason='owner templates require csrf() global not registered in test env')
    def test_tenant_suspend_activate(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(f'/owner/tenants/{ctx.tenant_id}/suspend')
        assert resp.status_code in (302, 200)
        resp = client.post(f'/owner/tenants/{ctx.tenant_id}/activate')
        assert resp.status_code in (302, 200)

    def test_tenant_usage(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get(f'/owner/tenant-usage/{ctx.tenant_id}')
        assert resp.status_code in (200, 302)


class TestOwnerUsers:
    def test_users_list(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/users')
        assert resp.status_code in (200, 302)

    def test_users_edit_post(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.post(
            f'/owner/users/{u.id}/edit',
            data={'full_name': 'معدل', 'role': 'doctor'},
        )
        assert resp.status_code in (302, 200)

    def test_users_delete_post(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.post(f'/owner/users/{u.id}/delete')
        assert resp.status_code in (302, 200)

    def test_users_toggle_active(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.post(f'/owner/users/{u.id}/toggle-active')
        assert resp.status_code in (302, 200)


class TestOwnerModules:
    def test_modules_list(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/modules')
        assert resp.status_code in (200, 302)

    def test_modules_toggle(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post('/owner/modules/lab/toggle')
        assert resp.status_code in (302, 200)


@pytest.mark.skip(reason='flaky')
class TestOwnerPlansPackages:
    def test_plans_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/plans')
        assert resp.status_code in (200, 302)

    def test_plans_create_post(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(
            '/owner/plans/create',
            data={
                'name': f'plan_{uuid.uuid4().hex[:6]}',
                'price': '99',
                'billing_cycle': 'monthly',
            },
        )
        assert resp.status_code in (302, 200)

    def test_packages_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/packages')
        assert resp.status_code in (200, 302)

    @pytest.mark.skip(reason='flaky in sharded CI tenant context')
    def test_packages_create_post(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(
            '/owner/packages/create',
            data={
                'name': f'pkg_{uuid.uuid4().hex[:6]}',
                'description': 'باقة اختبار',
            },
        )
        assert resp.status_code in (302, 200)

    def test_bundles_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/bundles')
        assert resp.status_code in (200, 302)


class TestOwnerBillingSubscriptions:
    def test_billing_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/billing')
        assert resp.status_code in (200, 302)

    def test_subscriptions_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/subscriptions')
        assert resp.status_code in (200, 302)


class TestOwnerSupportAudit:
    def test_support_tickets(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/support-tickets')
        assert resp.status_code in (200, 302)

    def test_audit_logs(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/audit-logs')
        assert resp.status_code in (200, 302)

    def test_error_audit_logs(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/error-audit-logs')
        assert resp.status_code in (200, 302)

    def test_error_logs(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/error-logs')
        assert resp.status_code in (200, 302)


class TestOwnerSystemConfig:
    @pytest.mark.skip(reason='owner templates require csrf() global not registered in test env')
    def test_system_config_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/system-config')
        assert resp.status_code in (200, 302)

    def test_system_config_save(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.post(
            '/owner/system-config/save',
            data={'config_key': 'test_key', 'config_value': 'test_value'},
        )
        assert resp.status_code in (302, 200)

    def test_emergency_switches(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/emergency-switches')
        assert resp.status_code in (200, 302)


class TestOwnerProvision:
    def test_provision_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/provision')
        assert resp.status_code in (200, 302)


class TestOwnerApiKeysWebhooks:
    def test_api_keys_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/api-keys')
        assert resp.status_code in (200, 302)

    def test_webhooks_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/webhooks')
        assert resp.status_code in (200, 302)

    def test_themes_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/themes')
        assert resp.status_code in (200, 302)

    def test_branding_page(self, login_as, client, ctx):
        _make_owner(login_as, client, ctx)
        resp = client.get('/owner/branding')
        assert resp.status_code in (200, 302)
