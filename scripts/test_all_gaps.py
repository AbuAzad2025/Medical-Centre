"""
Comprehensive test for all 12 newly implemented gap features
"""
import os
import sys
import random
from datetime import date, datetime, timezone

# Set env before imports
os.environ['SECRET_KEY'] = 'test-secret-key-for-compilation-only'
os.environ['FLASK_ENV'] = 'testing'
os.environ['SUPPRESS_DEPRECATION_WARNINGS'] = '1'
os.environ['SUPPRESS_LOGGING'] = '1'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from models import (
    UserMFASettings, MFALoginAttempt,
    NursingAssessment,
    PatientEducationMaterial, PatientEducationAssignment,
    BackupRestoreLog,
    TelemedicineAppointment,
    SSOConfiguration, SSOUserMapping,
    AIImagingAnalysis,
    BiometricCredential, BiometricAuthChallenge,
    DataWarehouseSync, DailyVisitSummary, MonthlyFinanceSummary,
    WhatIfScenario,
    User, Patient, Department
)

app = create_app('testing')
app.config['WTF_CSRF_ENABLED'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

errors = []
successes = []

def test(name, fn):
    try:
        fn()
        successes.append(name)
        print(f"  PASS: {name}")
    except Exception as e:
        errors.append((name, str(e)))
        print(f"  FAIL: {name} -> {e}")

with app.app_context():
    db.create_all()

    # Create test user and patient
    dept = Department(name='Test Dept', name_ar='قسم الاختبار')
    db.session.add(dept)
    db.session.commit()

    user = User(
        username='testuser',
        email='test@test.com',
        password_hash='fakehash',
        full_name='Test User',
        department_id=dept.id
    )
    db.session.add(user)
    db.session.commit()

    patient = Patient(
        first_name='Test',
        last_name='Patient',
        first_name_ar='مريض',
        last_name_ar='اختبار',
        gender='male',
        birth_date=date(1990, 1, 1),
        phone='0500000000'
    )
    db.session.add(patient)
    db.session.commit()

    print("=" * 60)
    print("Testing all 12 gap features")
    print("=" * 60)

    # 1. 2FA / MFA
    def test_mfa():
        mfa = UserMFASettings(user_id=user.id, totp_secret='BASE32SECRET', totp_enabled=True)
        db.session.add(mfa)
        db.session.commit()
        assert mfa.totp_enabled is True
        assert mfa.user_id == user.id

        attempt = MFALoginAttempt(user_id=user.id, success=True, method='totp')
        db.session.add(attempt)
        db.session.commit()
        assert attempt.success is True
    test("1. 2FA TOTP Setup & MFA Log", test_mfa)

    # 2. Nursing Assessments
    def test_nursing_assessments():
        braden = NursingAssessment(
            patient_id=patient.id,
            nurse_id=user.id,
            assessment_type='braden',
            braden_sensory_perception=4,
            braden_moisture=3,
            braden_activity=4,
            braden_mobility=3,
            braden_nutrition=4,
            braden_friction_shear=3
        )
        db.session.add(braden)
        db.session.commit()
        assert braden.braden_total == 21
        braden.total_score = braden.braden_total
        braden.risk_level = 'low'
        db.session.commit()

        glasgow = NursingAssessment(
            patient_id=patient.id,
            nurse_id=user.id,
            assessment_type='glasgow',
            glasgow_eye=4,
            glasgow_verbal=5,
            glasgow_motor=6
        )
        db.session.add(glasgow)
        db.session.commit()
        assert glasgow.glasgow_total == 15
    test("2. Nursing Assessments (Braden + Glasgow)", test_nursing_assessments)

    # 3. Patient Education Materials
    def test_patient_education():
        mat = PatientEducationMaterial(
            title='Diabetes Education',
            category='disease',
            content_text='Manage your blood sugar...',
            language='ar',
            created_by=user.id
        )
        db.session.add(mat)
        db.session.commit()
        assert mat.id is not None

        assign = PatientEducationAssignment(
            patient_id=patient.id,
            material_id=mat.id,
            assigned_by=user.id
        )
        db.session.add(assign)
        db.session.commit()
        assert assign.status == 'assigned'
    test("3. Patient Education Materials & Assignment", test_patient_education)

    # 4. Backup Restore
    def test_backup_restore():
        log = BackupRestoreLog(
            operation='restore',
            status='success',
            initiated_by=user.id,
            details='{"message": "test"}'
        )
        db.session.add(log)
        db.session.commit()
        assert log.status == 'success'
    test("4. Backup Restore Log", test_backup_restore)

    # 5. Telemedicine
    def test_telemedicine():
        from datetime import datetime, timezone
        tm = TelemedicineAppointment(
            patient_id=patient.id,
            doctor_id=user.id,
            scheduled_start=datetime.now(timezone.utc),
            meeting_provider='jitsi',
            meeting_url='https://meet.jit.si/test',
            meeting_id='test123',
            created_by=user.id
        )
        db.session.add(tm)
        db.session.commit()
        assert tm.status == 'scheduled'
        assert tm.meeting_url is not None
    test("5. Telemedicine Appointment", test_telemedicine)

    # 6. SSO Config
    def test_sso():
        cfg = SSOConfiguration(
            name='Corp AD',
            provider_type='active_directory',
            server_url='ldaps://dc.corp.com',
            is_active=True
        )
        db.session.add(cfg)
        db.session.commit()
        assert cfg.is_active is True
        assert cfg.provider_type == 'active_directory'
    test("6. SSO / LDAP Configuration", test_sso)

    # 7. AI Imaging Analysis
    def test_ai_imaging():
        ai = AIImagingAnalysis(
            patient_id=patient.id,
            provider='internal',
            analysis_type='detection',
            status='pending'
        )
        db.session.add(ai)
        db.session.commit()
        assert ai.status == 'pending'
    test("7. AI Imaging Analysis", test_ai_imaging)

    # 8. Biometric Auth
    def test_biometric():
        cred = BiometricCredential(
            user_id=user.id,
            credential_id='cred123',
            public_key='fakepubkey',
            device_type='fingerprint',
            device_name='TouchID'
        )
        db.session.add(cred)
        db.session.commit()
        assert cred.is_active is True

        ch = BiometricAuthChallenge(
            user_id=user.id,
            challenge='challenge123',
            challenge_type='registration',
            expires_at=db.func.now()
        )
        db.session.add(ch)
        db.session.commit()
        assert ch.used is False
    test("8. Biometric Auth (WebAuthn)", test_biometric)

    # 9. Data Warehouse
    def test_data_warehouse():
        sync = DataWarehouseSync(
            sync_name='daily_visits_summary',
            status='success'
        )
        db.session.add(sync)
        db.session.commit()
        assert sync.status == 'success'

        ds = DailyVisitSummary(
            date=date(2026, 1, 1),
            total_visits=100,
            revenue_total=5000
        )
        db.session.add(ds)
        db.session.commit()
        assert ds.total_visits == 100

        ms = MonthlyFinanceSummary(year=2026, month=1, total_invoices=50, total_paid=3000)
        db.session.add(ms)
        db.session.commit()
        assert ms.total_paid == 3000
    test("9. Data Warehouse (Sync + Daily + Monthly)", test_data_warehouse)

    # 10. What-If Scenarios
    def test_what_if():
        scenario = WhatIfScenario(
            name='Add 2 Doctors',
            scenario_type='add_doctor',
            baseline_visits_per_day=50,
            baseline_revenue_per_day=5000,
            param_new_staff_count=2,
            created_by=user.id
        )
        scenario.calculate_projections()
        db.session.add(scenario)
        db.session.commit()
        assert scenario.projected_visits_per_day is not None
        assert float(scenario.projected_visits_per_day) == 66  # 50 + 2*8
    test("10. What-If Scenario Engine", test_what_if)

    # 11. Voice Dictation (static file exists)
    def test_voice_dictation_file():
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'js', 'voice_dictation.js')
        assert os.path.exists(js_path), f"File not found: {js_path}"
    test("11. Voice Dictation JS File", test_voice_dictation_file)

    # 12. Document OCR (static file exists)
    def test_ocr_file():
        js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'js', 'document_ocr.js')
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'advanced', 'document_ocr.html')
        assert os.path.exists(js_path), f"File not found: {js_path}"
        assert os.path.exists(template_path), f"File not found: {template_path}"
    test("12. Document OCR Files", test_ocr_file)

    print("=" * 60)
    print(f"RESULTS: {len(successes)} passed, {len(errors)} failed")
    print("=" * 60)
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
        sys.exit(1)
    else:
        print("\nALL 12 GAP FEATURES VERIFIED SUCCESSFULLY!")
        sys.exit(0)
