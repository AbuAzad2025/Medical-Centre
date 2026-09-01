"""Dynamic bundle isolation validation tests."""

import pytest
from sqlalchemy import func, select

from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module
from app.core.tenant.models import (
    ProductBundle,
    Tenant,
    seed_default_bundles,
)
from app.extensions import db
from app.shared.enums import TenantStatus
from services.feature_gate_service import FeatureGateService, ModuleNotEnabledError
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
        slug=f'iso-{bundle_slug}-{datetime.now(UTC).timestamp()}',
        name=f'Iso {bundle_slug}',
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


class TestCanActivateModuleEnforcesBundleBoundaries:
    def test_module_in_bundle_allowed(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            ok, err = can_activate_module(t.id, 'pharmacy')
            assert ok is True, f'pharmacy should be allowed in standalone_pharmacy: {err}'

    def test_module_outside_bundle_blocked(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            ok, err = can_activate_module(t.id, 'lab')
            assert ok is False, 'lab should be blocked in standalone_pharmacy bundle'
            assert 'not included' in (err or '').lower()

    def test_module_outside_bundle_blocked_for_doctor_clinic(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            ok, err = can_activate_module(t.id, 'pharmacy')
            assert ok is False, 'pharmacy should be blocked in private_doctor_clinic bundle'
            assert 'not included' in (err or '').lower()

    def test_module_already_active_short_circuits(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            ok, _err = can_activate_module(t.id, 'pharmacy')
            assert ok is True


class TestPrescriptionServiceDynamicModule:
    def test_doctor_can_create_prescription_in_doctor_bundle(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            doc = ensure_test_user(db, t, username='doc_iso', role='doctor')
            from models.patient import Patient

            p = Patient(first_name='ع', last_name='م', tenant_id=t.id)
            db.session.add(p)
            db.session.commit()
            from services.prescription_service import PrescriptionService

            ok, result = PrescriptionService.create_prescription(
                patient_id=p.id,
                doctor_id=doc.id,
                items=[{'medication_id': None, 'quantity': 1, 'dosage': '1', 'duration_days': 1}],
            )
            assert ok is True, f'Prescription should work in doctor bundle: {result}'

    def test_doctor_blocked_when_pharmacy_bundle_only(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            doc = ensure_test_user(db, t, username='doc_iso2', role='doctor')
            p = ensure_test_user(db, t, username='pat_iso2', role='patient')
            from services.prescription_service import PrescriptionService

            # doctor module is not active in standalone_pharmacy bundle
            with pytest.raises(ModuleNotEnabledError) as exc_info:
                PrescriptionService.create_prescription(
                    patient_id=p.id,
                    doctor_id=doc.id,
                    items=[
                        {'medication_id': None, 'quantity': 1, 'dosage': '1', 'duration_days': 1}
                    ],
                )
            assert 'doctor' in str(exc_info.value)


class TestLabServiceDynamicVisit:
    def test_lab_walkin_without_visit_in_standalone_lab(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            labtech = ensure_test_user(db, t, username='lab_iso', role='lab')
            from services.lab_service import lab_service

            ok, result = lab_service.create_request(
                visit_id=None,
                test_ids=[],
                requested_by=labtech.id,
                tenant_id=t.id,
            )
            assert ok is False, 'Empty test_ids should fail, but not crash'
            assert 'No test IDs' in str(result.get('error', ''))

    def test_lab_requires_visit_when_doctor_active(self, app):
        t = _tenant_with_bundle('clinic_with_lab', app)
        with tenant_test_context(app, t):
            labtech = ensure_test_user(db, t, username='lab_iso2', role='lab')
            from services.lab_service import lab_service

            ok, result = lab_service.create_request(
                visit_id=None,
                test_ids=[1],
                requested_by=labtech.id,
                tenant_id=t.id,
            )
            assert ok is False
            assert 'visit_id is required' in str(result.get('error', ''))


class TestPharmacySaleServiceDirectSale:
    def test_direct_sale_in_standalone_pharmacy(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            pharm = ensure_test_user(db, t, username='pharm_iso', role='pharmacist')
            from services.pharmacy_sale_service import PharmacySaleService

            result = PharmacySaleService.create_direct_sale(
                patient_id=None,
                dispensed_by=pharm.id,
                items=[
                    {'medication_id': None, 'quantity': 1, 'price': 10.0, 'name': 'Paracetamol'}
                ],
                tenant_id=t.id,
            )
            # May fail because medication_id None, but should not crash on missing prescription module
            assert isinstance(result, dict), f'Expected dict, got {type(result)}'


class TestDashboardServiceDynamicFiltering:
    def test_pharmacy_dashboard_does_not_query_lab(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            pharm = ensure_test_user(db, t, username='pharm_dash', role='pharmacist')
            from app.shared.dashboard_service import _load_role_data

            data = _load_role_data('pharmacist', pharm)
            assert 'pending_lab' not in data.get('lists', {})
            assert 'pending_radiology' not in data.get('lists', {})

    def test_lab_dashboard_does_not_query_doctor(self, app):
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            labtech = ensure_test_user(db, t, username='lab_dash', role='lab')
            from app.shared.dashboard_service import _load_role_data

            data = _load_role_data('lab', labtech)
            assert 'waiting_patients' not in data.get('metrics', {})
            assert 'waiting_list' not in data.get('lists', {})


class TestFeatureGateServiceModuleEnabled:
    def test_module_enabled_reflects_bundle(self, app):
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            assert FeatureGateService.module_enabled(t.id, 'pharmacy') is True
            assert FeatureGateService.module_enabled(t.id, 'lab') is False
            assert FeatureGateService.module_enabled(t.id, 'doctor') is False

    def test_module_enabled_reflects_doctor_bundle(self, app):
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            assert FeatureGateService.module_enabled(t.id, 'doctor') is True
            assert FeatureGateService.module_enabled(t.id, 'pharmacy') is False
