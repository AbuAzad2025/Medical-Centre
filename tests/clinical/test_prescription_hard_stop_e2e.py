"""
E2E Clinical Safety Hard-Stop Integration Tests
Validates that PrescriptionService.create_prescription() blocks hazardous
orders via ClinicalSafetyService unless head_physician override is supplied.

Requirements:
  - PostgreSQL test database (not SQLite) for full ORM compatibility
  - Seeded PatientAllergy, DrugInteraction, Medication, PatientProblem tables
"""
import os
import sys
import pytest

# Force testing env before any imports
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-validation-only-32chars')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://postgres:123@localhost:5432/medical_test')
os.environ.setdefault('SUPPRESS_DEPRECATION_WARNINGS', '1')
os.environ.setdefault('SUPPRESS_LOGGING', '1')
os.environ.setdefault('SKIP_PLATFORM_BOOTSTRAP', '1')
os.environ.setdefault('RLS_BYPASS_ALLOWED', '1')
os.environ['ENABLE_SAAS_MODE'] = 'false'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import g
from app_factory import create_app, db
from models.patient import Patient, PatientAllergy
from models.medication import Medication, Prescription, PrescriptionItem
from models.drug_interaction import DrugInteraction
from models.problem_list import PatientProblem
from models.user import User
from models.tenant import Tenant
from services.prescription_service import PrescriptionService
from services.clinical_safety_service import ClinicalSafetyService, SafetyCheckSeverity
from app.extensions import db
from sqlalchemy import select
from sqlalchemy import select


@pytest.fixture(scope='module')
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        # Create default tenant with id=1
        from models.tenant import Tenant
        tenant = db.session.execute(select(Tenant).filter_by(id=1)).scalars().first()
        if not tenant:
            tenant = Tenant(
                id=1,
                slug='test-tenant',
                name='Test Tenant',
                contact_email='test@test.local',
                status='active',
                product_profile_code='multi_department_center',
            )
            db.session.add(tenant)
            db.session.commit()
        yield app
        db.session.remove()
        try:
            db.drop_all()
        except Exception as e:
            pass


@pytest.fixture(scope='function')
def rollback_db(app):
    """Transactional isolation: every write is rolled back after the test."""
    from flask_sqlalchemy.session import Session as _FSASession
    connection = db.engine.connect()
    transaction = connection.begin()
    db.session.remove()
    _original_get_bind = _FSASession.get_bind
    _FSASession.get_bind = lambda self, *a, **k: connection
    db.session.configure(join_transaction_mode='create_savepoint')
    try:
        yield db
    finally:
        _FSASession.get_bind = _original_get_bind
        db.session.remove()
        try:
            transaction.rollback()
        finally:
            connection.close()
            db.session.configure(join_transaction_mode='conditional_savepoint')


@pytest.fixture(scope='function')
def test_patient(app, rollback_db):
    g.tenant_id = 1
    g._tenant_filter_bypass = True
    db.session.info['_tenant_id'] = 1
    p = Patient(
        first_name='Test', last_name='Patient',
        phone='0501234567', gender='M',
        tenant_id=1,
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture(scope='function')
def test_doctor(app, rollback_db):
    g.tenant_id = 1
    g._tenant_filter_bypass = True
    db.session.info['_tenant_id'] = 1
    # Clean up any leftover doctor from a prior aborted fixture
    from sqlalchemy import delete
    db.session.execute(delete(User).filter_by(username='dr_test', tenant_id=1))
    db.session.commit()
    d = User(
        username='dr_test', email='dr@test.local',
        full_name='Dr Test', role='doctor', is_active=True,
        tenant_id=1,
    )
    d.set_password('ValidPass123!@#')
    db.session.add(d)
    db.session.commit()
    return d


@pytest.fixture(scope='function')
def test_medications(app, rollback_db):
    g.tenant_id = 1
    g._tenant_filter_bypass = True
    db.session.info['_tenant_id'] = 1
    meds = {
        'amoxicillin': Medication(
            trade_name='Amoxicillin', scientific_name='Amoxicillin',
            dosage_form='tablet', strength='500mg',
            price=10.0, stock_quantity=100, minimum_stock=10,
            tenant_id=1,
        ),
        'warfarin': Medication(
            trade_name='Warfarin', scientific_name='Warfarin',
            dosage_form='tablet', strength='5mg',
            price=20.0, stock_quantity=50, minimum_stock=5,
            tenant_id=1,
        ),
        'isotretinoin': Medication(
            trade_name='Isotretinoin', scientific_name='Isotretinoin',
            dosage_form='capsule', strength='20mg',
            price=30.0, stock_quantity=20, minimum_stock=2,
            pregnancy_category='X', tenant_id=1,
        ),
        'paracetamol': Medication(
            trade_name='Paracetamol', scientific_name='Paracetamol',
            dosage_form='tablet', strength='500mg',
            price=5.0, stock_quantity=200, minimum_stock=20,
            tenant_id=1,
        ),
    }
    for m in meds.values():
        db.session.add(m)
    db.session.commit()
    return meds


class TestPrescriptionHardStops:
    """
    End-to-end clinical safety validation.
    Each test seeds the full relational state and asserts HARD_STOP behavior.
    """

    def test_allergy_hard_stop_blocks_prescription(self, app, rollback_db, test_patient, test_doctor, test_medications):
        """Patient allergic to amoxicillin → prescription for amoxicillin must be HARD_STOPped."""
        amox = test_medications['amoxicillin']
        # Seed allergy (allergen must match medication name string for current safety logic)
        allergy = PatientAllergy(
            patient_id=test_patient.id,
            allergen='amoxicillin', severity='severe',
        )
        db.session.add(allergy)
        db.session.commit()

        # Debug direct safety call
        from services.clinical_safety_service import ClinicalSafetyService
        is_safe, alerts = ClinicalSafetyService.check_prescription_safety(
            patient_id=test_patient.id,
            medication_id=amox.id,
            proposed_items=[{'drug_id': amox.id, 'dosage': '500mg', 'quantity': 1, 'duration_days': 7}],
            doctor_id=test_doctor.id,
            tenant_id=1,
        )
        print("DEBUG allergy alerts:", [(a.check_type, a.severity.value, a.message) for a in alerts])

        ok, result = PrescriptionService.create_prescription(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            tenant_id=1,
            items=[{'medication_id': amox.id, 'dosage': '500mg', 'quantity': 1, 'duration_days': 7}],
        )
        assert not ok, f"Prescription should have been blocked by allergy HARD_STOP. Alerts: {[(a.check_type, a.severity.value, a.message) for a in alerts]}"
        assert 'HARD STOP' in str(result) or 'allergy' in str(result).lower(), f"Expected allergy hard stop, got: {result}"

    def test_drug_interaction_hard_stop(self, app, rollback_db, test_patient, test_doctor, test_medications):
        """Amoxicillin + Warfarin major interaction must be HARD_STOPped."""
        amox = test_medications['amoxicillin']
        warf = test_medications['warfarin']
        # Seed interaction
        interaction = DrugInteraction(
            medication_a_id=amox.id, medication_b_id=warf.id,
            severity='HIGH', description='Increased bleeding risk',
        )
        db.session.add(interaction)
        db.session.commit()

        # Create an active prescription for warfarin first
        pres = Prescription(
            patient_id=test_patient.id, doctor_id=test_doctor.id,
            prescription_number='RX001', tenant_id=1, status='active',
        )
        db.session.add(pres)
        db.session.flush()
        item = PrescriptionItem(
            prescription_id=pres.id, medication_id=warf.id,
            dosage='5mg', quantity=30, duration_days=30,
            unit_price=20.0, total_price=600.0, tenant_id=1,
        )
        db.session.add(item)
        db.session.commit()

        # Debug direct safety call
        from services.clinical_safety_service import ClinicalSafetyService
        is_safe, alerts = ClinicalSafetyService.check_prescription_safety(
            patient_id=test_patient.id,
            medication_id=amox.id,
            proposed_items=[{'drug_id': amox.id, 'dosage': '500mg', 'quantity': 10, 'duration_days': 7}],
            doctor_id=test_doctor.id,
            tenant_id=1,
        )
        print("DEBUG interaction alerts:", [(a.check_type, a.severity.value, a.message) for a in alerts])

        # Now try to prescribe amoxicillin → should hit interaction hard stop
        ok, result = PrescriptionService.create_prescription(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            tenant_id=1,
            items=[{'medication_id': amox.id, 'dosage': '500mg', 'quantity': 10, 'duration_days': 7}],
        )
        assert not ok, f"Prescription should have been blocked by drug interaction HARD_STOP. Alerts: {[(a.check_type, a.severity.value, a.message) for a in alerts]}"
        assert 'interaction' in str(result).lower() or 'HARD STOP' in str(result), f"Expected interaction hard stop, got: {result}"

    def test_pregnancy_contraindication_hard_stop(self, app, rollback_db, test_patient, test_doctor, test_medications):
        """Pregnant patient prescribed Category X drug → HARD_STOP."""
        isotretinoin = test_medications['isotretinoin']
        test_patient.is_pregnant = True
        test_patient.pregnancy_weeks = 12
        db.session.commit()

        ok, result = PrescriptionService.create_prescription(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            tenant_id=1,
            items=[{'medication_id': isotretinoin.id, 'dosage': '20mg', 'quantity': 30, 'duration_days': 30}],
        )
        assert not ok, "Prescription should have been blocked by pregnancy contraindication HARD_STOP"
        assert 'pregnancy' in str(result).lower() or 'category' in str(result).lower() or 'HARD STOP' in str(result), f"Expected pregnancy hard stop, got: {result}"

    def test_safe_prescription_passes_without_hard_stop(self, app, rollback_db, test_patient, test_doctor, test_medications):
        """Paracetamol for patient with no allergies or interactions → should succeed."""
        paracetamol = test_medications['paracetamol']

        ok, result = PrescriptionService.create_prescription(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            tenant_id=1,
            items=[{'medication_id': paracetamol.id, 'dosage': '500mg', 'quantity': 20, 'duration_days': 5}],
        )
        assert ok, f"Safe prescription should succeed, got: {result}"
        assert isinstance(result, Prescription)

    def test_skip_safety_checks_allows_override(self, app, rollback_db, test_patient, test_doctor, test_medications):
        """Head physician skip_safety_checks=True must allow otherwise blocked prescription."""
        amox = test_medications['amoxicillin']
        allergy = PatientAllergy(
            patient_id=test_patient.id,
            allergen='penicillin', severity='severe',
        )
        db.session.add(allergy)
        db.session.commit()

        ok, result = PrescriptionService.create_prescription(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            tenant_id=1,
            items=[{'medication_id': amox.id, 'dosage': '500mg', 'quantity': 1, 'duration_days': 7}],
            skip_safety_checks=True,
        )
        assert ok, "skip_safety_checks=True should allow prescription despite allergy"
        assert isinstance(result, Prescription)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
