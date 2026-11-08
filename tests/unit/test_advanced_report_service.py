"""DB-backed tests for services.advanced_report_service aggregates."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.shared.enums import InvoiceStatus
from models.department import Department
from models.invoice import Invoice
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.advanced_report_service import AdvancedReportService

R = AdvancedReportService


@pytest.fixture
def report_data(app, test_tenant, db):
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    dept = Department(
        name=f'AdvReport-{suffix}',
        name_ar='قسم التقارير',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db.session.add(dept)
    db.session.flush()

    doctor = User(
        username=f'adr_doc_{suffix}',
        email=f'adr_doc_{suffix}@test.local',
        full_name='Report Doctor',
        role='doctor',
        is_active=True,
        tenant_id=test_tenant.id,
        department_id=dept.id,
    )
    doctor.set_password('test123')
    db.session.add(doctor)
    db.session.flush()

    p1 = Patient(
        tenant_id=test_tenant.id,
        first_name='Ana',
        last_name='Lima',
        phone=f'0521{suffix[-6:]}',
        gender='F',
        birth_date=date(1990, 5, 1),
    )
    p2 = Patient(
        tenant_id=test_tenant.id,
        first_name='Bruno',
        last_name='Silva',
        phone=f'0522{suffix[-6:]}',
        gender='M',
        birth_date=date(2010, 5, 1),
    )
    db.session.add_all([p1, p2])
    db.session.flush()

    today = date.today()
    visit1 = Visit(
        tenant_id=test_tenant.id,
        patient_id=p1.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        visit_date=today,
        visit_time=datetime.now(UTC),
        status='COMPLETED',
        visit_type='CONSULTATION',
        total_amount=100,
        paid_amount=100,
    )
    visit2 = Visit(
        tenant_id=test_tenant.id,
        patient_id=p2.id,
        department_id=dept.id,
        doctor_id=doctor.id,
        visit_date=today,
        visit_time=datetime.now(UTC),
        status='COMPLETED',
        visit_type='FOLLOW_UP',
        total_amount=200,
        paid_amount=50,
    )
    db.session.add_all([visit1, visit2])
    db.session.flush()

    for amount, method in ((100, 'CASH'), (200, 'CARD'), (100, 'CASH')):
        db.session.add(
            Payment(
                tenant_id=test_tenant.id,
                patient_id=p1.id,
                visit_id=visit1.id,
                method=method,
                amount=amount,
                currency='ILS',
                status='CONFIRMED',
                payment_date=datetime.now(UTC),
            )
        )
    inv = Invoice(
        tenant_id=test_tenant.id,
        visit_id=visit1.id,
        total_amount=400,
        status=InvoiceStatus.PAID,
        currency='ILS',
    )
    db.session.add(inv)
    db.session.commit()
    return {
        'dept': dept,
        'doctor': doctor,
        'p1': p1,
        'p2': p2,
        'visit1': visit1,
        'visit2': visit2,
        'today': today,
    }


class TestPatientAnalytics:
    def test_counts_and_groups(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=7)
        out = R.generate_patient_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        analytics = out['analytics']
        assert analytics['total_patients'] == 2
        assert analytics['gender_distribution']['F'] == 1
        assert analytics['gender_distribution']['M'] == 1
        assert analytics['age_groups']['36-50'] == 1  # Ana (1990)
        assert analytics['age_groups']['0-18'] == 1  # Bruno (2010)
        assert analytics['status_distribution']['active'] == 2

    def test_department_filter_uses_distinct_patients(self, app, test_tenant, report_data, db):
        dept = report_data['dept']
        start = datetime.now(UTC) - timedelta(days=7)
        out = R.generate_patient_analytics(start, datetime.now(UTC), department_id=dept.id)
        assert out['success'] is True
        # One patient per visit row would be double counted without DISTINCT
        assert out['analytics']['total_patients'] == 2


class TestVisitAnalytics:
    def test_totals_and_types(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_visit_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        analytics = out['analytics']
        assert analytics['total_visits'] == 2
        assert analytics['visit_type_distribution']['CONSULTATION'] == 1
        assert analytics['visit_type_distribution']['FOLLOW_UP'] == 1
        assert analytics['daily_visits'] != {}


class TestFinancialAnalytics:
    def test_revenue_not_cross_joined(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_financial_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        payments = out['analytics']['payments']
        assert payments['total_count'] == 3
        # 100 + 200 + 100 = 400, not 400 x (number of payments)
        assert payments['total_revenue'] == 400
        assert payments['method_distribution']['CASH']['count'] == 2
        assert payments['method_distribution']['CASH']['amount'] == 200.0
        assert payments['method_distribution']['CARD']['amount'] == 200.0

    def test_invoice_metrics(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_financial_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        invoices = out['analytics']['invoices']
        assert invoices['total_count'] == 1
        assert invoices['paid_count'] == 1
        assert invoices['total_amount'] == 400


class TestDoctorPerformanceAnalytics:
    def test_performance_aggregates(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_doctor_performance_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        rows = out['analytics']['doctor_performance']
        assert len(rows) == 1
        doc = rows[0]
        assert doc['doctor_id'] == report_data['doctor'].id
        assert doc['total_visits'] == 2
        assert doc['completed_visits'] == 2
        assert doc['completion_rate'] == 100.0
        assert doc['total_revenue'] == 300
        assert doc['paid_revenue'] == 150

    def test_filter_by_doctor(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_doctor_performance_analytics(
            start, datetime.now(UTC), doctor_id=report_data['doctor'].id
        )
        assert out['success'] is True
        assert len(out['analytics']['doctor_performance']) == 1


class TestDepartmentAnalytics:
    def test_department_aggregates(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        dept = report_data['dept']
        out = R.generate_department_analytics(start, datetime.now(UTC), department_id=dept.id)
        assert out['success'] is True
        rows = out['analytics']['department_analytics']
        assert len(rows) == 1
        row = rows[0]
        assert row['department_id'] == dept.id
        assert row['total_visits'] == 2
        assert row['total_revenue'] == 300


class TestSystemUsageAnalytics:
    def test_totals(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_system_usage_analytics(start, datetime.now(UTC))
        assert out['success'] is True
        usage = out['analytics']
        assert usage['total_users'] >= 1
        assert usage['active_users'] >= 1
        assert 'role_distribution' in usage['users']
        assert usage['users']['role_distribution']['doctor'] >= 1


class TestComprehensiveReport:
    def test_wraps_subreports(self, app, test_tenant, report_data, db):
        start = datetime.now(UTC) - timedelta(days=1)
        out = R.generate_comprehensive_report(start, datetime.now(UTC))
        assert out['success'] is True
        report = out['comprehensive_report']
        assert 'patient_analytics' in report
        assert 'visit_analytics' in report
        assert 'financial_analytics' in report
        assert 'doctor_performance' in report
        assert 'department_analytics' in report
        assert 'system_usage' in report
        assert 'generated_at' in out


class TestExportAnalytics:
    def test_json_passthrough(self, app):
        out = R.export_analytics([{'a': 1}], format='json')
        assert out == {'success': True, 'data': [{'a': 1}]}

    def test_csv_export(self, app):
        out = R.export_analytics([{'name': 'Ana', 'amount': 100}], format='csv')
        assert out['success'] is True
        assert 'name,amount' in out['data']
        assert 'Ana,100' in out['data']

    def test_csv_formula_injection_neutralized(self, app):
        rows = [
            {'cell': '=HYPERLINK("http://evil.example")'},
            {'cell': '+1+1'},
            {'cell': '@SUM(1)'},
            {'cell': '-2-2'},
        ]
        out = R.export_analytics(rows, format='csv')
        assert out['success'] is True
        import csv
        import io

        cells = list(csv.reader(io.StringIO(out['data'])))[1:]
        assert all(cell[0].startswith("'") for cell in cells)

    def test_csv_extras_ignored_not_raised(self, app):
        rows = [{'a': 1, 'b': 2}, {'a': 3}]
        out = R.export_analytics(rows, format='csv')
        assert out['success'] is True
        assert '3,' in out['data']

    def test_unsupported_format(self, app):
        out = R.export_analytics([{'a': 1}], format='xlsx')
        assert out['success'] is False
