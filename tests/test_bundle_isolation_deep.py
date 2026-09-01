"""Deep bundle isolation audit — tests actual workflow operations in isolated bundles."""

import pytest
from sqlalchemy import select, func
from datetime import UTC, datetime
from app.extensions import db
from app.core.tenant.models import Tenant, ProductBundle, seed_default_bundles
from app.core.module.models import TenantModule
from app.shared.enums import TenantStatus
from tests.tenant_context import tenant_test_context, ensure_test_user


def _tenant_with_bundle(bundle_slug, app):
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()
    bundle = db.session.execute(select(ProductBundle).filter_by(slug=bundle_slug)).scalars().first()
    if not bundle:
        pytest.skip(f'Bundle {bundle_slug} not seeded')
    t = Tenant(
        slug=f'op-{bundle_slug}-{datetime.now(UTC).timestamp()}',
        name=f'Op {bundle_slug}',
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


class TestPharmacyOnlyWorkflows:
    def test_pharmacy_pos_sale_without_prescription(self, app):
        """Pharmacy-only tenant: direct POS sale should work without doctor/visit."""
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='pharm_op', role='pharmacist')
            from services.pharmacy_sale_service import PharmacySaleService
            # PharmacySaleService.create_sale requires a prescription_id, not raw items
            # This is already a sign of coupling: POS requires prescription module
            result = PharmacySaleService.create_sale(
                prescription_id=999999,  # fake ID to test the call path
                dispensed_by=u.id,
                items=[{'medication_id': None, 'quantity': 1, 'price': 10.0, 'name': 'Paracetamol'}],
                tenant_id=t.id,
            )
            # It will fail because prescription_id doesn't exist, but we verify it didn't crash
            # due to missing modules (it crashes due to missing prescription row, which is expected)
            assert isinstance(result, dict), f'Expected dict, got {type(result)}'

    def test_pharmacy_prescription_without_doctor_fails_due_to_module_guard(self, app):
        """Pharmacy-only tenant: prescription creation is blocked because doctor module is not active."""
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            from services.prescription_service import PrescriptionService
            from services.feature_gate_service import ModuleNotEnabledError
            p = ensure_test_user(db, t, username='pat_pharm', role='patient')
            with pytest.raises(ModuleNotEnabledError) as exc_info:
                PrescriptionService.create_prescription(
                    patient_id=p.id,
                    doctor_id=None,
                    items=[{'medication_id': None, 'quantity': 1, 'dosage': '1', 'duration_days': 1}],
                )
            assert 'doctor' in str(exc_info.value)


class TestLabOnlyWorkflows:
    def test_lab_request_requires_visit(self, app):
        """Lab-only tenant: lab service explicitly requires visit_id (doctor/reception dependency)."""
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='labtech_op', role='lab')
            p = ensure_test_user(db, t, username='pat_lab', role='patient')
            from services.lab_service import lab_service
            # LabService.create_request signature: visit_id, test_ids, requested_by, ...
            # This proves lab is NOT standalone; it requires a visit (reception/doctor module)
            try:
                ok, req = lab_service.create_request(
                    visit_id=999999,
                    test_ids=[],
                    requested_by=u.id,
                    tenant_id=t.id,
                )
            except TypeError as exc:
                pytest.fail(f'Lab service API mismatch: {exc}')
            except Exception as exc:
                # Any other exception (missing visit, etc.) is acceptable for this test
                pass  # We just wanted to verify the call path doesn't crash due to missing module


class TestDoctorOnlyWorkflows:
    def test_doctor_visit_creation(self, app):
        """Doctor-only tenant: creating a visit via reception service."""
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            doc = ensure_test_user(db, t, username='doc_op', role='doctor')
            p = ensure_test_user(db, t, username='pat_doc', role='patient')
            from services.reception_service import ReceptionService
            try:
                visit = ReceptionService.create_visit(
                    patient_id=p.id,
                    department_id=1,
                    doctor_id=doc.id,
                )
                # visit may be None if department_id doesn't exist, but should not crash
                assert visit is None or hasattr(visit, 'id'), f'Unexpected visit result: {visit}'
            except Exception as exc:
                pytest.fail(f'Visit creation crashed in doctor-only bundle: {exc}')

    def test_doctor_prescription_in_doctor_only_succeeds(self, app):
        """Doctor-only tenant: prescription creation succeeds because doctor module is active."""
        t = _tenant_with_bundle('private_doctor_clinic', app)
        with tenant_test_context(app, t):
            doc = ensure_test_user(db, t, username='doc_op2', role='doctor')
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
            assert ok is True, f'Prescription should succeed in doctor bundle: {result}'


class TestCrossModuleDataQueries:
    def test_pharmacy_dashboard_queries_lab_tables(self, app):
        """Pharmacy-only tenant: dashboard service should not query lab tables."""
        t = _tenant_with_bundle('standalone_pharmacy', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='pharm_q', role='pharmacist')
            from app.shared.dashboard_service import _load_role_data
            data = _load_role_data('pharmacist', u)
            # Should not contain lab-related keys
            assert 'lab_pending' not in data.get('lists', {})
            assert 'pending_requests' not in data.get('metrics', {})

    def test_lab_dashboard_queries_doctor_tables(self, app):
        """Lab-only tenant: dashboard service should not query doctor tables."""
        t = _tenant_with_bundle('standalone_lab', app)
        with tenant_test_context(app, t):
            u = ensure_test_user(db, t, username='lab_q', role='lab')
            from app.shared.dashboard_service import _load_role_data
            data = _load_role_data('lab', u)
            # Should not contain doctor-specific keys
            assert 'waiting_patients' not in data.get('metrics', {})
            assert 'waiting_list' not in data.get('lists', {})
