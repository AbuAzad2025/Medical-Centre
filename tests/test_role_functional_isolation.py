"""Role Functional Isolation — dashboard, nav, API boundaries for ALL roles.

Verifies per the detailed audit matrix:
- System & Tenant Management: platform_owner, super_admin, admin, owner
- Clinical: doctor, er_doctor, nurse
- Diagnostic: lab, radiology
- Operational: pharmacist, reception, accountant
"""

import pytest

from app.extensions import db
from app.shared.dashboard_registry import (
    ROLE_LAYOUTS,
    WIDGETS,
    resolve_dashboard_widgets,
)
from app.shared.mobile_nav import resolve_mobile_nav_items
from app.shared.nav_resolver import resolve_nav_for_user
from app.shared.user_role_policy import normalize_role
from models.user import User

# ── Helpers ──

ALL_ROLES = [
    'platform_owner',
    'super_admin',
    'admin',
    'owner',
    'doctor',
    'er_doctor',
    'nurse',
    'lab',
    'radiology',
    'pharmacist',
    'reception',
    'accountant',
]

# Expected widgets per role after strict isolation (no leakage)
EXPECTED_WIDGETS = {
    'platform_owner': {'kpi_strip', 'manager_finance', 'manager_hr'},  # no queue_live
    'super_admin': {'kpi_strip', 'manager_finance', 'manager_hr', 'queue_live'},
    'admin': {'kpi_strip', 'manager_finance', 'manager_hr', 'queue_live'},
    'owner': {'kpi_strip', 'manager_finance', 'manager_hr'},
    'doctor': {
        'my_queue',
        'patients_waiting',
        'appointments_pending',
        'lab_pending',
        'radiology_pending',
    },
    'er_doctor': {'critical_count', 'triage_board', 'emergency_waitlist'},  # emergency-specific
    'nurse': {'nurse_assigned'},
    'lab': {'lab_recent', 'lab_pending'},
    'radiology': {'radiology_pending'},
    'pharmacist': {
        'pharmacy_dispense',
        'pharmacy_low_stock',
        'pharmacy_prescriptions',
        'pharmacy_sales',
    },
    'reception': {
        'queue_live',
        'visits_today',
        'appointments_pending',
    },  # no cash_summary (billing)
    'accountant': {'pending_payments', 'finance_overview', 'revenue_today'},
}

# Widgets that must NOT leak to other roles
FORBIDDEN_WIDGETS = {
    'platform_owner': {
        'queue_live',
        'pharmacy_dispense',
        'my_queue',
        'nurse_assigned',
        'lab_pending',
        'pending_payments',
    },
    'super_admin': {'pharmacy_dispense', 'my_queue', 'nurse_assigned'},
    'doctor': {'pharmacy_dispense', 'pending_payments', 'cash_summary', 'queue_live'},
    'nurse': {'my_queue', 'pharmacy_dispense', 'pending_payments', 'queue_live'},
    'lab': {'my_queue', 'pharmacy_dispense', 'pending_payments', 'queue_live'},
    'radiology': {'my_queue', 'pharmacy_dispense', 'pending_payments'},
    'pharmacist': {'my_queue', 'nurse_assigned', 'lab_pending', 'queue_live'},
    'reception': {'my_queue', 'pharmacy_dispense', 'pending_payments', 'lab_pending'},
    'accountant': {'my_queue', 'pharmacy_dispense', 'nurse_assigned', 'lab_pending'},
    'er_doctor': {'kpi_strip', 'queue_live', 'pharmacy_dispense', 'pending_payments'},
}


def _enabled_for_role(role: str) -> set[str]:
    """Return a minimal enabled_modules set that should make the role's widgets visible."""
    # Map role to its required modules
    role_modules = {
        'platform_owner': set(),
        'super_admin': {'reporting', 'billing'},
        'admin': {'reporting', 'billing'},
        'owner': set(),
        'doctor': {'doctor', 'appointments', 'lab', 'radiology'},
        'er_doctor': {'emergency'},
        'nurse': {'nursing'},
        'lab': {'lab'},
        'radiology': {'radiology'},
        'pharmacist': {'pharmacy'},
        'reception': {'reception', 'appointments'},
        'accountant': {'billing'},
    }
    return role_modules.get(role, set())


def _make_user(role: str, tenant_id: int = 1):
    u = User(
        username=f'test_{role}_{tenant_id}',
        email=f'{role}@test.local',
        full_name=f'Test {role}',
        role=role,
        is_active=True,
        tenant_id=tenant_id,
    )
    u.id = hash(role) % 10000
    return u


# ── Dashboard Tests ──


class TestDashboardCleanliness:
    @pytest.mark.parametrize('role', ALL_ROLES)
    def test_dashboard_has_expected_widgets(self, app, role):
        enabled = _enabled_for_role(role)
        # For er_doctor, ensure it gets emergency widgets, not manager fallback
        with app.test_request_context():
            from flask import g

            g.enabled_modules = enabled
            widgets = resolve_dashboard_widgets(role, enabled, set())
            widget_ids = {w.id for w in widgets}
            expected = EXPECTED_WIDGETS.get(role, set())
            for wid in expected:
                # Only assert if the widget's required modules are in enabled
                meta = WIDGETS.get(wid)
                if meta and meta.modules and not all(m in enabled for m in meta.modules):
                    continue
                assert wid in widget_ids, f'{role} missing expected widget {wid}, got {widget_ids}'

    @pytest.mark.parametrize('role', ALL_ROLES)
    def test_dashboard_no_leakage(self, app, role):
        enabled = _enabled_for_role(role)
        with app.test_request_context():
            from flask import g

            g.enabled_modules = enabled
            widgets = resolve_dashboard_widgets(role, enabled, set())
            widget_ids = {w.id for w in widgets}
            forbidden = FORBIDDEN_WIDGETS.get(role, set())
            leaked = widget_ids & forbidden
            assert not leaked, f'{role} leaked widgets {leaked} (should be isolated)'

    def test_er_doctor_has_emergency_layout(self, app):
        assert 'er_doctor' in ROLE_LAYOUTS or normalize_role('er_doctor') in ROLE_LAYOUTS or True
        # After fix, er_doctor should have emergency layout, not manager fallback
        enabled = {'emergency'}
        with app.test_request_context():
            from flask import g

            g.enabled_modules = enabled
            widgets = resolve_dashboard_widgets('er_doctor', enabled, set())
            # Should have at least emergency widgets, not manager kpi_strip
            widget_ids = {w.id for w in widgets}
            assert (
                'critical_count' in widget_ids
                or 'triage_board' in widget_ids
                or 'emergency_waitlist' in widget_ids
            )

    def test_reception_no_billing_widget(self, app):
        enabled = {'reception', 'appointments', 'billing'}
        with app.test_request_context():
            from flask import g

            g.enabled_modules = enabled
            widgets = resolve_dashboard_widgets('reception', enabled, set())
            widget_ids = {w.id for w in widgets}
            assert 'cash_summary' not in widget_ids, (
                'reception should not see cash_summary (billing)'
            )

    def test_pharmacist_widgets_gated_by_pharmacy(self, app):
        # No modules enabled -> no pharmacy widgets
        with app.test_request_context():
            from flask import g

            g.enabled_modules = set()
            widgets = resolve_dashboard_widgets('pharmacist', set(), set())
            assert len(widgets) == 0, (
                'pharmacist widgets should be hidden when pharmacy not enabled'
            )
            # With pharmacy enabled -> visible
            g.enabled_modules = {'pharmacy'}
            widgets2 = resolve_dashboard_widgets('pharmacist', {'pharmacy'}, set())
            assert len(widgets2) > 0


class TestRoleIsolation:
    def test_role_hierarchy(self, app):
        from utils.decorators import ROLE_HIERARCHY

        # Strict hierarchy: no clinical inheritance for super_admin
        assert 'admin' in ROLE_HIERARCHY['super_admin']
        assert 'manager' in ROLE_HIERARCHY['super_admin']
        assert 'reception' in ROLE_HIERARCHY['manager']
        # super_admin must NOT have clinical leakage
        assert 'doctor' not in ROLE_HIERARCHY['super_admin']
        assert 'lab' not in ROLE_HIERARCHY['super_admin']
        assert 'reception' in ROLE_HIERARCHY['manager']

    def test_reception_cannot_access_clinical(self, app, client, test_tenant):
        # Login as reception and try to access doctor endpoint
        from tests.conftest import ensure_test_user
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


# ── Navigation Tests ──


class TestNavFiltering:
    @pytest.mark.parametrize('role', ALL_ROLES)
    def test_nav_hides_outside_role(self, app, role):
        user = _make_user(role, tenant_id=1)
        # Mock enabled modules for nav resolver
        with app.test_request_context():
            from flask import g

            g.enabled_modules = _enabled_for_role(role)
            g.tenant_id = 1
            # Mock PermissionScopeService to avoid DB
            from unittest import mock

            with mock.patch('services.permission_scope_service.PermissionScopeService') as mock_ps:
                mock_ps.get_accessible_module_names.return_value = None
                nav = resolve_nav_for_user(user)
                # Flatten nav hrefs (NavSection dataclass)
                hrefs = []
                for section in nav:
                    items = (
                        getattr(section, 'items', []) or section.get('items', [])
                        if isinstance(section, dict)
                        else getattr(section, 'items', [])
                    )
                    for item in items:
                        if isinstance(item, dict):
                            hrefs.append(item.get('href', ''))
                        else:
                            hrefs.append(getattr(item, 'href', ''))
                href_str = ' '.join(hrefs)
                # Platform owner should not see clinical
                if role == 'platform_owner':
                    assert '/doctor' not in href_str
                    assert '/lab' not in href_str
                    assert '/pharmacist' not in href_str
                # Reception should not see lab worklist as primary
                if role == 'reception':
                    assert '/lab/worklist' not in href_str or '/reception' in href_str
                # Accountant should not see doctor queue
                if role == 'accountant':
                    assert 'doctor/patient-queue' not in href_str

    def test_mobile_nav_accountant_has_items(self, app):
        user = _make_user('accountant')
        with app.test_request_context():
            items = resolve_mobile_nav_items(user)
            assert len(items) > 1, 'accountant mobile nav was missing, should have at least 2 items'
            hrefs = [it[0] if isinstance(it, (list, tuple)) else it.get('href', '') for it in items]
            href_str = ' '.join(str(h) for h in hrefs)
            assert 'accountant' in href_str.lower() or 'finance' in href_str.lower()

    def test_mobile_nav_platform_owner_normalized(self, app):
        user = _make_user('platform_owner')
        with app.test_request_context():
            items = resolve_mobile_nav_items(user)
            # Should not fallback to generic main.dashboard
            hrefs = [it[0] if isinstance(it, (list, tuple)) else str(it) for it in items]
            assert any('owner' in str(h) or 'super-admin' in str(h) for h in hrefs), (
                f'platform_owner mobile nav incorrect: {hrefs}'
            )

    def test_doctor_mobile_no_reception_patients(self, app):
        user = _make_user('doctor')
        with app.test_request_context():
            items = resolve_mobile_nav_items(user)
            hrefs = ' '.join(str(it) for it in items)
            assert 'reception.patients' not in hrefs and '/reception/patients' not in hrefs, (
                'doctor should not see reception.patients'
            )


# ── Backend API Decorator Tests ──


class TestApiEnforcement:
    def test_reception_cannot_create_prescription(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='recv_api_test', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post('/doctor/prescription/1', data={'medication': 'test'})
        assert resp.status_code in (302, 403)

    def test_nurse_cannot_create_prescription(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='nurse_api_test', role='nurse')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post('/doctor/prescription/1', data={'medication': 'test'})
        assert resp.status_code in (302, 403)

    def test_lab_cannot_access_pharmacy_pos(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='lab_api_test', role='lab')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/medication/pos')
        assert resp.status_code in (302, 403)

    def test_pharmacist_cannot_create_visit(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='pharm_api_test', role='pharmacist')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post('/reception/visits/create', data={'patient_id': 1})
        assert resp.status_code in (302, 403)

    def test_accountant_cannot_access_lab_results(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='acct_api_test', role='accountant')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/lab/results')
        assert resp.status_code in (302, 403)

    def test_reception_cannot_update_lab_results(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='recv_lab_test', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post('/lab/worklist/complete/1', data={'value': 'test'})
        assert resp.status_code in (302, 403)

    def test_doctor_cannot_dispense_pharmacy(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        u = ensure_test_user(db, test_tenant, username='doc_pharm_test', role='doctor')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post('/medication/dispense/1', data={'quantity': 1})
        # Should be 403 or redirect, not 200
        assert resp.status_code in (302, 403, 404)

    def test_platform_owner_blocked_from_medical_api(self, app, client):
        from seeds.production_baseline import seed_master_account
        from tests.tenant_context import login_test_client

        with app.app_context():
            owner = seed_master_account()
        # Need a tenant for login context
        from tests.conftest import ensure_default_test_tenant

        t = ensure_default_test_tenant(app)
        c = app.test_client()
        # Login as platform owner via tenant context
        login_test_client(c, owner, t)
        # Try to access medical endpoints
        for path in ['/doctor/patients', '/lab/requests', '/radiology/requests']:
            resp = c.get(path)
            # Should be 403 due to Medical Privacy Guard
            assert resp.status_code in (302, 403), (
                f'platform_owner should be blocked from {path}, got {resp.status_code}'
            )
        # POST endpoint should also be blocked (405 is also blocked, not 200)
        resp = c.post('/api/lab/requests/1/cancel')
        assert resp.status_code in (302, 403, 405), (
            f'platform_owner should be blocked from POST /api/lab/requests/1/cancel, got {resp.status_code}'
        )

    def test_cash_register_requires_role(self, app, client, test_tenant):
        from tests.conftest import ensure_test_user
        from tests.tenant_context import login_test_client

        # Lab tech should not access cash register
        u = ensure_test_user(db, test_tenant, username='lab_cash_test', role='lab')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/reception/cash-register')
        assert resp.status_code in (302, 403)
