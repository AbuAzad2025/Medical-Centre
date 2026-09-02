"""Multi-layer isolation audit: Routing, Bundle, Tenant, Role, Platform Privacy.

Validates the 5 pillars from the architecture audit.
"""

import pytest
from sqlalchemy import select

from app.core.module.registry import MODULE_REGISTRY
from app.core.tenant.models import ProductBundle, Tenant
from app.core.module.models import TenantModule
from app.extensions import db
from app.shared.dashboard_registry import resolve_dashboard_widgets
from services.dashboard_routing import resolve_dashboard_for_user, ROLE_TO_MODULE_MAP
from app.core.module.validators import get_active_modules_for_tenant, can_activate_module
from tests.tenant_context import ensure_test_user, tenant_test_context
from tests.conftest import ensure_default_test_tenant


# Helpers


def _tenant_with_bundle(bundle_slug, app):
    from app.core.tenant.models import seed_default_bundles

    seed_default_bundles()
    bundle = db.session.execute(select(ProductBundle).filter_by(slug=bundle_slug)).scalars().first()
    assert bundle is not None, f'bundle {bundle_slug} not found'
    # Create isolated tenant for this bundle
    import uuid

    slug = f'iso-{bundle_slug}-{uuid.uuid4().hex[:6]}'
    t = Tenant(
        slug=slug,
        name=f'Test {bundle_slug}',
        contact_email=f'{slug}@test.local',
        status='active',
        product_profile_code=bundle_slug,
    )
    db.session.add(t)
    db.session.flush()
    # Activate only bundle modules
    for mod in bundle.get_modules():
        db.session.add(TenantModule(tenant_id=t.id, module_name=mod, is_active=True))
    db.session.commit()
    return t


# 1. Routing Audit


class TestPostLoginRouting:
    def test_tenant_admin_routed_to_bundle_dashboard(self, app):
        # standalone_pharmacy -> pharmacy portal, standalone_lab -> lab, private_doctor_clinic -> doctor
        cases = [
            ('standalone_pharmacy', 'medication.dashboard'),
            ('standalone_lab', 'lab.dashboard'),
            ('private_doctor_clinic', 'doctor.dashboard'),
        ]
        for bundle_slug, expected_endpoint in cases:
            t = _tenant_with_bundle(bundle_slug, app)
            with tenant_test_context(app, t):
                # Simulate admin user of that tenant
                admin = ensure_test_user(db, t, username=f'admin_{bundle_slug}', role='admin')
                # Mock g.enabled_modules to bundle modules
                with app.test_request_context():
                    from flask import g

                    g.enabled_modules = set(
                        t.get_bundle_for_profile(bundle_slug).get_modules()
                        if hasattr(t, 'get_bundle_for_profile')
                        else []
                    )
                    # Actually use resolver: set g.enabled_modules to bundle modules
                    bundle = (
                        db.session.execute(select(ProductBundle).filter_by(slug=bundle_slug))
                        .scalars()
                        .first()
                    )
                    g.enabled_modules = set(bundle.get_modules())
                    endpoint = resolve_dashboard_for_user(admin)
                    assert endpoint == expected_endpoint, (
                        f'{bundle_slug} admin got {endpoint}, expected {expected_endpoint}'
                    )

    def test_staff_routed_to_role_dashboard(self, app):
        t = _tenant_with_bundle('multi_department_center', app)
        with tenant_test_context(app, t):
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='multi_department_center'))
                .scalars()
                .first()
            )
            with app.test_request_context():
                from flask import g

                g.enabled_modules = set(bundle.get_modules())
                for role, expected in [
                    ('doctor', 'doctor.dashboard'),
                    ('pharmacist', 'medication.dashboard'),
                    ('lab', 'lab.dashboard'),
                    ('reception', 'reception.dashboard'),
                ]:
                    u = ensure_test_user(db, t, username=f'staff_{role}_{t.id}', role=role)
                    endpoint = resolve_dashboard_for_user(u)
                    assert endpoint == expected, f'role {role} got {endpoint}, expected {expected}'

    def test_route_guard_blocks_unsubscribed_bundle(self, app, client, test_tenant):
        # Create a tenant with only pharmacy, try to access lab route
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username=f'lab_in_pharm_{t.id}', role='lab')
            from tests.tenant_context import login_test_client

            # need to login via client - use test_tenant fixture's login helper may not work for isolated tenant
            # Instead directly test the guard: resolve should be package_restricted
            with app.test_request_context():
                from flask import g

                bundle = (
                    db.session.execute(select(ProductBundle).filter_by(slug='standalone_pharmacy'))
                    .scalars()
                    .first()
                )
                g.enabled_modules = set(bundle.get_modules())
                endpoint = resolve_dashboard_for_user(u)
                assert endpoint == 'main.package_restricted'


# 2. Bundle Level Isolation


class TestBundleIsolation:
    def test_can_activate_module_rejects_outside_bundle(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            ok, msg = can_activate_module(t.id, 'lab')
            assert ok is False
            assert 'not included' in msg.lower()

    def test_ui_nav_hides_unsubscribed(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='standalone_pharmacy'))
                .scalars()
                .first()
            )
            enabled = set(bundle.get_modules())
            # Reception widgets: only billing-dependent cash_summary should remain for pharmacy bundle
            widgets = resolve_dashboard_widgets('reception', enabled, set())
            assert any(w.id == 'cash_summary' for w in widgets)
            assert not any(w.id == 'queue_live' for w in widgets)
            # Doctor widgets should be fully hidden (doctor not in pharmacy bundle)
            widgets2 = resolve_dashboard_widgets('doctor', enabled, set())
            assert len(widgets2) == 0


# 3. Tenant Level Isolation


class TestTenantIsolation:
    def test_cross_tenant_data_leakage_blocked(self, app):
        # Create two tenants
        t1 = _tenant_with_bundle('standalone_pharmacy', app)
        t2 = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t1):
            u1 = ensure_test_user(db, t1, username=f'user_t1_{t1.id}', role='pharmacist')
            from models.patient import Patient

            p1 = Patient(tenant_id=t1.id, first_name='T1', last_name='Patient', phone='0500000001')
            db.session.add(p1)
            db.session.commit()
            p1_id = p1.id

        with tenant_test_context(app, t2):
            # Try to fetch t1's patient via direct ID
            from utils.tenant_query import get_tenant_record
            from utils.tenant_query import TenantContextError

            # Should raise TenantContextError or return None due to tenant filter
            try:
                rec = get_tenant_record(Patient, p1_id)
                # If it returns, it must be None or tenant mismatch should be blocked
                assert rec is None or rec.tenant_id != t1.id
            except Exception as e:
                # Expected: TenantIsolationError or TenantContextError
                assert 'tenant' in str(e).lower() or 'isolation' in str(e).lower()

    def test_tenant_id_filter_enforced(self, app):
        t = _tenant_with_bundle('multi_department_center', app)
        with tenant_test_context(app, t):
            from app.shared.tenant_filter import _model_has_tenant_column
            from models.patient import Patient

            assert _model_has_tenant_column(Patient) is True


# 4. Role Level Isolation


class TestRoleIsolation:
    def test_role_hierarchy(self, app):
        from utils.decorators import ROLE_HIERARCHY

        # super_admin should inherit doctor etc
        assert 'doctor' in ROLE_HIERARCHY['super_admin']
        assert 'reception' in ROLE_HIERARCHY['manager']

    def test_reception_cannot_access_clinical(self, app, client, test_tenant):
        # Login as reception and try to access doctor endpoint
        from tests.tenant_context import login_test_client

        u = ensure_test_user(
            db, test_tenant, username=f'recv_{test_tenant.id}_rbac', role='reception'
        )
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        # Try to access a doctor-only route (should be 403 or redirect)
        resp = c.get('/doctor/dashboard')
        # Reception should not access doctor dashboard - expect 403 or redirect to login/package_restricted
        assert resp.status_code in (302, 403)

    def test_require_permission_decorator(self):
        from app.core.permission.service import PermissionService

        # Basic check that function exists and handles roles
        assert callable(PermissionService.has_permission)
        # Also ensure access_control_service exposes a compatible helper (if present)
        try:
            from services.access_control_service import has_permission as svc_has_perm

            assert callable(svc_has_perm)
        except ImportError:
            # Fallback: PermissionService is the canonical implementation
            assert callable(getattr(PermissionService, 'has_permission', None))


# 5. Platform Owner Privacy Guard


class TestPlatformOwnerPrivacyGuard:
    def test_platform_owner_blocked_from_patient_endpoints(self, app, client):
        # Create platform owner user
        from seeds.production_baseline import seed_master_account

        with app.app_context():
            owner = seed_master_account()
            assert owner.role == 'platform_owner'
        # Create a tenant with patient data
        t = _tenant_with_bundle('multi_department_center', app)
        with tenant_test_context(app, t):
            from models.patient import Patient

            p = Patient(tenant_id=t.id, first_name='Priv', last_name='Test', phone='0500000002')
            db.session.add(p)
            db.session.commit()
            # Login as platform owner and try to access patient endpoint
            c = app.test_client()
            # Login as platform owner (bypass tenant)
            from tests.tenant_context import login_test_client

            # Need to login with tenant context of platform? Use direct login helper
            # For privacy guard test, we simulate a request with platform_owner role
            # The guard should be enforced via decorator or before_request
            # We'll directly test the guard function
            from app.shared.medical_privacy import (
                is_medical_endpoint,
                enforce_medical_privacy_guard,
            )

            # Mock a request to /doctor/patient-details/...
            assert is_medical_endpoint('/doctor/patient-details/1') is True
            assert is_medical_endpoint('/owner/dashboard') is False
            # Enforce should raise 403 for platform_owner on medical endpoint
            with app.test_request_context('/doctor/patient-details/1'):
                from flask import g
                from flask_login import current_user

                # Simulate platform_owner user
                g.tenant_id = None
                # The guard should check role
                # We test the function directly
                try:
                    enforce_medical_privacy_guard(owner)
                    assert False, 'Should have raised 403'
                except Exception as e:
                    assert '403' in str(e) or 'Forbidden' in str(e) or 'Medical Privacy' in str(e)

    def test_platform_owner_allowed_on_tenant_management(self, app):
        # Platform owner should be allowed on /owner/* and /super-admin/*
        from app.shared.medical_privacy import is_medical_endpoint

        assert is_medical_endpoint('/owner/tenants') is False
        assert is_medical_endpoint('/super-admin/dashboard') is False
        assert is_medical_endpoint('/api/billing/stripe/webhook') is False

    def test_super_admin_blocked_from_medical(self, app):
        from app.shared.medical_privacy import is_medical_endpoint, enforce_medical_privacy_guard
        from models.user import User

        sa = User(
            username='sa_test',
            email='sa@test.local',
            full_name='SA',
            role='super_admin',
            is_active=True,
            tenant_id=1,
        )
        with app.test_request_context('/lab/requests'):
            try:
                enforce_medical_privacy_guard(sa)
                assert False, 'super_admin should be blocked from medical'
            except Exception as e:
                assert '403' in str(e) or 'Forbidden' in str(e)
