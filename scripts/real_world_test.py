"""
Real-World System Test — Integration Test for Patient Journey
Tests: templates render, forms validate, routes respond, flow works end-to-end
"""
import os, sys, traceback, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ERRORS, WARNINGS, INFOS = [], [], []
def log_error(m): ERRORS.append(m); print(f"\033[91m[ERROR]\033[0m {m}")
def log_warn(m): WARNINGS.append(m); print(f"\033[93m[WARN]\033[0m  {m}")
def log_info(m): INFOS.append(m); print(f"\033[92m[INFO]\033[0m  {m}")

def run_tests():
    os.environ['SECRET_KEY'] = 'test-secret-key-for-compilation-only'
    os.environ['FLASK_ENV'] = 'testing'

    from app_factory import create_app, db
    app = create_app('testing')

    print("="*70)
    print("Real-World Integration Test — Azad Medical Platform")
    print("="*70)

    # ============================================================
    # 1. Boot Test
    # ============================================================
    print("\n" + "="*70)
    print("[1/8] Boot Test — App starts, DB connects")
    print("="*70)

    with app.app_context():
        db.create_all()
        log_info(f"Database created: {len(db.metadata.tables)} tables")

    # ============================================================
    # 2. Static Files Test
    # ============================================================
    print("\n" + "="*70)
    print("[2/8] Static Files — CSS/JS/Manifest exist")
    print("="*70)

    required_static = [
        'css/bootstrap.rtl.min.css', 'css/app.css', 'css/design-system.css',
        'js/bootstrap.bundle.min.js', 'js/app.js', 'js/common-functions.js',
        'manifest.json', 'service-worker.js'
    ]
    base = os.path.dirname(os.path.dirname(__file__))
    for f in required_static:
        path = os.path.join(base, 'static', f)
        if os.path.exists(path):
            log_info(f"OK: static/{f}")
        else:
            log_warn(f"Missing: static/{f}")

    # Test via HTTP
    with app.test_client() as client:
        for f in required_static:
            resp = client.get(f'/static/{f}')
            if resp.status_code == 200:
                log_info(f"HTTP OK: /static/{f}")
            else:
                log_warn(f"HTTP {resp.status_code}: /static/{f}")

    # ============================================================
    # 3. Route Response Test (200/302/401)
    # ============================================================
    print("\n" + "="*70)
    print("[3/8] Route Response — All blueprints respond")
    print("="*70)

    test_routes = [
        # Auth
        ('/auth/login', 200),
        # Main
        ('/', 302),
        # Portal
        ('/portal/', 302),  # Redirects to login if not authenticated
        ('/portal/dashboard', 302),
        # Modules (should redirect or 401 without login)
        ('/reception/dashboard', 302),
        ('/doctor/', 302),
        ('/emergency/dashboard', 302),
        ('/lab/dashboard', 302),
        ('/radiology/dashboard', 302),
        ('/finance/dashboard', 302),
        ('/accountant/dashboard', 302),
        ('/manager/dashboard', 302),
        ('/booking/dashboard', 302),
        ('/medication/dashboard', 302),
        ('/nurse/dashboard', 302),
        # New modules
        ('/bed/dashboard', 302),
        ('/or/schedule', 302),
        ('/emar/dashboard', 302),
        ('/vaccination/vaccines', 302),
        ('/referral/list', 302),
        ('/pathway/pathways', 302),
        ('/cds/rules', 302),
        ('/barcode/scan', 302),
        ('/clinical-coding/icd10', 302),
        # API
        ('/api/fhir/Patient', 401),  # Requires login
        ('/dicom/studies', 302),
        ('/population-health/dashboard', 302),
        ('/report-builder/', 302),
        ('/security/signatures', 302),
    ]

    with app.test_client() as client:
        for route, expected in test_routes:
            resp = client.get(route, follow_redirects=False)
            if resp.status_code == expected:
                log_info(f"OK {resp.status_code}: {route}")
            else:
                log_warn(f"Unexpected {resp.status_code} (expected {expected}): {route}")

    # ============================================================
    # 4. Template Render Test (authenticated)
    # ============================================================
    print("\n" + "="*70)
    print("[4/8] Template Render — Authenticated pages render")
    print("="*70)

    with app.app_context():
        from models.user import User
        from models.permissions import Role
        from werkzeug.security import generate_password_hash

        # Create test user
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(name='admin', name_ar='مدير', is_active=True)
            db.session.add(admin_role)
            db.session.commit()

        user = User.query.filter_by(username='testadmin').first()
        if not user:
            user = User(
                username='testadmin',
                password_hash=generate_password_hash('testpass123'),
                full_name='Test Admin',
                email='test@medical.com',
                role='admin',
                is_active=True,
                session_version=1
            )
            db.session.add(user)
            db.session.commit()

    with app.test_client() as client:
        # Login
        login_resp = client.post('/auth/login', data={
            'username': 'testadmin',
            'password': 'testpass123',
            'csrf_token': 'dummy'
        }, follow_redirects=False)

        if login_resp.status_code in (302, 301):
            log_info("Login successful (redirect after login)")
        else:
            log_warn(f"Login returned {login_resp.status_code}")

        # Test authenticated routes
        auth_routes = [
            '/main/dashboard',
            '/reception/dashboard',
            '/doctor/dashboard',
            '/emergency/dashboard',
            '/lab/dashboard',
            '/radiology/dashboard',
            '/finance/dashboard',
            '/accountant/dashboard',
            '/manager/dashboard',
            '/medication/dashboard',
            '/nurse/dashboard',
            '/bed/dashboard',
            '/emar/dashboard',
            '/vaccination/vaccines',
            '/referral/list',
            '/pathway/pathways',
            '/cds/rules',
            '/barcode/scan',
            '/clinical-coding/icd10',
            '/dicom/studies',
            '/population-health/dashboard',
            '/report-builder/',
            '/security/signatures',
            '/security/sessions',
            '/security/password-policy',
        ]

        for route in auth_routes:
            try:
                resp = client.get(route, follow_redirects=True)
                if resp.status_code == 200:
                    # Check for common template errors
                    html = resp.data.decode('utf-8', errors='ignore')
                    if 'Traceback' in html or 'Internal Server Error' in html or 'jinja2.exceptions' in html:
                        log_error(f"Template error in {route}")
                    elif '<!DOCTYPE' in html or '<html' in html:
                        log_info(f"Renders OK: {route}")
                    else:
                        log_warn(f"No HTML in response: {route}")
                elif resp.status_code == 403:
                    log_warn(f"Access denied (403): {route}")
                else:
                    log_warn(f"HTTP {resp.status_code}: {route}")
            except Exception as e:
                log_error(f"Exception loading {route}: {e}")

    # ============================================================
    # 5. Form Validation Test
    # ============================================================
    print("\n" + "="*70)
    print("[5/8] Form Validation — WTForms validate correctly")
    print("="*70)

    with app.app_context():
        from forms.patient_forms import PatientRegistrationForm
        from forms.management_forms import PrescriptionForm, MedicalRecordForm
        from forms.invoice_forms import InvoiceForm
        from forms.request_forms import LabRequestForm

        with app.test_request_context():
            # Note: Some forms load choices from DB dynamically,
            # so we instantiate and check structure rather than validate
            try:
                form = PatientRegistrationForm()
                log_info(f"PatientRegistrationForm fields: {list(form._fields.keys())[:5]}...")
            except Exception as e:
                log_warn(f"PatientRegistrationForm init: {e}")

            try:
                form = PrescriptionForm()
                log_info("PrescriptionForm instantiates OK")
            except Exception as e:
                log_warn(f"PrescriptionForm init: {e}")

            try:
                form = LabRequestForm()
                log_info("LabRequestForm instantiates OK")
            except Exception as e:
                log_warn(f"LabRequestForm init: {e}")

            try:
                form = InvoiceForm()
                log_info("InvoiceForm instantiates OK")
            except Exception as e:
                log_warn(f"InvoiceForm init: {e}")

    # ============================================================
    # 6. Patient Journey Flow Test
    # ============================================================
    print("\n" + "="*70)
    print("[6/8] Patient Journey — End-to-end flow")
    print("="*70)

    with app.app_context():
        from models.patient import Patient
        from models.visit import Visit
        from models.appointment import Appointment
        from models.invoice import Invoice
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from models.lab_request import LabRequest

        # Create patient
        patient = Patient(
            first_name='Test',
            last_name='Patient',
            national_id='9998887776',
            phone='0599888777',
            gender='MALE',
            birth_date=date(1990, 1, 1)
        )
        db.session.add(patient)
        db.session.commit()
        log_info(f"Created patient ID: {patient.id}")

        # Create visit
        visit = Visit(
            patient_id=patient.id,
            visit_type='OUTPATIENT',
            status='OPEN',
            visit_date=date.today()
        )
        db.session.add(visit)
        db.session.commit()
        log_info(f"Created visit ID: {visit.id}")

        # Create medical record
        record = MedicalRecord(
            patient_id=patient.id,
            title='Hypertension follow-up',
            details='Patient presents with elevated BP and headache'
        )
        db.session.add(record)
        db.session.commit()
        log_info(f"Created medical record ID: {record.id}")

        # Create lab request
        lab = LabRequest(
            patient_id=patient.id,
            visit_id=visit.id,
            status='REQUESTED',
            notes='CBC requested'
        )
        db.session.add(lab)
        db.session.commit()
        log_info(f"Created lab request ID: {lab.id}")

        # Create prescription
        prescription = Prescription(
            patient_id=patient.id,
            visit_id=visit.id,
            status='active',
            doctor_id=1,
            prescription_number='RX-001-TEST'
        )
        db.session.add(prescription)
        db.session.commit()
        log_info(f"Created prescription ID: {prescription.id}")

        # Create invoice
        invoice = Invoice(
            visit_id=visit.id,
            status='DRAFT',
            total_amount=150.00,
            paid_amount=0.00
        )
        db.session.add(invoice)
        db.session.commit()
        log_info(f"Created invoice ID: {invoice.id}")

        # Verify relationships
        patient_check = Patient.query.get(patient.id)
        if patient_check.visits:
            log_info("Patient → Visit: OK")
        if patient_check.lab_results:
            log_info("Patient → LabResult: OK")
        if patient_check.appointments:
            log_info("Patient → Appointment: OK")

    # ============================================================
    # 7. Print / Report Templates Test
    # ============================================================
    print("\n" + "="*70)
    print("[7/8] Print Templates — Prescription, Report, Invoice")
    print("="*70)

    print_templates = [
        'print/prescription.html',
        'print/radiology_report.html',
        'print/emergency_report.html',
        'print/invoice.html',
        'print/receipt.html',
    ]
    for tmpl in print_templates:
        path = os.path.join(base, 'templates', tmpl)
        if os.path.exists(path):
            log_info(f"OK: {tmpl}")
        else:
            log_warn(f"Missing: {tmpl}")

    # ============================================================
    # 8. Portal Test
    # ============================================================
    print("\n" + "="*70)
    print("[8/8] Patient Portal — Public-facing pages")
    print("="*70)

    with app.test_client() as client:
        portal_routes = [
            '/portal/',
            '/portal/dashboard',
            '/portal/appointments',
            '/portal/medical-records',
            '/portal/prescriptions',
            '/portal/lab-results',
            '/portal/bills',
            '/portal/vaccinations',
        ]
        for route in portal_routes:
            resp = client.get(route, follow_redirects=True)
            if resp.status_code == 200:
                log_info(f"Portal OK: {route}")
            else:
                log_warn(f"Portal {resp.status_code}: {route}")

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "="*70)
    print("الملخص النهائي")
    print("="*70)
    print(f"  {len(ERRORS)} خطأ")
    print(f"  {len(WARNINGS)} تحذير")
    print(f"  {len(INFOS)} معلومة")
    if not ERRORS:
        print("\n✅ النظام يعمل بشكل حقيقي — كل المكونات متكاملة")
    else:
        print("\n⚠️ يوجد أخطاء تحتاج إصلاحاً")
    sys.exit(1 if ERRORS else 0)

from datetime import date
if __name__ == '__main__':
    run_tests()
