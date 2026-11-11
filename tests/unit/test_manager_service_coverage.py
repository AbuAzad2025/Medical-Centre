"""Coverage tests for services.manager_service.py."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import sys

import pytest
from sqlalchemy.orm import Session as SA_Session

from models.user import User
from services.manager_service import ManagerService

pytest_plugins = ['tests._isolated_tenant']


def _make_user(db, tenant_id, username, role='doctor', is_active=True, department_id=None):
    u = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=is_active,
        tenant_id=tenant_id,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.flush()
    return u


def _make_department(db, tenant_id, name='Dept'):
    from models.department import Department

    d = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(d)
    db.session.flush()
    return d


def _make_patient(db, tenant_id, first_name='Patient', last_name='Test'):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_visit(db, tenant_id, patient, department, status='OPEN', created_at=None):
    from models.visit import Visit

    if created_at is None:
        created_at = datetime.now(UTC)
    v = Visit(
        patient_id=patient.id,
        department_id=department.id,
        doctor_id=None,
        status=status,
        payment_status='PENDING',
        total_amount=0,
        paid_amount=0,
        visit_type='REGULAR',
        payment_method='cash',
        is_emergency=False,
        created_at=created_at,
        visit_date=date.today(),
    )
    db.session.add(v)
    db.session.flush()
    return v


def _make_invoice(db, tenant_id, total_amount=Decimal('100.00')):
    from models.invoice import Invoice

    inv = Invoice(
        tenant_id=tenant_id,
        invoice_number=f'INV-{datetime.now(UTC).strftime("%H%M%S%f")}',
        total_amount=total_amount,
        currency='ILS',
        status='ISSUED',
        created_at=datetime.now(UTC),
    )
    db.session.add(inv)
    db.session.flush()
    return inv


def _make_payment(db, tenant_id, amount=Decimal('100.00')):
    from models.payment import Payment

    pay = Payment(
        tenant_id=tenant_id,
        amount=amount,
        method='cash',
        currency='ILS',
        status='CONFIRMED',
        created_at=datetime.now(UTC),
    )
    db.session.add(pay)
    db.session.flush()
    return pay


def _make_expense(db, tenant_id, amount=Decimal('50.00')):
    from models.expense import Expense

    exp = Expense(
        tenant_id=tenant_id,
        category='rent',
        amount=amount,
        description='Test expense',
    )
    db.session.add(exp)
    db.session.flush()
    return exp


def _make_audit_trail(db, tenant_id, action='login', created_at=None):
    from models.audit_trail import AuditTrail

    if created_at is None:
        created_at = datetime.now(UTC)
    audit = AuditTrail(
        tenant_id=tenant_id,
        user_id=None,
        action=action,
        entity_type='user',
        entity_id=0,
        created_at=created_at,
    )
    db.session.add(audit)
    db.session.flush()
    return audit


def _boom(*a, **k):
    raise RuntimeError('db down')


def _get_module():
    """Get the actual module object (not the singleton)."""
    return sys.modules['services.manager_service']


class TestManagerService:
    def test_get_organization_stats(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        user = _make_user(db, test_tenant.id, 'mgr_stats_user')
        patient = _make_patient(db, test_tenant.id)
        today = datetime.now(UTC)
        _make_visit(db, test_tenant.id, patient, dept, status='WAITING', created_at=today)
        _make_visit(db, test_tenant.id, patient, dept, status='INPATIENT', created_at=today - timedelta(days=1))

        result = ManagerService.get_organization_stats()
        assert 'total_patients' in result
        assert 'total_staff' in result
        assert 'total_visits' in result
        assert 'total_departments' in result
        assert 'today_visits' in result
        assert 'active_visits' in result

    def test_get_organization_stats_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_organization_stats()
        assert result == {}

    def test_get_financial_summary(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _make_invoice(db, test_tenant.id, Decimal('500.00'))
        _make_payment(db, test_tenant.id, Decimal('300.00'))
        _make_expense(db, test_tenant.id, Decimal('100.00'))

        result = ManagerService.get_financial_summary()
        assert 'total_billed' in result
        assert 'total_collected' in result
        assert 'total_expenses' in result
        assert 'net_revenue' in result
        assert result['net_revenue'] == 200.0

    def test_get_financial_summary_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_financial_summary()
        assert result == {}

    def test_get_staff_stats(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _make_user(db, test_tenant.id, 'staff_active', role='doctor', is_active=True)
        _make_user(db, test_tenant.id, 'staff_inactive', role='doctor', is_active=False)
        _make_user(db, test_tenant.id, 'staff_patient', role='patient', is_active=True)

        result = ManagerService.get_staff_stats()
        assert 'total' in result
        assert 'active' in result

    def test_get_staff_stats_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_staff_stats()
        assert result == {'total': 0, 'active': 0}

    def test_get_recent_activities(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _make_audit_trail(db, test_tenant.id, action='login')
        _make_audit_trail(db, test_tenant.id, action='logout', created_at=datetime.now(UTC) - timedelta(hours=1))

        result = ManagerService.get_recent_activities(limit=5)
        assert isinstance(result, list)

    def test_get_recent_activities_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_recent_activities()
        assert result == []

    def test_get_department_performance(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id, name='Cardiology')
        patient = _make_patient(db, test_tenant.id)
        _make_visit(db, test_tenant.id, patient, dept, status='COMPLETED')
        _make_visit(db, test_tenant.id, patient, dept, status='COMPLETED')

        result = ManagerService.get_department_performance()
        assert isinstance(result, list)

    def test_get_department_performance_with_id(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id, name='Cardiology')
        patient = _make_patient(db, test_tenant.id)
        _make_visit(db, test_tenant.id, patient, dept, status='COMPLETED')

        result = ManagerService.get_department_performance(department_id=dept.id)
        assert isinstance(result, list)

    def test_get_department_performance_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_department_performance()
        assert result == []

    def test_get_satisfaction_stats(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from models.patient_satisfaction import PatientSatisfactionSurvey

        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept, status='COMPLETED')

        s1 = PatientSatisfactionSurvey(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            patient_id=patient.id,
            token='TOKEN-001',
            rating=4,
            submitted_at=datetime.now(UTC),
        )
        s2 = PatientSatisfactionSurvey(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            patient_id=patient.id,
            token='TOKEN-002',
            rating=5,
            submitted_at=datetime.now(UTC),
        )
        db.session.add(s1)
        db.session.add(s2)
        db.session.flush()

        result = ManagerService.get_satisfaction_stats()
        assert 'average_rating' in result
        assert 'total_responses' in result
        assert result['total_responses'] == 2

    def test_get_satisfaction_stats_no_responses(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = ManagerService.get_satisfaction_stats()
        assert result == {'average_rating': 0, 'total_responses': 0}

    def test_get_satisfaction_stats_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        monkeypatch.setattr(SA_Session, 'execute', _boom, raising=False)
        result = ManagerService.get_satisfaction_stats()
        assert result == {'average_rating': 0, 'total_responses': 0}

    def test_approve_request_leave_module_missing(self, app, db, test_tenant):
        """models.staff does not exist, so leave approval returns False."""
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = ManagerService.approve_request('leave', 999, approved_by=1)
        assert result is False

    def test_approve_request_expense(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        exp = _make_expense(db, test_tenant.id, Decimal('100.00'))

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = ManagerService.approve_request('expense', exp.id, approved_by=1)
            assert result is True

    def test_approve_request_unknown_type(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = ManagerService.approve_request('unknown_type', 999, approved_by=1)
        assert result is False

    def test_approve_request_tenant_context_error(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from utils.tenant_query import TenantContextError

        ms_module = _get_module()

        def get_record_boom(*a, **k):
            raise TenantContextError('no tenant')

        monkeypatch.setattr(ms_module, 'get_tenant_record', get_record_boom)
        result = ManagerService.approve_request('expense', 999, approved_by=1)
        assert result is False

    def test_approve_request_commit_failure(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        ms_module = sys.modules['services.manager_service']

        exp = _make_expense(db, test_tenant.id, Decimal('100.00'))

        def commit_boom(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(ms_module, 'safe_commit', commit_boom)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g as bind2

            bind2(test_tenant, db_session=db.session)
            result = ManagerService.approve_request('expense', exp.id, approved_by=1)
            assert result is False
