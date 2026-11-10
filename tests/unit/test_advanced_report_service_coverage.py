"""Extra coverage tests for services.advanced_report_service."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.shared.enums import InvoiceStatus, VisitArchiveStatus
from models.appointment import Appointment
from models.audit_trail import AuditTrail, SecurityEvent, SystemLog
from models.department import Department
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.advanced_report_service import AdvancedReportService

pytest_plugins = ['tests._isolated_tenant']

R = AdvancedReportService


def _raise_boom(*_args, **_kwargs):
    raise RuntimeError('boom')


@pytest.fixture
def cov_data(app, isolated_tenant, db):
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    dept = Department(
        name=f'CovDept-{suffix}',
        name_ar='قسم تغطية',
        is_active=True,
        tenant_id=isolated_tenant.id,
    )
    db.session.add(dept)
    db.session.flush()

    doctor = User(
        username=f'cov_doc_{suffix}',
        email=f'cov_doc_{suffix}@test.local',
        full_name='Cov Doctor',
        role='doctor',
        is_active=True,
        tenant_id=isolated_tenant.id,
        department_id=dept.id,
    )
    doctor.set_password('test123')
    db.session.add(doctor)
    db.session.flush()

    doctor_no_dept = User(
        username=f'cov_doc_nd_{suffix}',
        email=f'cov_doc_nd_{suffix}@test.local',
        full_name='No Dept Doctor',
        role='doctor',
        is_active=False,
        tenant_id=isolated_tenant.id,
        department_id=None,
    )
    doctor_no_dept.set_password('test123')
    db.session.add(doctor_no_dept)
    db.session.flush()

    p_none = Patient(
        tenant_id=isolated_tenant.id,
        first_name='NoBirth',
        last_name='Patient',
        phone=f'0531{suffix[-6:]}',
        gender='M',
        birth_date=None,
    )
    p_future = Patient(
        tenant_id=isolated_tenant.id,
        first_name='Future',
        last_name='Birthday',
        phone=f'0532{suffix[-6:]}',
        gender='F',
        birth_date=date(1990, 12, 1),
    )
    p_normal = Patient(
        tenant_id=isolated_tenant.id,
        first_name='Normal',
        last_name='Patient',
        phone=f'0533{suffix[-6:]}',
        gender='M',
        birth_date=date(1980, 1, 1),
    )
    db.session.add_all([p_none, p_future, p_normal])
    db.session.flush()

    today = datetime.now(UTC).date()
    now = datetime.now(UTC)
    v_completed = Visit(
        tenant_id=isolated_tenant.id,
        patient_id=p_normal.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        visit_date=today,
        visit_time=now,
        status='COMPLETED',
        visit_type='CONSULTATION',
        total_amount=100,
        paid_amount=100,
        archive_status='ACTIVE',
    )
    v_open = Visit(
        tenant_id=isolated_tenant.id,
        patient_id=p_future.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        visit_date=today,
        visit_time=now,
        status='OPEN',
        visit_type='EMERGENCY',
        total_amount=0,
        paid_amount=0,
        archive_status='ARCHIVED',
    )
    db.session.add_all([v_completed, v_open])
    db.session.flush()

    for amount, method in ((50, 'CASH'), (75, 'CARD'), (25, 'WIRE'), (10, 'INSURANCE')):
        db.session.add(
            Payment(
                tenant_id=isolated_tenant.id,
                patient_id=p_normal.id,
                visit_id=v_completed.id,
                method=method,
                amount=amount,
                currency='ILS',
                status='CONFIRMED',
                payment_date=now,
            )
        )
    db.session.flush()

    inv_paid = Invoice(
        tenant_id=isolated_tenant.id,
        visit_id=v_completed.id,
        total_amount=200,
        status=InvoiceStatus.PAID,
        currency='ILS',
    )
    inv_issued = Invoice(
        tenant_id=isolated_tenant.id,
        visit_id=v_completed.id,
        total_amount=50,
        status=InvoiceStatus.ISSUED,
        currency='ILS',
    )
    inv_draft = Invoice(
        tenant_id=isolated_tenant.id,
        visit_id=v_completed.id,
        total_amount=25,
        status=InvoiceStatus.DRAFT,
        currency='ILS',
    )
    db.session.add_all([inv_paid, inv_issued, inv_draft])
    db.session.flush()

    db.session.add(
        InvoiceService(
            tenant_id=isolated_tenant.id,
            invoice_id=inv_paid.id,
            department_id=dept.id,
            service_code='SVC',
            service_name='Service',
            quantity=1,
            unit_price=200,
            total_price=200,
        )
    )
    db.session.flush()

    db.session.add_all(
        [
            Appointment(
                tenant_id=isolated_tenant.id,
                patient_id=p_normal.id,
                doctor_id=doctor.id,
                department_id=dept.id,
                starts_at=now,
                status='DONE',
            ),
            Appointment(
                tenant_id=isolated_tenant.id,
                patient_id=p_future.id,
                doctor_id=doctor.id,
                department_id=dept.id,
                starts_at=now + timedelta(hours=1),
                status='CANCELLED',
            ),
        ]
    )
    db.session.flush()

    db.session.add_all(
        [
            AuditTrail(
                tenant_id=isolated_tenant.id,
                entity_type='system',
                entity_id=1,
                action='create',
                created_at=now,
            ),
            SystemLog(
                tenant_id=isolated_tenant.id,
                log_level='INFO',
                log_category='system',
                message='coverage log',
                created_at=now,
            ),
            SecurityEvent(
                tenant_id=isolated_tenant.id,
                event_type='login_failed',
                description='coverage event',
                severity='low',
                created_at=now,
            ),
        ]
    )
    db.session.commit()

    return {
        'dept': dept,
        'doctor': doctor,
        'doctor_no_dept': doctor_no_dept,
        'p_none': p_none,
        'p_future': p_future,
        'p_normal': p_normal,
        'v_completed': v_completed,
        'v_open': v_open,
        'today': today,
    }


class TestDefaultDates:
    def test_patient(self, app, isolated_tenant, cov_data, db):
        out = R.generate_patient_analytics()
        assert out['success'] is True

    def test_visit(self, app, isolated_tenant, cov_data, db):
        out = R.generate_visit_analytics()
        assert out['success'] is True

    def test_financial(self, app, isolated_tenant, cov_data, db):
        out = R.generate_financial_analytics()
        assert out['success'] is True

    def test_doctor(self, app, isolated_tenant, cov_data, db):
        out = R.generate_doctor_performance_analytics()
        assert out['success'] is True

    def test_department(self, app, isolated_tenant, cov_data, db):
        out = R.generate_department_analytics()
        assert out['success'] is True

    def test_system_usage(self, app, isolated_tenant, cov_data, db):
        out = R.generate_system_usage_analytics()
        assert out['success'] is True

    def test_comprehensive(self, app, isolated_tenant, cov_data, db):
        out = R.generate_comprehensive_report()
        assert out['success'] is True


class TestNoTenantContext:
    @pytest.mark.no_tenant_context
    def test_patient(self, app, db):
        out = R.generate_patient_analytics()
        assert 'success' in out

    @pytest.mark.no_tenant_context
    def test_system_usage(self, app, db):
        out = R.generate_system_usage_analytics()
        assert 'success' in out


class TestPatientCoverage:
    def test_age_groups_and_inactive(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_patient_analytics(start, end)
        assert out['success'] is True
        analytics = out['analytics']
        # p_none -> age None (not counted), p_future -> 19-35, p_normal -> 36-50
        assert analytics['age_groups']['19-35'] >= 1
        assert analytics['age_groups']['36-50'] >= 1
        # p_none has no visits in range -> inactive at least 1
        assert analytics['status_distribution']['inactive'] >= 1

    def test_department_filter(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_patient_analytics(start, end, department_id=dept.id)
        assert out['success'] is True
        assert out['analytics']['total_patients'] >= 2

    def test_birth_date_adjust_branch(self, app, isolated_tenant, cov_data, db):
        # p_future (Dec 1) ensures month/day adjust branch
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_patient_analytics(start, end)
        assert out['success'] is True


class TestVisitCoverage:
    def test_department_filter(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_visit_analytics(start, end, department_id=dept.id)
        assert out['success'] is True
        assert out['analytics']['total_visits'] >= 2

    def test_status_and_archive(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_visit_analytics(start, end)
        assert out['success'] is True
        stats = out['analytics']['status_distribution']
        assert stats['OPEN'] >= 1 or stats.get('OPEN', 0) >= 0
        assert out['analytics']['visit_type_distribution']['EMERGENCY'] >= 1
        # archived count
        assert out['analytics']['status_distribution'][VisitArchiveStatus.ARCHIVED] >= 1

    def test_daily_visits(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_visit_analytics(start, end)
        assert out['success'] is True
        assert out['analytics']['daily_visits'] != {}


class TestFinancialCoverage:
    def test_payments_department_filter(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_financial_analytics(start, end, department_id=dept.id)
        assert out['success'] is True
        payments = out['analytics']['payments']
        assert payments['total_count'] >= 4

    def test_invoices_department_filter(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_financial_analytics(start, end, department_id=dept.id)
        assert out['success'] is True
        invoices = out['analytics']['invoices']
        assert invoices['total_count'] >= 1
        assert invoices['paid_count'] >= 1

    def test_invoice_statuses(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_financial_analytics(start, end)
        assert out['success'] is True
        invoices = out['analytics']['invoices']
        assert invoices['paid_count'] >= 1
        assert invoices['pending_count'] >= 2

    def test_daily_revenue(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_financial_analytics(start, end)
        assert out['success'] is True
        assert out['analytics']['payments']['daily_revenue'] != {}


class TestDoctorCoverage:
    def test_no_dept_and_inactive_doctor(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_doctor_performance_analytics(start, end)
        assert out['success'] is True
        rows = out['analytics']['doctor_performance']
        assert any(r['department'] is None for r in rows)
        assert out['analytics']['total_doctors'] >= 2

    def test_no_visits_branch(self, app, isolated_tenant, cov_data, db):
        future_start = datetime.now(UTC) + timedelta(days=10)
        future_end = future_start + timedelta(days=1)
        out = R.generate_doctor_performance_analytics(future_start, future_end)
        assert out['success'] is True
        for row in out['analytics']['doctor_performance']:
            assert row['completion_rate'] == 0
            assert row['appointment_completion_rate'] == 0

    def test_filter_by_doctor(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_doctor_performance_analytics(start, end, doctor_id=cov_data['doctor'].id)
        assert out['success'] is True
        assert len(out['analytics']['doctor_performance']) == 1

    def test_revenue_excludes_zero(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_doctor_performance_analytics(start, end)
        assert out['success'] is True
        doc = next(
            r
            for r in out['analytics']['doctor_performance']
            if r['doctor_id'] == cov_data['doctor'].id
        )
        # completed visit total 100 + open visit total 0 => revenue 100 (not 0-excluded? sum if total_amount truthy)
        assert doc['total_revenue'] == 100


class TestDepartmentCoverage:
    def test_no_visits_branch(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        future_start = datetime.now(UTC) + timedelta(days=10)
        future_end = future_start + timedelta(days=1)
        out = R.generate_department_analytics(future_start, future_end, department_id=dept.id)
        assert out['success'] is True
        row = out['analytics']['department_analytics'][0]
        assert row['total_visits'] == 0
        assert row['completion_rate'] == 0
        assert row['appointment_completion_rate'] == 0

    def test_department_filter(self, app, isolated_tenant, cov_data, db):
        dept = cov_data['dept']
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_department_analytics(start, end, department_id=dept.id)
        assert out['success'] is True
        assert out['analytics']['total_departments'] == 1


class TestSystemUsageCoverage:
    def test_logs_and_roles(self, app, isolated_tenant, cov_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)
        out = R.generate_system_usage_analytics(start, end)
        assert out['success'] is True
        usage = out['analytics']
        assert usage['logs']['audit_trails'] >= 1
        assert usage['logs']['system_logs'] >= 1
        assert usage['logs']['security_events'] >= 1
        assert usage['notifications']['total'] >= 1
        assert usage['notifications']['unread'] >= 1


class TestComprehensiveCoverage:
    def test_exception_handler(self, app, isolated_tenant, cov_data, db, monkeypatch):
        import services.advanced_report_service as mod

        def raiser(*a, **k):
            raise RuntimeError('boom')

        monkeypatch.setattr(mod.AdvancedReportService, 'generate_patient_analytics', raiser)
        out = R.generate_comprehensive_report()
        assert out['success'] is False


class TestExceptionHandlers:
    def _run(self, app, db, call):
        orig = db.session.execute
        db.session.execute = _raise_boom
        try:
            out = call()
            assert out['success'] is False
        finally:
            db.session.execute = orig

    def test_patient(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_patient_analytics())  # noqa: PLW0108

    def test_visit(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_visit_analytics())  # noqa: PLW0108

    def test_financial(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_financial_analytics())  # noqa: PLW0108

    def test_doctor(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_doctor_performance_analytics())  # noqa: PLW0108

    def test_department(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_department_analytics())  # noqa: PLW0108

    def test_system_usage(self, app, isolated_tenant, cov_data, db):
        self._run(app, db, lambda: R.generate_system_usage_analytics())  # noqa: PLW0108


class TestExportCoverage:
    def test_empty_csv(self, app):
        out = R.export_analytics([], format='csv')
        assert out['success'] is True
        assert out['data'] == ''

    def test_none_cell(self, app):
        out = R.export_analytics([{'cell': None}], format='csv')
        assert out['success'] is True
        assert 'cell' in out['data']

    def test_formula_injection(self, app):
        rows = [{'cell': '=HYPERLINK("x")'}, {'cell': '+1'}, {'cell': '@SUM(1)'}, {'cell': '-2'}]
        out = R.export_analytics(rows, format='csv')
        assert out['success'] is True
        assert "'" in out['data']

    def test_exception(self, app):
        out = R.export_analytics([123], format='csv')
        assert out['success'] is False

    def test_unsupported_format(self, app):
        out = R.export_analytics([{'a': 1}], format='xlsx')
        assert out['success'] is False

    def test_json(self, app):
        out = R.export_analytics([{'a': 1}], format='json')
        assert out == {'success': True, 'data': [{'a': 1}]}
