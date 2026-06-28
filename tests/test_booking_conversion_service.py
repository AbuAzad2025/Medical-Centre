"""Tests for booking_conversion_service (Wave 3).

Exposes latent bugs fixed against live schema:
- convert_to_visit used non-existent booking.preferred_date; is_new_patient was
  always False after flush.
- convert_to_appointment used non-existent appointment_date instead of starts_at.
- lab/radiology conversions omitted required visit_id (NOT NULL).
"""
import types
import uuid
from datetime import date, time, datetime, timezone

import pytest
from flask import g

from services.booking_conversion_service import (
    OnlineBookingConversionService as OBCS,
    AppointmentCheckinService,
)
from models.online_booking import OnlineBooking
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.department import Department
from models.user import User
from app.shared.enums import BookingState, VisitState, AppointmentState, OrderState


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


@pytest.fixture
def fx(app, rollback_db, test_tenant):
    db = rollback_db

    def ctx():
        return app.test_request_context()
        # caller sets g.tenant_id inside

    def dept():
        d = Department(name='D' + uuid.uuid4().hex[:4], name_ar='قسم')
        db.session.add(d)
        db.session.commit()
        return d

    def doctor(department_id=None):
        un = 'bk_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='Dr', role='doctor',
                 is_active=True, tenant_id=test_tenant.id, department_id=department_id)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def booking(**kw):
        d = dept()
        params = dict(
            booking_reference='BK-' + uuid.uuid4().hex[:8],
            first_name='حجز', last_name='اختبار',
            phone='05' + f"{uuid.uuid4().int % 10**8:08d}",
            appointment_date=date.today(),
            appointment_time=time(10, 30),
            department_id=d.id,
            status=BookingState.PENDING,
            tenant_id=test_tenant.id,
        )
        params.update(kw)
        b = OnlineBooking(**params)
        db.session.add(b)
        db.session.commit()
        return b

    return types.SimpleNamespace(db=db, tenant=test_tenant, ctx=ctx, booking=booking, doctor=doctor, dept=dept)


class TestConvertToVisit:
    def test_new_patient_creates_visit(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_to_visit(b)
        assert res['is_new_patient'] is True
        v = Visit.query.get(res['visit_id'])
        assert v.status == VisitState.OPEN.value
        assert b.status == BookingState.CONVERTED

    def test_existing_patient_reused(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            p = Patient(tenant_id=fx.tenant.id, first_name='x', last_name='y', phone=b.phone)
            fx.db.session.add(p)
            fx.db.session.commit()
            res = OBCS.convert_to_visit(b)
        assert res['is_new_patient'] is False
        assert res['patient_id'] == p.id


class TestConvertToAppointment:
    def test_creates_appointment_with_starts_at(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_to_appointment(b)
        ap = Appointment.query.get(res['appointment_id'])
        assert ap.starts_at is not None
        assert ap.status == AppointmentState.SCHEDULED
        assert b.status == BookingState.CONVERTED


class TestConvertBasedOnProfile:
    def test_default_visit(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_based_on_profile(b, profile_code=None)
        assert 'visit_id' in res

    def test_clinic_appointment(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_based_on_profile(b, profile_code='private_doctor_clinic')
        assert 'appointment_id' in res

    def test_standalone_lab_has_visit_id(self, fx, app, monkeypatch):
        b = fx.booking()
        monkeypatch.setattr(
            'services.barcode_service.setup_barcode_for_lab_request',
            lambda *a, **k: None,
        )
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_based_on_profile(b, profile_code='standalone_lab')
        lr = LabRequest.query.get(res['lab_request_id'])
        assert lr.visit_id is not None
        assert lr.patient_id == res['patient_id']

    def test_standalone_radiology_has_visit_id(self, fx, app):
        b = fx.booking()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = OBCS.convert_based_on_profile(b, profile_code='standalone_radiology')
        rr = RadiologyRequest.query.get(res['radiology_request_id'])
        assert rr.visit_id is not None


class TestAppointmentCheckin:
    def test_checkin_creates_visit(self, fx, app):
        from models.appointment import Appointment
        doc = fx.doctor()
        p = Patient(tenant_id=fx.tenant.id, first_name='a', last_name='b', phone='+970599111000')
        fx.db.session.add(p)
        fx.db.session.commit()
        ap = Appointment(
            tenant_id=fx.tenant.id, patient_id=p.id, doctor_id=doc.id,
            starts_at=datetime.now(timezone.utc), status=AppointmentState.SCHEDULED,
        )
        fx.db.session.add(ap)
        fx.db.session.commit()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = AppointmentCheckinService.checkin(ap)
        assert res['status'] == VisitState.CHECKED_IN
        assert Visit.query.get(res['visit_id']).status == VisitState.CHECKED_IN.value

    def test_walkin(self, fx, app):
        p = Patient(tenant_id=fx.tenant.id, first_name='w', last_name='k', phone='+970599222000')
        fx.db.session.add(p)
        fx.db.session.commit()
        with app.test_request_context():
            g.tenant_id = fx.tenant.id
            res = AppointmentCheckinService.create_walkin(p.id)
        assert res['status'] == VisitState.OPEN
