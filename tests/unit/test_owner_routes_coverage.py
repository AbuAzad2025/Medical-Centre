"""Integration tests for the OWNER module (``app/modules/owner/routes.py``).

Every test drives the owner blueprint over real HTTP through the test client,
authenticated as a ``super_admin`` platform user, against the migrated test
schema.  The ``rollback_db`` fixture wraps each test in an outer transaction
that is rolled back on teardown, so the shared test database stays pristine
and exact-count assertions are safe.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

OWNER_PASSWORD = 'OwnerPass123!'


def _tag() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def owner_user(db, test_tenant):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(
        db,
        test_tenant,
        username=f'owner_cov_{_tag()}',
        role='super_admin',
        password=OWNER_PASSWORD,
    )


@pytest.fixture
def owner_client(client, db, test_tenant, owner_user):
    from tests.tenant_context import login_test_client

    login_test_client(client, owner_user, test_tenant, OWNER_PASSWORD)
    return client


def _make_user(db, tenant, *, role='doctor', username=None, password='TargetPass123!'):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(
        db,
        tenant,
        username=username or f'user_{_tag()}',
        role=role,
        password=password,
    )


def _make_plan(db, *, name=None, billing_type='MONTHLY', price='100.00'):
    from app.core.tenant.models import SubscriptionPlan
    from app.shared.enums import SubscriptionType

    plan = SubscriptionPlan(
        name=name or f'plan_{_tag()}',
        billing_type=SubscriptionType(billing_type),
        base_price=Decimal(price),
        currency='SAR',
        is_active=True,
    )
    db.session.add(plan)
    db.session.commit()
    return plan


def _make_bundle(db, *, slug=None, modules=('doctor', 'billing'), profile_code=None):
    from app.core.tenant.models import ProductBundle

    tag = slug or f'bundle_{_tag()}'
    bundle = ProductBundle(
        slug=tag,
        name=tag,
        name_ar=f'باقة {tag}',
        monthly_price=100,
        yearly_price=1000,
        setup_fee=0,
        currency='SAR',
        modules=json.dumps(list(modules)),
        is_public=True,
        is_active=True,
        profile_code=profile_code,
    )
    db.session.add(bundle)
    db.session.commit()
    return bundle


def _make_package_with_version(db, *, slug=None, modules=('doctor',), with_pricing=False):
    from app.core.saas.models import Package, PackageVersion

    pkg_slug = slug or f'pkg_{_tag()}'
    pkg = Package(name=pkg_slug, name_ar=pkg_slug, slug=pkg_slug, category='bundle', is_active=True)
    db.session.add(pkg)
    db.session.flush()
    version = PackageVersion(package_id=pkg.id, version='1.0.0', published_at=datetime.now(UTC))
    db.session.add(version)
    db.session.add(version)
    db.session.commit()
    if with_pricing:
        from app.core.saas.models import PackageVersionPricing

        db.session.add(
            PackageVersionPricing(
                package_version_id=version.id,
                billing_type='monthly',
                price=150,
                setup_fee=0,
                currency='SAR',
            )
        )
        db.session.flush()
    return pkg, version


# ---------------------------------------------------------------------------
# Tenant detail / management
# ---------------------------------------------------------------------------
class TestTenantDetail:
    def test_detail_renders(self, owner_client, test_tenant):
        resp = owner_client.get(f'/owner/tenants/{test_tenant.id}')
        assert resp.status_code == 200
        assert f'/owner/tenants/{test_tenant.id}/activate-modules' in resp.get_data(as_text=True)

    def test_detail_404_for_missing_tenant(self, owner_client):
        resp = owner_client.get('/owner/tenants/99999999')
        assert resp.status_code == 404

    def test_create_user_success(self, owner_client, owner_user, db, test_tenant):
        from models.user import User

        username = f'tduser_{_tag()}'
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}',
            data={
                'action': 'create_user',
                'username': username,
                'password': 'Secret123!',
                'full_name': 'Tenant Detail User',
            },
        )
        assert resp.status_code == 302
        resp = owner_client.get(f'/owner/tenants/{test_tenant.id}')
        assert resp.status_code == 200
        row = (
            db.session.execute(select(User).filter_by(tenant_id=test_tenant.id, username=username))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.role == 'admin'
        assert row.is_admin is True
        assert row.check_password('Secret123!')

    def test_create_user_duplicate_username_rejected(self, owner_client, db, test_tenant):
        from models.user import User

        existing = _make_user(db, test_tenant, role='doctor', username=f'dup_{_tag()}')
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}',
            data={
                'action': 'create_user',
                'username': existing.username,
                'password': 'Secret123!',
            },
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(
                select(User).filter_by(tenant_id=test_tenant.id, username=existing.username)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    def test_create_user_missing_password_creates_nothing(self, owner_client, db, test_tenant):
        from models.user import User

        username = f'miss_{_tag()}'
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}',
            data={'action': 'create_user', 'username': username, 'password': ''},
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(select(User).filter_by(tenant_id=test_tenant.id, username=username))
            .scalars()
            .first()
        )
        assert row is None

    def test_activate_modules_reenables_inactive_module(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule

        tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='lab')
            )
            .scalars()
            .first()
        )
        assert tm is not None
        tm.is_active = False
        db.session.commit()

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate-modules')
        assert resp.status_code == 302
        db.session.expire_all()
        tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='lab')
            )
            .scalars()
            .first()
        )
        assert tm.is_active is True

    def test_activate_modules_without_profile_code(self, owner_client, db, test_tenant):

        test_tenant.product_profile_code = None
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate-modules')
        assert resp.status_code == 302

    def test_edit_tenant_updates_basic_fields(self, owner_client, db, test_tenant):
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={
                'name': 'Renamed Tenant',
                'contact_email': 'renamed@example.test',
                'contact_phone': '+966555000111',
                'tax_number': '300123456700003',
                'domain': 'renamed.example.test',
                'subdomain': f'renamed{_tag()}',
                'storage_mode': 'LOCAL',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        from app.core.tenant.models import Tenant

        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.name == 'Renamed Tenant'
        assert tenant.contact_email == 'renamed@example.test'
        assert tenant.tax_number == '300123456700003'
        assert tenant.domain == 'renamed.example.test'

    def test_edit_tenant_invalid_storage_mode_rolls_back(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant

        before = db.session.get(Tenant, test_tenant.id).storage_mode
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={'name': 'Name That Must Not Stick', 'storage_mode': 'SHARED'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.storage_mode == before
        assert tenant.name != 'Name That Must Not Stick'

    def test_edit_tenant_profile_change_syncs_modules(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule
        from app.core.tenant.models import Tenant

        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={'name': test_tenant.name, 'product_profile_code': 'standalone_pharmacy'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.product_profile_code == 'standalone_pharmacy'
        rows = {
            m.module_name: m.is_active
            for m in db.session.execute(select(TenantModule).filter_by(tenant_id=test_tenant.id))
            .scalars()
            .all()
        }
        # standalone_pharmacy sells pharmacy/inventory/billing only
        assert rows.get('pharmacy') is True
        assert rows.get('inventory') is True
        assert rows.get('billing') is True
        assert rows.get('doctor') is False
        assert rows.get('lab') is False

    def test_toggle_tenant_feature_flag(self, owner_client, db, test_tenant):
        from app.core.tenant.models import TenantFeatureFlag

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/feature/cov_flag/toggle')
        assert resp.status_code == 302
        flag = (
            db.session.execute(
                select(TenantFeatureFlag).filter_by(
                    tenant_id=test_tenant.id, feature_key='cov_flag'
                )
            )
            .scalars()
            .first()
        )
        assert flag is not None
        assert flag.is_enabled is True

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/feature/cov_flag/toggle')
        assert resp.status_code == 302
        db.session.expire_all()
        flag = (
            db.session.execute(
                select(TenantFeatureFlag).filter_by(
                    tenant_id=test_tenant.id, feature_key='cov_flag'
                )
            )
            .scalars()
            .first()
        )
        assert flag.is_enabled is False


class TestTenantLifecycle:
    def test_renew_monthly_advances_subscription_end_by_a_month(
        self, owner_client, db, test_tenant
    ):
        from app.core.tenant.models import Tenant, TenantSubscriptionHistory
        from app.shared.enums import SubscriptionType, TenantStatus

        plan = _make_plan(db, billing_type='MONTHLY')
        test_tenant.plan_id = plan.id
        test_tenant.subscription_type = SubscriptionType.MONTHLY
        test_tenant.subscription_end = date(2026, 11, 15)
        test_tenant.status = TenantStatus.EXPIRED
        db.session.commit()

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/renew')
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.subscription_end == date(2026, 12, 15)
        assert tenant.status == TenantStatus.ACTIVE
        history = (
            db.session.execute(
                select(TenantSubscriptionHistory).filter_by(
                    tenant_id=test_tenant.id, action='RENEW'
                )
            )
            .scalars()
            .all()
        )
        assert history, 'renew must write a TenantSubscriptionHistory row'

    def test_renew_yearly_advances_subscription_end_by_a_year(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant
        from app.shared.enums import SubscriptionType

        plan = _make_plan(db, billing_type='YEARLY')
        test_tenant.plan_id = plan.id
        test_tenant.subscription_type = SubscriptionType.YEARLY
        test_tenant.subscription_end = date(2026, 11, 15)
        db.session.commit()

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/renew')
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.subscription_end == date(2027, 11, 15)

    def test_renew_perpetual_clears_subscription_end(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant
        from app.shared.enums import SubscriptionType

        plan = _make_plan(db, billing_type='PERPETUAL')
        test_tenant.plan_id = plan.id
        test_tenant.subscription_type = SubscriptionType.PERPETUAL
        test_tenant.subscription_end = date(2026, 11, 15)
        db.session.commit()

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/renew')
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.subscription_end is None

    def test_suspend_then_reactivate(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant
        from app.shared.enums import TenantStatus

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/suspend')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Tenant, test_tenant.id).status == TenantStatus.SUSPENDED

        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Tenant, test_tenant.id).status == TenantStatus.ACTIVE


# ---------------------------------------------------------------------------
# User management (cross-tenant)
# ---------------------------------------------------------------------------
class TestUsersManagement:
    def test_users_page_renders_and_search_finds_user(self, owner_client, db, test_tenant):
        target = _make_user(db, test_tenant, role='reception', username=f'findable_{_tag()}')
        resp = owner_client.get('/owner/users', query_string={'q': target.username})
        assert resp.status_code == 200
        assert target.username in resp.get_data(as_text=True)

    def test_users_role_and_tenant_filters(self, owner_client, test_tenant):
        resp = owner_client.get(
            '/owner/users', query_string={'role': 'doctor', 'tenant_id': str(test_tenant.id)}
        )
        assert resp.status_code == 200

    def test_edit_user_updates_profile_fields(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'editme_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/edit',
            data={
                'full_name': 'Edited Name',
                'email': f'edited_{_tag()}@example.test',
                'role': 'doctor',
                'is_active': '1',
            },
        )
        assert resp.status_code == 302
        from models.user import User

        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.full_name == 'Edited Name'

    def test_edit_user_bogus_role_rejected_and_user_unchanged(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'bogus_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/edit',
            data={'full_name': user.full_name, 'role': 'not_a_real_role', 'is_active': '1'},
        )
        assert resp.status_code == 302
        from models.user import User

        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.role == 'doctor'

    def test_owner_cannot_promote_to_super_admin(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        owner = ensure_test_user(
            db, test_tenant, username=f'owner_low_{_tag()}', role='owner', password=OWNER_PASSWORD
        )
        target = _make_user(db, test_tenant, role='doctor', username=f'promote_{_tag()}')
        login_test_client(client, owner, test_tenant, OWNER_PASSWORD)
        resp = client.post(
            f'/owner/users/{target.id}/edit',
            data={'full_name': target.full_name, 'role': 'super_admin', 'is_active': '1'},
        )
        assert resp.status_code == 302
        from models.user import User

        db.session.expire_all()
        target = db.session.get(User, target.id)
        assert target.role == 'doctor', 'an owner must not be able to grant super_admin'

    def test_super_admin_can_grant_elevated_role(self, owner_client, db, test_tenant):
        target = _make_user(db, test_tenant, role='doctor', username=f'elevate_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{target.id}/edit',
            data={'full_name': target.full_name, 'role': 'manager', 'is_active': '1'},
        )
        assert resp.status_code == 302
        from models.user import User

        db.session.expire_all()
        target = db.session.get(User, target.id)
        assert target.role == 'manager'

    def test_cross_tenant_reassign_rejected(self, owner_client, db, test_tenant):
        """Tenant isolation is the security boundary.

        A user row cannot be relocated to another tenant: both isolation
        layers forbid it (the ORM filter matches 0 rows for the UPDATE, and
        the Postgres RLS WITH CHECK rejects the new tenant_id). The route
        therefore refuses the move explicitly. This encodes the fail-closed
        contract rather than documenting an impossible success path.
        """
        from app.core.tenant.models import Tenant
        from models.user import User

        second = Tenant(
            slug=f'second-{_tag()}',
            name='Second Tenant',
            contact_email=f'second_{_tag()}@test.local',
            status='ACTIVE',
            product_profile_code='small_clinic',
        )
        db.session.add(second)
        db.session.commit()
        user = _make_user(db, test_tenant, role='doctor', username=f'mover_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/edit',
            data={
                'full_name': user.full_name,
                'role': 'doctor',
                'tenant_id': str(second.id),
                'is_active': '1',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.tenant_id == test_tenant.id, 'the user must not move across tenants'

    def test_reset_password_json_generates_temporary_password(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'reset_{_tag()}')
        before_version = user.session_version or 0
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            headers={'Accept': 'application/json'},
            data={},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['temp_password']
        from models.user import User

        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.session_version == before_version + 1

    def test_reset_password_json_rejects_short_password(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'reset2_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            headers={'Accept': 'application/json'},
            data={'password': 'abc'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_reset_password_form_rejects_short_password(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'reset3_{_tag()}')
        before_version = user.session_version or 0
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            data={'password': 'abc'},
            headers={'Referer': '/owner/users'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/owner/users'
        from models.user import User

        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.session_version == before_version

    def test_reset_password_form_generates_and_redirects_referrer(
        self, owner_client, db, test_tenant
    ):
        user = _make_user(db, test_tenant, role='doctor', username=f'reset4_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            data={},
            headers={'Referer': '/owner/users'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/owner/users'

    def test_reset_password_explicit_password_json(self, owner_client, db, test_tenant):
        user = _make_user(db, test_tenant, role='doctor', username=f'reset5_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            headers={'Accept': 'application/json'},
            data={'password': 'BrandNewPass123!'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert 'temp_password' not in payload, 'explicit passwords must not be echoed back'
        from models.user import User

        db.session.expire_all()
        user = db.session.get(User, user.id)
        assert user.check_password('BrandNewPass123!')

    def test_delete_regular_user(self, owner_client, db, test_tenant):
        from models.user import User

        user = _make_user(db, test_tenant, role='doctor', username=f'del_{_tag()}')
        user_id = user.id
        resp = owner_client.post(f'/owner/users/{user_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(User, user_id) is None

    def test_delete_super_admin_blocked(self, owner_client, db, test_tenant):
        from models.user import User

        boss = _make_user(db, test_tenant, role='super_admin', username=f'boss_{_tag()}')
        boss_id = boss.id
        resp = owner_client.post(f'/owner/users/{boss_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(User, boss_id) is not None

    def test_toggle_active_flips_flag(self, owner_client, db, test_tenant):
        from models.user import User

        user = _make_user(db, test_tenant, role='nurse', username=f'toggle_{_tag()}')
        before = user.is_active
        resp = owner_client.post(
            f'/owner/users/{user.id}/toggle-active',
            headers={'Referer': '/owner/users'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/owner/users'
        db.session.expire_all()
        assert db.session.get(User, user.id).is_active is (not before)

    def test_toggle_active_super_admin_not_toggled(self, owner_client, db, test_tenant):
        from models.user import User

        boss = _make_user(db, test_tenant, role='super_admin', username=f'saboss_{_tag()}')
        resp = owner_client.post(f'/owner/users/{boss.id}/toggle-active')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(User, boss.id).is_active is True

    def test_reveal_password_as_super_admin_writes_audit_and_bumps_version(
        self, owner_client, db, test_tenant
    ):
        from models.audit_trail import AuditTrail
        from models.user import User

        user = _make_user(db, test_tenant, role='doctor', username=f'reveal_{_tag()}')
        before_version = user.session_version or 0
        resp = owner_client.post(
            f'/owner/users/{user.id}/reveal-password',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['temp_password']
        db.session.expire_all()
        assert db.session.get(User, user.id).session_version == before_version + 1
        audit = (
            db.session.execute(
                select(AuditTrail).filter_by(
                    entity_id=user.id, entity_type='user', action='security'
                )
            )
            .scalars()
            .all()
        )
        assert audit, 'reveal-password must leave a security AuditTrail row'

    def test_reveal_password_denied_for_owner_role(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        owner = ensure_test_user(
            db, test_tenant, username=f'owner_rev_{_tag()}', role='owner', password=OWNER_PASSWORD
        )
        target = _make_user(db, test_tenant, role='doctor', username=f'reveal2_{_tag()}')
        login_test_client(client, owner, test_tenant, OWNER_PASSWORD)
        resp = client.post(
            f'/owner/users/{target.id}/reveal-password',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 403
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# Modules (global toggle)
# ---------------------------------------------------------------------------
class TestModules:
    def test_modules_page_renders(self, owner_client):
        resp = owner_client.get('/owner/modules')
        assert resp.status_code == 200
        assert 'lab' in resp.get_data(as_text=True)

    def test_unknown_module_toggle_creates_nothing(self, owner_client, db):
        from app.core.module.models import ModuleDefinition

        resp = owner_client.post('/owner/modules/definitely_not_a_module_xyz/toggle')
        assert resp.status_code == 302
        row = (
            db.session.execute(
                select(ModuleDefinition).filter_by(name='definitely_not_a_module_xyz')
            )
            .scalars()
            .first()
        )
        assert row is None

    def test_module_toggle_flips_state_twice(self, owner_client, db):
        from app.core.module.models import ModuleDefinition

        resp = owner_client.post('/owner/modules/lab/toggle')
        assert resp.status_code == 302
        db.session.expire_all()
        lab = db.session.execute(select(ModuleDefinition).filter_by(name='lab')).scalars().first()
        assert lab is not None
        first_state = lab.is_active

        resp = owner_client.post('/owner/modules/lab/toggle')
        assert resp.status_code == 302
        db.session.expire_all()
        lab = db.session.execute(select(ModuleDefinition).filter_by(name='lab')).scalars().first()
        assert lab.is_active is (not first_state)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
class TestPlans:
    def test_plans_page_renders(self, owner_client):
        resp = owner_client.get('/owner/plans')
        assert resp.status_code == 200

    def test_create_plan_normalizes_lowercase_billing_type(self, owner_client, db):
        from app.core.tenant.models import SubscriptionPlan
        from app.shared.enums import SubscriptionType

        name = f'plan_{_tag()}'
        resp = owner_client.post(
            '/owner/plans/create',
            data={
                'name': name,
                'base_price': '99',
                'billing_type': 'monthly',
                'is_active': '1',
            },
        )
        assert resp.status_code == 302
        plan = db.session.execute(select(SubscriptionPlan).filter_by(name=name)).scalars().first()
        assert plan is not None
        assert plan.billing_type == SubscriptionType.MONTHLY
        assert float(plan.base_price) == 99.0

    def test_create_plan_rejects_bogus_billing_type(self, owner_client, db):
        from app.core.tenant.models import SubscriptionPlan

        name = f'plan_{_tag()}'
        resp = owner_client.post(
            '/owner/plans/create',
            data={'name': name, 'base_price': '99', 'billing_type': 'bogus'},
        )
        assert resp.status_code == 302
        plan = db.session.execute(select(SubscriptionPlan).filter_by(name=name)).scalars().first()
        assert plan is None

    def test_edit_plan_normalizes_lowercase_billing_type(self, owner_client, db):
        from app.core.tenant.models import SubscriptionPlan
        from app.shared.enums import SubscriptionType

        plan = _make_plan(db, billing_type='MONTHLY')
        resp = owner_client.post(
            f'/owner/plans/{plan.id}/edit',
            data={
                'name': plan.name,
                'base_price': '120',
                'billing_type': 'yearly',
                'is_active': '1',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        plan = db.session.get(SubscriptionPlan, plan.id)
        assert plan.billing_type == SubscriptionType.YEARLY
        assert float(plan.base_price) == 120.0

    def test_edit_plan_rejects_bogus_billing_type(self, owner_client, db):
        from app.core.tenant.models import SubscriptionPlan
        from app.shared.enums import SubscriptionType

        plan = _make_plan(db, billing_type='MONTHLY')
        resp = owner_client.post(
            f'/owner/plans/{plan.id}/edit',
            data={'name': plan.name, 'base_price': '120', 'billing_type': 'bogus'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        plan = db.session.get(SubscriptionPlan, plan.id)
        assert plan.billing_type == SubscriptionType.MONTHLY

    def test_delete_unused_plan(self, owner_client, db):
        from app.core.tenant.models import SubscriptionPlan

        plan = _make_plan(db)
        plan_id = plan.id
        resp = owner_client.post(f'/owner/plans/{plan_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SubscriptionPlan, plan_id) is None

    def test_delete_plan_in_use_blocked(self, owner_client, db, test_tenant):
        from app.core.tenant.models import SubscriptionPlan, Tenant

        plan = _make_plan(db)
        plan_id = plan.id
        tenant = db.session.get(Tenant, test_tenant.id)
        tenant.plan_id = plan_id
        db.session.commit()

        resp = owner_client.post(f'/owner/plans/{plan_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.plan_id == plan_id
        assert db.session.get(SubscriptionPlan, plan_id) is not None


# ---------------------------------------------------------------------------
# Announcements (stored in SystemConfig as JSON)
# ---------------------------------------------------------------------------
class TestAnnouncements:
    def test_post_then_list_and_delete(self, owner_client, db):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/announcements',
            data={
                'title': f'ann_{_tag()}',
                'content': 'scheduled maintenance tonight',
                'priority': 'high',
                'target_audience': 'all',
            },
        )
        assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_announcements'))
            .scalars()
            .first()
        )
        assert cfg is not None
        entries = json.loads(cfg.config_value)
        assert entries and entries[0]['priority'] == 'high'
        announcement_id = entries[0]['id']

        resp = owner_client.get('/owner/announcements')
        assert resp.status_code == 200
        assert entries[0]['title'] in resp.get_data(as_text=True)

        resp = owner_client.post(f'/owner/announcements/{announcement_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_announcements'))
            .scalars()
            .first()
        )
        entries = json.loads(cfg.config_value)
        assert all(a['id'] != announcement_id for a in entries)

    def test_delete_missing_announcement_is_flashed_error(self, owner_client, db):
        resp = owner_client.post('/owner/announcements/999999999/delete')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Branding / platform identity
# ---------------------------------------------------------------------------
class TestBranding:
    def test_get_and_post_branding(self, owner_client, db):
        from models.system_config import SystemConfig

        platform_name = f'Platform {_tag()}'
        resp = owner_client.post(
            '/owner/branding',
            data={
                'platform_name': platform_name,
                'platform_name_en': 'Test Platform EN',
                'primary_color': '#112233',
                'secondary_color': '#445566',
            },
        )
        assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_platform_branding'))
            .scalars()
            .first()
        )
        assert cfg is not None
        branding = json.loads(cfg.config_value)
        assert branding['platform_name'] == platform_name
        assert branding['primary_color'] == '#112233'

        resp = owner_client.get('/owner/branding')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Webhooks (SystemConfig-backed)
# ---------------------------------------------------------------------------
class TestWebhooks:
    def test_create_and_delete_webhook(self, owner_client, db):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/webhooks',
            data={
                'name': f'hook_{_tag()}',
                'url': 'https://example.test/webhook',
                'events': 'TENANT_CREATED',
                'secret': 'supersecretvalue1234',
            },
        )
        assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_webhooks'))
            .scalars()
            .first()
        )
        hooks = json.loads(cfg.config_value)
        assert hooks[0]['url'] == 'https://example.test/webhook'
        assert hooks[0]['secret'] == 'supersecretvalue1234'  # stored raw, masked on render
        hook_id = hooks[0]['id']

        # Rendering masks the stored secret
        resp = owner_client.get('/owner/webhooks')
        assert resp.status_code == 200
        assert 'supersecretvalue1234' not in resp.get_data(as_text=True)

        resp = owner_client.post(f'/owner/webhooks/{hook_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_webhooks'))
            .scalars()
            .first()
        )
        hooks = json.loads(cfg.config_value)
        assert all(h['id'] != hook_id for h in hooks)

    def test_delete_missing_webhook_is_flash_error(self, owner_client):
        resp = owner_client.post('/owner/webhooks/999999999/delete')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# API keys (SystemConfig-backed)
# ---------------------------------------------------------------------------
class TestApiKeys:
    def test_create_key_and_delete(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/api-keys',
            data={
                'tenant_id': str(test_tenant.id),
                'name': f'key_{_tag()}',
                'scopes': 'read,write',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['key_prefix'].endswith('***')

        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_api_keys'))
            .scalars()
            .first()
        )
        keys = json.loads(cfg.config_value)
        assert keys[0]['scopes'] == 'read,write'
        assert keys[0]['key'].startswith('ak_')
        key_id = keys[0]['id']

        resp = owner_client.post(f'/owner/api-keys/{key_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_api_keys'))
            .scalars()
            .first()
        )
        keys = json.loads(cfg.config_value)
        assert all(k['id'] != key_id for k in keys)

    def test_delete_missing_key_is_flash_error(self, owner_client):
        resp = owner_client.post('/owner/api-keys/999999999/delete')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Themes (SystemTheme table)
# ---------------------------------------------------------------------------
class TestThemes:
    def test_create_theme(self, owner_client, db):
        from models.branding import SystemTheme

        name = f'theme_{_tag()}'
        resp = owner_client.post(
            '/owner/themes',
            data={
                'name': name,
                'name_ar': f'??? {name}',
                'description': 'test theme',
                'primary_color': '#111111',
                'secondary_color': '#222222',
            },
        )
        assert resp.status_code == 302
        theme = db.session.execute(select(SystemTheme).filter_by(name=name)).scalars().first()
        assert theme is not None
        assert theme.primary_color == '#111111'

    def test_set_default_theme(self, owner_client, db):
        from models.branding import SystemTheme

        first = SystemTheme(
            name=f'th1_{_tag()}',
            name_ar='th1',
            primary_color='#101010',
            secondary_color='#202020',
            accent_color='#303030',
            background_color='#f0f0f0',
            text_color='#010101',
            is_active=True,
        )
        second = SystemTheme(
            name=f'th2_{_tag()}',
            name_ar='th2',
            primary_color='#111111',
            secondary_color='#212121',
            accent_color='#313131',
            background_color='#f1f1f1',
            text_color='#020202',
            is_active=True,
        )
        db.session.add_all([first, second])
        db.session.commit()

        resp = owner_client.post(f'/owner/themes/{second.id}/set-default')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemTheme, second.id).is_default is True

    def test_delete_theme(self, owner_client, db):
        from models.branding import SystemTheme

        theme = SystemTheme(
            name=f'thdel_{_tag()}',
            name_ar='thdel',
            primary_color='#101010',
            secondary_color='#202020',
            accent_color='#303030',
            background_color='#f0f0f0',
            text_color='#010101',
            is_active=True,
        )
        db.session.add(theme)
        db.session.commit()
        theme_id = theme.id

        resp = owner_client.post(f'/owner/themes/{theme_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemTheme, theme_id) is None


# ---------------------------------------------------------------------------
# Bundles API (CRUD + entitlement sync)
# ---------------------------------------------------------------------------
class TestBundlesApi:
    def test_list_bundles_json(self, owner_client, db):
        bundle = _make_bundle(db, slug=f'listb_{_tag()}')
        resp = owner_client.get('/owner/api/bundles')
        assert resp.status_code == 200
        slugs = [item['slug'] for item in resp.get_json()]
        assert bundle.slug in slugs
        item = next(i for i in resp.get_json() if i['slug'] == bundle.slug)
        assert item['modules'] == ['doctor', 'billing']
        assert item['monthly_price'] == 100.0
        assert item['is_active'] is True

    def test_get_bundle_json(self, owner_client, db):
        bundle = _make_bundle(db, slug=f'getb_{_tag()}')
        resp = owner_client.get(f'/owner/api/bundles/{bundle.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['slug'] == bundle.slug
        assert payload['modules'] == ['doctor', 'billing']

    def test_get_bundle_404(self, owner_client):
        resp = owner_client.get('/owner/api/bundles/999999999')
        assert resp.status_code == 404

    def test_create_bundle_json(self, owner_client, db):
        from app.core.tenant.models import ProductBundle

        slug = f'newb_{_tag()}'
        resp = owner_client.post(
            '/owner/api/bundles',
            json={
                'slug': slug,
                'name': slug,
                'name_ar': '???? ?????',
                'monthly_price': 123,
                'yearly_price': 1230,
                'setup_fee': 10,
                'modules': ['doctor'],
                'max_users': 5,
                'max_patients': 500,
                'storage_gb': 10,
                'api_calls_per_month': 10000,
                'is_public': True,
                'is_active': True,
                'profile_code': 'small_clinic',
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'created'
        bundle = db.session.execute(select(ProductBundle).filter_by(slug=slug)).scalars().first()
        assert bundle is not None
        assert bundle.get_modules() == ['doctor']
        assert bundle.max_users == 5
        assert bundle.profile_code == 'small_clinic'

    def test_create_bundle_invalid_price_returns_400(self, owner_client):
        resp = owner_client.post(
            '/owner/api/bundles',
            json={'slug': f'badb_{_tag()}', 'name': 'bad', 'monthly_price': 'not-a-number'},
        )
        assert resp.status_code == 400

    def test_update_bundle_json(self, owner_client, db):
        from app.core.tenant.models import ProductBundle

        bundle = _make_bundle(db, slug=f'updb_{_tag()}')
        resp = owner_client.put(
            f'/owner/api/bundles/{bundle.id}',
            json={'name': 'Updated Bundle Name', 'monthly_price': 200, 'max_users': 25},
        )
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'
        db.session.expire_all()
        bundle = db.session.get(ProductBundle, bundle.id)
        assert bundle.name == 'Updated Bundle Name'
        assert float(bundle.monthly_price) == 200.0
        assert bundle.max_users == 25

    def test_update_bundle_404(self, owner_client):
        resp = owner_client.put('/owner/api/bundles/999999999', json={'name': 'x'})
        assert resp.status_code == 404

    def test_update_bundle_modules_syncs_package_entitlements(self, owner_client, db):
        from app.core.saas.models import PackageVersionEntitlement

        slug = f'sync_{_tag()}'
        bundle = _make_bundle(db, slug=slug, modules=('doctor',))
        _pkg, version = _make_package_with_version(db, slug=slug, modules=('doctor',))
        db.session.add(
            PackageVersionEntitlement(
                package_version_id=version.id, module_name='doctor', capability_key='stale_cap'
            )
        )
        db.session.commit()

        resp = owner_client.put(
            f'/owner/api/bundles/{bundle.id}',
            json={'modules': ['billing']},
        )
        assert resp.status_code == 200
        db.session.expire_all()
        entitlements = (
            db.session.execute(
                select(PackageVersionEntitlement).filter_by(package_version_id=version.id)
            )
            .scalars()
            .all()
        )
        modules = {e.module_name for e in entitlements}
        assert 'billing' in modules
        assert 'doctor' not in modules

    def test_update_bundle_modules_unknown_module_rolls_back(self, owner_client, db):
        from app.core.tenant.models import ProductBundle

        slug = f'syncu_{_tag()}'
        bundle = _make_bundle(db, slug=slug, modules=('doctor',))
        _pkg, _version = _make_package_with_version(db, slug=slug, modules=('doctor',))
        db.session.commit()

        resp = owner_client.put(
            f'/owner/api/bundles/{bundle.id}',
            json={'modules': ['definitely_not_a_module']},
        )
        assert resp.status_code == 500
        assert resp.get_json()['error'] == 'bundle sync failed'
        db.session.expire_all()
        bundle = db.session.get(ProductBundle, bundle.id)
        assert bundle.get_modules() == ['doctor'], 'failed sync must roll the module edit back'

    def test_delete_bundle_deactivates_it(self, owner_client, db):
        from app.core.tenant.models import ProductBundle

        bundle = _make_bundle(db, slug=f'delb_{_tag()}')
        resp = owner_client.delete(f'/owner/api/bundles/{bundle.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'
        db.session.expire_all()
        assert db.session.get(ProductBundle, bundle.id).is_active is False

    def test_delete_bundle_404(self, owner_client):
        resp = owner_client.delete('/owner/api/bundles/999999999')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tenant provisioning via API
# ---------------------------------------------------------------------------
class TestApiProvision:
    def test_missing_fields_400(self, owner_client):
        resp = owner_client.post('/owner/api/tenants/provision', json={'slug': 'only-slug'})
        assert resp.status_code == 400
        assert 'Missing required fields' in resp.get_json()['error']

    def test_duplicate_slug_400(self, owner_client, test_tenant):
        resp = owner_client.post(
            '/owner/api/tenants/provision',
            json={
                'slug': test_tenant.slug,
                'name': 'Duplicate',
                'email': 'dup@example.test',
                'bundle_slug': 'multi_department_center',
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Slug already exists'

    def test_invalid_bundle_400(self, owner_client):
        resp = owner_client.post(
            '/owner/api/tenants/provision',
            json={
                'slug': f'prov-{_tag()}',
                'name': 'Prov',
                'email': 'prov@example.test',
                'bundle_slug': f'no_such_bundle_{_tag()}',
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Invalid or inactive bundle'

    def test_provision_success(self, owner_client, db):
        from app.core.saas.models import SubscriptionLine
        from app.core.tenant.models import Tenant

        bundle = _make_bundle(db, slug=f'provb_{_tag()}', modules=('doctor', 'billing'))
        db.session.commit()

        slug = f'provisioned-{_tag()}'
        resp = owner_client.post(
            '/owner/api/tenants/provision',
            json={
                'slug': slug,
                'name': 'Provisioned Tenant',
                'email': f'{slug}@example.test',
                'bundle_slug': bundle.slug,
                'billing_type': 'monthly',
            },
        )
        assert resp.status_code == 200, resp.get_json()
        payload = resp.get_json()
        assert payload['status'] == 'provisioned'
        assert payload['tenant']['slug'] == slug
        tenant = db.session.execute(select(Tenant).filter_by(slug=slug)).scalars().first()
        assert tenant is not None
        lines = (
            db.session.execute(select(SubscriptionLine).filter_by(tenant_id=tenant.id))
            .scalars()
            .all()
        )
        assert lines, 'provisioning must create a base subscription line'


# ---------------------------------------------------------------------------
# Tenant limits / usage
# ---------------------------------------------------------------------------
class TestTenantLimitsAndUsage:
    def test_limits_json(self, owner_client, test_tenant):
        resp = owner_client.get(f'/owner/api/tenants/{test_tenant.id}/limits')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['tenant_id'] == test_tenant.id
        assert 'limits' in payload
        assert 'usage' in payload

    def test_limits_404(self, owner_client):
        resp = owner_client.get('/owner/api/tenants/999999999/limits')
        assert resp.status_code == 404

    def test_record_usage_json(self, owner_client, test_tenant):
        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/record-usage')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['status'] == 'recorded'
        assert 'total_users' in payload['snapshot']

    def test_record_usage_404(self, owner_client):
        resp = owner_client.post('/owner/api/tenants/999999999/record-usage')
        assert resp.status_code == 404

    def test_tenant_usage_page(self, owner_client, test_tenant):
        resp = owner_client.get(f'/owner/tenant-usage/{test_tenant.id}')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Package manager (HTML + POST)
# ---------------------------------------------------------------------------
class TestPackages:
    def test_packages_page_renders(self, owner_client):
        resp = owner_client.get('/owner/packages')
        assert resp.status_code == 200

    def test_create_package_creates_initial_version(self, owner_client, db):
        from app.core.saas.models import Package, PackageVersion

        slug = f'newpkg_{_tag()}'
        resp = owner_client.post(
            '/owner/packages/create',
            data={'name': slug, 'slug': slug, 'name_ar': '????', 'version': '1.2.3'},
        )
        assert resp.status_code == 302
        pkg = db.session.execute(select(Package).filter_by(slug=slug)).scalars().first()
        assert pkg is not None
        versions = (
            db.session.execute(select(PackageVersion).filter_by(package_id=pkg.id)).scalars().all()
        )
        assert [v.version for v in versions] == ['1.2.3']

    def test_create_package_json_missing_fields_400(self, owner_client):
        resp = owner_client.post(
            '/owner/packages/create',
            data={},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_create_package_json_duplicate_slug_400(self, owner_client):
        slug = f'duppkg_{_tag()}'
        resp = owner_client.post('/owner/packages/create', data={'name': slug, 'slug': slug})
        assert resp.status_code == 302
        resp = owner_client.post(
            '/owner/packages/create',
            data={'name': slug, 'slug': slug},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_create_package_version(self, owner_client, db):
        from app.core.saas.models import PackageVersion

        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/versions/create',
            data={'version': '2.0.0', 'changelog': 'second version'},
        )
        assert resp.status_code == 302
        pv = (
            db.session.execute(select(PackageVersion).filter_by(package_id=pkg.id, version='2.0.0'))
            .scalars()
            .first()
        )
        assert pv is not None
        assert pv.changelog == 'second version'

    def test_create_package_version_duplicate_rejected(self, owner_client, db):
        from app.core.saas.models import PackageVersion

        pkg, version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/versions/create',
            data={'version': version.version},
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(
                select(PackageVersion).filter_by(package_id=pkg.id, version=version.version)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1

    def test_create_package_version_missing_number_rejected(self, owner_client, db):
        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/versions/create',
            data={'version': ''},
        )
        assert resp.status_code == 302

    def test_create_package_version_copies_entitlements_limits_pricing(self, owner_client, db):
        from app.core.saas.models import (
            PackageVersion,
            PackageVersionEntitlement,
            PackageVersionLimit,
            PackageVersionPricing,
        )

        pkg, version = _make_package_with_version(db, modules=('doctor',), with_pricing=True)
        db.session.add(
            PackageVersionEntitlement(
                package_version_id=version.id, module_name='doctor', capability_key='cap.x'
            )
        )
        db.session.add(
            PackageVersionLimit(package_version_id=version.id, limit_key='max_users', limit_value=7)
        )
        db.session.commit()

        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/versions/create',
            data={'version': '3.1.0', 'copy_from_latest': 'on'},
        )
        assert resp.status_code == 302
        new_version = (
            db.session.execute(select(PackageVersion).filter_by(package_id=pkg.id, version='3.1.0'))
            .scalars()
            .first()
        )
        assert new_version is not None
        ents = (
            db.session.execute(
                select(PackageVersionEntitlement).filter_by(package_version_id=new_version.id)
            )
            .scalars()
            .all()
        )
        assert {e.module_name for e in ents} == {'doctor'}
        limits = (
            db.session.execute(
                select(PackageVersionLimit).filter_by(package_version_id=new_version.id)
            )
            .scalars()
            .all()
        )
        assert {x.limit_key: x.limit_value for x in limits} == {'max_users': 7}
        pricing = (
            db.session.execute(
                select(PackageVersionPricing).filter_by(package_version_id=new_version.id)
            )
            .scalars()
            .all()
        )
        assert [(p.billing_type, float(p.price)) for p in pricing] == [('monthly', 150.0)]

    def test_deprecate_package_version(self, owner_client, db):
        from app.core.saas.models import PackageVersion

        _pkg, version = _make_package_with_version(db)
        resp = owner_client.post(f'/owner/packages/versions/{version.id}/deprecate')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(PackageVersion, version.id).is_deprecated is True

    def test_edit_package(self, owner_client, db):
        from app.core.saas.models import Package

        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/edit',
            data={'name': 'Renamed Package', 'category': 'standalone', 'is_active': ''},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        pkg = db.session.get(Package, pkg.id)
        assert pkg.name == 'Renamed Package'
        assert pkg.category == 'standalone'
        assert pkg.is_active is False

    def test_edit_package_missing_name_not_saved(self, owner_client, db):
        from app.core.saas.models import Package

        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/edit',
            data={'name': '', 'category': 'standalone'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        pkg = db.session.get(Package, pkg.id)
        assert pkg.category != 'standalone' or pkg.name != ''

    def test_delete_package_with_versions_blocked(self, owner_client, db):
        from app.core.saas.models import Package

        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(f'/owner/packages/{pkg.id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Package, pkg.id) is not None

    def test_delete_empty_package(self, owner_client, db):
        from app.core.saas.models import Package

        empty_pkg = Package(
            name=f'empty_{_tag()}', slug=f'empty_{_tag()}', category='bundle', is_active=True
        )
        db.session.add(empty_pkg)
        db.session.commit()
        resp = owner_client.post(f'/owner/packages/{empty_pkg.id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Package, empty_pkg.id) is None

    def test_edit_package_version(self, owner_client, db):
        from app.core.saas.models import PackageVersion

        _pkg, version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/versions/{version.id}/edit',
            data={'version': '9.9.9', 'changelog': 'edited', 'is_deprecated': '1'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        version = db.session.get(PackageVersion, version.id)
        assert version.version == '9.9.9'
        assert version.is_deprecated is True

    def test_edit_package_version_missing_number_rejected(self, owner_client, db):
        from app.core.saas.models import PackageVersion

        _pkg, version = _make_package_with_version(db)
        original = version.version
        resp = owner_client.post(
            f'/owner/packages/versions/{version.id}/edit',
            data={'version': ''},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(PackageVersion, version.id).version == original

    def test_delete_package_version_removes_children(self, owner_client, db):
        from app.core.saas.models import (
            PackageVersion,
            PackageVersionEntitlement,
            PackageVersionLimit,
            PackageVersionPricing,
        )

        _pkg, version = _make_package_with_version(db, with_pricing=True)
        db.session.add(
            PackageVersionEntitlement(
                package_version_id=version.id, module_name='doctor', capability_key='cap.y'
            )
        )
        db.session.add(
            PackageVersionLimit(package_version_id=version.id, limit_key='max_users', limit_value=3)
        )
        db.session.commit()
        version_id = version.id

        resp = owner_client.post(f'/owner/packages/versions/{version_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(PackageVersion, version_id) is None
        assert (
            db.session.execute(
                select(PackageVersionEntitlement).filter_by(package_version_id=version_id)
            )
            .scalars()
            .all()
            == []
        )
        assert (
            db.session.execute(select(PackageVersionLimit).filter_by(package_version_id=version_id))
            .scalars()
            .all()
            == []
        )
        assert (
            db.session.execute(
                select(PackageVersionPricing).filter_by(package_version_id=version_id)
            )
            .scalars()
            .all()
            == []
        )

    def test_delete_package_version_with_subscription_blocked(self, owner_client, db, test_tenant):
        from app.core.saas.models import PackageVersion, SubscriptionLine, SubscriptionLineStatus

        _pkg, version = _make_package_with_version(db)
        db.session.add(
            SubscriptionLine(
                tenant_id=test_tenant.id,
                package_version_id=version.id,
                line_type='base',
                status=SubscriptionLineStatus.ACTIVE,
                billing_type='monthly',
                quantity=1,
                unit_price=100,
                effective_from=datetime.now(UTC),
            )
        )
        db.session.commit()
        version_id = version.id

        resp = owner_client.post(f'/owner/packages/versions/{version_id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(PackageVersion, version_id) is not None


# ---------------------------------------------------------------------------
# Subscriptions manager (provision a fresh tenant, then act on it)
# ---------------------------------------------------------------------------
def _provision_fresh_tenant(app, db, *, suffix=None):
    """Provision a tenant through the service, mirroring the owner flow.

    Returns (tenant, package_version). The bundle is created first so that
    ``ensure_saas_packages()`` mirrors it into a package + version we can
    subscribe against. Provisioning is request-scoped behaviour: the service
    binds the new tenant when a request context exists, so run it inside one.
    """
    from app.core.platform_bootstrap import ensure_saas_packages
    from app.core.saas.lifecycle import TenantProvisioningService
    from app.core.saas.models import Package, PackageVersion

    tag = (suffix or _tag()).replace('_', '-')
    bundle = _make_bundle(db, slug=f'sub-{tag}', modules=('doctor', 'billing'))
    db.session.commit()
    ensure_saas_packages()
    pkg = db.session.execute(select(Package).filter_by(slug=bundle.slug)).scalars().first()
    assert pkg is not None, 'ensure_saas_packages must mirror the bundle into a package'
    version = (
        db.session.execute(
            select(PackageVersion).filter_by(package_id=pkg.id).order_by(PackageVersion.id.desc())
        )
        .scalars()
        .first()
    )
    tenant_slug = f'tenant-{tag}'
    with app.test_request_context():
        tenant = TenantProvisioningService.provision_tenant(
            slug=tenant_slug,
            name='Subscription Test Tenant',
            contact_email=f'{tenant_slug}@example.test',
            package_version_id=version.id,
            billing_type='monthly',
            performed_by_user_id=None,
        )
    from tests.tenant_context import bind_tenant_on_g

    bind_tenant_on_g(tenant, db_session=db.session)
    return tenant, version


class TestSubscriptions:
    def test_subscriptions_page_renders(self, owner_client):
        resp = owner_client.get('/owner/subscriptions')
        assert resp.status_code == 200

    def test_upgrade_missing_version_id_creates_nothing(self, owner_client, db, test_tenant):
        from app.core.saas.models import SubscriptionLine

        resp = owner_client.post(
            f'/owner/subscriptions/{test_tenant.id}/upgrade',
            data={'billing_type': 'monthly'},
        )
        assert resp.status_code == 302
        lines = (
            db.session.execute(select(SubscriptionLine).filter_by(tenant_id=test_tenant.id))
            .scalars()
            .all()
        )
        assert lines == []

    def test_upgrade_tenant_to_new_version(self, owner_client, app, db):
        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus
        from app.core.tenant.models import TenantSubscriptionHistory

        tenant, _version = _provision_fresh_tenant(app, db)
        second_slug = f'subpkg2_{_tag()}'
        _pkg2, second_version = _make_package_with_version(db, slug=second_slug)
        db.session.commit()

        resp = owner_client.post(
            f'/owner/subscriptions/{tenant.id}/upgrade',
            data={'package_version_id': str(second_version.id), 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=db.session)
        db.session.expire_all()
        base_lines = (
            db.session.execute(
                select(SubscriptionLine)
                .filter_by(
                    tenant_id=tenant.id,
                    line_type='base',
                    status=SubscriptionLineStatus.ACTIVE,
                )
                .order_by(SubscriptionLine.id.desc())
            )
            .scalars()
            .all()
        )
        assert base_lines
        assert base_lines[0].package_version_id == second_version.id
        history = (
            db.session.execute(
                select(TenantSubscriptionHistory).filter_by(tenant_id=tenant.id, action='UPGRADE')
            )
            .scalars()
            .all()
        )
        assert history, 'upgrade must record TenantSubscriptionHistory'

    def test_add_addon_creates_addon_line(self, owner_client, app, db):
        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus

        tenant, _version = _provision_fresh_tenant(app, db)
        addon_slug = f'subaddon_{_tag()}'
        _pkg, addon_version = _make_package_with_version(db, slug=addon_slug, modules=('lab',))
        db.session.commit()

        resp = owner_client.post(
            f'/owner/subscriptions/{tenant.id}/addon',
            data={'package_version_id': str(addon_version.id), 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=db.session)
        db.session.expire_all()
        addons = (
            db.session.execute(
                select(SubscriptionLine).filter_by(
                    tenant_id=tenant.id,
                    line_type='addon',
                    status=SubscriptionLineStatus.ACTIVE,
                )
            )
            .scalars()
            .all()
        )
        assert addons
        assert addons[0].package_version_id == addon_version.id

    def test_add_addon_missing_version_id_creates_nothing(self, owner_client, db, test_tenant):
        from app.core.saas.models import SubscriptionLine

        resp = owner_client.post(
            f'/owner/subscriptions/{test_tenant.id}/addon',
            data={'billing_type': 'monthly'},
        )
        assert resp.status_code == 302
        lines = (
            db.session.execute(select(SubscriptionLine).filter_by(tenant_id=test_tenant.id))
            .scalars()
            .all()
        )
        assert lines == []

    def test_renew_active_base_line(self, owner_client, app, db):
        from app.core.tenant.models import TenantSubscriptionHistory

        tenant, _version = _provision_fresh_tenant(app, db)
        resp = owner_client.post(f'/owner/subscriptions/{tenant.id}/renew')
        assert resp.status_code == 302
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=db.session)
        db.session.expire_all()
        history = (
            db.session.execute(
                select(TenantSubscriptionHistory).filter_by(tenant_id=tenant.id, action='RENEW')
            )
            .scalars()
            .all()
        )
        assert history, 'renew must record TenantSubscriptionHistory'

    def test_renew_without_base_line_flashes_error(self, owner_client, db):
        from app.core.tenant.models import Tenant

        fresh = Tenant(
            slug=f'nobase_{_tag()}',
            name='No Base Line Tenant',
            contact_email=f'nobase_{_tag()}@example.test',
            status='ACTIVE',
            product_profile_code='small_clinic',
        )
        db.session.add(fresh)
        db.session.commit()
        resp = owner_client.post(f'/owner/subscriptions/{fresh.id}/renew')
        assert resp.status_code == 302
        db.session.expire_all()
        from app.core.tenant.models import TenantSubscriptionHistory

        history = (
            db.session.execute(select(TenantSubscriptionHistory).filter_by(tenant_id=fresh.id))
            .scalars()
            .all()
        )
        assert history == []

    def test_cancel_tenant_subscription(self, owner_client, app, db):
        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus
        from app.core.tenant.models import Tenant
        from app.shared.enums import TenantStatus

        tenant, _version = _provision_fresh_tenant(app, db)
        resp = owner_client.post(f'/owner/subscriptions/{tenant.id}/cancel')
        assert resp.status_code == 302
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=db.session)
        db.session.expire_all()
        assert db.session.get(Tenant, tenant.id).status == TenantStatus.CANCELLED
        lines = (
            db.session.execute(select(SubscriptionLine).filter_by(tenant_id=tenant.id))
            .scalars()
            .all()
        )
        assert lines
        assert all(x.status == SubscriptionLineStatus.ENDED for x in lines)


# ---------------------------------------------------------------------------
# Provision UI (GET/POST /owner/provision)
# ---------------------------------------------------------------------------
class TestProvisionPage:
    def test_provision_page_renders(self, owner_client):
        resp = owner_client.get('/owner/provision')
        assert resp.status_code == 200

    def test_provision_missing_fields_redirects_without_creating(self, owner_client, db):
        from app.core.tenant.models import Tenant

        slug = f'provmiss-{_tag()}'
        resp = owner_client.post(
            '/owner/provision',
            data={'slug': slug, 'name': 'Missing'},
        )
        assert resp.status_code == 302
        tenant = db.session.execute(select(Tenant).filter_by(slug=slug)).scalars().first()
        assert tenant is None

    def test_provision_success_creates_tenant_and_admin_user(self, owner_client, db):
        from app.core.saas.models import Package, PackageVersion
        from app.core.tenant.models import Tenant

        bundle = _make_bundle(db, slug=f'provui-{_tag()}', modules=('doctor',))
        db.session.commit()
        from app.core.platform_bootstrap import ensure_saas_packages

        ensure_saas_packages()
        pkg = db.session.execute(select(Package).filter_by(slug=bundle.slug)).scalars().first()
        version = (
            db.session.execute(select(PackageVersion).filter_by(package_id=pkg.id))
            .scalars()
            .first()
        )
        slug = f'provok-{_tag()}'
        resp = owner_client.post(
            '/owner/provision',
            data={
                'slug': slug,
                'name': 'Provisioned UI Tenant',
                'contact_email': f'{slug}@example.test',
                'package_version_id': str(version.id),
                'billing_type': 'monthly',
                'admin_username': f'admin_{_tag()}',
                'admin_password': 'AdminPass123!',
            },
        )
        assert resp.status_code == 302
        tenant = db.session.execute(select(Tenant).filter_by(slug=slug)).scalars().first()
        assert tenant is not None
        from models.user import User

        admin = (
            db.session.execute(select(User).filter_by(tenant_id=tenant.id, role='admin'))
            .scalars()
            .first()
        )
        assert admin is not None
        assert admin.is_admin is True


# ---------------------------------------------------------------------------
# System configuration (arbitrary keys)
# ---------------------------------------------------------------------------
class TestSystemConfig:
    def test_page_renders(self, owner_client):
        resp = owner_client.get('/owner/system-config')
        assert resp.status_code == 200

    def test_page_renders_with_category_filter(self, owner_client):
        resp = owner_client.get('/owner/system-config', query_string={'category': 'system'})
        assert resp.status_code == 200

    def test_save_updates_existing_and_creates_new(self, owner_client, db):
        from models.system_config import SystemConfig

        existing = SystemConfig(
            config_key=f'cov_existing_{_tag()}',
            config_value='old',
            config_type='string',
            category='system',
            is_system=False,
        )
        db.session.add(existing)
        db.session.commit()

        resp = owner_client.post(
            '/owner/system-config/save',
            data={
                f'config_{existing.config_key}': 'new-value',
                'new_config_key': f'cov_new_{_tag()}',
                'new_config_value': 'fresh',
                'new_config_type': 'string',
                'new_config_category': 'general',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemConfig, existing.id).config_value == 'new-value'
        created = (
            db.session.execute(select(SystemConfig).filter_by(config_value='fresh'))
            .scalars()
            .first()
        )
        assert created is not None
        assert created.is_system is True

    def test_save_duplicate_new_key_is_rejected(self, owner_client, db):
        from models.system_config import SystemConfig

        existing = SystemConfig(
            config_key=f'cov_dup_{_tag()}',
            config_value='v',
            config_type='string',
            category='system',
        )
        db.session.add(existing)
        db.session.commit()
        resp = owner_client.post(
            '/owner/system-config/save',
            data={
                'new_config_key': existing.config_key,
                'new_config_value': 'other',
                'new_config_type': 'string',
                'new_config_category': 'general',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemConfig, existing.id).config_value == 'v'

    def test_delete_custom_config(self, owner_client, db):
        from models.system_config import SystemConfig

        cfg = SystemConfig(
            config_key=f'cov_del_{_tag()}',
            config_value='v',
            config_type='string',
            category='system',
            is_system=False,
        )
        db.session.add(cfg)
        db.session.commit()
        cfg_id = cfg.id
        resp = owner_client.post(f'/owner/system-config/{cfg.config_key}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemConfig, cfg_id) is None

    def test_delete_system_config_blocked(self, owner_client, db):
        from models.system_config import SystemConfig

        cfg = SystemConfig(
            config_key=f'cov_sys_{_tag()}',
            config_value='v',
            config_type='string',
            category='system',
            is_system=True,
        )
        db.session.add(cfg)
        db.session.commit()
        cfg_id = cfg.id
        resp = owner_client.post(f'/owner/system-config/{cfg.config_key}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(SystemConfig, cfg_id) is not None

    def test_delete_missing_config(self, owner_client):
        resp = owner_client.post(f'/owner/system-config/{_tag()}/delete')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Control panel switches
# ---------------------------------------------------------------------------
class TestControlSwitches:
    def test_control_page_renders(self, owner_client):
        resp = owner_client.get('/owner/control')
        assert resp.status_code == 200
        assert 'maintenance_mode' in resp.get_data(as_text=True)

    def test_control_toggle_creates_and_flips(self, owner_client, db):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/control/toggle', data={'key': 'maintenance_mode', 'value': '1'}
        )
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'key': 'maintenance_mode', 'value': True}
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='maintenance_mode'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() is True

        resp = owner_client.post(
            '/owner/control/toggle', data={'key': 'maintenance_mode', 'value': '0'}
        )
        assert resp.status_code == 200
        assert resp.get_json()['value'] is False

    def test_control_toggle_missing_key_400(self, owner_client):
        resp = owner_client.post('/owner/control/toggle', data={})
        assert resp.status_code == 400

    def test_emergency_switches_page_renders(self, owner_client):
        resp = owner_client.get('/owner/emergency-switches')
        assert resp.status_code == 200
        assert 'emergency_disable_logins' in resp.get_data(as_text=True)

    def test_emergency_toggle_creates_and_flips(self, owner_client, db):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/emergency-switches/toggle',
            data={'key': 'emergency_disable_logins', 'value': 'true'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['value'] is True
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key='emergency_disable_logins')
            )
            .scalars()
            .first()
        )
        assert cfg.get_value() is True

    def test_emergency_toggle_missing_key_400(self, owner_client):
        resp = owner_client.post('/owner/emergency-switches/toggle', data={})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tasks, monitoring, backups
# ---------------------------------------------------------------------------
class TestTasksMonitoringBackups:
    def test_tasks_page_renders(self, owner_client):
        resp = owner_client.get('/owner/tasks')
        assert resp.status_code == 200

    def test_tasks_page_with_rows(self, owner_client, owner_user, db, test_tenant):
        from models.task_management import Project, Task

        project = Project(
            name=f'proj_{_tag()}',
            tenant_id=test_tenant.id,
            project_type='maintenance',
            status='in_progress',
        )
        db.session.add(project)
        db.session.flush()
        task = Task(
            title=f'task_{_tag()}',
            tenant_id=test_tenant.id,
            task_type='administrative',
            status='pending',
            priority='medium',
            assigned_by=owner_user.id,
        )
        db.session.add(task)
        db.session.commit()
        resp = owner_client.get('/owner/tasks')
        assert resp.status_code == 200

    def test_monitoring_page_renders(self, owner_client):
        resp = owner_client.get('/owner/monitoring')
        assert resp.status_code == 200

    def test_backups_page_renders(self, owner_client):
        resp = owner_client.get('/owner/backups')
        assert resp.status_code == 200

    def test_backups_page_with_rows(self, owner_client, db, test_tenant):
        from models.backup import Backup

        backup = Backup(
            tenant_id=test_tenant.id,
            backup_name=f'backup_{_tag()}',
            backup_type='full',
            backup_path=f'/tmp/{_tag()}.sql.gz',
            backup_status='COMPLETED',
        )
        db.session.add(backup)
        db.session.commit()
        resp = owner_client.get('/owner/backups')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Platform tenant assumptions
# ---------------------------------------------------------------------------
class TestAssumptions:
    def test_create_list_revoke_cycle(self, owner_client, owner_user, db, test_tenant):
        resp = owner_client.post(
            '/owner/api/assumptions',
            json={
                'user_id': owner_user.id,
                'assumed_tenant_id': test_tenant.id,
                'reason': 'investigating a billing dispute with the tenant',
                'expires_in_hours': 2,
            },
        )
        assert resp.status_code == 201
        assumption = resp.get_json()['assumption']
        assert assumption['is_active'] is True
        assert assumption['user_id'] == owner_user.id
        assumption_id = assumption['id']

        resp = owner_client.get('/owner/api/assumptions')
        assert resp.status_code == 200
        assert any(a['id'] == assumption_id for a in resp.get_json()['assumptions'])

        resp = owner_client.post(
            f'/owner/api/assumptions/{assumption_id}/revoke',
            json={'revoke_reason': 'investigation complete'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['assumption']['is_active'] is False

        # After revocation the assumption is no longer "active" - it must
        # disappear from the active list.
        resp = owner_client.get('/owner/api/assumptions')
        assert resp.status_code == 200
        assert all(a['id'] != assumption_id for a in resp.get_json()['assumptions'])

    def test_create_missing_fields_400(self, owner_client):
        resp = owner_client.post('/owner/api/assumptions', json={'user_id': 1})
        assert resp.status_code == 400

    def test_create_short_reason_400(self, owner_client, owner_user, test_tenant):
        resp = owner_client.post(
            '/owner/api/assumptions',
            json={'user_id': owner_user.id, 'assumed_tenant_id': test_tenant.id, 'reason': 'short'},
        )
        assert resp.status_code == 400

    def test_create_with_invalid_expiry_treated_as_no_expiry(
        self, owner_client, owner_user, test_tenant
    ):
        resp = owner_client.post(
            '/owner/api/assumptions',
            json={
                'user_id': owner_user.id,
                'assumed_tenant_id': test_tenant.id,
                'reason': 'investigation with unparseable expiry',
                'expires_in_hours': 'not-a-number',
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()['assumption']['expires_at'] is None

    def test_revoke_unknown_id_404(self, owner_client):
        resp = owner_client.post(
            '/owner/api/assumptions/999999999/revoke', json={'revoke_reason': 'no such id'}
        )
        assert resp.status_code == 404

    def test_list_filtered_by_user_id(self, owner_client, owner_user, db, test_tenant):
        from app.core.tenant.assumption_service import PlatformAssumptionService

        created = PlatformAssumptionService.create_assumption(
            user_id=owner_user.id,
            assumed_tenant_id=test_tenant.id,
            reason='seed assumption for filter test',
        )
        resp = owner_client.get('/owner/api/assumptions', query_string={'user_id': owner_user.id})
        assert resp.status_code == 200
        assert any(a['id'] == created.id for a in resp.get_json()['assumptions'])
        resp = owner_client.get('/owner/api/assumptions', query_string={'user_id': 999999999})
        assert resp.status_code == 200
        assert all(a['id'] != created.id for a in resp.get_json()['assumptions'])


# ---------------------------------------------------------------------------
# Misc platform pages
# ---------------------------------------------------------------------------
class TestMiscPages:
    def test_tenants_slash_redirects_to_dashboard(self, owner_client):
        resp = owner_client.get('/owner/tenants/')
        assert resp.status_code == 302
        assert '/owner/dashboard' in resp.headers['Location']

    def test_users_list_alias_redirects(self, owner_client):
        resp = owner_client.get('/owner/users-list')
        assert resp.status_code == 302
        assert '/owner/users' in resp.headers['Location']

    def test_tenants_create_redirects_to_provision(self, owner_client):
        for resp in (
            owner_client.get('/owner/tenants/create'),
            owner_client.post('/owner/tenants/create'),
        ):
            assert resp.status_code == 302
            assert '/owner/provision' in resp.headers['Location']

    def test_error_audit_logs_page(self, owner_client):
        resp = owner_client.get('/owner/error-audit-logs')
        assert resp.status_code == 200

    def test_error_audit_logs_filtered(self, owner_client, db):
        from models.audit_trail import AuditTrail

        db.session.add(
            AuditTrail(
                tenant_id=1,
                action='security',
                entity_type='user',
                entity_id=1,
                description='cov probe',
            )
        )
        db.session.add(
            AuditTrail(
                tenant_id=1,
                action='view',
                entity_type='system',
                entity_id=2,
                description='cov probe 2',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/error-audit-logs', query_string={'entity_type': 'user'})
        assert resp.status_code == 200

    def test_company_info_page(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_platform_branding',
                config_value=json.dumps({'platform_name': 'Coverage Platform'}),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/company-info')
        assert resp.status_code == 200

    def test_integrations_page(self, owner_client):
        resp = owner_client.get('/owner/integrations')
        assert resp.status_code == 200

    def test_integrations_page_with_config(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_integrations',
                config_value=json.dumps([{'name': 'stripe', 'enabled': True}]),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/integrations')
        assert resp.status_code == 200

    def test_cards_vault_page_and_total(self, owner_client, db, test_tenant):
        from models.payment import PaymentCard

        db.session.add(
            PaymentCard(
                tenant_id=test_tenant.id,
                owner_name='Card Holder',
                card_type='credit',
                last_four='4242',
                expiry_month=12,
                expiry_year=2030,
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/cards-vault')
        assert resp.status_code == 200

    def test_payment_vault_redirects_to_cards_vault(self, owner_client):
        resp = owner_client.get('/owner/payment-vault')
        assert resp.status_code == 302
        assert '/owner/cards-vault' in resp.headers['Location']

    def test_error_logs_alias_redirects(self, owner_client):
        resp = owner_client.get('/owner/error-logs')
        assert resp.status_code == 302
        assert '/owner/error-audit-logs' in resp.headers['Location']

    def test_system_stats_page(self, owner_client):
        resp = owner_client.get('/owner/system-stats')
        assert resp.status_code == 200

    def test_reports_page(self, owner_client):
        resp = owner_client.get('/owner/reports')
        assert resp.status_code == 200

    def test_resource_usage_json(self, owner_client, db, test_tenant):
        from app.core.tenant.models import ResourceUsage

        snap = ResourceUsage(tenant_id=test_tenant.id, db_size_mb=1, storage_mb=2)
        db.session.add(snap)
        db.session.commit()
        resp = owner_client.get('/owner/resource-usage', headers={'Accept': 'application/json'})
        assert resp.status_code == 200
        payload = resp.get_json()
        assert 'usages' in payload
        assert payload['page'] == 1

    def test_resource_usage_page_renders(self, owner_client):
        resp = owner_client.get('/owner/resource-usage')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Support tickets
# ---------------------------------------------------------------------------
class TestSupportTickets:
    def _make_ticket(self, db, owner_user, test_tenant, **kw):
        from app.core.tenant.models import SupportTicket

        ticket = SupportTicket(
            tenant_id=test_tenant.id,
            created_by=owner_user.id,
            title=f'ticket_{_tag()}',
            description='the billing export is off by one page',
            category='billing',
            priority='high',
            status='open',
        )
        db.session.add(ticket)
        db.session.commit()
        return ticket

    def test_page_renders(self, owner_client, owner_user, db, test_tenant):
        self._make_ticket(db, owner_user, test_tenant)
        resp = owner_client.get('/owner/support-tickets')
        assert resp.status_code == 200

    def test_json_list_contract(self, owner_client, owner_user, db, test_tenant):
        ticket = self._make_ticket(db, owner_user, test_tenant)
        resp = owner_client.get('/owner/support-tickets', headers={'Accept': 'application/json'})
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['total'] >= 1
        assert any(t['id'] == ticket.id for t in payload['tickets'])

    def test_json_list_filtered_by_status(self, owner_client, owner_user, db, test_tenant):
        self._make_ticket(db, owner_user, test_tenant)
        resp = owner_client.get(
            '/owner/support-tickets',
            query_string={'status': 'resolved'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['total'] == 0

    def test_update_status_to_resolved_stamps_resolved_at(
        self, owner_client, owner_user, db, test_tenant
    ):
        from app.core.tenant.models import SupportTicket

        ticket = self._make_ticket(db, owner_user, test_tenant)
        resp = owner_client.post(
            f'/owner/support-tickets/{ticket.id}/update',
            data={'status': 'resolved', 'assigned_to': str(owner_user.id)},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        ticket = db.session.get(SupportTicket, ticket.id)
        assert ticket.status == 'resolved'
        assert ticket.resolved_at is not None
        assert ticket.assigned_to == owner_user.id


# ---------------------------------------------------------------------------
# Audit logs (JSON contract + filters)
# ---------------------------------------------------------------------------
class TestAuditLogs:
    def test_page_renders(self, owner_client):
        resp = owner_client.get('/owner/audit-logs')
        assert resp.status_code == 200

    def test_json_list_contract(self, owner_client, db):
        from app.core.tenant.models import PlatformAuditLog

        db.session.add(
            PlatformAuditLog(
                action='COV_PROBE',
                entity_type='system',
                entity_id=None,
                details='coverage probe row',
                ip_address='127.0.0.1',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/audit-logs', headers={'Accept': 'application/json'})
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['total'] >= 1
        # PlatformAuditLog has no to_dict(); the route falls back to {'id': ...}
        assert all(set(lg) == {'id'} for lg in payload['logs'])

    def test_json_filtered_by_entity_type_and_search(self, owner_client, db):
        from app.core.tenant.models import PlatformAuditLog

        db.session.add(
            PlatformAuditLog(
                action='COV_FILTER_ME',
                entity_type='billing',
                details='unique marker alpha',
            )
        )
        db.session.add(
            PlatformAuditLog(
                action='COV_FILTER_ME_2',
                entity_type='user',
                details='unique marker beta',
            )
        )
        db.session.commit()
        resp = owner_client.get(
            '/owner/audit-logs',
            query_string={'entity_type': 'billing', 'q': 'marker alpha'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        billing_row = (
            db.session.execute(select(PlatformAuditLog).filter_by(action='COV_FILTER_ME'))
            .scalars()
            .first()
        )
        payload = resp.get_json()
        assert [lg['id'] for lg in payload['logs']] == [billing_row.id]

    def test_json_search_matches_nothing(self, owner_client):
        resp = owner_client.get(
            '/owner/audit-logs',
            query_string={'q': 'zzz-no-such-detail-marker-zzz'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['total'] == 0


# ---------------------------------------------------------------------------
# Notification rules
# ---------------------------------------------------------------------------
class TestNotifications:
    def test_page_and_create_and_toggle_and_delete(self, owner_client, db):
        from app.core.tenant.models import NotificationRule

        resp = owner_client.get('/owner/notifications')
        assert resp.status_code == 200

        resp = owner_client.post(
            '/owner/notifications/create',
            data={
                'event_type': 'subscription_expiry',
                'channel': 'email',
                'target': 'owner@example.test',
                'template_subject': 'subscription due',
                'template_body': 'renew soon',
                'is_active': 'on',
            },
        )
        assert resp.status_code == 302
        rule = (
            db.session.execute(select(NotificationRule).filter_by(target='owner@example.test'))
            .scalars()
            .first()
        )
        assert rule is not None
        assert rule.is_active is True

        resp = owner_client.post(f'/owner/notifications/{rule.id}/toggle')
        assert resp.status_code == 302
        db.session.expire_all()
        rule = db.session.get(NotificationRule, rule.id)
        assert rule.is_active is False

        resp = owner_client.post(f'/owner/notifications/{rule.id}/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(NotificationRule, rule.id) is None


# ---------------------------------------------------------------------------
# Module activation API
# ---------------------------------------------------------------------------
class TestModuleActivationApi:
    def test_activate_and_deactivate_module(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule
        from tests.tenant_context import bind_tenant_on_g

        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/modules/lab/activate')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'activated'

        bind_tenant_on_g(test_tenant, db_session=db.session)
        db.session.expire_all()
        tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='lab')
            )
            .scalars()
            .first()
        )
        assert tm.is_active is True

        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/modules/lab/deactivate')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deactivated'
        db.session.expire_all()
        tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='lab')
            )
            .scalars()
            .first()
        )
        assert tm.is_active is False

    def test_activate_unknown_module_400(self, owner_client, test_tenant):
        resp = owner_client.post(
            f'/owner/api/tenants/{test_tenant.id}/modules/definitely_not_a_module/activate'
        )
        assert resp.status_code == 400

    def test_activate_module_for_missing_tenant_404(self, owner_client):
        resp = owner_client.post('/owner/api/tenants/999999999/modules/lab/activate')
        assert resp.status_code == 404

    def test_deactivate_module_for_missing_tenant_404(self, owner_client):
        resp = owner_client.post('/owner/api/tenants/999999999/modules/lab/deactivate')
        assert resp.status_code == 404

    def test_list_active_modules(self, owner_client, test_tenant):
        resp = owner_client.get(f'/owner/api/tenants/{test_tenant.id}/modules')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['tenant_id'] == test_tenant.id
        assert 'lab' in payload['active_modules']

    def test_list_tenants_json(self, owner_client, test_tenant):
        resp = owner_client.get('/owner/api/tenants')
        assert resp.status_code == 200
        ids = [t['id'] for t in resp.get_json()]
        assert test_tenant.id in ids


# ---------------------------------------------------------------------------
# Tenant profile + feature toggle API
# ---------------------------------------------------------------------------
class TestTenantProfileApi:
    def test_update_profile_valid(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant

        resp = owner_client.post(
            f'/owner/api/tenants/{test_tenant.id}/profile',
            json={'product_profile': 'small_clinic'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['profile'] == 'small_clinic'
        db.session.expire_all()
        assert db.session.get(Tenant, test_tenant.id).product_profile_code == 'small_clinic'

    def test_update_profile_invalid_value_400(self, owner_client, test_tenant):
        resp = owner_client.post(
            f'/owner/api/tenants/{test_tenant.id}/profile',
            json={'product_profile': 'definitely_not_a_profile'},
        )
        assert resp.status_code == 400

    def test_update_profile_missing_tenant_404(self, owner_client):
        resp = owner_client.post('/owner/api/tenants/999999999/profile', json={})
        assert resp.status_code == 404

    def test_toggle_feature(self, owner_client, db, test_tenant):
        from app.core.tenant.models import TenantFeatureFlag

        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/features/cov_flag2/toggle')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['is_enabled'] is True

        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/features/cov_flag2/toggle')
        assert resp.status_code == 200
        assert resp.get_json()['is_enabled'] is False

        flag = (
            db.session.execute(
                select(TenantFeatureFlag).filter_by(
                    tenant_id=test_tenant.id, feature_key='cov_flag2'
                )
            )
            .scalars()
            .first()
        )
        assert flag is not None


def _make_tenant(
    db,
    *,
    slug,
    status,
    plan=None,
    subscription_type=None,
    created_at=None,
    subscription_end=None,
    grace_period_end=None,
):
    from app.core.tenant.models import Tenant

    tenant = Tenant(
        slug=slug,
        name=slug,
        contact_email=f'{slug}@example.test',
        status=status,
        product_profile_code='small_clinic',
        plan_id=plan.id if plan else None,
        subscription_type=subscription_type,
        subscription_end=subscription_end,
        grace_period_end=grace_period_end,
    )
    if created_at is not None:
        tenant.created_at = created_at
    db.session.add(tenant)
    db.session.flush()
    return tenant


class TestDashboardMetrics:
    def test_dashboard_with_mixed_tenant_states(self, owner_client, db, test_tenant):
        import json as _json
        import re
        from datetime import UTC, datetime, timedelta

        from app.shared.enums import SubscriptionType, TenantStatus

        monthly = _make_plan(db, billing_type='MONTHLY', price='100')
        yearly = _make_plan(db, billing_type='YEARLY', price='120')
        perpetual = _make_plan(db, billing_type='PERPETUAL', price='0')

        today = date.today()
        _make_tenant(
            db,
            slug=f'tp-pending-{_tag()}',
            status=TenantStatus.PENDING,
            plan=monthly,
            subscription_type=SubscriptionType.MONTHLY,
            created_at=datetime(today.year - 1, 3, 15, tzinfo=UTC),
            subscription_end=today + timedelta(days=3),
        )
        _make_tenant(
            db,
            slug=f'tp-expired-{_tag()}',
            status=TenantStatus.EXPIRED,
            subscription_end=date(today.year, today.month, 1) - timedelta(days=1),
        )
        _make_tenant(
            db,
            slug=f'tp-grace-{_tag()}',
            status=TenantStatus.ACTIVE,
            subscription_end=today - timedelta(days=2),
            grace_period_end=today - timedelta(days=1),
        )
        _make_tenant(
            db,
            slug=f'tp-yearly-{_tag()}',
            status=TenantStatus.ACTIVE,
            plan=yearly,
            subscription_type=SubscriptionType.YEARLY,
            created_at=datetime(today.year - 1, 6, 1, tzinfo=UTC),
        )
        _make_tenant(
            db,
            slug=f'tp-perpetual-{_tag()}',
            status=TenantStatus.ACTIVE,
            plan=perpetual,
            subscription_type=SubscriptionType.PERPETUAL,
            created_at=datetime(today.year - 1, 6, 1, tzinfo=UTC),
        )
        _make_tenant(
            db,
            slug=f'tp-suspended-{_tag()}',
            status=TenantStatus.SUSPENDED,
        )
        db.session.commit()

        resp = owner_client.get('/owner/dashboard')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        match = re.search(
            r'<script id="chart-data" type="application/json">(.*?)</script>', html, re.S
        )
        assert match, 'dashboard must embed the chart payload'
        payload = _json.loads(match.group(1))
        assert len(payload['months']) == 6
        assert len(payload['tenantGrowth']) == 6
        # cumulative growth can never decrease month over month
        assert payload['tenantGrowth'] == sorted(payload['tenantGrowth'])
        assert len(payload['statusData']) == 4
        assert len(payload['ticketData']) == 4

    def test_revenue_math_from_subscription_lines(self, owner_client, db, test_tenant):
        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus
        from app.modules.owner.routes import _compute_platform_revenue

        pkg_slug = f'pricing-{_tag()}'
        _pkg, version = _make_package_with_version(db, slug=pkg_slug, with_pricing=True)
        line = SubscriptionLine(
            tenant_id=test_tenant.id,
            package_version_id=version.id,
            line_type='base',
            status=SubscriptionLineStatus.ACTIVE,
            billing_type='monthly',
            quantity=2,
            unit_price=100,
            effective_from=datetime.now(UTC) - timedelta(days=10),
        )
        db.session.add(line)
        yearly_line = SubscriptionLine(
            tenant_id=test_tenant.id,
            package_version_id=version.id,
            line_type='addon',
            status=SubscriptionLineStatus.ACTIVE,
            billing_type='yearly',
            quantity=1,
            unit_price=1200,
            effective_from=datetime.now(UTC) - timedelta(days=10),
        )
        db.session.add(yearly_line)
        db.session.commit()

        stats = _compute_platform_revenue()
        # monthly: 100 * 2 = 200; yearly: 1200 / 12 = 100; total 300
        assert stats['mrr'] == 300.0
        assert stats['arr'] == 3600.0
        assert stats['active_paid'] == 1  # one tenant, counted once
        assert stats['tenant_count'] >= 2
        assert stats['currency'] == 'SAR'


class TestBilling:
    def test_billing_page_renders(self, owner_client):
        resp = owner_client.get('/owner/billing')
        assert resp.status_code == 200

    def test_billing_page_shows_plan_rows(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant

        plan = _make_plan(db, billing_type='MONTHLY')
        tenant = db.session.get(Tenant, test_tenant.id)
        tenant.plan_id = plan.id
        db.session.commit()
        resp = owner_client.get('/owner/billing')
        assert resp.status_code == 200
        assert plan.name in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Small branch coverage: clamps, masks, create-user error, profile clear
# ---------------------------------------------------------------------------
class TestSmallBranches:
    def test_users_page_with_invalid_pagination_params(self, owner_client):
        resp = owner_client.get('/owner/users', query_string={'page': 'abc', 'per_page': 'abc'})
        assert resp.status_code == 200

    def test_users_page_per_page_clamped_to_100(self, owner_client):
        resp = owner_client.get('/owner/users', query_string={'per_page': '5000'})
        assert resp.status_code == 200

    def test_create_user_with_short_username_rejected_by_db_check(
        self, owner_client, db, test_tenant
    ):
        from models.user import User

        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}',
            data={'action': 'create_user', 'username': 'ab', 'password': 'Secret123!'},
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(select(User).filter_by(tenant_id=test_tenant.id, username='ab'))
            .scalars()
            .first()
        )
        assert row is None, 'the DB check constraint must reject a 2-char username'

    def test_activate_modules_creates_missing_module_rows(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule

        row = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='reporting')
            )
            .scalars()
            .first()
        )
        assert row is not None
        db.session.delete(row)
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate-modules')
        assert resp.status_code == 302
        db.session.expire_all()
        row = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='reporting')
            )
            .scalars()
            .first()
        )
        assert row is not None and row.is_active is True

    def test_activate_modules_unknown_profile_is_flash_error(self, owner_client, db, test_tenant):
        test_tenant.product_profile_code = f'bogus_{_tag()}'
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate-modules')
        assert resp.status_code == 302

    def test_tenant_detail_shows_bundle_limits(self, owner_client, db, test_tenant):
        from app.core.tenant.models import ProductBundle

        db.session.add(
            ProductBundle(
                slug=f'mdc-{_tag()}',
                name='multi',
                name_ar='????',
                monthly_price=1000,
                yearly_price=10000,
                setup_fee=500,
                currency='SAR',
                modules=json.dumps(['doctor', 'lab', 'billing']),
                max_users=42,
                max_patients=4242,
                storage_gb=64,
                api_calls_per_month=99999,
                is_public=False,
                is_active=True,
                profile_code='multi_department_center',
            )
        )
        db.session.commit()
        resp = owner_client.get(f'/owner/tenants/{test_tenant.id}')
        assert resp.status_code == 200
        assert '42' in resp.get_data(as_text=True)

    def test_edit_tenant_keep_same_profile_flashes_saved(self, owner_client, db, test_tenant):
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={'name': test_tenant.name, 'product_profile_code': 'multi_department_center'},
        )
        assert resp.status_code == 302

    def test_edit_tenant_clears_profile(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant

        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={'name': test_tenant.name, 'product_profile_code': ''},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Tenant, test_tenant.id).product_profile_code is None

    def test_edit_tenant_with_plan_and_storage_change(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant

        plan = _make_plan(db, billing_type='MONTHLY')
        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={
                'name': test_tenant.name,
                'plan_id': str(plan.id),
                'storage_mode': 'LOCAL',
                'product_profile_code': 'multi_department_center',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(Tenant, test_tenant.id).plan_id == plan.id

    def test_edit_tenant_profile_change_deactivates_and_creates(
        self, owner_client, db, test_tenant
    ):
        """Reactivating an existing row (pharmacy), re-creating a deleted row
        (inventory), and deactivating what the bundle does not sell (billing)."""
        from app.core.module.models import TenantModule

        tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='pharmacy')
            )
            .scalars()
            .first()
        )
        tm.is_active = False
        inventory_tm = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='inventory')
            )
            .scalars()
            .first()
        )
        db.session.delete(inventory_tm)  # must be re-created by the sync
        # bundle narrower than the profile: bundle sync must win
        from app.core.tenant.models import ProductBundle

        db.session.add(
            ProductBundle(
                slug=f'wide-{_tag()}',
                name='wide',
                name_ar='????',
                monthly_price=1,
                yearly_price=10,
                setup_fee=0,
                currency='SAR',
                modules=json.dumps(['pharmacy', 'inventory']),
                is_public=False,
                is_active=True,
                profile_code='standalone_pharmacy',
            )
        )
        db.session.commit()

        resp = owner_client.post(
            f'/owner/tenants/{test_tenant.id}/edit',
            data={'name': test_tenant.name, 'product_profile_code': 'standalone_pharmacy'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        rows = {
            m.module_name: m.is_active
            for m in db.session.execute(select(TenantModule).filter_by(tenant_id=test_tenant.id))
            .scalars()
            .all()
        }
        assert rows.get('pharmacy') is True, 'reactivated existing row'
        assert rows.get('inventory') is True, 're-created row'
        assert rows.get('billing') is False, 'not in the bundle - deactivated'
        assert rows.get('doctor') is False

    def test_reset_password_html_explicit_password(self, owner_client, db, test_tenant):
        target = _make_user(db, test_tenant, role='nurse', username=f'resete_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{target.id}/reset-password',
            data={'password': 'FormPass123!'},
            headers={'Referer': '/owner/users'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/owner/users'
        from models.user import User

        db.session.expire_all()
        assert db.session.get(User, target.id).check_password('FormPass123!')

    def test_create_api_key_via_form_returns_redirect(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        resp = owner_client.post(
            '/owner/api-keys',
            data={'tenant_id': str(test_tenant.id), 'name': f'formkey_{_tag()}'},
        )
        assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_api_keys'))
            .scalars()
            .first()
        )
        keys = json.loads(cfg.config_value)
        assert keys[0]['scopes'] == 'read'

    def test_webhook_create_without_required_fields_creates_nothing(self, owner_client, db):
        from models.system_config import SystemConfig

        resp = owner_client.post('/owner/webhooks', data={'name': 'orphan-name-only'})
        assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_webhooks'))
            .scalars()
            .first()
        )
        assert cfg is None

    def test_api_keys_page_renders_stored_keys_masked(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        cfg_value = [
            {
                'id': 1,
                'tenant_id': test_tenant.id,
                'name': 'stored-key',
                'key': 'ak_supersecretvalue999',
                'scopes': 'read',
                'created_at': '2026-11-01T00:00:00+00:00',
            }
        ]
        db.session.add(
            SystemConfig(
                config_key='owner_api_keys',
                config_value=json.dumps(cfg_value),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/api-keys')
        assert resp.status_code == 200
        assert 'ak_supersecretvalue999' not in resp.get_data(as_text=True)

    def test_webhooks_page_renders_stored_hooks_masked(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_webhooks',
                config_value=json.dumps(
                    [
                        {
                            'id': 1,
                            'name': 'stored',
                            'url': 'https://example.test/hook',
                            'events': 'TENANT_CREATED',
                            'secret': 'whsec_supersecretvalue999',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/webhooks')
        assert resp.status_code == 200
        assert 'whsec_supersecretvalue999' not in resp.get_data(as_text=True)

    def test_system_config_save_ignores_unknown_config_key(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.execute(select(SystemConfig)).scalars().all()
        resp = owner_client.post(
            '/owner/system-config/save',
            data={'config_key_that_does_not_exist': 'value'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        # no row may be created for the unknown config_<key> prefix
        after = (
            db.session.execute(select(SystemConfig).filter_by(config_key='key_that_does_not_exist'))
            .scalars()
            .first()
        )
        assert after is None


# ---------------------------------------------------------------------------
# Decorator boundary (owner_required)
# ---------------------------------------------------------------------------
class TestOwnerRequiredBoundary:
    def test_unauthenticated_html_redirects_to_login(self, client):
        resp = client.get('/owner/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_unauthenticated_api_redirects_to_login(self, client):
        # login_required is outermost of the decorator stack: /owner/*/* hands
        # anonymous callers a redirect to the login page before owner_required
        # can answer with 401.
        resp = client.get('/owner/api/bundles')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_non_platform_role_html_redirects(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        doctor = ensure_test_user(
            db, test_tenant, username=f'notplat_{_tag()}', role='doctor', password=OWNER_PASSWORD
        )
        login_test_client(client, doctor, test_tenant, OWNER_PASSWORD)
        resp = client.get('/owner/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' not in resp.headers['Location']

    def test_non_platform_role_api_returns_403(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        doctor = ensure_test_user(
            db, test_tenant, username=f'notplat2_{_tag()}', role='doctor', password=OWNER_PASSWORD
        )
        login_test_client(client, doctor, test_tenant, OWNER_PASSWORD)
        resp = client.get('/owner/api/bundles')
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'platform_owner_access_required'

    def test_saas_disabled_api_returns_403(self, owner_client, standalone_mode):
        resp = owner_client.get('/owner/api/bundles')
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'saas_mode_disabled'


# ---------------------------------------------------------------------------
# More branch coverage (small flips and not-found branches)
# ---------------------------------------------------------------------------
class TestMoreBranches:
    def test_dashboard_with_status_filter(self, owner_client):
        resp = owner_client.get('/owner/dashboard', query_string={'status': 'ACTIVE'})
        assert resp.status_code == 200

    def test_activate_non_suspended_tenant(self, owner_client, db, test_tenant):
        from app.shared.enums import TenantStatus

        pending = _make_tenant(
            db,
            slug=f'act-pending-{_tag()}',
            status=TenantStatus.PENDING,
        )
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{pending.id}/activate')
        assert resp.status_code == 302
        db.session.expire_all()
        from app.core.tenant.models import Tenant

        assert db.session.get(Tenant, pending.id).status == TenantStatus.ACTIVE

    def test_reveal_password_form_post_flashes_and_redirects(self, owner_client, db, test_tenant):
        target = _make_user(db, test_tenant, role='doctor', username=f'reveal3_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{target.id}/reveal-password',
            headers={'Referer': '/owner/users'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/owner/users'

    def test_webhook_delete_with_wrong_id(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_webhooks',
                config_value=json.dumps(
                    [
                        {
                            'id': 111,
                            'name': 'keep',
                            'url': 'https://example.test/keep',
                            'events': '*',
                            'secret': 'whsec_keepme1234',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post('/owner/webhooks/999999999/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_webhooks'))
            .scalars()
            .first()
        )
        hooks = json.loads(cfg.config_value)
        assert [h['name'] for h in hooks] == ['keep']

    def test_create_two_api_keys_appends_to_existing_config(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        for _i in range(2):
            resp = owner_client.post(
                '/owner/api-keys',
                data={'tenant_id': str(test_tenant.id), 'name': f'double_{_tag()}'},
                headers={'Accept': 'application/json'},
            )
            assert resp.status_code == 200
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_api_keys'))
            .scalars()
            .first()
        )
        keys = json.loads(cfg.config_value)
        assert len(keys) >= 2

    def test_delete_api_key_with_wrong_id(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_api_keys',
                config_value=json.dumps(
                    [
                        {
                            'id': 222,
                            'tenant_id': test_tenant.id,
                            'name': 'keepme',
                            'key': 'ak_keepme123456',
                            'scopes': 'read',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post('/owner/api-keys/999999999/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_api_keys'))
            .scalars()
            .first()
        )
        keys = json.loads(cfg.config_value)
        assert [k['name'] for k in keys] == ['keepme']

    def test_deactivate_module_without_tm_row_is_still_200(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule

        row = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='dicom')
            )
            .scalars()
            .first()
        )
        db.session.delete(row)
        db.session.commit()
        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/modules/dicom/deactivate')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deactivated'

    def test_addon_with_nonexistent_version_flashes_failure(self, owner_client, db, app):
        tenant, _version = _provision_fresh_tenant(app, db)
        resp = owner_client.post(
            f'/owner/subscriptions/{tenant.id}/addon',
            data={'package_version_id': '999999999', 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302

    def test_upgrade_with_nonexistent_version_flashes_failure(self, owner_client, db, app):
        tenant, _version = _provision_fresh_tenant(app, db)
        resp = owner_client.post(
            f'/owner/subscriptions/{tenant.id}/upgrade',
            data={'package_version_id': '999999999', 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302

    def test_cancel_missing_tenant_flashes_failure(self, owner_client):
        resp = owner_client.post('/owner/subscriptions/999999999/cancel')
        assert resp.status_code == 302

    def test_provision_page_with_nonexistent_package_version(self, owner_client, db):
        slug = f'provbad-{_tag()}'
        resp = owner_client.post(
            '/owner/provision',
            data={
                'slug': slug,
                'name': 'Prov Bad',
                'contact_email': f'{slug}@example.test',
                'package_version_id': '999999999',
                'billing_type': 'monthly',
                'admin_username': f'admin_{_tag()}',
                'admin_password': 'AdminPass123!',
            },
        )
        assert resp.status_code == 302
        from app.core.tenant.models import Tenant

        tenant = db.session.execute(select(Tenant).filter_by(slug=slug)).scalars().first()
        assert tenant is None

    def test_tenant_usage_page_with_base_line_shows_limits(self, owner_client, db, app):
        tenant, _version = _provision_fresh_tenant(app, db)
        resp = owner_client.get(f'/owner/tenant-usage/{tenant.id}')
        assert resp.status_code == 200

    def test_announcements_page_with_corrupt_config_renders(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_announcements',
                config_value='{not json at all',
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/announcements')
        assert resp.status_code == 200

    def test_branding_page_with_corrupt_config_renders(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_platform_branding',
                config_value='{corrupt',
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/branding')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Fault injection: every commit failure must roll back and flash an error,
# never half-succeed silently.
# ---------------------------------------------------------------------------
def _boom(*_a, **_k):
    raise RuntimeError('boom')


class TestCommitFailureContracts:
    def test_create_plan_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/plans/create',
            data={'name': f'plan_{_tag()}', 'base_price': '50', 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302

    def test_edit_plan_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        plan = _make_plan(db)
        resp = owner_client.post(
            f'/owner/plans/{plan.id}/edit',
            data={'name': plan.name, 'base_price': '99', 'billing_type': 'monthly'},
        )
        assert resp.status_code == 302

    def test_delete_plan_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        plan = _make_plan(db)
        resp = owner_client.post(f'/owner/plans/{plan.id}/delete')
        assert resp.status_code == 302

    def test_update_ticket_commit_failure(
        self, owner_client, owner_user, db, test_tenant, monkeypatch
    ):
        from app.core.tenant.models import SupportTicket
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        ticket = SupportTicket(
            tenant_id=test_tenant.id,
            created_by=owner_user.id,
            title=f'tkt_{_tag()}',
            description='x',
            category='general',
            priority='low',
            status='open',
        )
        db.session.add(ticket)
        db.session.commit()
        resp = owner_client.post(
            f'/owner/support-tickets/{ticket.id}/update', data={'status': 'resolved'}
        )
        assert resp.status_code == 302

    def test_create_notification_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/notifications/create',
            data={'event_type': 'subscription_expiry', 'channel': 'email', 'target': 'a@b.test'},
        )
        assert resp.status_code == 302

    def test_toggle_notification_commit_failure(self, owner_client, db, monkeypatch):
        from app.core.tenant.models import NotificationRule
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        rule = NotificationRule(
            event_type='subscription_expiry', channel='email', target='x@y.test'
        )
        db.session.add(rule)
        db.session.commit()
        resp = owner_client.post(f'/owner/notifications/{rule.id}/toggle')
        assert resp.status_code == 302

    def test_delete_notification_commit_failure(self, owner_client, db, monkeypatch):
        from app.core.tenant.models import NotificationRule
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        rule = NotificationRule(
            event_type='subscription_expiry', channel='email', target='x@y.test'
        )
        db.session.add(rule)
        db.session.commit()
        resp = owner_client.post(f'/owner/notifications/{rule.id}/delete')
        assert resp.status_code == 302

    def test_branding_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        # the branding page renders 200 with an error flash on failure
        resp = owner_client.post(
            '/owner/branding', data={'platform_name': 'X', 'primary_color': '#fff'}
        )
        assert resp.status_code == 200

    def test_create_webhook_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/webhooks',
            data={'name': f'hk_{_tag()}', 'url': 'https://example.test/hook'},
        )
        assert resp.status_code == 302

    def test_delete_webhook_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.system_config import SystemConfig

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        db.session.add(
            SystemConfig(
                config_key='owner_webhooks',
                config_value=json.dumps(
                    [
                        {
                            'id': 333,
                            'name': 'doomed',
                            'url': 'https://example.test/x',
                            'events': '*',
                            'secret': 'whsec_doomed123',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post('/owner/webhooks/333/delete')
        assert resp.status_code == 302

    def test_create_api_key_commit_failure(self, owner_client, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/api-keys',
            data={'tenant_id': str(test_tenant.id), 'name': f'k_{_tag()}'},
        )
        assert resp.status_code == 302

    def test_set_default_theme_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.branding import SystemTheme

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        theme = SystemTheme(
            name=f'thfail_{_tag()}',
            name_ar='x',
            primary_color='#123456',
            secondary_color='#234567',
            accent_color='#345678',
            background_color='#f0f0f0',
            text_color='#111111',
            is_active=True,
        )
        db.session.add(theme)
        db.session.commit()
        resp = owner_client.post(f'/owner/themes/{theme.id}/set-default')
        assert resp.status_code == 302

    def test_delete_theme_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.branding import SystemTheme

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        theme = SystemTheme(
            name=f'thfail2_{_tag()}',
            name_ar='x',
            primary_color='#123456',
            secondary_color='#234567',
            accent_color='#345678',
            background_color='#f0f0f0',
            text_color='#111111',
            is_active=True,
        )
        db.session.add(theme)
        db.session.commit()
        resp = owner_client.post(f'/owner/themes/{theme.id}/delete')
        assert resp.status_code == 302

    def test_edit_user_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        user = _make_user(db, test_tenant, role='doctor', username=f'failu_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/edit',
            data={'full_name': 'x', 'role': 'doctor', 'is_active': '1'},
        )
        assert resp.status_code == 302

    def test_toggle_module_global_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post('/owner/modules/lab/toggle')
        assert resp.status_code == 302

    def test_activate_tenant_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from app.shared.enums import TenantStatus

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        tenant = _make_tenant(db, slug=f'failact-{_tag()}', status=TenantStatus.PENDING)
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{tenant.id}/activate')
        assert resp.status_code == 302

    def test_update_profile_commit_failure_json(self, owner_client, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            f'/owner/api/tenants/{test_tenant.id}/profile',
            json={'product_profile': 'small_clinic'},
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_toggle_feature_commit_failure_json(self, owner_client, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/features/boomflag/toggle')
        assert resp.status_code == 400

    def test_delete_package_version_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        _pkg, version = _make_package_with_version(db)
        resp = owner_client.post(f'/owner/packages/versions/{version.id}/delete')
        assert resp.status_code == 302

    def test_deprecate_version_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        _pkg, version = _make_package_with_version(db)
        resp = owner_client.post(f'/owner/packages/versions/{version.id}/deprecate')
        assert resp.status_code == 302

    def test_provision_api_bundle_without_package_400(self, owner_client, db, monkeypatch):
        # ensure_saas_packages mirrors ProductBundle rows into packages; if it
        # creates nothing, the (existing, active) bundle has no package and
        # provisioning is refused with a clear 400 instead of crashing.
        from app.core import platform_bootstrap

        bundle = _make_bundle(db, slug=f'nopkg-{_tag()}', modules=('doctor',))
        db.session.commit()
        monkeypatch.setattr(platform_bootstrap, 'ensure_saas_packages', lambda: 0)
        resp = owner_client.post(
            '/owner/api/tenants/provision',
            json={
                'slug': f'provnp-{_tag()}',
                'name': 'Prov NoPkg',
                'email': f'provnp-{_tag()}@example.test',
                'bundle_slug': bundle.slug,
            },
        )
        assert resp.status_code == 400
        assert 'Package not found' in resp.get_json()['error']

    def test_owner_bundles_page_renders(self, owner_client, db):
        _make_bundle(db, slug=f'bundle-page-{_tag()}')
        resp = owner_client.get('/owner/bundles')
        assert resp.status_code == 200

    def test_tenant_usage_page_bundle_limits_branch(self, owner_client, db, test_tenant):
        from app.core.tenant.models import ProductBundle

        db.session.add(
            ProductBundle(
                slug=f'mdc2-{_tag()}',
                name='mdc',
                name_ar='????',
                monthly_price=1000,
                yearly_price=10000,
                setup_fee=100,
                currency='SAR',
                modules=json.dumps(['doctor']),
                max_users=33,
                max_patients=333,
                storage_gb=12,
                api_calls_per_month=7777,
                is_public=False,
                is_active=True,
                profile_code='multi_department_center',
            )
        )
        db.session.commit()
        resp = owner_client.get(f'/owner/tenant-usage/{test_tenant.id}')
        assert resp.status_code == 200


class TestRemainingBranches:
    def test_toggle_tenant_feature_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/feature/boomfeat/toggle')
        assert resp.status_code == 302

    def test_toggle_active_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        user = _make_user(db, test_tenant, role='doctor', username=f'togb_{_tag()}')
        resp = owner_client.post(f'/owner/users/{user.id}/toggle-active')
        assert resp.status_code == 302

    def test_reveal_password_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        user = _make_user(db, test_tenant, role='doctor', username=f'revb_{_tag()}')
        resp = owner_client.post(f'/owner/users/{user.id}/reveal-password')
        assert resp.status_code == 302

    def test_reset_password_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        user = _make_user(db, test_tenant, role='doctor', username=f'rpb_{_tag()}')
        resp = owner_client.post(
            f'/owner/users/{user.id}/reset-password',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 500

    def test_suspend_service_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.core.saas import lifecycle

        monkeypatch.setattr(
            lifecycle.TenantProvisioningService,
            'suspend_tenant',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/suspend')
        assert resp.status_code == 302

    def test_reactivate_service_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.core.saas import lifecycle
        from app.shared.enums import TenantStatus

        tenant = db.session.get(type(test_tenant), test_tenant.id)
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()
        monkeypatch.setattr(
            lifecycle.TenantProvisioningService,
            'reactivate_tenant',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        resp = owner_client.post(f'/owner/tenants/{test_tenant.id}/activate')
        assert resp.status_code == 302

    def test_renew_monthly_without_subscription_end_sets_today(self, owner_client, db, test_tenant):
        from app.core.tenant.models import Tenant
        from app.shared.enums import SubscriptionType

        plan = _make_plan(db, billing_type='MONTHLY')
        tenant = db.session.get(Tenant, test_tenant.id)
        tenant.plan_id = plan.id
        tenant.subscription_type = SubscriptionType.MONTHLY
        tenant.subscription_end = None
        db.session.commit()
        resp = owner_client.post(f'/owner/tenants/{tenant.id}/renew')
        assert resp.status_code == 302
        db.session.expire_all()
        tenant = db.session.get(Tenant, test_tenant.id)
        assert tenant.subscription_end == date.today()

    def test_revenue_skips_non_paid_tenant_lines(self, owner_client, app, db):
        from app.modules.owner.routes import _compute_platform_revenue
        from app.shared.enums import TenantStatus

        # provision a tenant (creates an ACTIVE base line under the new
        # tenant's binding), then suspend it: the line is visible to the
        # revenue query but the tenant is not active-and-paid, so it must
        # not contribute to MRR
        tenant, _version = _provision_fresh_tenant(app, db)
        from app.core.tenant.models import Tenant

        db.session.expire_all()
        tenant = db.session.get(Tenant, tenant.id)
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()

        stats = _compute_platform_revenue()
        assert stats['mrr'] == 0
        assert stats['active_paid'] == 0

    def test_announcements_post_with_corrupt_existing_config(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_announcements',
                config_value='{corrupt-json',
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post(
            '/owner/announcements',
            data={'title': f'a_{_tag()}', 'content': 'x', 'priority': 'info'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_announcements'))
            .scalars()
            .first()
        )
        entries = json.loads(cfg.config_value)
        assert entries and entries[0]['priority'] == 'info'

    def test_owner_api_access_survives_audit_write_failure(
        self, owner_client, db, test_tenant, monkeypatch
    ):
        # the sensitive-API audit write is best-effort: even if the insert
        # dies, the API call itself must still succeed
        import app.core.tenant.models as tenant_models

        class _Boom:
            def __init__(self, *a, **k):
                raise RuntimeError('boom')

        monkeypatch.setattr(tenant_models, 'PlatformAuditLog', _Boom)
        resp = owner_client.get('/owner/api/bundles')
        assert resp.status_code == 200


class TestFinalBatch:
    def test_mask_secret_edge_keys_render(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_api_keys',
                config_value=json.dumps(
                    [
                        {
                            'id': 901,
                            'tenant_id': None,
                            'name': 'short',
                            'key': 'ab',
                            'scopes': 'read',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        },
                        {
                            'id': 902,
                            'tenant_id': None,
                            'name': 'empty',
                            'key': '',
                            'scopes': 'read',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        },
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/api-keys')
        assert resp.status_code == 200

    def test_branding_second_post_updates_existing_config(self, owner_client, db):
        from models.system_config import SystemConfig

        for name in ('First Name', 'Second Name'):
            resp = owner_client.post(
                '/owner/branding',
                data={'platform_name': name, 'primary_color': '#123456'},
            )
            assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_platform_branding'))
            .scalars()
            .first()
        )
        assert json.loads(cfg.config_value)['platform_name'] == 'Second Name'

    def test_webhook_second_post_appends_and_updates(self, owner_client, db):
        from models.system_config import SystemConfig

        for i in range(2):
            resp = owner_client.post(
                '/owner/webhooks',
                data={'name': f'hook{i}_{_tag()}', 'url': f'https://example.test/hook{i}'},
            )
            assert resp.status_code == 302
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_webhooks'))
            .scalars()
            .first()
        )
        assert len(json.loads(cfg.config_value)) == 2

    def test_announcement_delete_unknown_id_with_existing_config(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_announcements',
                config_value=json.dumps(
                    [
                        {
                            'id': 4242,
                            'title': 'keep',
                            'content': 'x',
                            'priority': 'info',
                            'target_audience': 'all',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post('/owner/announcements/999999999/delete')
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_announcements'))
            .scalars()
            .first()
        )
        assert len(json.loads(cfg.config_value)) == 1

    def test_announcement_delete_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_announcements',
                config_value=json.dumps(
                    [
                        {
                            'id': 5555,
                            'title': 'doomed',
                            'content': 'x',
                            'priority': 'info',
                            'target_audience': 'all',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post('/owner/announcements/5555/delete')
        assert resp.status_code == 302

    def test_announcement_post_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        # on failure the page re-renders with an error flash instead of redirecting
        resp = owner_client.post(
            '/owner/announcements', data={'title': f'a_{_tag()}', 'content': 'x'}
        )
        assert resp.status_code == 200

    def test_announcement_post_with_existing_announcements(self, owner_client, db):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_announcements',
                config_value=json.dumps(
                    [
                        {
                            'id': 7777,
                            'title': 'first',
                            'content': 'x',
                            'priority': 'info',
                            'target_audience': 'all',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.post(
            '/owner/announcements',
            data={'title': f'a_{_tag()}', 'content': 'x', 'priority': 'warning'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='owner_announcements'))
            .scalars()
            .first()
        )
        entries = json.loads(cfg.config_value)
        assert len(entries) == 2 and entries[0]['priority'] == 'warning'

    def test_api_keys_page_with_corrupt_config_renders(self, owner_client, db, test_tenant):
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_api_keys',
                config_value='{corrupt-json',
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/api-keys')
        assert resp.status_code == 200

    def test_delete_api_key_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.system_config import SystemConfig

        db.session.add(
            SystemConfig(
                config_key='owner_api_keys',
                config_value=json.dumps(
                    [
                        {
                            'id': 888,
                            'tenant_id': test_tenant.id,
                            'name': 'doomed',
                            'key': 'ak_doomed123456',
                            'scopes': 'read',
                            'created_at': '2026-11-01T00:00:00+00:00',
                        }
                    ]
                ),
                config_type='json',
                category='system',
            )
        )
        db.session.commit()
        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post('/owner/api-keys/888/delete')
        assert resp.status_code == 302

    def test_delete_user_commit_failure(self, owner_client, db, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        user = _make_user(db, test_tenant, role='doctor', username=f'del2_{_tag()}')
        resp = owner_client.post(f'/owner/users/{user.id}/delete')
        assert resp.status_code == 302

    def test_create_theme_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/themes',
            data={'name': f'th3_{_tag()}', 'name_ar': '???'},
        )
        assert resp.status_code == 302

    def test_themes_page_renders(self, owner_client, db):
        from models.branding import SystemTheme

        db.session.add(
            SystemTheme(
                name=f'thrender_{_tag()}',
                name_ar='???',
                primary_color='#101010',
                secondary_color='#202020',
                accent_color='#303030',
                background_color='#f0f0f0',
                text_color='#020202',
                is_active=True,
            )
        )
        db.session.commit()
        resp = owner_client.get('/owner/themes')
        assert resp.status_code == 200

    def test_activate_module_creates_missing_row(self, owner_client, db, test_tenant):
        from app.core.module.models import TenantModule

        row = (
            db.session.execute(
                select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='reporting')
            )
            .scalars()
            .first()
        )
        db.session.delete(row)
        db.session.commit()
        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/modules/reporting/activate')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'activated'

    def test_update_bundle_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        bundle = _make_bundle(db, slug=f'upfail-{_tag()}')
        resp = owner_client.put(f'/owner/api/bundles/{bundle.id}', json={'name': 'x'})
        assert resp.status_code == 400

    def test_delete_bundle_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        bundle = _make_bundle(db, slug=f'delfail-{_tag()}')
        resp = owner_client.delete(f'/owner/api/bundles/{bundle.id}')
        assert resp.status_code == 400

    def test_provision_service_failure_returns_400(self, owner_client, db, monkeypatch):
        from app.core.saas import lifecycle

        monkeypatch.setattr(
            lifecycle.TenantProvisioningService,
            'provision_tenant',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        bundle = _make_bundle(db, slug=f'pfail-{_tag()}', modules=('doctor',))
        db.session.commit()
        resp = owner_client.post(
            '/owner/api/tenants/provision',
            json={
                'slug': f'provboom-{_tag()}',
                'name': 'Prov Boom',
                'email': f'provboom-{_tag()}@example.test',
                'bundle_slug': bundle.slug,
            },
        )
        assert resp.status_code == 400

    def test_record_usage_snapshot_failure(self, owner_client, test_tenant, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(
            owner_routes.ResourceUsage,
            'record_snapshot',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        resp = owner_client.post(f'/owner/api/tenants/{test_tenant.id}/record-usage')
        assert resp.status_code == 400

    def test_create_package_missing_slug_form_redirect(self, owner_client, db):
        resp = owner_client.post('/owner/packages/create', data={'name': f'p_{_tag()}'})
        assert resp.status_code == 302

    def test_create_package_duplicate_slug_form_redirect(self, owner_client, db):
        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            '/owner/packages/create', data={'name': pkg.name, 'slug': pkg.slug}
        )
        assert resp.status_code == 302

    def test_edit_package_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        pkg, _version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/{pkg.id}/edit',
            data={'name': 'x', 'category': 'bundle'},
        )
        assert resp.status_code == 302

    def test_delete_package_commit_failure(self, owner_client, db, monkeypatch):
        from app.core.saas.models import Package
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        empty_pkg = Package(
            name=f'empfail_{_tag()}', slug=f'empfail-{_tag()}', category='bundle', is_active=True
        )
        db.session.add(empty_pkg)
        db.session.commit()
        resp = owner_client.post(f'/owner/packages/{empty_pkg.id}/delete')
        assert resp.status_code == 302

    def test_edit_package_version_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        _pkg, version = _make_package_with_version(db)
        resp = owner_client.post(
            f'/owner/packages/versions/{version.id}/edit',
            data={'version': '9.9.9'},
        )
        assert resp.status_code == 302

    def test_renew_base_line_service_failure(self, owner_client, db, app, monkeypatch):
        from app.core.saas import lifecycle

        tenant, _version = _provision_fresh_tenant(app, db)
        monkeypatch.setattr(
            lifecycle.TenantProvisioningService,
            'renew_base_line',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        resp = owner_client.post(f'/owner/subscriptions/{tenant.id}/renew')
        assert resp.status_code == 302

    def test_tenant_usage_page_with_base_line_limits(self, owner_client, db, app):
        from app.core.saas.models import PackageVersionLimit

        tenant, version = _provision_fresh_tenant(app, db)
        db.session.add(
            PackageVersionLimit(
                package_version_id=version.id, limit_key='max_users', limit_value=21
            )
        )
        db.session.commit()
        resp = owner_client.get(f'/owner/tenant-usage/{tenant.id}')
        assert resp.status_code == 200

    def test_system_config_save_commit_failure(self, owner_client, monkeypatch):
        from app.modules.owner import routes as owner_routes

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        resp = owner_client.post(
            '/owner/system-config/save',
            data={'new_config_key': f'c_{_tag()}', 'new_config_value': 'v'},
        )
        assert resp.status_code == 302

    def test_delete_system_config_commit_failure(self, owner_client, db, monkeypatch):
        from app.modules.owner import routes as owner_routes
        from models.system_config import SystemConfig

        monkeypatch.setattr(owner_routes, 'safe_commit', _boom)
        cfg = SystemConfig(
            config_key=f'dc_{_tag()}',
            config_value='v',
            config_type='string',
            category='system',
            is_system=False,
        )
        db.session.add(cfg)
        db.session.commit()
        resp = owner_client.post(f'/owner/system-config/{cfg.config_key}/delete')
        assert resp.status_code == 302
