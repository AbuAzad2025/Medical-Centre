"""
Service-level coverage for app/shared/dashboard_service.py â€” the Command Center
data + render helper.

Every DB-writing test runs under ``rollback_db`` so the session-scoped test
database stays pristine. Where count assertions would otherwise be polluted by
rows other tests committed to the shared default tenant, each test builds its
own tenant (``_fresh_tenant``) and binds it via ``tenant_test_context`` â€” the
same pattern the bundle-isolation suite uses â€” so every count is exact and
independent of test order. Read-only/pure helpers are exercised with plain
fakes.

Error branches are exercised by monkeypatching ``db.session.execute`` (or a
module-internal dependency) to raise, which is the actual failure mode the
``except Exception`` fallbacks exist for.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import g

from app.extensions import db
from app.shared import dashboard_service as ds
from app.shared.dashboard_registry import WidgetMeta
from models.appointment import Appointment
from models.emergency import EmergencyCase
from models.invoice import Invoice
from models.lab_request import LabRequest
from models.medication import Medication, PharmacySale, Prescription
from models.patient import Patient
from models.payment import Payment
from models.queue_management import QueueManagement
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from tests.tenant_context import (
    activate_tenant_modules,
    ensure_test_user,
    tenant_test_context,
)


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:12]}'


def _fresh_tenant(app, modules=()):
    from app.core.tenant.models import Tenant
    from app.shared.enums import TenantStatus

    t = Tenant(
        slug=_uniq('dashcov'),
        name='Dashboard Coverage Tenant',
        contact_email=f'{_uniq("cov")}@example.com',
        status=TenantStatus.ACTIVE,
    )
    db.session.add(t)
    db.session.commit()
    if modules:
        activate_tenant_modules(app, t, list(modules))
    return t


def _make_user(tenant, role, **extra):
    return ensure_test_user(db, tenant, username=_uniq(f'cov_{role}'), role=role, **extra)


def _patient(tenant):
    p = Patient(
        tenant_id=tenant.id,
        first_name=_uniq('First'),
        last_name=_uniq('Last'),
        gender='F',
        phone=f'059{uuid.uuid4().int % 10**7:07d}',
        national_id=_uniq('NAT'),
    )
    db.session.add(p)
    db.session.commit()
    return p


class _Raiser:
    """Session.execute replacement that always fails â€” drives the
    ``except Exception`` fallback branches in the loaders."""

    def __call__(self, *args, **kwargs):
        raise RuntimeError('boom')


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# build_hero_context â€” pure
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _fake_datetime(hour: int):
    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 10, hour, 30)

    return FakeDateTime


class TestBuildHeroContext:
    def test_morning_shift(self, monkeypatch):
        monkeypatch.setattr('app.shared.dashboard_service.datetime', _fake_datetime(9))
        user = SimpleNamespace(full_name='Ø£Ø­Ù…Ø¯', username='ahmed', role='doctor')
        ctx = ds.build_hero_context(user)
        assert ctx['shift_label'] == 'ØµØ¨Ø§Ø­'
        assert ctx['greeting_name'] == 'Ø£Ø­Ù…Ø¯'
        assert ctx['role_label'] == 'doctor'

    def test_noon_shift(self, monkeypatch):
        monkeypatch.setattr('app.shared.dashboard_service.datetime', _fake_datetime(13))
        ctx = ds.build_hero_context(SimpleNamespace(full_name=None, username='sam', role='nurse'))
        assert ctx['shift_label'] == 'Ø¸Ù‡Ø±'
        # full_name missing -> username is used
        assert ctx['greeting_name'] == 'sam'

    def test_evening_shift(self, monkeypatch):
        monkeypatch.setattr('app.shared.dashboard_service.datetime', _fake_datetime(19))
        ctx = ds.build_hero_context(SimpleNamespace(full_name='Ø³', username='u', role='lab'))
        assert ctx['shift_label'] == 'Ù…Ø³Ø§Ø¡'

    def test_date_label_uses_arabic_weekday_and_gregorian_date(self, monkeypatch):
        monkeypatch.setattr('app.shared.dashboard_service.datetime', _fake_datetime(9))
        weekdays = [
            'Ø§Ù„Ø§Ø«Ù†ÙŠÙ†',
            'Ø§Ù„Ø«Ù„Ø§Ø«Ø§Ø¡',
            'Ø§Ù„Ø£Ø±Ø¨Ø¹Ø§Ø¡',
            'Ø§Ù„Ø®Ù…ÙŠØ³',
            'Ø§Ù„Ø¬Ù…Ø¹Ø©',
            'Ø§Ù„Ø³Ø¨Øª',
            'Ø§Ù„Ø£Ø­Ø¯',
        ]
        d = date(2026, 11, 10)
        ctx = ds.build_hero_context(SimpleNamespace(full_name='x', username='x', role='r'))
        assert ctx['date_label'] == f'{weekdays[d.weekday()]} {d.day}/{d.month}/{d.year}'


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# _enabled_modules / _user_hidden_widgets / _tenant_id â€” helpers with g
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestEnabledModules:
    def test_missing_attribute_returns_empty(self, app):
        g.pop('enabled_modules', None)
        assert ds._enabled_modules() == set()

    def test_none_returns_empty(self, app):
        g.enabled_modules = None
        assert ds._enabled_modules() == set()

    def test_list_is_normalized_to_set(self, app):
        g.enabled_modules = ['lab', 'pharmacy']
        assert ds._enabled_modules() == {'lab', 'pharmacy'}


class TestUserHiddenWidgets:
    def test_user_without_preferences(self):
        user = SimpleNamespace(preferences=None)
        assert ds._user_hidden_widgets(user) == set()

    def test_hidden_widgets_from_preferences(self):
        user = SimpleNamespace(
            preferences={'dashboard': {'hidden_widgets': ['queue_live', 'kpi_strip']}}
        )
        assert ds._user_hidden_widgets(user) == {'queue_live', 'kpi_strip'}

    def test_non_dict_dashboard_branch(self, monkeypatch):
        monkeypatch.setattr(
            'app.shared.user_preferences.get_user_preferences',
            lambda _u: {'dashboard': 'not-a-dict'},
        )
        assert ds._user_hidden_widgets(SimpleNamespace()) == set()

    def test_missing_dashboard_branch(self, monkeypatch):
        monkeypatch.setattr(
            'app.shared.user_preferences.get_user_preferences',
            lambda _u: {},
        )
        assert ds._user_hidden_widgets(SimpleNamespace()) == set()


class TestTenantId:
    def test_user_tenant_id_wins(self, app):
        g.tenant_id = 111
        assert ds._tenant_id(SimpleNamespace(tenant_id=222)) == 222

    def test_falls_back_to_g(self, app):
        g.tenant_id = 111
        assert ds._tenant_id(SimpleNamespace(tenant_id=None)) == 111
        # no attribute at all -> same fallback
        assert ds._tenant_id(SimpleNamespace()) == 111

    def test_none_when_neither_set(self, app):
        g.pop('tenant_id', None)
        assert ds._tenant_id(SimpleNamespace(tenant_id=None)) is None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# _module_active
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestModuleActive:
    def test_no_tenant_means_active(self):
        assert ds._module_active(None, 'lab') is True

    def test_module_not_activated_returns_false(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception'])
        with tenant_test_context(app, t):
            assert ds._module_active(t.id, 'lab') is False

    def test_module_activated_returns_true(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['lab'])
        with tenant_test_context(app, t):
            assert ds._module_active(t.id, 'lab') is True

    def test_exception_returns_true(self, monkeypatch):
        def boom(_tid):
            raise RuntimeError('validator down')

        monkeypatch.setattr('app.core.module.validators.get_active_modules_for_tenant', boom)
        assert ds._module_active(123, 'lab') is True


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Reception loader â€” real rows
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadReceptionData:
    def test_empty_tenant_returns_zeroes(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            data = ds._load_role_data('reception', user)
        assert data['metrics']['queue_count'] == 0
        assert data['metrics']['visits_today'] == 0
        assert data['metrics']['total_patients'] == 0
        assert data['lists']['active_queue'] == []
        assert data['lists']['today_visits'] == []
        assert data['lists']['today_appointments'] == []

    def test_populated_tenant_counts_rows(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception', 'appointments'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            patient = _patient(t)
            # Visits: 3 today (OPEN/COMPLETED/CANCELLED) + 1 old
            today = date.today()
            v_open = Visit(tenant_id=t.id, patient_id=patient.id, status='OPEN', visit_date=today)
            v_done = Visit(
                tenant_id=t.id, patient_id=patient.id, status='COMPLETED', visit_date=today
            )
            v_old = Visit(
                tenant_id=t.id,
                patient_id=patient.id,
                status='OPEN',
                visit_date=date(2020, 1, 1),
            )
            db.session.add_all([v_open, v_done, v_old])
            # Appointments: 2 today (SCHEDULED + CONFIRMED) + 1 cancelled today + 1 old
            now = datetime.now()
            # same patient: distinct starts_at values (uq_appointment_patient_time)
            a1 = Appointment(
                tenant_id=t.id, patient_id=patient.id, starts_at=now, status='SCHEDULED'
            )
            a2 = Appointment(
                tenant_id=t.id,
                patient_id=patient.id,
                starts_at=now + timedelta(minutes=30),
                status='CONFIRMED',
            )
            a3 = Appointment(
                tenant_id=t.id,
                patient_id=patient.id,
                starts_at=now + timedelta(minutes=60),
                status='CANCELLED',
            )
            a4 = Appointment(
                tenant_id=t.id,
                patient_id=patient.id,
                starts_at=datetime(2020, 1, 1, 9, 0),
                status='SCHEDULED',
            )
            db.session.add_all([a1, a2, a3, a4])
            # Queue: waiting + called counted in queue_count; in_progress listed but
            # not counted; completed neither.
            q_wait = QueueManagement(
                tenant_id=t.id, patient_id=patient.id, queue_number=_uniq('Q'), status='waiting'
            )
            q_called = QueueManagement(
                tenant_id=t.id, patient_id=patient.id, queue_number=_uniq('Q'), status='called'
            )
            q_prog = QueueManagement(
                tenant_id=t.id,
                patient_id=patient.id,
                queue_number=_uniq('Q'),
                status='in_progress',
            )
            q_done = QueueManagement(
                tenant_id=t.id,
                patient_id=patient.id,
                queue_number=_uniq('Q'),
                status='completed',
            )
            db.session.add_all([q_wait, q_called, q_prog, q_done])
            db.session.commit()
            data = ds._load_role_data('reception', user)

        m = data['metrics']
        lst = data['lists']
        assert m['queue_count'] == 2  # waiting + called only
        # stats count visits created today, regardless of visit_date (v_old was
        # created today too), so all 3 count here.
        assert m['visits_today'] == 3
        assert m['total_patients'] == 1
        assert isinstance(lst['active_queue'], list)
        assert isinstance(lst['today_visits'], list)
        assert isinstance(lst['today_appointments'], list)

    def test_stats_exception_yields_zero_metrics(self, rollback_db, app, monkeypatch):
        from services.core_queries import core_queries

        t = _fresh_tenant(app, modules=['reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            monkeypatch.setattr(
                core_queries,
                'get_basic_dashboard_stats',
                lambda: (_ for _ in ()).throw(RuntimeError('stats down')),
            )
            data = ds._load_role_data('reception', user)
        assert data['metrics']['visits_today'] == 0
        assert data['metrics']['total_patients'] == 0

    def test_stats_non_dict_yields_zero_metrics(self, rollback_db, app, monkeypatch):
        from services.core_queries import core_queries

        t = _fresh_tenant(app, modules=['reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            monkeypatch.setattr(core_queries, 'get_basic_dashboard_stats', lambda: 42)
            data = ds._load_role_data('reception', user)
        assert data['metrics']['visits_today'] == 0
        assert data['metrics']['total_patients'] == 0


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Manager loader â€” real rows
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.mark.parametrize('role', ['manager', 'admin', 'super_admin', 'owner'])
class TestLoadManagerData:
    def test_empty_tenant(self, rollback_db, app, role):
        t = _fresh_tenant(app, modules=['billing'])
        with tenant_test_context(app, t):
            user = _make_user(t, role)
            data = ds._load_role_data(role, user)
        m = data['metrics']
        assert m['today_revenue'] == 0.0
        assert m['pending_invoices'] == 0
        assert m['pending_amount'] == 0.0
        assert m['staff_count'] == 1  # the user we just created
        assert m['active_staff'] == 1
        assert m['visits_today'] == 0

    def test_populated_tenant(self, rollback_db, app, role):
        t = _fresh_tenant(app, modules=['reception', 'billing'])
        with tenant_test_context(app, t):
            user = _make_user(t, role)
            patient = _patient(t)
            today = date.today()
            visit = Visit(tenant_id=t.id, patient_id=patient.id, status='OPEN', visit_date=today)
            db.session.add(visit)
            inv1 = Invoice(tenant_id=t.id, status='DRAFT', total_amount=100, paid_amount=0)
            inv2 = Invoice(tenant_id=t.id, status='ISSUED', total_amount=200, paid_amount=50)
            db.session.add_all([inv1, inv2])
            pay = Payment(tenant_id=t.id, amount=150, status='CONFIRMED')
            db.session.add(pay)
            db.session.commit()
            data = ds._load_role_data(role, user)

        m = data['metrics']
        assert m['today_revenue'] == 150.0
        assert m['pending_invoices'] == 2  # DRAFT + ISSUED
        assert m['pending_amount'] == 250.0  # (100-0) + (200-50)
        assert m['staff_count'] == 1
        assert m['active_staff'] == 1
        assert m['visits_today'] == 1


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Accountant loader â€” real rows
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadAccountantData:
    def test_empty_tenant_collection_rate_zero(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['billing'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'accountant')
            data = ds._load_role_data('accountant', user)
        m = data['metrics']
        assert m['pending_invoices'] == 0
        assert m['pending_amount'] == 0.0
        assert m['today_collected'] == 0.0
        assert m['collection_rate'] == 0.0
        assert m['total_billed'] == 0.0
        assert m['total_collected'] == 0.0
        assert m['today_payments'] == 0
        assert data['lists']['recent_payments'] == []

    def test_populated_tenant_computes_rate(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['billing'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'accountant')
            inv_issued = Invoice(tenant_id=t.id, status='ISSUED', total_amount=100, paid_amount=40)
            inv_partial = Invoice(
                tenant_id=t.id, status='PARTIAL', total_amount=200, paid_amount=50
            )
            inv_draft = Invoice(tenant_id=t.id, status='DRAFT', total_amount=50, paid_amount=0)
            db.session.add_all([inv_issued, inv_partial, inv_draft])
            pay_today = Payment(tenant_id=t.id, amount=30, status='CONFIRMED')
            pay_old = Payment(
                tenant_id=t.id,
                amount=70,
                status='CONFIRMED',
                created_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
            db.session.add_all([pay_today, pay_old])
            db.session.commit()
            data = ds._load_role_data('accountant', user)

        m = data['metrics']
        lst = data['lists']
        assert m['pending_invoices'] == 2  # ISSUED + DRAFT (PARTIAL not counted)
        assert m['pending_amount'] == 260.0  # (100-40) + (200-50) + (50-0)
        assert m['today_collected'] == 30.0
        assert m['total_billed'] == 350.0
        assert m['total_collected'] == 100.0
        assert m['collection_rate'] == round(100.0 / 350.0 * 100, 1) == 28.6
        assert m['today_payments'] == 1
        assert [p.id for p in lst['recent_payments']][0] == pay_today.id


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Error fallbacks â€” db.session.execute raises everywhere
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_RAISER_EXPECT = [
    (
        'reception',
        {'queue_count': 0, 'visits_today': 0, 'total_patients': 0},
        {'active_queue': [], 'today_visits': [], 'today_appointments': []},
    ),
    (
        'manager',
        {
            'today_revenue': 0.0,
            'pending_invoices': 0,
            'pending_amount': 0.0,
            'staff_count': 0,
            'active_staff': 0,
            'visits_today': 0,
        },
        {},
    ),
    (
        'accountant',
        {
            'pending_invoices': 0,
            'pending_amount': 0.0,
            'today_collected': 0.0,
            'collection_rate': 0.0,
            'total_billed': 0.0,
            'total_collected': 0.0,
            'today_payments': 0,
        },
        {'recent_payments': []},
    ),
    (
        'doctor',
        {'waiting_patients': 0, 'today_visits': 0},
        {
            'waiting_list': [],
            'today_appointments': [],
            'pending_lab': [],
            'pending_radiology': [],
        },
    ),
    (
        'lab',
        {'pending_requests': 0, 'completed_today': 0},
        {'lab_pending': []},
    ),
    (
        'technician',
        {'pending_requests': 0, 'completed_today': 0},
        {'lab_pending': []},
    ),
    (
        'radiology',
        {'pending_reports': 0},
        {'pending_radiology': []},
    ),
    (
        'emergency',
        {'critical_count': 0, 'active_cases': 0},
        {'emergency_cases': [], 'emergency_queue': []},
    ),
    ('nurse', {}, {'assigned': []}),
    (
        'pharmacist',
        {'dispense_today': 0, 'today_sales': 0.0},
        {
            'low_stock': [],
            'pending_prescriptions': [],
            'recent_sales': [],
        },
    ),
]


@pytest.mark.parametrize(('role', 'metrics_fallback', 'lists_fallback'), _RAISER_EXPECT)
def test_loader_exception_fallbacks(
    rollback_db, app, monkeypatch, role, metrics_fallback, lists_fallback
):
    modules = {
        'doctor': ['lab', 'radiology'],
        'radiology': ['radiology'],
        'emergency': ['emergency'],
        'nurse': ['nursing'],
        'pharmacist': ['pharmacy', 'doctor'],
        'lab': ['lab'],
        'technician': ['lab'],
    }.get(role, [])
    t = _fresh_tenant(app, modules=modules)
    with tenant_test_context(app, t):
        user = _make_user(t, role)
        monkeypatch.setattr(db.session, 'execute', _Raiser())
        data = ds._load_role_data(role, user)
    for key, value in metrics_fallback.items():
        assert data['metrics'][key] == value, f'{role}.metrics.{key}'
    for key, value in lists_fallback.items():
        assert data['lists'][key] == value, f'{role}.lists.{key}'


def test_load_role_data_unknown_role_returns_empty_schema(rollback_db, app):
    t = _fresh_tenant(app)
    with tenant_test_context(app, t):
        user = _make_user(t, 'reception')
        data = ds._load_role_data('patient', user)
    assert data == {'metrics': {}, 'lists': {}}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Doctor loader â€” real rows, module gating on lab/radiology
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _doctor_rows(t, doctor, other_doctor):
    patient = _patient(t)
    today = date.today()
    yesterday = date(2020, 1, 1)
    visits = {
        'open_today': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='OPEN',
            visit_date=today,
        ),
        'checked_in_today': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='CHECKED_IN',
            visit_date=today,
        ),
        'in_progress_today': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='IN_PROGRESS',
            visit_date=today,
        ),
        'completed_today': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='COMPLETED',
            visit_date=today,
        ),
        'open_old': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='OPEN',
            visit_date=yesterday,
        ),
        'other_doctor_open': Visit(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=other_doctor.id,
            status='OPEN',
            visit_date=today,
        ),
    }
    db.session.add_all(list(visits.values()))
    now = datetime.now()
    # distinct starts_at: uq_appointment_patient_time on (patient_id, starts_at)
    appts = [
        Appointment(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            starts_at=now,
            status='SCHEDULED',
        ),
        Appointment(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            starts_at=now + timedelta(minutes=30),
            status='CONFIRMED',
        ),
        Appointment(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=other_doctor.id,
            starts_at=now + timedelta(minutes=60),
            status='SCHEDULED',
        ),
    ]
    db.session.add_all(appts)
    db.session.commit()
    return patient, visits, appts


class TestLoadDoctorData:
    def test_doctor_metrics_lists_and_module_lists(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['doctor', 'lab', 'radiology', 'appointments'])
        with tenant_test_context(app, t):
            doctor = _make_user(t, 'doctor')
            other = _make_user(t, 'doctor')
            patient, visits, _appts = _doctor_rows(t, doctor, other)
            lab_req = LabRequest(
                tenant_id=t.id,
                patient_id=patient.id,
                visit_id=visits['open_today'].id,
                status='REQUESTED',
            )
            lab_prog = LabRequest(
                tenant_id=t.id,
                patient_id=patient.id,
                visit_id=visits['open_today'].id,
                status='IN_PROGRESS',
            )
            lab_done = LabRequest(
                tenant_id=t.id,
                patient_id=patient.id,
                visit_id=visits['open_today'].id,
                status='DONE',
            )
            rad_req = RadiologyRequest(
                tenant_id=t.id,
                patient_id=patient.id,
                visit_id=visits['open_today'].id,
                status='REQUESTED',
            )
            rad_prog = RadiologyRequest(
                tenant_id=t.id,
                patient_id=patient.id,
                visit_id=visits['open_today'].id,
                status='IN_PROGRESS',
            )
            db.session.add_all([lab_req, lab_prog, lab_done, rad_req, rad_prog])
            db.session.commit()
            data = ds._load_role_data('doctor', doctor)

        m = data['metrics']
        lst = data['lists']
        # waiting_patients: OPEN visits for this doctor, any date (2)
        assert m['waiting_patients'] == 2
        # today_visits: this doctor's visits today, any status (4)
        assert m['today_visits'] == 4
        assert {v.id for v in lst['waiting_list']} == {
            visits['open_today'].id,
            visits['checked_in_today'].id,
            visits['in_progress_today'].id,
        }
        assert isinstance(lst['today_appointments'], list)
        assert isinstance(lst['pending_lab'], list)
        assert isinstance(lst['pending_radiology'], list)

    def test_doctor_without_lab_radiology_modules_gets_empty_lists(self, rollback_db, app):
        t = _fresh_tenant(app)  # no modules activated
        with tenant_test_context(app, t):
            doctor = _make_user(t, 'doctor')
            patient = _patient(t)
            v = Visit(
                tenant_id=t.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                status='OPEN',
                visit_date=date.today(),
            )
            db.session.add(v)
            db.session.commit()
            data = ds._load_role_data('doctor', doctor)
        assert data['lists']['pending_lab'] == []
        assert data['lists']['pending_radiology'] == []


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Lab / technician loader â€” service path and fallback path
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.mark.parametrize('role', ['lab', 'technician'])
class TestLoadLabData:
    def test_with_lab_module_uses_lab_service_stats(self, rollback_db, app, role):
        t = _fresh_tenant(app, modules=['lab', 'reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, role)
            patient = _patient(t)
            r1 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='REQUESTED')
            r2 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='REQUESTED')
            r3 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='IN_PROGRESS')
            db.session.add_all([r1, r2, r3])
            db.session.commit()
            data = ds._load_role_data(role, user)

        m = data['metrics']
        lst = data['lists']
        # lab_service.get_dashboard_stats() counts status == REQUESTED only
        assert m['pending_requests'] == 2
        assert m['completed_today'] == 0
        # pending list covers REQUESTED/RECEIVED/IN_PROGRESS
        assert {r.id for r in lst['lab_pending']} == {r1.id, r2.id, r3.id}

    def test_without_lab_module_falls_back_to_count_queries(self, rollback_db, app, role):
        t = _fresh_tenant(app, modules=['doctor'])  # lab gate closed, patients writable
        with tenant_test_context(app, t):
            user = _make_user(t, role)
            patient = _patient(t)
            r1 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='REQUESTED')
            r2 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='IN_PROGRESS')
            r3 = LabRequest(tenant_id=t.id, patient_id=patient.id, status='DONE')
            db.session.add_all([r1, r2, r3])
            db.session.commit()
            data = ds._load_role_data(role, user)

        m = data['metrics']
        # fallback counts REQUESTED + IN_PROGRESS
        assert m['pending_requests'] == 2
        assert m['completed_today'] == 0
        assert {r.id for r in data['lists']['lab_pending']} == {r1.id, r2.id}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Radiology loader â€” real rows + module gating
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadRadiologyData:
    def test_with_module_counts_pending(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['radiology', 'reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'radiology')
            patient = _patient(t)
            r1 = RadiologyRequest(tenant_id=t.id, patient_id=patient.id, status='REQUESTED')
            r2 = RadiologyRequest(tenant_id=t.id, patient_id=patient.id, status='IN_PROGRESS')
            r3 = RadiologyRequest(tenant_id=t.id, patient_id=patient.id, status='DONE')
            db.session.add_all([r1, r2, r3])
            db.session.commit()
            data = ds._load_role_data('radiology', user)

        assert data['metrics']['pending_reports'] == 2
        assert {r.id for r in data['lists']['pending_radiology']} == {r1.id, r2.id}

    def test_without_module_skips_block(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['doctor'])  # radiology gate closed, patients writable
        with tenant_test_context(app, t):
            user = _make_user(t, 'radiology')
            patient = _patient(t)
            r1 = RadiologyRequest(tenant_id=t.id, patient_id=patient.id, status='REQUESTED')
            db.session.add(r1)
            db.session.commit()
            data = ds._load_role_data('radiology', user)

        assert 'pending_reports' not in data['metrics']
        assert 'pending_radiology' not in data['lists']


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Emergency loader â€” real rows + module gating
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _case(t, patient, severity, status='IN_PROGRESS'):
    c = EmergencyCase(
        tenant_id=t.id,
        patient_id=patient.id,
        case_number=_uniq('ER'),
        chief_complaint='pain',
        severity=severity,
        status=status,
    )
    db.session.add(c)
    return c


class TestLoadEmergencyData:
    def test_with_module_counts_and_lists(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['emergency'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'emergency')
            patient = _patient(t)
            high = _case(t, patient, 'HIGH')
            crit = _case(t, patient, 'CRITICAL')
            moderate = _case(t, patient, 'MODERATE')
            _done_high = _case(t, patient, 'HIGH', status='COMPLETED')
            db.session.commit()
            data = ds._load_role_data('emergency', user)

        m = data['metrics']
        lst = data['lists']
        # HIGH + CRITICAL, excluding COMPLETED
        assert m['critical_count'] == 2
        # everything except the COMPLETED case
        assert m['active_cases'] == 3
        assert {c.id for c in lst['emergency_cases']} == {
            high.id,
            crit.id,
            moderate.id,
        }
        # queue: HIGH/CRITICAL (URGENT is not an allowed severity in the DB check)
        assert {c.id for c in lst['emergency_queue']} == {high.id, crit.id}

    def test_without_module_skips_block(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'emergency')
            patient = _patient(t)
            _case(t, patient, 'HIGH')
            db.session.commit()
            data = ds._load_role_data('emergency', user)

        assert 'critical_count' not in data['metrics']
        assert 'emergency_cases' not in data['lists']


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Nurse loader â€” real rows + module gating
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadNurseData:
    def test_with_module_lists_todays_active_visits(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['nursing', 'reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'nurse')
            patient = _patient(t)
            today = date.today()
            v_open = Visit(tenant_id=t.id, patient_id=patient.id, status='OPEN', visit_date=today)
            v_prog = Visit(
                tenant_id=t.id, patient_id=patient.id, status='IN_PROGRESS', visit_date=today
            )
            v_check = Visit(
                tenant_id=t.id, patient_id=patient.id, status='CHECKED_IN', visit_date=today
            )
            v_done = Visit(
                tenant_id=t.id, patient_id=patient.id, status='COMPLETED', visit_date=today
            )
            v_old = Visit(
                tenant_id=t.id,
                patient_id=patient.id,
                status='OPEN',
                visit_date=date(2020, 1, 1),
            )
            db.session.add_all([v_open, v_prog, v_check, v_done, v_old])
            db.session.commit()
            data = ds._load_role_data('nurse', user)

        assert {v.id for v in data['lists']['assigned']} == {
            v_open.id,
            v_prog.id,
            v_check.id,
        }

    def test_without_module_skips_block(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'nurse')
            patient = _patient(t)
            db.session.add(
                Visit(
                    tenant_id=t.id,
                    patient_id=patient.id,
                    status='OPEN',
                    visit_date=date.today(),
                )
            )
            db.session.commit()
            data = ds._load_role_data('nurse', user)

        assert 'assigned' not in data['lists']


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Pharmacist loader â€” real rows + module gating on pharmacy and doctor
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestLoadPharmacistData:
    def _rows(self, t, patient, doctor):
        med_low = Medication(
            tenant_id=t.id,
            scientific_name='Sci A',
            trade_name='MedLow',
            dosage_form='tablet',
            strength='500mg',
            stock_quantity=2,
            minimum_stock=10,
        )
        med_out = Medication(
            tenant_id=t.id,
            scientific_name='Sci B',
            trade_name='MedOut',
            dosage_form='tablet',
            strength='250mg',
            stock_quantity=0,
            minimum_stock=5,
        )
        med_ok = Medication(
            tenant_id=t.id,
            scientific_name='Sci C',
            trade_name='MedOk',
            dosage_form='tablet',
            strength='100mg',
            stock_quantity=100,
            minimum_stock=10,
        )
        rx_active = Prescription(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            prescription_number=_uniq('RX'),
            status='active',
        )
        rx_done = Prescription(
            tenant_id=t.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            prescription_number=_uniq('RX'),
            status='dispensed',
        )
        sale = PharmacySale(
            tenant_id=t.id,
            total_amount=77.5,
            status='completed',
        )
        db.session.add_all([med_low, med_out, med_ok, rx_active, rx_done, sale])
        db.session.commit()
        return med_low, med_out, med_ok, rx_active, sale

    def test_with_pharmacy_and_doctor_modules(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['pharmacy', 'doctor'])
        with tenant_test_context(app, t):
            pharmacist = _make_user(t, 'pharmacist')
            doctor = _make_user(t, 'doctor')
            patient = _patient(t)
            med_low, med_out, _ok, rx_active, sale = self._rows(t, patient, doctor)
            data = ds._load_role_data('pharmacist', pharmacist)

        m = data['metrics']
        lst = data['lists']
        assert {x.id for x in lst['low_stock']} == {med_low.id, med_out.id}
        assert [x.id for x in lst['pending_prescriptions']] == [rx_active.id]
        assert [s.id for s in lst['recent_sales']] == [sale.id]
        assert m['dispense_today'] == 1
        assert m['today_sales'] == 77.5

    def test_without_doctor_module_prescriptions_are_empty(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['pharmacy'])
        with tenant_test_context(app, t):
            pharmacist = _make_user(t, 'pharmacist')
            doctor = _make_user(t, 'doctor')
            patient = _patient(t)
            self._rows(t, patient, doctor)
            data = ds._load_role_data('pharmacist', pharmacist)

        assert data['lists']['pending_prescriptions'] == []

    def test_without_pharmacy_module_skips_block(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            pharmacist = _make_user(t, 'pharmacist')
            med = Medication(
                tenant_id=t.id,
                scientific_name='Sci',
                trade_name='Med',
                dosage_form='tablet',
                strength='1mg',
                stock_quantity=0,
                minimum_stock=5,
            )
            db.session.add(med)
            db.session.commit()
            data = ds._load_role_data('pharmacist', pharmacist)

        assert 'dispense_today' not in data['metrics']
        assert 'low_stock' not in data['lists']


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# build_now_cards â€” pure widget -> card mapping
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _w(wid, priority=1, action_url=None, action_label=None):
    return WidgetMeta(
        id=wid,
        title_ar=f'Ø¹Ù†ÙˆØ§Ù† {wid}',
        roles=('x',),
        modules=(),
        size='md',
        priority=priority,
        template='dashboards/widgets/_x.html',
        icon='fa-x',
        action_url=action_url,
        action_label=action_label,
    )


class TestBuildNowCards:
    def test_non_priority_one_widgets_are_skipped(self):
        cards = ds.build_now_cards(
            [_w('queue_live', priority=2)], {'metrics': {}}, role='reception'
        )
        assert cards == []

    def test_queue_live(self):
        cards = ds.build_now_cards(
            [_w('queue_live')], {'metrics': {'queue_count': 7}}, role='reception'
        )
        assert cards[0]['value'] == 7
        assert cards[0]['id'] == 'queue_live'
        assert cards[0]['title'] == 'Ø¹Ù†ÙˆØ§Ù† queue_live'
        assert cards[0]['icon'] == 'fa-x'

    def test_my_queue_and_patients_waiting(self):
        for wid in ('my_queue', 'patients_waiting'):
            cards = ds.build_now_cards(
                [_w(wid)], {'metrics': {'waiting_patients': 3}}, role='doctor'
            )
            assert cards[0]['value'] == 3

    def test_cash_summary_accountant_formats_pending_amount(self):
        cards = ds.build_now_cards(
            [_w('cash_summary')],
            {'metrics': {'pending_amount': Decimal('12.5')}},
            role='accountant',
        )
        assert cards[0]['value'] == '12.50'

    def test_cash_summary_accountant_falls_back_to_today_collected(self):
        cards = ds.build_now_cards(
            [_w('cash_summary')],
            {'metrics': {'today_collected': 99.9}},
            role='accountant',
        )
        assert cards[0]['value'] == '99.90'

    def test_cash_summary_non_accountant_uses_visits_today(self):
        cards = ds.build_now_cards(
            [_w('cash_summary')],
            {'metrics': {'visits_today': 11}},
            role='reception',
        )
        assert cards[0]['value'] == 11

    def test_cash_summary_non_accountant_zero_visits_falls_back_to_queue(self):
        cards = ds.build_now_cards(
            [_w('cash_summary')],
            {'metrics': {'visits_today': 0, 'queue_count': 4}},
            role='reception',
        )
        assert cards[0]['value'] == 4

    def test_worklist_urgent(self):
        cards = ds.build_now_cards(
            [_w('worklist_urgent')], {'metrics': {'pending_requests': 6}}, role='lab'
        )
        assert cards[0]['value'] == 6

    def test_critical_count_and_triage_board(self):
        cards = ds.build_now_cards(
            [_w('critical_count'), _w('triage_board')],
            {'metrics': {'critical_count': 2, 'active_cases': 9}},
            role='emergency',
        )
        assert [c['value'] for c in cards] == [2, 9]

    def test_pending_payments(self):
        cards = ds.build_now_cards(
            [_w('pending_payments')], {'metrics': {'pending_invoices': 14}}, role='accountant'
        )
        assert cards[0]['value'] == 14

    def test_finance_overview_formats_rate_with_percent(self):
        cards = ds.build_now_cards(
            [_w('finance_overview')], {'metrics': {'collection_rate': 87.25}}, role='accountant'
        )
        assert cards[0]['value'] == '87.2%'

    def test_finance_overview_non_numeric_rate_passes_through(self):
        cards = ds.build_now_cards(
            [_w('finance_overview')], {'metrics': {'collection_rate': 'n/a'}}, role='accountant'
        )
        assert cards[0]['value'] == 'n/a'

    def test_revenue_today_formats_amount(self):
        cards = ds.build_now_cards(
            [_w('revenue_today')],
            {'metrics': {'today_collected': Decimal('1234.5')}},
            role='accountant',
        )
        assert cards[0]['value'] == '1234.50'

    def test_kpi_strip_manager_large_revenue_rounds_to_int(self):
        cards = ds.build_now_cards(
            [_w('kpi_strip')], {'metrics': {'today_revenue': 4321.6}}, role='manager'
        )
        assert cards[0]['value'] == '4322'

    def test_kpi_strip_manager_small_revenue_passes_through(self):
        cards = ds.build_now_cards(
            [_w('kpi_strip')], {'metrics': {'today_revenue': 500}}, role='manager'
        )
        assert cards[0]['value'] == 500

    def test_kpi_strip_manager_missing_revenue_falls_back_to_visits(self):
        cards = ds.build_now_cards(
            [_w('kpi_strip')], {'metrics': {'visits_today': 8}}, role='manager'
        )
        assert cards[0]['value'] == 8

    def test_kpi_strip_non_manager_uses_visits_today(self):
        cards = ds.build_now_cards(
            [_w('kpi_strip')], {'metrics': {'visits_today': 5}}, role='reception'
        )
        assert cards[0]['value'] == 5

    def test_manager_finance_rounds_pending_amount(self):
        cards = ds.build_now_cards(
            [_w('manager_finance')],
            {'metrics': {'pending_amount': Decimal('9876.6')}},
            role='manager',
        )
        assert cards[0]['value'] == '9877'

    def test_manager_hr_prefers_staff_count(self):
        cards = ds.build_now_cards(
            [_w('manager_hr')], {'metrics': {'staff_count': 21, 'active_staff': 20}}, role='manager'
        )
        assert cards[0]['value'] == 21

    def test_manager_hr_falls_back_to_active_staff(self):
        cards = ds.build_now_cards(
            [_w('manager_hr')], {'metrics': {'active_staff': 20}}, role='manager'
        )
        assert cards[0]['value'] == 20

    def test_nurse_assigned_counts_assigned_list(self):
        cards = ds.build_now_cards(
            [_w('nurse_assigned')], {'lists': {'assigned': [1, 2, 3]}}, role='nurse'
        )
        assert cards[0]['value'] == 3

    def test_pharmacy_dispense_and_sales(self):
        cards = ds.build_now_cards(
            [_w('pharmacy_dispense'), _w('pharmacy_sales')],
            {'metrics': {'dispense_today': 4, 'today_sales': Decimal('55.25')}},
            role='pharmacist',
        )
        assert [c['value'] for c in cards] == [4, '55.25']

    def test_unknown_widget_id_renders_dash(self):
        cards = ds.build_now_cards([_w('bogus_widget')], {'metrics': {}}, role='manager')
        assert cards[0]['value'] == 'â€”'

    def test_action_url_resolves_to_href(self, app):
        cards = ds.build_now_cards(
            [
                _w(
                    'queue_live',
                    action_url='reception.queue_management',
                    action_label='Ø§Ù„Ø·Ø§Ø¨ÙˆØ±',
                )
            ],
            {'metrics': {'queue_count': 1}},
            role='reception',
        )
        assert cards[0]['action_href']
        assert cards[0]['action_label'] == 'Ø§Ù„Ø·Ø§Ø¨ÙˆØ±'

    def test_action_url_build_failure_yields_none(self, app):
        cards = ds.build_now_cards(
            [_w('queue_live', action_url='bogus.nonexistent_endpoint')],
            {'metrics': {'queue_count': 1}},
            role='reception',
        )
        assert cards[0]['action_href'] is None

    def test_missing_action_url_yields_none(self, app):
        cards = ds.build_now_cards(
            [_w('queue_live', action_url=None)], {'metrics': {}}, role='reception'
        )
        assert cards[0]['action_href'] is None

    def test_cards_are_capped_at_four(self):
        widgets = [
            _w('queue_live'),
            _w('my_queue'),
            _w('worklist_urgent'),
            _w('critical_count'),
            _w('triage_board'),
        ]
        cards = ds.build_now_cards(widgets, {'metrics': {}}, role='reception')
        assert len(cards) == 4

    def test_missing_metrics_and_lists_sections(self):
        cards = ds.build_now_cards([_w('queue_live')], {}, role='reception')
        assert cards[0]['value'] == 0


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# build_command_center_context â€” the assembled page context
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestBuildCommandCenterContext:
    def test_reception_context_shape(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception', 'billing', 'appointments'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            g.enabled_modules = {'reception', 'billing', 'appointments'}
            ctx = ds.build_command_center_context(user, role='reception')

        assert ctx['dashboard_role'] == 'reception'
        from app.shared.dashboard_registry import ROLE_DASHBOARD_TITLES

        assert ctx['dashboard_title'] == ROLE_DASHBOARD_TITLES['reception']
        assert isinstance(ctx['widgets'], list) and ctx['widgets']
        assert all(w.priority == 1 for w in ctx['now_widgets'])
        now_ids = {w.id for w in ctx['now_widgets']}
        assert now_ids.issubset({w.id for w in ctx['widgets']})
        assert all(w.id not in now_ids for w in ctx['body_widgets'])
        assert len(ctx['now_cards']) <= 4
        assert isinstance(ctx['widget_data'], dict)
        assert 'metrics' in ctx['widget_data'] and 'lists' in ctx['widget_data']
        assert ctx['quick_actions'], 'reception role should resolve quick actions'
        for action in ctx['quick_actions']:
            assert action['href'].startswith('/')
            assert action['icon'] and action['label']
        assert ctx['hidden_widget_ids'] == []
        assert all(item['hidden'] is False for item in ctx['customizable_widgets'])
        assert [item['id'] for item in ctx['customizable_widgets']] == [
            'queue_live',
            'visits_today',
            'appointments_pending',
        ]
        assert 'hero' in ctx and 'greeting_name' in ctx['hero']

    def test_role_defaults_to_user_role(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'nurse')
            ctx = ds.build_command_center_context(user)
        assert ctx['dashboard_role'] == 'nurse'

    def test_extra_kwargs_are_merged_into_context(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'nurse')
            ctx = ds.build_command_center_context(user, role='nurse', custom_key='custom-value')
        assert ctx['custom_key'] == 'custom-value'

    def test_hidden_widgets_are_excluded_and_marked(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception', 'billing', 'appointments'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            user.preferences = {'dashboard': {'hidden_widgets': ['queue_live']}}
            db.session.commit()
            g.enabled_modules = {'reception', 'billing', 'appointments'}
            ctx = ds.build_command_center_context(user, role='reception')

        widget_ids = {w.id for w in ctx['widgets']}
        assert 'queue_live' not in widget_ids
        assert 'queue_live' in ctx['hidden_widget_ids']
        marked = {item['id']: item['hidden'] for item in ctx['customizable_widgets']}
        assert marked['queue_live'] is True
        assert marked['visits_today'] is False
        assert 'queue_live' not in {w.id for w in ctx['now_widgets']}

    def test_unknown_role_falls_back_to_manager_layout_and_default_title(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            ctx = ds.build_command_center_context(user, role='bogus_role_xyz')

        assert ctx['dashboard_title'] == 'Ù„ÙˆØ­Ø© Ø§Ù„Ù‚ÙŠØ§Ø¯Ø©'
        assert [item['id'] for item in ctx['customizable_widgets']] == [
            'kpi_strip',
            'manager_finance',
            'manager_hr',
            'queue_live',
        ]
        # the role matches no widget metadata -> nothing resolves
        assert ctx['widgets'] == []
        assert ctx['now_widgets'] == []
        assert ctx['body_widgets'] == []
        assert ctx['now_cards'] == []
        assert ctx['quick_actions'] == []

    def test_quick_action_url_errors_are_skipped(self, rollback_db, app, monkeypatch):
        t = _fresh_tenant(app, modules=['reception'])
        monkeypatch.setattr(
            'app.shared.dashboard_service.ROLE_QUICK_ACTIONS',
            {'reception': [('bogus.nope', 'fa-x', 'broken')]},
        )
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            ctx = ds.build_command_center_context(user, role='reception')
        assert ctx['quick_actions'] == []

    def test_enabled_modules_filter_widgets(self, rollback_db, app):
        t = _fresh_tenant(app)  # no modules active for this tenant
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            g.enabled_modules = set()
            ctx = ds.build_command_center_context(user, role='reception')
        # every reception widget requires a module, so nothing resolves
        assert ctx['widgets'] == []


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# render_command_center / snapshot_metrics
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRenderAndSnapshot:
    def test_render_command_center_renders_real_template(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception', 'billing', 'appointments'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            g.enabled_modules = {'reception', 'billing', 'appointments'}
            output = ds.render_command_center(user, role='reception')
        assert isinstance(output, str)
        assert len(output) > 0

    def test_snapshot_metrics_shape(self, rollback_db, app):
        t = _fresh_tenant(app, modules=['reception'])
        with tenant_test_context(app, t):
            user = _make_user(t, 'reception')
            snap = ds.snapshot_metrics(user, role='reception')

        assert snap['role'] == 'reception'
        assert isinstance(snap['metrics'], dict)
        ts = datetime.fromisoformat(snap['ts'])
        assert ts.tzinfo is not None

    def test_snapshot_metrics_role_defaults_to_user(self, rollback_db, app):
        t = _fresh_tenant(app)
        with tenant_test_context(app, t):
            user = _make_user(t, 'manager')
            snap = ds.snapshot_metrics(user)
        assert snap['role'] == 'manager'
