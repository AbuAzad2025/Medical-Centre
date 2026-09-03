"""Radiology bundles audit: standalone_radiology and radiology_with_reception.

Verifies both bundles coexist untouched and their flows work:
- standalone_radiology: radiology+billing+reporting, walk-in without visit allowed
- radiology_with_reception: reception+radiology+billing+appointments+reporting,
  reception->radiology transfer allowed, visit required when reception active
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.enums import TenantStatus
from tests.tenant_context import ensure_test_user, tenant_test_context


def _seed_bundles_if_empty():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


def _tenant_with_bundle(bundle_slug, app):
    _seed_bundles_if_empty()
    bundle = db.session.execute(select(ProductBundle).filter_by(slug=bundle_slug)).scalars().first()
    if not bundle:
        pytest.skip(f'Bundle {bundle_slug} not seeded')
    t = Tenant(
        slug=f'rad-{bundle_slug}-{datetime.now(UTC).timestamp()}',
        name=f'Rad {bundle_slug}',
        contact_email='test@local',
        status=TenantStatus.ACTIVE,
        product_profile_code=bundle_slug,
    )
    db.session.add(t)
    db.session.commit()
    for mod in bundle.get_modules():
        db.session.add(TenantModule(tenant_id=t.id, module_name=mod, is_active=True))
    db.session.commit()
    return t


def _make_dept(name, name_ar, tenant_id):
    from models.department import Department

    suf = uuid.uuid4().hex[:6]
    d = Department(
        name=f'{name}-{suf}', name_ar=f'{name_ar}-{suf}', is_active=True, tenant_id=tenant_id
    )
    db.session.add(d)
    db.session.commit()
    return d


class TestRadiologyBundleContents:
    def test_standalone_radiology_modules(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='standalone_radiology'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert bundle.get_modules() == ['radiology', 'billing', 'reporting']

    def test_radiology_with_reception_modules(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='radiology_with_reception'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert bundle.get_modules() == [
                'reception',
                'radiology',
                'billing',
                'appointments',
                'reporting',
            ]

    def test_both_radiology_bundles_coexist(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            slugs = db.session.execute(select(ProductBundle.slug)).scalars().all()
            assert 'standalone_radiology' in slugs
            assert 'radiology_with_reception' in slugs


class TestRadiologyBundleActivation:
    def test_radiology_allowed_in_both(self, app):
        for slug in ('standalone_radiology', 'radiology_with_reception'):
            t = _tenant_with_bundle(slug, app)
            with tenant_test_context(app, t):
                ok, err = can_activate_module(t.id, 'radiology')
                assert ok is True, f'radiology should be allowed in {slug}: {err}'

    def test_reception_only_in_with_reception(self, app):
        t_standalone = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t_standalone):
            ok, _ = can_activate_module(t_standalone.id, 'reception')
            assert ok is False
        t_with = _tenant_with_bundle('radiology_with_reception', app)
        with tenant_test_context(app, t_with):
            ok, _ = can_activate_module(t_with.id, 'reception')
            assert ok is True

    def test_pharmacy_blocked_in_radiology_bundles(self, app):
        for slug in ('standalone_radiology', 'radiology_with_reception'):
            t = _tenant_with_bundle(slug, app)
            with tenant_test_context(app, t):
                ok, err = can_activate_module(t.id, 'pharmacy')
                assert ok is False, f'pharmacy should be blocked in {slug}'
                assert 'not included' in (err or '').lower()


class TestRadiologyBundleFlows:
    def test_standalone_walkin_without_visit(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            tech = ensure_test_user(db, t, username=f'radwalk_{t.id}', role='radiology')
            from models.patient import Patient

            p = Patient(tenant_id=t.id, first_name='Rad', last_name='Walkin')
            db.session.add(p)
            db.session.commit()
            from services.radiology_service import radiology_service

            ok, result = radiology_service.create_request(
                visit_id=None,
                requested_by=tech.id,
                modality='XRay',
                body_part='Chest',
                tenant_id=t.id,
                patient_id=p.id,
            )
            assert ok is True, f'walk-in should work in standalone_radiology: {result}'

    def test_with_reception_requires_visit(self, app):
        t = _tenant_with_bundle('radiology_with_reception', app)
        with tenant_test_context(app, t):
            tech = ensure_test_user(db, t, username=f'radrec_{t.id}', role='radiology')
            from models.patient import Patient

            p = Patient(tenant_id=t.id, first_name='Rad', last_name='Rec')
            db.session.add(p)
            db.session.commit()
            from services.radiology_service import radiology_service

            ok, result = radiology_service.create_request(
                visit_id=None,
                requested_by=tech.id,
                modality='XRay',
                body_part='Chest',
                tenant_id=t.id,
                patient_id=p.id,
            )
            assert ok is False
            assert 'visit_id is required' in str(result.get('error', ''))

    def test_reception_to_radiology_transfer_allowed(self, app):
        from services.queue_management_service import QueueManagementService

        t = _tenant_with_bundle('radiology_with_reception', app)
        with tenant_test_context(app, t):
            from models.patient import Patient
            from models.visit import Visit

            recep_dept = _make_dept('ReceptionRad', 'استقبال أشعة', t.id)
            rad_dept = _make_dept('RadDept', 'أشعة قسم', t.id)
            p = Patient(tenant_id=t.id, first_name='Rad', last_name='Flow')
            db.session.add(p)
            db.session.commit()
            v = Visit(tenant_id=t.id, patient_id=p.id, department_id=recep_dept.id, status='OPEN')
            db.session.add(v)
            db.session.commit()
            recep = ensure_test_user(db, t, username=f'radflow_recep_{t.id}', role='reception')
            svc = QueueManagementService()
            ok, msg = svc.transfer_visit(
                v.id, rad_dept.id, transferred_by=recep.id, source='reception'
            )
            assert ok is True, f'reception->radiology should be allowed: {msg}'

    def test_radiology_dashboard_routing(self, app):
        t = _tenant_with_bundle('standalone_radiology', app)
        with tenant_test_context(app, t):
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='standalone_radiology'))
                .scalars()
                .first()
            )
            with app.test_request_context():
                from flask import g

                from services.dashboard_routing import resolve_dashboard_for_user

                g.enabled_modules = set(bundle.get_modules())
                tech = ensure_test_user(db, t, username=f'raddash_{t.id}', role='radiology')
                assert resolve_dashboard_for_user(tech) == 'radiology.dashboard'
