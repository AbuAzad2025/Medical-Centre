"""Tests for services.reception_service.ReceptionService (live schema)."""
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.shared.enums import VisitState
from models.appointment import Appointment
from models.patient import Patient
from models.visit import Visit
from services.reception_service import ReceptionService


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


@pytest.fixture
def rfx(rollback_db):
    db = rollback_db

    def patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'ر'),
            last_name=kw.get('last_name', 'س'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
        )
        db.session.add(p)
        db.session.commit()
        return p

    def department_id():
        from models.department import Department
        tag = uuid.uuid4().hex[:6]
        d = Department(name='Dept-' + tag, name_ar='قسم-' + tag)
        db.session.add(d)
        db.session.commit()
        return d.id

    def appointment(patient_id, department_id=None, status='SCHEDULED', days_ahead=0):
        starts = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        apt = Appointment(
            patient_id=patient_id,
            department_id=department_id,
            starts_at=starts,
            status=status,
        )
        db.session.add(apt)
        db.session.commit()
        return apt

    return types.SimpleNamespace(db=db, patient=patient, department_id=department_id, appointment=appointment)


class TestTodayStats:
    def test_counts_visits_and_appointments(self, rfx):
        p = rfx.patient()
        rfx.appointment(p.id)
        v = Visit(patient_id=p.id, status=VisitState.OPEN.value)
        rfx.db.session.add(v)
        rfx.db.session.commit()
        stats = ReceptionService.get_today_stats()
        assert stats['today_visits'] >= 1
        assert stats['today_appointments'] >= 1
        assert 'waiting' in stats


class TestRegisterPatient:
    def test_splits_name(self, rfx):
        p = ReceptionService.register_patient({'name': 'أحمد علي', 'phone': '0501111111'})
        assert p is not None
        assert p.first_name == 'أحمد'
        assert p.last_name == 'علي'


class TestSearchPatients:
    def test_finds_by_phone(self, rfx):
        p = rfx.patient(phone='0502222222')
        hits = ReceptionService.search_patients('050222')
        assert any(x.id == p.id for x in hits)


class TestCreateVisit:
    def test_uses_open_status(self, rfx):
        p = rfx.patient()
        dept = rfx.department_id()
        v = ReceptionService.create_visit(p.id, dept)
        assert v is not None
        assert v.status == VisitState.OPEN.value


class TestGetQueue:
    def test_returns_open_visits(self, rfx):
        p = rfx.patient()
        dept = rfx.department_id()
        v = Visit(patient_id=p.id, department_id=dept, status=VisitState.OPEN.value)
        rfx.db.session.add(v)
        rfx.db.session.commit()
        q = ReceptionService.get_queue(dept)
        assert any(x.id == v.id for x in q)


class TestCheckInAppointment:
    def test_sets_checked_in(self, rfx):
        p = rfx.patient()
        apt = rfx.appointment(p.id)
        assert ReceptionService.check_in_appointment(apt.id) is True
        rfx.db.session.refresh(apt)
        assert apt.status == 'CHECKED_IN'

    def test_missing_returns_false(self, rfx):
        assert ReceptionService.check_in_appointment(99999999) is False


class TestUpcomingAppointments:
    def test_future_only(self, rfx):
        p = rfx.patient()
        future = rfx.appointment(p.id, days_ahead=2)
        past = rfx.appointment(p.id, days_ahead=-5)
        upcoming = ReceptionService.get_upcoming_appointments()
        ids = {a.id for a in upcoming}
        assert future.id in ids
        assert past.id not in ids
