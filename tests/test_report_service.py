"""Tests for services.report_service.ReportService.

Drives the deterministic aggregation/audit reports against the live schema with
a seeded "today" dataset so the daily/monthly audit bodies, financial rollups,
debt tracking and audit-issue branches all execute. ``rollback_db``.
"""
import types
import uuid
from datetime import datetime, date, timedelta, timezone

import pytest

from services.report_service import ReportService as RP
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.payment import Payment
from models.invoice import Invoice
from models.department import Department
from models.user import User
from app.shared.enums import VisitState, AppointmentState


@pytest.fixture
def seed(rollback_db):
    db = rollback_db
    now = datetime.now()
    today = date.today()

    dept = Department(name='Cardio', name_ar='قلبية')
    db.session.add(dept)
    db.session.commit()

    un = 'rp_' + uuid.uuid4().hex[:8]
    doc = User(username=un, email=un + '@x.com', full_name='Dr', role='doctor',
               is_active=True, department_id=dept.id)
    doc.set_password('p')
    db.session.add(doc)
    db.session.commit()

    pat = Patient(first_name='تق', last_name='رير', phone='+97059900000')
    db.session.add(pat)
    db.session.commit()

    def visit(**kw):
        params = dict(patient_id=pat.id, doctor_id=doc.id, department_id=dept.id,
                      visit_date=today, created_at=now, status=VisitState.COMPLETED,
                      visit_type='REGULAR', total_amount=200, paid_amount=200)
        params.update(kw)
        v = Visit(**params)
        db.session.add(v)
        db.session.commit()
        return v

    def payment(visit_id, amount=200, method='CASH', status='CONFIRMED'):
        p = Payment(visit_id=visit_id, amount=amount, method=method, status=status,
                    currency='ILS', operation_type='visit_payment',
                    payment_date=now, created_at=now)
        db.session.add(p)
        db.session.commit()
        return p

    v = visit()
    payment(v.id)
    db.session.add(Appointment(patient_id=pat.id, doctor_id=doc.id, department_id=dept.id,
                               starts_at=now, status=AppointmentState.DONE))
    db.session.add(Invoice(invoice_number='INV-' + uuid.uuid4().hex[:8], visit_id=v.id,
                           created_by=doc.id, status='PAID', currency='ILS',
                           total_amount=200, paid_amount=200, created_at=now))
    db.session.commit()

    return types.SimpleNamespace(db=db, dept=dept, doc=doc, pat=pat, visit=visit,
                                 payment=payment, now=now, today=today)


class TestSummaries:
    def test_dashboard_summary(self, seed):
        res = RP.get_dashboard_summary()
        assert res['success'] is True
        assert set(res['summary']) == {'patients', 'visits', 'appointments', 'financial'}

    def test_dashboard_summary_by_department(self, seed):
        res = RP.get_dashboard_summary(department_id=seed.dept.id)
        assert res['success'] is True

    def test_financial_report(self, seed):
        res = RP.get_financial_report()
        assert res['success'] is True
        assert res['summary']['total_revenue'] >= 200

    def test_financial_report_by_department(self, seed):
        res = RP.get_financial_report(department_id=seed.dept.id)
        assert res['success'] is True


class TestEntityReports:
    def test_patient_report(self, seed):
        res = RP.get_patient_report(seed.pat.id)
        assert res['success'] is True
        assert res['patient']['id'] == seed.pat.id
        assert len(res['visits']) >= 1

    def test_patient_report_not_found(self, seed):
        assert RP.get_patient_report(99999999)['success'] is False

    def test_department_report(self, seed):
        res = RP.get_department_report(seed.dept.id)
        assert res['success'] is True
        assert res['statistics']['total_visits'] >= 1

    def test_department_report_not_found(self, seed):
        assert RP.get_department_report(99999999)['success'] is False

    def test_doctor_performance(self, seed):
        res = RP.get_doctor_performance_report(seed.doc.id)
        assert res['success'] is True
        assert res['statistics']['total_visits'] >= 1

    def test_doctor_performance_non_doctor(self, seed):
        un = 'rec_' + uuid.uuid4().hex[:6]
        u = User(username=un, email=un + '@x.com', full_name='R', role='reception', is_active=True)
        u.set_password('p')
        seed.db.session.add(u)
        seed.db.session.commit()
        assert RP.get_doctor_performance_report(u.id)['success'] is False

    def test_doctor_performance_in_progress_pending(self, seed):
        seed.visit(status=VisitState.IN_PROGRESS, payment_status='PENDING',
                   total_amount=100, paid_amount=0)
        res = RP.get_doctor_performance_report(seed.doc.id)
        assert res['success'] is True
        assert res['statistics'].get('pending_visits', 0) >= 1

    def test_dashboard_summary_date_range(self, seed):
        start = datetime.combine(seed.today - timedelta(days=30), datetime.min.time())
        end = datetime.combine(seed.today, datetime.max.time())
        res = RP.get_dashboard_summary(start_date=start, end_date=end)
        assert res['success'] is True

    def test_export_csv_exception(self, seed, monkeypatch):
        monkeypatch.setattr(
            'csv.DictWriter',
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')),
        )
        res = RP.export_report('x', [{'a': 1}], format='csv')
        assert res['success'] is False


class TestExport:
    def test_export_json(self, seed):
        res = RP.export_report('x', [{'a': 1}], format='json')
        assert res['success'] is True and res['data'] == [{'a': 1}]

    def test_export_csv(self, seed):
        res = RP.export_report('x', [{'a': 1, 'b': 2}], format='csv')
        assert res['success'] is True
        assert 'a' in res['data']

    def test_export_unsupported(self, seed):
        assert RP.export_report('x', [], format='pdf')['success'] is False


class TestAuditReports:
    def test_daily_audit_basic(self, seed):
        res = RP.get_daily_audit_report()
        assert res['success'] is True
        assert 'summary' in res and 'audit_issues' in res
        assert res['summary']['total_visits'] >= 1

    def test_daily_audit_issue_branches(self, seed):
        # unpaid visit (PENDING, not force)
        seed.visit(status=VisitState.OPEN, payment_status='PENDING',
                   is_force_payment=False, total_amount=100, paid_amount=0)
        # force payment pending approval
        seed.visit(is_force_payment=True, force_payment_approved_by=None,
                   force_payment_reason='عاجل', payment_status='PENDING')
        # insurance visit
        seed.visit(payment_method='insurance', insurance_amount=300,
                   patient_share=50, insurance_provider='شركة')
        # cancelled + large cash payments today
        v = seed.visit()
        seed.payment(v.id, amount=1500, method='CASH', status='CONFIRMED')
        seed.payment(v.id, amount=80, method='CASH', status='CANCELLED')
        res = RP.get_daily_audit_report()
        assert res['success'] is True
        types_found = {i['type'] for i in res['audit_issues']}
        assert {'UNPAID_VISITS', 'FORCE_PAYMENT_PENDING',
                'CANCELLED_PAYMENTS', 'LARGE_CASH_PAYMENTS'} <= types_found

    def test_daily_audit_explicit_date(self, seed):
        res = RP.get_daily_audit_report(target_date=datetime.now())
        assert res['success'] is True

    def test_monthly_audit(self, seed):
        # debt branch + force-payment KPI-alert branch (force % over 5% threshold)
        seed.visit(payment_status='DEBT', total_amount=200, paid_amount=50)
        seed.visit(is_force_payment=True, force_payment_approved_by=None,
                   force_payment_reason='عاجل', payment_status='PENDING')
        seed.visit(is_force_payment=True, force_payment_approved_by=seed.doc.id,
                   force_payment_reason='موافق', status=VisitState.COMPLETED)
        res = RP.get_monthly_audit_report()
        assert res['success'] is True
        assert 'kpis' in res and 'financial' in res
        assert res['kpis']['force_payment_percentage'] > 0
        assert isinstance(res['kpi_alerts'], list)

    def test_monthly_audit_explicit_period(self, seed):
        now = datetime.now()
        res = RP.get_monthly_audit_report(year=now.year, month=now.month)
        assert res['success'] is True

    def test_debt_tracking(self, seed):
        seed.visit(payment_status='DEBT', total_amount=500, paid_amount=100)
        res = RP.get_debt_tracking_report()
        assert res['success'] is True
        assert res['summary']['total_debts'] >= 1

    def test_debt_tracking_age_buckets(self, seed):
        old = datetime.now() - timedelta(days=40)
        seed.visit(payment_status='DEBT', total_amount=300, paid_amount=50, created_at=old)
        res = RP.get_debt_tracking_report()
        assert res['success'] is True
        assert len(res.get('debts_by_age', {}).get('31-60_days', [])) >= 1

    def test_financial_report_card_method(self, seed):
        v = seed.visit()
        seed.payment(v.id, amount=75, method='CARD', status='CONFIRMED')
        res = RP.get_financial_report()
        assert res['success'] is True
        assert res['summary'].get('card_revenue', 0) >= 75

    def test_monthly_audit_collection_rate_alert(self, seed, monkeypatch):
        seed.visit(payment_status='DEBT', total_amount=1000, paid_amount=10)
        res = RP.get_monthly_audit_report()
        assert res['success'] is True
        if res['kpis'].get('collection_rate', 100) < 90:
            assert any(a.get('kpi') == 'collection_rate' for a in res.get('kpi_alerts', []))


class TestSlowQueries:
    def test_slow_queries_report(self, seed):
        res = RP.get_slow_queries_report(limit=5)
        assert isinstance(res, dict) and 'success' in res

    def test_capture_weekly_slow_queries(self, seed):
        res = RP.capture_weekly_slow_queries(limit=5, created_by=seed.doc.id)
        assert isinstance(res, dict) and 'success' in res
