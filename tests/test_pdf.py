"""
Tests for PDF report generation (Phase 2)
"""
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO


class TestPDFReportPrinter:
    def test_pdf_printer_initializes(self, app):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        assert printer is not None

    def test_generate_report_returns_pdf_bytes(self, app):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_report('Test Title', {'name': 'Test'}, [{'heading': 'Section', 'lines': ['Line1']}])
        assert pdf.startswith(b'%PDF'), f"Expected PDF header, got {pdf[:20]}"
        assert len(pdf) > 100

    def test_arabic_text_in_report(self, app):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_report('تقرير اختبار', {'الاسم': 'مريض تجريبي'}, [])
        assert pdf.startswith(b'%PDF')

    def test_generate_lab_report_no_results(self, app, test_lab_request):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_lab_report(test_lab_request)
        assert pdf.startswith(b'%PDF'), f"Expected PDF header, got {pdf[:20]}"
        assert len(pdf) > 500

    def test_generate_lab_report_with_results(self, app, test_lab_request_with_results):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_lab_report(test_lab_request_with_results)
        assert pdf.startswith(b'%PDF')
        assert len(pdf) > 800

    def test_generate_radiology_report(self, app, test_radiology_result):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_radiology_report(test_radiology_result)
        assert pdf.startswith(b'%PDF')
        assert len(pdf) > 500

    def test_generate_radiology_report_empty_fields(self, app, test_radiology_result_empty):
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf = printer.generate_radiology_report(test_radiology_result_empty)
        assert pdf.startswith(b'%PDF')

    def test_lab_pdf_endpoint_returns_pdf(self, app, client, lab_auth_client, test_lab_request):
        resp = client.get(f'/lab/print_request/{test_lab_request.id}/pdf')
        assert resp.status_code == 200
        assert resp.mimetype == 'application/pdf'
        assert resp.content_length > 500

    def test_lab_pdf_endpoint_not_found(self, app, client, lab_auth_client):
        resp = client.get('/lab/print_request/99999/pdf')
        assert resp.status_code == 404

    def test_radiology_pdf_endpoint_returns_pdf(self, app, client, rad_auth_client, test_radiology_result):
        resp = client.get(f'/radiology/print_report/{test_radiology_result.id}/pdf')
        assert resp.status_code == 200
        assert resp.mimetype == 'application/pdf'
        assert resp.content_length > 500

    def test_radiology_pdf_endpoint_not_found(self, app, client, rad_auth_client):
        resp = client.get('/radiology/print_report/99999/pdf')
        assert resp.status_code == 404


# ── Fixtures for creating test lab/radiology data ──────────────────────

@pytest.fixture(scope='function')
def test_patient(app, test_tenant):
    from models.patient import Patient
    from app_factory import db
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='مريض',
        last_name='اختبار',
        first_name_ar='مريض',
        last_name_ar='اختبار',
        phone='+970599123456',
        gender='male',
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture(scope='function')
def test_visit(app, test_tenant, test_patient):
    from models.visit import Visit
    from app_factory import db
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=test_patient.id,
        visit_type='lab',  # or diagnosis, whichever is valid
        status='active',
    )
    db.session.add(v)
    db.session.commit()
    return v


@pytest.fixture(scope='function')
def test_lab_request(app, test_tenant, test_patient, test_visit):
    from models.lab_request import LabRequest
    from app_factory import db
    from datetime import datetime, timezone
    uid = datetime.now(timezone.utc).strftime('%H%M%S%f')
    lr = LabRequest(
        tenant_id=test_tenant.id,
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        request_number=f'LAB-TEST-{uid}',
        status='DONE',
        notes='اختبار معملي تجريبي',
    )
    db.session.add(lr)
    db.session.commit()
    return lr


@pytest.fixture(scope='function')
def test_lab_request_with_results(app, test_tenant, test_patient, test_lab_request):
    from models.lab_request import LabResult
    from app_factory import db
    results_data = [
        {'test_code': 'CBC', 'test_name': 'صورة دم كاملة', 'value': '5.2', 'unit': 'x10^12/L', 'reference_range': '4.5-6.0', 'status': 'READY'},
        {'test_code': 'HGB', 'test_name': 'هيموجلوبين', 'value': '14.5', 'unit': 'g/dL', 'reference_range': '13.0-17.0', 'status': 'READY'},
        {'test_code': 'WBC', 'test_name': 'كريات بيضاء', 'value': '7.8', 'unit': 'x10^9/L', 'reference_range': '4.0-11.0', 'status': 'READY'},
    ]
    for rd in results_data:
        r = LabResult(
            tenant_id=test_tenant.id,
            request_id=test_lab_request.id,
            patient_id=test_patient.id,
            **rd
        )
        db.session.add(r)
    db.session.commit()
    return test_lab_request


@pytest.fixture(scope='function')
def test_radiology_request(app, test_tenant, test_patient, test_visit):
    from models.radiology_request import RadiologyRequest
    from app_factory import db
    from datetime import datetime, timezone
    uid = datetime.now(timezone.utc).strftime('%H%M%S%f')
    rr = RadiologyRequest(
        tenant_id=test_tenant.id,
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        request_number=f'RAD-TEST-{uid}',
        status='DONE',
        modality='XRay',
        body_part='الصدر',
    )
    db.session.add(rr)
    db.session.commit()
    return rr


@pytest.fixture(scope='function')
def test_radiology_result(app, test_tenant, test_patient, test_radiology_request):
    from models.radiology_result import RadiologyResult
    from app_factory import db
    rr = RadiologyResult(
        tenant_id=test_tenant.id,
        request_id=test_radiology_request.id,
        patient_id=test_patient.id,
        findings='الرئتان واضحتان بدون احتقان. القلب بحجم طبيعي.',
        impression='صورة الصدر طبيعية',
        notes='لا توجد توصيات إضافية',
        status='READY',
    )
    db.session.add(rr)
    db.session.commit()
    return rr


@pytest.fixture(scope='function')
def test_radiology_result_empty(app, test_tenant, test_patient, test_radiology_request):
    from models.radiology_result import RadiologyResult
    from app_factory import db
    rr = RadiologyResult(
        tenant_id=test_tenant.id,
        request_id=test_radiology_request.id,
        patient_id=test_patient.id,
        findings='',
        impression='',
        notes='',
        status='PENDING',
    )
    db.session.add(rr)
    db.session.commit()
    return rr


@pytest.fixture(scope='function')
def lab_user(app, test_tenant):
    from models.user import User
    from app_factory import db
    u = User.query.filter_by(username='lab_test_user').first()
    if not u:
        u = User(
            username='lab_test_user',
            email='lab@test.local',
            full_name='فني مختبر',
            role='lab',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
    return u


@pytest.fixture(scope='function')
def lab_auth_client(app, client, lab_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'lab_test_user',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


@pytest.fixture(scope='function')
def rad_user(app, test_tenant):
    from models.user import User
    from app_factory import db
    u = User.query.filter_by(username='rad_test_user').first()
    if not u:
        u = User(
            username='rad_test_user',
            email='rad@test.local',
            full_name='فني أشعة',
            role='radiology',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
    return u


@pytest.fixture(scope='function')
def rad_auth_client(app, client, rad_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'rad_test_user',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client
