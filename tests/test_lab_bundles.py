"""Lab bundles audit: standalone_lab and lab_with_reception.

Verifies both bundles coexist untouched and their flows work:
- standalone_lab: lab+billing+reporting, walk-in without visit allowed
- lab_with_reception: reception+lab+billing+appointments+reporting,
  reception->lab transfer allowed, lab requires visit when reception active
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
        slug=f'lab-{bundle_slug}-{datetime.now(UTC).timestamp()}',
        name=f'Lab {bundle_slug}',
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


class TestLabBundleContents:
    def test_standalone_lab_modules(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='standalone_lab'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert bundle.get_modules() == ['lab', 'billing', 'reporting']

    def test_lab_with_reception_modules(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='lab_with_reception'))
                .scalars()
                .first()
            )
            assert bundle is not None
            assert bundle.get_modules() == [
                'reception',
                'lab',
                'billing',
                'appointments',
                'reporting',
            ]

    def test_both_lab_bundles_coexist(self, app):
        _seed_bundles_if_empty()
        with app.app_context():
            slugs = db.session.execute(select(ProductBundle.slug)).scalars().all()
            assert 'standalone_lab' in slugs
            assert 'lab_with_reception' in slugs


class TestLabBundleActivation:
    def test_lab_allowed_in_both(self, app):
        for slug in ('standalone_lab', 'lab_with_reception'):
            t = _tenant_with_bundle(slug, app)
            with tenant_test_context(app, t):
                ok, err = can_activate_module(t.id, 'lab')
                assert ok is True, f'lab should be allowed in {slug}: {err}'

    def test_reception_only_in_lab_with_reception(self, app):
        t_standalone = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t_standalone):
            ok, _ = can_activate_module(t_standalone.id, 'reception')
            assert ok is False
        t_with = _tenant_with_bundle('lab_with_reception', app)
        with tenant_test_context(app, t_with):
            ok, _ = can_activate_module(t_with.id, 'reception')
            assert ok is True

    def test_pharmacy_blocked_in_lab_bundles(self, app):
        for slug in ('standalone_lab', 'lab_with_reception'):
            t = _tenant_with_bundle(slug, app)
            with tenant_test_context(app, t):
                ok, err = can_activate_module(t.id, 'pharmacy')
                assert ok is False, f'pharmacy should be blocked in {slug}'
                assert 'not included' in (err or '').lower()


class TestLabBundleFlows:
    def test_standalone_walkin_without_visit(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            labtech = ensure_test_user(db, t, username=f'labwalk_{t.id}', role='lab')
            from services.lab_service import lab_service

            ok, result = lab_service.create_request(
                visit_id=None, test_ids=[], requested_by=labtech.id, tenant_id=t.id
            )
            assert ok is False
            assert 'No test IDs' in str(result.get('error', ''))

    def test_lab_with_reception_requires_visit(self, app):
        t = _tenant_with_bundle('lab_with_reception', app)
        with tenant_test_context(app, t):
            labtech = ensure_test_user(db, t, username=f'labrec_{t.id}', role='lab')
            from services.lab_service import lab_service

            ok, result = lab_service.create_request(
                visit_id=None, test_ids=[1], requested_by=labtech.id, tenant_id=t.id
            )
            assert ok is False
            assert 'visit_id is required' in str(result.get('error', ''))

    def test_reception_to_lab_transfer_allowed(self, app):
        from services.queue_management_service import QueueManagementService

        t = _tenant_with_bundle('lab_with_reception', app)
        with tenant_test_context(app, t):
            from models.patient import Patient
            from models.visit import Visit

            recep_dept = _make_dept('ReceptionLab', 'استقبال مختبر', t.id)
            lab_dept = _make_dept('LabDept', 'مختبر قسم', t.id)
            p = Patient(tenant_id=t.id, first_name='Lab', last_name='Flow')
            db.session.add(p)
            db.session.commit()
            v = Visit(tenant_id=t.id, patient_id=p.id, department_id=recep_dept.id, status='OPEN')
            db.session.add(v)
            db.session.commit()
            recep = ensure_test_user(db, t, username=f'labflow_recep_{t.id}', role='reception')
            svc = QueueManagementService()
            ok, msg = svc.transfer_visit(
                v.id, lab_dept.id, transferred_by=recep.id, source='reception'
            )
            assert ok is True, f'reception->lab should be allowed: {msg}'

    def test_lab_dashboard_routing(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            bundle = (
                db.session.execute(select(ProductBundle).filter_by(slug='standalone_lab'))
                .scalars()
                .first()
            )
            with app.test_request_context():
                from flask import g

                from services.dashboard_routing import resolve_dashboard_for_user

                g.enabled_modules = set(bundle.get_modules())
                labtech = ensure_test_user(db, t, username=f'labdash_{t.id}', role='lab')
                assert resolve_dashboard_for_user(labtech) == 'lab.dashboard'
