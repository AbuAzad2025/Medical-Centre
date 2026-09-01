"""Bundle Isolation Audit — tests whether each bundle actually runs without cross-module breakage."""

import pytest
from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import get_active_modules_for_tenant
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.dashboard_registry import resolve_dashboard_widgets
from app.shared.dashboard_service import _load_role_data
from app.shared.enums import TenantStatus
from services.dashboard_routing import resolve_dashboard_for_user
from tests.tenant_context import ensure_test_user, tenant_test_context


def _seed_bundles_if_empty():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


def _tenant_with_bundle(bundle_slug, app):
    _seed_bundles_if_empty()
    bundle = db.session.execute(select(ProductBundle).filter_by(slug=bundle_slug)).scalars().first()
    if not bundle:
        pytest.skip(f'Bundle {bundle_slug} not seeded')
    from datetime import UTC, datetime

    t = Tenant(
        slug=f'test-{bundle_slug}-{datetime.now(UTC).timestamp()}',
        name=f'Test {bundle_slug}',
        contact_email='test@local',
        status=TenantStatus.ACTIVE,
        product_profile_code=bundle_slug,
    )
    db.session.add(t)
    db.session.commit()
    # activate only this bundle's modules
    for mod in bundle.get_modules():
        db.session.add(TenantModule(tenant_id=t.id, module_name=mod, is_active=True))
    db.session.commit()
    return t


class TestStandalonePharmacyBundle:
    def test_pharmacy_dashboard_resolves(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='pharm', role='pharmacist')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint != 'main.package_restricted', f'pharmacist got restricted: {endpoint}'

    def test_pharmacy_data_loads_without_crashing(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='pharm2', role='pharmacist')
            data = _load_role_data('pharmacist', u)
            assert isinstance(data, dict)
            assert 'metrics' in data
            assert 'lists' in data

    def test_pharmacy_widgets_resolve(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            mods = get_active_modules_for_tenant(t.id)
            widgets = resolve_dashboard_widgets('pharmacist', mods)
            # Should have at least one widget; empty means layout is broken
            assert len(widgets) >= 1, (
                f'pharmacist widgets empty for standalone_pharmacy (mods={mods})'
            )


class TestStandaloneLabBundle:
    def test_lab_dashboard_resolves(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='labtech', role='lab')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint != 'main.package_restricted', f'lab got restricted: {endpoint}'

    def test_lab_data_loads_without_crashing(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='labtech2', role='lab')
            data = _load_role_data('lab', u)
            assert isinstance(data, dict)

    def test_lab_widgets_resolve(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            mods = get_active_modules_for_tenant(t.id)
            widgets = resolve_dashboard_widgets('lab', mods)
            assert len(widgets) >= 1, f'lab widgets empty for standalone_lab (mods={mods})'


class TestStandaloneRadiologyBundle:
    def test_radiology_dashboard_resolves(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='radtech', role='radiology')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint != 'main.package_restricted', f'radiology got restricted: {endpoint}'

    def test_radiology_data_loads_without_crashing(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='radtech2', role='radiology')
            data = _load_role_data('radiology', u)
            assert isinstance(data, dict)

    def test_radiology_widgets_resolve(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            mods = get_active_modules_for_tenant(t.id)
            widgets = resolve_dashboard_widgets('radiology', mods)
            assert len(widgets) >= 1, (
                f'radiology widgets empty for standalone_radiology (mods={mods})'
            )


class TestPrivateDoctorClinicBundle:
    def test_doctor_dashboard_resolves(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='doc', role='doctor')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint != 'main.package_restricted', f'doctor got restricted: {endpoint}'

    def test_doctor_data_loads_without_crashing(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='doc2', role='doctor')
            data = _load_role_data('doctor', u)
            assert isinstance(data, dict)

    def test_doctor_widgets_resolve(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            mods = get_active_modules_for_tenant(t.id)
            widgets = resolve_dashboard_widgets('doctor', mods)
            assert len(widgets) >= 1, (
                f'doctor widgets empty for private_doctor_clinic (mods={mods})'
            )


class TestCrossBundleBreakage:
    """Simulate a pharmacist in a lab-only tenant — should get restricted."""

    def test_pharmacist_in_lab_only_tenant_restricted(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='pharm_in_lab', role='pharmacist')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint == 'main.package_restricted', (
                f'pharmacist should be restricted in lab-only, got {endpoint}'
            )

    def test_doctor_in_pharmacy_only_tenant_restricted(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='doc_in_pharm', role='doctor')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint == 'main.package_restricted', (
                f'doctor should be restricted in pharmacy-only, got {endpoint}'
            )

    def test_lab_tech_in_radiology_only_tenant_restricted(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='lab_in_rad', role='lab')
            endpoint = resolve_dashboard_for_user(u)
            assert endpoint == 'main.package_restricted', (
                f'lab should be restricted in radiology-only, got {endpoint}'
            )
