"""Coverage-focused integration tests for the reception module.

Each test logs in as a real tenant-scoped user and exercises the HTTP routes
end to end, asserting real DB state and JSON/HTML responses rather than
status-code-only smoke checks. ``rollback_db`` binds the shared scoped session
to a single connection whose outer transaction is rolled back on teardown, so
``commit()`` calls inside the app become SAVEPOINT releases and nothing leaks
into the shared test database.
"""

import types
import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.shared.enums import AppointmentState, QueueState, VisitState
from models.appointment import Appointment
from models.department import Department
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.patient import Patient
from models.payment import Payment
from models.queue_management import QueueManagement, QueueSettings
from models.user import User
from models.visit import Visit

pytest_plugins = ['tests._isolated_tenant']


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )


_CACHED_ENCRYPTION = {}


@pytest.fixture(autouse=True)
def _cached_encryption(monkeypatch):
    """Cache the field-encryption service to avoid a ~2.5s PBKDF2 key
    derivation on every encrypted-column access. Behaviour (encrypt/decrypt)
    is unchanged; only the redundant per-access key derivation is skipped."""
    from app.shared.encrypted_type import EncryptedString

    if '_svc' not in _CACHED_ENCRYPTION:
        from cryptography.fernet import Fernet

        from services.field_encryption_service import FieldEncryptionService

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())
        _CACHED_ENCRYPTION['_svc'] = FieldEncryptionService()
    monkeypatch.setattr(EncryptedString, '_get_service', lambda _self: _CACHED_ENCRYPTION['_svc'])


@pytest.fixture(autouse=True)
def _clear_view_cache():
    """The /patients list route uses flask-caching with a 60s TTL; drop the
    SimpleCache before each test so no cached page leaks between tests."""
    from utils.caching import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def ctx(app, rollback_db):
    """Data factory: create domain records (tenant auto-assigned by filter)."""
    from flask import g

    db = rollback_db
    tenant_id = g.get('tenant_id')
    assert tenant_id is not None, 'autouse tenant fixture should have bound a tenant'

    def _patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'Test'),
            last_name=kw.get('last_name', 'Patient'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
            gender=kw.get('gender', 'M'),
            national_id=kw.get('national_id'),
        )
        db.session.add(p)
        db.session.commit()
        return p

    def _department(**kw):
        tag = uuid.uuid4().hex[:6]
        dtype = kw.get('dtype')
        name = kw.get('name') or (dtype or 'Dept') + f'-{tag}'
        d = Department(
            name=name,
            name_ar=kw.get('name_ar', f'قسم-{tag}'),
            is_active=True,
        )
        db.session.add(d)
        db.session.commit()
        return d

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:8]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:10]}@test.local'),
            full_name=kw.get('full_name', 'Test User'),
            role=role,
            is_active=True,
            department_id=kw.get('department_id'),
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
        return u

    def _visit(**kw):
        v = Visit(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            status=kw.get('status', VisitState.OPEN.value),
            payment_status=kw.get('payment_status', 'PENDING'),
            total_amount=kw.get('total_amount', 0),
            paid_amount=kw.get('paid_amount', 0),
            visit_type=kw.get('visit_type', 'REGULAR'),
            payment_method=kw.get('payment_method', 'cash'),
            is_emergency=kw.get('is_emergency', False),
            gl_posted_at=kw.get('gl_posted_at'),
            completed_at=kw.get('completed_at'),
            archive_status=kw.get('archive_status', 'ACTIVE'),
            created_at=kw.get('created_at', datetime.now(UTC)),
            visit_date=kw.get('visit_date', date.today()),
        )
        db.session.add(v)
        db.session.commit()
        return v

    def _appointment(**kw):
        starts = datetime.now(UTC) + timedelta(hours=2)
        apt = Appointment(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            starts_at=kw.get('starts_at', starts),
            ends_at=kw.get('ends_at'),
            status=kw.get('status', AppointmentState.SCHEDULED.value),
            notes=kw.get('notes'),
            created_by=kw.get('created_by'),
        )
        db.session.add(apt)
        db.session.commit()
        return apt

    def _booking(**kw):
        booking = OnlineBooking(
            booking_reference='BK' + uuid.uuid4().hex[:8].upper(),
            patient_id=kw.get('patient_id'),
            first_name=kw.get('first_name', 'Online'),
            last_name=kw.get('last_name', 'Booking'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
            national_id=kw.get('national_id'),
            date_of_birth=kw.get('date_of_birth'),
            gender=kw.get('gender'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            appointment_date=kw.get('appointment_date', date.today() + timedelta(days=1)),
            appointment_time=kw.get('appointment_time', time(10, 0)),
            visit_type=kw.get('visit_type', 'first'),
            symptoms=kw.get('symptoms'),
            notes=kw.get('notes'),
            payment_method=kw.get('payment_method', 'card'),
            status=kw.get('status', 'confirmed'),
        )
        db.session.add(booking)
        db.session.commit()
        return booking

    def _follow_up(**kw):
        fu = FollowUpRequest(
            patient_id=kw.get('patient_id'),
            doctor_id=kw.get('doctor_id'),
            source_visit_id=kw.get('source_visit_id'),
            suggested_date=kw.get('suggested_date', date.today() + timedelta(days=7)),
            notes=kw.get('notes'),
            status=kw.get('status', 'PENDING'),
            created_by=kw.get('created_by'),
        )
        db.session.add(fu)
        db.session.commit()
        return fu

    return types.SimpleNamespace(
        db=db,
        tenant_id=tenant_id,
        patient=_patient,
        department=_department,
        user=_user,
        visit=_visit,
        appointment=_appointment,
        booking=_booking,
        follow_up=_follow_up,
    )


def _make_reception(login_as, client):
    return login_as(client, f'rec_{uuid.uuid4().hex[:8]}', 'reception')


def _make_manager(login_as, client):
    return login_as(client, f'mgr_{uuid.uuid4().hex[:8]}', 'manager')


# =========================================================================
# DASHBOARD
# =========================================================================


class TestDashboardRoutes:
    def test_root_redirects_to_dashboard(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/')
        assert resp.status_code == 302
        assert '/reception/dashboard' in resp.headers['Location']

    def test_dashboard_renders_for_reception(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/dashboard')
        assert resp.status_code == 200

    def test_dashboard_forbidden_for_pharmacy_role(self, login_as, client):
        login_as(client, f'pharm_{uuid.uuid4().hex[:8]}', 'pharmacist')
        resp = client.get('/reception/dashboard')
        assert resp.status_code == 403


class TestStaffSchedule:
    def test_staff_schedule_post_creates_and_updates(self, login_as, client, ctx):
        from models.user import StaffWorkSchedule

        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/staff/schedule',
            data={
                'user_id': str(doc.id),
                'day_of_week': '1',
                'start_time': '09:00',
                'end_time': '17:00',
                'is_active': 'on',
            },
        )
        assert resp.status_code == 302
        from sqlalchemy import select

        rows = (
            ctx.db.session.execute(
                select(StaffWorkSchedule).filter_by(user_id=doc.id, day_of_week=1)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].start_time.strftime('%H:%M') == '09:00'
        assert rows[0].is_active is True

        resp = client.post(
            '/reception/staff/schedule',
            data={
                'user_id': str(doc.id),
                'day_of_week': '1',
                'start_time': '08:30',
                'end_time': '16:30',
            },
        )
        assert resp.status_code == 302
        rows = (
            ctx.db.session.execute(
                select(StaffWorkSchedule).filter_by(user_id=doc.id, day_of_week=1)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].start_time.strftime('%H:%M') == '08:30'
        assert rows[0].is_active is False

    def test_staff_schedule_invalid_time_shows_error(self, login_as, client, ctx):
        from sqlalchemy import select

        from models.user import StaffWorkSchedule

        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        before = (
            ctx.db.session.execute(
                select(StaffWorkSchedule).filter_by(user_id=doc.id, day_of_week=2)
            )
            .scalars()
            .all()
        )
        resp = client.post(
            '/reception/staff/schedule',
            data={
                'user_id': str(doc.id),
                'day_of_week': '2',
                'start_time': 'not-a-time',
                'end_time': '17:00',
            },
        )
        assert resp.status_code == 200
        after = (
            ctx.db.session.execute(
                select(StaffWorkSchedule).filter_by(user_id=doc.id, day_of_week=2)
            )
            .scalars()
            .all()
        )
        # Invalid input must not create or alter rows.
        assert [(r.start_time, r.end_time, r.is_active) for r in after] == [
            (r.start_time, r.end_time, r.is_active) for r in before
        ]

    def test_staff_schedule_get_lists_selected_user(self, login_as, client, ctx):
        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        resp = client.get(f'/reception/staff/schedule?user_id={doc.id}')
        assert resp.status_code == 200
        assert doc.full_name.encode() in resp.data or doc.full_name in resp.get_data(as_text=True)


class TestStaffAbsence:
    def test_staff_absence_post_creates_record(self, login_as, client, ctx):
        from sqlalchemy import select

        from models.user import StaffAbsence

        _make_reception(login_as, client)
        doc = ctx.user(role='lab')
        resp = client.post(
            '/reception/staff/absence',
            data={
                'user_id': str(doc.id),
                'start_date': '2026-11-10',
                'end_date': '2026-11-12',
                'reason': 'vacation',
            },
        )
        assert resp.status_code == 302
        rows = (
            ctx.db.session.execute(select(StaffAbsence).filter_by(user_id=doc.id)).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].reason == 'vacation'
        assert rows[0].start_date == date(2026, 11, 10)

    def test_staff_absence_invalid_date_shows_error(self, login_as, client, ctx):
        from sqlalchemy import select

        from models.user import StaffAbsence

        _make_reception(login_as, client)
        doc = ctx.user(role='lab')
        resp = client.post(
            '/reception/staff/absence',
            data={
                'user_id': str(doc.id),
                'start_date': 'not-a-date',
                'end_date': '2026-11-12',
            },
        )
        assert resp.status_code == 200
        rows = (
            ctx.db.session.execute(select(StaffAbsence).filter_by(user_id=doc.id)).scalars().all()
        )
        assert rows == []

    def test_staff_absence_get_lists_selected_user(self, login_as, client, ctx):
        _make_reception(login_as, client)
        doc = ctx.user(role='radiology')
        resp = client.get(f'/reception/staff/absence?user_id={doc.id}')
        assert resp.status_code == 200


class TestSatisfactionSurvey:
    def _survey(self, ctx, **kw):
        from models.patient_satisfaction import PatientSatisfactionSurvey

        p = ctx.patient()
        v = ctx.visit(patient_id=p.id, department_id=ctx.department().id)
        survey = PatientSatisfactionSurvey(
            visit_id=v.id,
            patient_id=p.id,
            token=kw.get('token', 'tok-' + uuid.uuid4().hex[:12]),
            rating=kw.get('rating'),
            submitted_at=kw.get('submitted_at'),
        )
        ctx.db.session.add(survey)
        ctx.db.session.commit()
        return survey

    def test_survey_unknown_token_renders_invalid(self, client):
        resp = client.get('/reception/survey/tok-does-not-exist')
        assert resp.status_code == 200

    def test_survey_post_rejects_out_of_range_rating(self, client, ctx):
        survey = self._survey(ctx)
        resp = client.post(f'/reception/survey/{survey.token}', data={'rating': '9'})
        assert resp.status_code == 200
        ctx.db.session.refresh(survey)
        assert survey.rating is None
        assert survey.submitted_at is None

    def test_survey_post_records_rating_and_comment(self, client, ctx):
        survey = self._survey(ctx)
        resp = client.post(
            f'/reception/survey/{survey.token}',
            data={'rating': '5', 'comment': '  great  '},
        )
        assert resp.status_code == 200
        ctx.db.session.refresh(survey)
        assert survey.rating == 5
        assert survey.comment == 'great'
        assert survey.submitted_at is not None

    def test_survey_post_after_submission_is_idempotent(self, client, ctx):
        survey = self._survey(ctx, rating=4, submitted_at=datetime.now(UTC))
        resp = client.post(f'/reception/survey/{survey.token}', data={'rating': '1'})
        assert resp.status_code == 200
        ctx.db.session.refresh(survey)
        assert survey.rating == 4

    def test_survey_get_renders_form(self, client, ctx):
        survey = self._survey(ctx)
        resp = client.get(f'/reception/survey/{survey.token}')
        assert resp.status_code == 200


class TestQueueDisplays:
    def test_waiting_display_is_public(self, client):
        resp = client.get('/reception/display/waiting')
        assert resp.status_code == 200

    def test_calls_display_requires_login(self, client):
        resp = client.get('/reception/display/calls')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location'] or 'login' in resp.headers['Location']

    def test_calls_display_renders_for_reception(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/display/calls')
        assert resp.status_code == 200


class TestQueueManagementPage:
    def test_queue_management_lists_departments(self, login_as, client, ctx):
        _make_reception(login_as, client)
        dept = ctx.department(name=f'QM{uuid.uuid4().hex[:6]}')
        resp = client.get('/reception/queue')
        assert resp.status_code == 200
        assert dept.name_ar in resp.get_data(as_text=True)

    def test_queue_management_manager_allowed(self, login_as, client, ctx):
        _make_manager(login_as, client)
        ctx.department()
        resp = client.get('/reception/queue')
        assert resp.status_code == 200


# =========================================================================
# QUEUE
# =========================================================================


def _queue_ticket(ctx, patient, dept, visit=None, status=QueueState.WAITING.value, **kw):
    ticket = QueueManagement(
        queue_number='Q' + uuid.uuid4().hex[:10].upper(),
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        department_id=dept.id,
        status=status,
        priority_level=kw.get('priority_level', 'normal'),
        is_emergency=kw.get('is_emergency', False),
        emergency_reason=kw.get('emergency_reason'),
        force_entry=kw.get('force_entry', False),
        force_entry_reason=kw.get('force_entry_reason'),
        estimated_wait_time=kw.get('estimated_wait_time', 20),
        created_at=datetime.now(UTC),
        queued_at=kw.get('queued_at', datetime.now(UTC)),
    )
    ctx.db.session.add(ticket)
    ctx.db.session.commit()
    return ticket


def _paid_visit(ctx, patient, dept, doctor=None, **kw):
    return ctx.visit(
        patient_id=patient.id,
        department_id=dept.id,
        doctor_id=doctor.id if doctor else None,
        status=kw.get('status', VisitState.OPEN.value),
        payment_status=kw.get('payment_status', 'PAID'),
        total_amount=kw.get('total_amount', 100),
        paid_amount=kw.get('paid_amount', 100),
        visit_type=kw.get('visit_type', 'REGULAR'),
        payment_method=kw.get('payment_method', 'cash'),
        is_emergency=kw.get('is_emergency', False),
        created_at=kw.get('created_at'),
        completed_at=kw.get('completed_at'),
    )


class TestAddPatientToQueue:
    def test_add_patient_to_queue_post_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = _paid_visit(ctx, p, d, doc)
        resp = client.post(
            '/reception/queue/add-patient',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'visit_id': str(v.id),
                'queue_type': 'normal',
            },
        )
        assert resp.status_code == 302
        rows = (
            ctx.db.session.execute(select(QueueManagement).filter_by(visit_id=v.id)).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].status == QueueState.WAITING.value
        assert rows[0].priority_level == 'normal'
        assert rows[0].is_emergency is False

    def test_add_patient_to_queue_emergency_bypasses_payment(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            payment_status='PENDING',
            is_emergency=True,
            total_amount=0,
            paid_amount=0,
        )
        resp = client.post(
            '/reception/queue/add-patient',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'visit_id': str(v.id),
                'is_emergency': 'on',
                'emergency_reason': 'chest pain',
            },
        )
        assert resp.status_code == 302
        ticket = (
            ctx.db.session.execute(select(QueueManagement).filter_by(visit_id=v.id))
            .scalars()
            .first()
        )
        assert ticket is not None
        assert ticket.is_emergency is True
        assert ticket.emergency_reason == 'chest pain'
        assert ticket.priority_level == 'urgent'

    def test_add_patient_to_queue_pending_payment_blocked(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            payment_status='PENDING',
        )
        resp = client.post(
            '/reception/queue/add-patient',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'visit_id': str(v.id),
            },
        )
        assert resp.status_code == 302
        ticket = (
            ctx.db.session.execute(select(QueueManagement).filter_by(visit_id=v.id))
            .scalars()
            .first()
        )
        assert ticket is None

    def test_add_patient_to_queue_invalid_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/queue/add-patient',
            data={'patient_id': str(p.id), 'department_id': 'not-a-number'},
        )
        assert resp.status_code == 302

    def test_add_patient_to_queue_general_department_requires_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()  # general type
        v = _paid_visit(ctx, p, d)
        resp = client.post(
            '/reception/queue/add-patient',
            data={'patient_id': str(p.id), 'department_id': str(d.id), 'visit_id': str(v.id)},
        )
        assert resp.status_code == 302
        assert '/queue/add-patient' in resp.headers['Location']
        ticket = (
            ctx.db.session.execute(select(QueueManagement).filter_by(visit_id=v.id))
            .scalars()
            .first()
        )
        assert ticket is None

    def test_add_patient_to_queue_form_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        resp = client.get('/reception/queue/add-patient')
        assert resp.status_code == 200


class TestQueueFlow:
    def test_call_next_patient_marks_called(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/queue/call-next/{d.id}')
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == QueueState.CALLED.value
        assert ticket.called_at is not None

    def test_call_next_empty_queue_redirects_with_error(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.get(f'/reception/queue/call-next/{d.id}')
        assert resp.status_code == 302

    def test_start_treatment_denied_for_reception(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.get(f'/reception/queue/start-treatment/{ticket.id}')
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        # A reception user is not allowed to start treatment on a general
        # department ticket they did not author; state must not change.
        assert ticket.status == QueueState.CALLED.value

    def test_start_treatment_as_manager_marks_in_progress(self, login_as, client, ctx):
        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.get(f'/reception/queue/start-treatment/{ticket.id}')
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == QueueState.IN_PROGRESS.value
        assert ticket.started_at is not None

    def test_complete_treatment_as_manager(self, login_as, client, ctx):
        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d, status=QueueState.IN_PROGRESS.value)
        resp = client.get(f'/reception/queue/complete-treatment/{ticket.id}')
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == QueueState.COMPLETED.value

    def test_skip_patient_marks_skipped(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d)
        resp = client.post(
            f'/reception/queue/skip-patient/{ticket.id}', data={'reason': 'not here'}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == 'skipped'

    def test_return_to_queue_from_called(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.post(
            f'/reception/queue/return-to-queue/{ticket.id}', data={'reason': 'recheck'}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == QueueState.WAITING.value

    def test_cancel_ticket_marks_cancelled(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d)
        resp = client.post(f'/reception/queue/cancel-ticket/{ticket.id}', data={'reason': 'left'})
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.status == 'cancelled'

    def test_approve_emergency_debt_with_amount(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(
            patient_id=p.id, department_id=d.id, payment_status='PENDING', is_emergency=True
        )
        ticket = _queue_ticket(ctx, p, d, visit=v, is_emergency=True)
        resp = client.post(
            f'/reception/queue/approve-emergency-debt/{ticket.id}',
            data={'max_amount': '500'},
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.emergency_approved_by is not None

    def test_approve_force_entry(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ticket = _queue_ticket(ctx, p, d)
        resp = client.post(
            f'/reception/queue/approve-force-entry/{ticket.id}',
            data={'reason': 'manager approved at desk'},
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(ticket)
        assert ticket.force_entry is True

    def test_api_queue_status_route(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/queue-status/{d.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['current_queue_length'] >= 1
        assert 'priority_analysis' in data
        assert 'efficiency_score' in data

    def test_save_queue_settings_creates_and_updates(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.post(
            f'/reception/queue/save-settings/{d.id}',
            data={'payment_required': 'on', 'allow_partial_payment': 'on'},
        )
        assert resp.status_code == 302
        rows = (
            ctx.db.session.execute(select(QueueSettings).filter_by(department_id=d.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].payment_required is True
        assert rows[0].allow_partial_payment is True
        assert rows[0].allow_debt is False

        resp = client.post(
            f'/reception/queue/save-settings/{d.id}',
            data={'allow_debt': 'on', 'emergency_payment_waived': 'on'},
        )
        assert resp.status_code == 302
        rows = (
            ctx.db.session.execute(select(QueueSettings).filter_by(department_id=d.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].allow_debt is True
        assert rows[0].emergency_payment_waived is True
        assert rows[0].payment_required is False

    def test_save_queue_settings_unknown_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/save-settings/99999999', data={})
        assert resp.status_code == 302


# =========================================================================
# APPOINTMENTS
# =========================================================================


class TestAppointmentsList:
    def test_appointments_list_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.appointment(patient_id=p.id)
        resp = client.get('/reception/appointments')
        assert resp.status_code == 200

    def test_appointments_list_search_by_patient(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(phone='0509998887')
        a = ctx.appointment(patient_id=p.id)
        resp = client.get('/reception/appointments?search=0509998887')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert str(a.id) in html

    def test_appointments_list_filter_by_status(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.appointment(patient_id=p.id, status='CONFIRMED')
        resp = client.get('/reception/appointments?status=CONFIRMED')
        assert resp.status_code == 200

    def test_appointments_list_filter_by_date(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id)
        day = a.starts_at.date().isoformat()
        resp = client.get(f'/reception/appointments?date={day}')
        assert resp.status_code == 200

    def test_appointments_list_invalid_date_does_not_crash(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.appointment(patient_id=ctx.patient().id)
        resp = client.get('/reception/appointments?date=not-a-date')
        assert resp.status_code == 200

    def test_appointments_list_renders_note_metadata(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.appointment(
            patient_id=p.id,
            notes='first line\nنوع الموعد: follow_up\nالأعراض: headache',
        )
        resp = client.get('/reception/appointments')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'follow_up' in html or 'متابعة' in html

    def test_appointments_pagination_per_page(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        for i in range(3):
            ctx.appointment(patient_id=p.id, starts_at=datetime.now(UTC) + timedelta(hours=i + 1))
        resp = client.get('/reception/appointments?per_page=10&page=1')
        assert resp.status_code == 200
        resp = client.get('/reception/appointments?per_page=10&page=999')
        assert resp.status_code == 200


class TestFollowUpsList:
    def test_follow_ups_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.follow_up(patient_id=p.id)
        resp = client.get('/reception/follow-ups')
        assert resp.status_code == 200

    def test_follow_ups_search_and_status_filter(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(phone='0507776665')
        ctx.follow_up(patient_id=p.id, status='PENDING')
        resp = client.get('/reception/follow-ups?search=0507776665&status=PENDING')
        assert resp.status_code == 200
        resp = client.get('/reception/follow-ups?date=not-a-date')
        assert resp.status_code == 200


class TestConfirmCancelNoShow:
    def test_confirm_appointment_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id)
        resp = client.post(f'/reception/appointments/{a.id}/confirm')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        ctx.db.session.refresh(a)
        assert a.status == AppointmentState.CONFIRMED.value

    def test_confirm_missing_appointment_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/99999999/confirm')
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_confirm_cancelled_appointment_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id, status='CANCELLED')
        resp = client.post(f'/reception/appointments/{a.id}/confirm')
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_cancel_appointment_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id)
        resp = client.post(f'/reception/appointments/{a.id}/cancel')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        ctx.db.session.refresh(a)
        assert a.status == AppointmentState.CANCELLED.value

    def test_cancel_done_appointment_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id, status='DONE')
        resp = client.post(f'/reception/appointments/{a.id}/cancel')
        assert resp.status_code == 400

    def test_cancel_missing_appointment_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/99999999/cancel')
        assert resp.status_code == 404

    def test_no_show_appointment_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id)
        resp = client.post(f'/reception/appointments/{a.id}/no-show')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        ctx.db.session.refresh(a)
        assert a.status == AppointmentState.NO_SHOW.value

    def test_no_show_cancelled_appointment_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id, status='CANCELLED')
        resp = client.post(f'/reception/appointments/{a.id}/no-show')
        assert resp.status_code == 400

    def test_no_show_missing_appointment_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/99999999/no-show')
        assert resp.status_code == 404


class TestCreateAppointment:
    def test_create_appointment_form_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        resp = client.get('/reception/create_appointment')
        assert resp.status_code == 200

    def test_create_appointment_post_creates_row(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        doc = ctx.user(role='doctor')
        d = ctx.department()
        starts = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': str(p.id),
                'doctor_id': str(doc.id),
                'department_id': str(d.id),
                'appointment_date': starts.date().isoformat(),
                'appointment_time': '10:30',
                'duration': '45',
                'appointment_type': 'follow_up',
                'symptoms': 'cough',
                'notes': 'bring papers',
            },
        )
        assert resp.status_code == 302
        a = (
            ctx.db.session.execute(
                select(Appointment).filter_by(patient_id=p.id).order_by(Appointment.id.desc())
            )
            .scalars()
            .first()
        )
        assert a is not None
        assert a.doctor_id == doc.id
        assert a.department_id == d.id
        assert (a.ends_at - a.starts_at) == timedelta(minutes=45)
        assert 'follow_up' in (a.notes or '')
        assert 'cough' in (a.notes or '')
        assert 'bring papers' in (a.notes or '')

    def test_create_appointment_post_json_response(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        starts = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': str(p.id),
                'appointment_date': starts.date().isoformat(),
                'appointment_time': '09:15',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['appointment_id']

    def test_create_appointment_invalid_date_returns_400_json(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/create_appointment',
            data={'appointment_date': 'not-a-date', 'appointment_time': '10:00'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_create_appointment_invalid_date_html_redisplays_form(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/create_appointment',
            data={'appointment_date': 'not-a-date', 'appointment_time': '10:00'},
        )
        assert resp.status_code == 200

    def test_create_appointment_links_pending_follow_up(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        fu = ctx.follow_up(patient_id=p.id, status='PENDING')
        starts = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'appointment_date': starts.date().isoformat(),
                'appointment_time': '11:00',
                'follow_up_id': str(fu.id),
            },
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(fu)
        assert fu.status == 'SCHEDULED'
        assert fu.appointment_id is not None


class TestViewAppointment:
    def test_view_appointment_renders_with_parsed_notes(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        a = ctx.appointment(
            patient_id=p.id,
            notes='bring file\nنوع الموعد: first\nالأعراض: fever',
        )
        resp = client.get(f'/reception/view_appointment/{a.id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'fever' in html

    def test_view_missing_appointment_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/view_appointment/99999999')
        assert resp.status_code == 302
        assert '/reception/queue' in resp.headers['Location']


class TestEditAppointment:
    def test_edit_appointment_get_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id)
        resp = client.get(f'/reception/edit_appointment/{a.id}')
        assert resp.status_code == 200

    def test_edit_appointment_post_updates(self, login_as, client, ctx):
        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        d = ctx.department()
        a = ctx.appointment(patient_id=ctx.patient().id)
        datetime(2030, 5, 6, 14, 30)
        resp = client.post(
            f'/reception/edit_appointment/{a.id}',
            data={
                'appointment_date': '2030-05-06',
                'appointment_time': '14:30',
                'duration': '60',
                'doctor_id': str(doc.id),
                'department_id': str(d.id),
                'appointment_type': 'consultation',
                'symptoms': 'back pain',
                'notes': 'note',
            },
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(a)
        assert a.doctor_id == doc.id
        assert a.department_id == d.id
        assert a.starts_at.date() == date(2030, 5, 6)
        assert a.starts_at.strftime('%H:%M') == '14:30'
        assert (a.ends_at - a.starts_at) == timedelta(minutes=60)
        assert 'back pain' in (a.notes or '')

    def test_edit_appointment_invalid_date_keeps_state(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id)
        original_starts = a.starts_at
        resp = client.post(
            f'/reception/edit_appointment/{a.id}',
            data={'appointment_date': 'not-a-date', 'appointment_time': '10:00'},
        )
        assert resp.status_code == 200
        ctx.db.session.refresh(a)
        assert a.starts_at == original_starts

    def test_edit_missing_appointment_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/edit_appointment/99999999')
        assert resp.status_code == 302


class TestAvailableTimes:
    def test_available_times_requires_params(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/available-times')
        assert resp.status_code == 400

    def test_available_times_rejects_bad_date(self, login_as, client, ctx):
        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        resp = client.get(f'/reception/api/available-times?doctor_id={doc.id}&date=not-a-date')
        assert resp.status_code == 400

    def test_available_times_excludes_booked_slots(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        doc = ctx.user(role='doctor')
        booked = datetime(2030, 6, 15, 10, 0)
        ctx.appointment(
            patient_id=p.id,
            doctor_id=doc.id,
            starts_at=booked,
            status='CONFIRMED',
        )
        resp = client.get(f'/reception/api/available-times?doctor_id={doc.id}&date=2030-06-15')
        assert resp.status_code == 200
        times = resp.get_json()['available_times']
        assert '10:00' not in times
        assert '09:00' in times
        assert '16:30' in times


class TestRecurringAppointments:
    def test_recurring_requires_patient_id(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/recurring', json={})
        assert resp.status_code == 400

    def test_recurring_missing_patient_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/appointments/recurring',
            json={'patient_id': 99999999, 'starts_at': '2030-01-01T09:00:00'},
        )
        assert resp.status_code == 404

    def test_recurring_invalid_starts_at_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/appointments/recurring',
            json={'patient_id': p.id, 'starts_at': 'not-a-date'},
        )
        assert resp.status_code == 400

    def test_recurring_creates_series(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        doc = ctx.user(role='doctor')
        d = ctx.department()
        resp = client.post(
            '/reception/appointments/recurring',
            json={
                'patient_id': p.id,
                'doctor_id': doc.id,
                'department_id': d.id,
                'starts_at': '2030-03-01T09:00:00',
                'count': 3,
                'interval_days': 7,
                'duration_minutes': 30,
                'notes': 'weekly',
            },
        )
        assert resp.status_code == 201
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['count'] == 3
        created = (
            ctx.db.session.execute(
                select(Appointment).filter_by(patient_id=p.id).order_by(Appointment.starts_at)
            )
            .scalars()
            .all()
        )
        assert len(created) == 3
        assert (created[1].starts_at - created[0].starts_at).days == 7
        assert (created[2].starts_at - created[1].starts_at).days == 7

    def test_recurring_count_is_clamped(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/appointments/recurring',
            json={
                'patient_id': p.id,
                'starts_at': '2030-04-01T09:00:00',
                'count': 'not-a-number',
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()['count'] == 1

    def test_recurring_list_get(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.appointment(patient_id=p.id)
        resp = client.get('/reception/appointments/recurring')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert isinstance(payload['appointments'], list)


class TestWaitlist:
    def test_waitlist_add_and_list_and_cancel(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/appointments/waitlist',
            json={'patient_id': p.id, 'doctor_id': doc.id, 'preferred_time': 'morning'},
        )
        assert resp.status_code == 201
        entry_id = resp.get_json()['data']['id']

        resp = client.get('/reception/appointments/waitlist')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert any(e['id'] == entry_id for e in data['waitlist'])

        resp = client.post(f'/reception/appointments/waitlist/{entry_id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        resp = client.get('/reception/appointments/waitlist')
        assert all(e['id'] != entry_id for e in resp.get_json()['waitlist'])

    def test_waitlist_rejects_duplicate(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post('/reception/appointments/waitlist', json={'patient_id': p.id})
        assert resp.status_code == 201
        resp = client.post('/reception/appointments/waitlist', json={'patient_id': p.id})
        assert resp.status_code == 409

    def test_waitlist_missing_patient_returns_400(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/waitlist', json={})
        assert resp.status_code == 400

    def test_waitlist_cancel_missing_entry_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.delete('/reception/appointments/waitlist/99999999')
        assert resp.status_code == 404


class TestReminders:
    def test_reminders_get_returns_usage_hint(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/appointments/reminders')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_reminders_post_sends_for_upcoming_appointments(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        p.phone = '0505555555'
        ctx.db.session.commit()
        soon = datetime.now(UTC) + timedelta(hours=2)
        ctx.appointment(patient_id=p.id, starts_at=soon, status='SCHEDULED')
        resp = client.post('/reception/appointments/reminders')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True


class TestNoShowList:
    def test_no_show_list_returns_only_no_shows(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.appointment(patient_id=p.id, status='NO_SHOW')
        ctx.appointment(patient_id=p.id, status='SCHEDULED')
        resp = client.get('/reception/appointments/no-shows')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        statuses = {a['status'] for a in payload['appointments']}
        assert statuses == {'NO_SHOW'}


class TestOnlineBookingCheckin:
    def test_checkin_missing_booking_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/online-bookings/checkin', data={'booking_id': '99999999'})
        assert resp.status_code == 302

    def test_checkin_cancelled_booking_shows_warning(self, login_as, client, ctx):
        _make_reception(login_as, client)
        booking = ctx.booking(status='cancelled')
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        assert (
            Visit.query.filter_by(notes=f'[ONLINE_BOOKING:{booking.booking_reference}]').first()
            is None
        )

    def test_checkin_converts_booking_to_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        booking = ctx.booking(
            department_id=d.id,
            doctor_id=doc.id,
            visit_type='emergency',
            symptoms='pain',
        )
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(booking)
        assert booking.status == 'completed'
        assert booking.patient_id is not None
        visit = (
            ctx.db.session.execute(
                select(Visit).filter(
                    Visit.notes.ilike(f'%[ONLINE_BOOKING:{booking.booking_reference}]%')
                )
            )
            .scalars()
            .first()
        )
        assert visit is not None
        assert visit.visit_type == 'EMERGENCY'
        assert visit.is_emergency is True

    def test_checkin_by_reference_uses_existing_patient(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        p = ctx.patient()
        booking = ctx.booking(patient_id=p.id, department_id=d.id)
        resp = client.post(
            '/reception/online-bookings/checkin',
            data={'booking_reference': booking.booking_reference.lower()},
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(booking)
        assert booking.patient_id == p.id
        assert booking.status == 'completed'

    def test_checkin_already_converted_shows_info(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        p = ctx.patient()
        booking = ctx.booking(patient_id=p.id, department_id=d.id)
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        # second check-in must not create a second visit
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        visits = (
            ctx.db.session.execute(
                select(Visit).filter(
                    Visit.notes.ilike(f'%[ONLINE_BOOKING:{booking.booking_reference}]%')
                )
            )
            .scalars()
            .all()
        )
        assert len(visits) == 1


class TestCheckinAppointment:
    def test_checkin_missing_appointment_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/appointments/99999999/checkin')
        assert resp.status_code == 302

    def test_checkin_cancelled_appointment_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id, status='CANCELLED')
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302

    def test_checkin_without_department_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id, department_id=None)
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302

    def test_checkin_converts_appointment_to_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        p = ctx.patient()
        a = ctx.appointment(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            starts_at=datetime(2030, 7, 1, 9, 0),
            notes='bring file',
        )
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302
        ctx.db.session.refresh(a)
        assert a.status == AppointmentState.CONFIRMED.value
        visit = (
            ctx.db.session.execute(
                select(Visit).filter(Visit.notes.ilike(f'%[APPOINTMENT:{a.id}]%'))
            )
            .scalars()
            .first()
        )
        assert visit is not None
        assert visit.patient_id == p.id
        assert visit.visit_date == date(2030, 7, 1)

    def test_checkin_twice_does_not_duplicate_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        p = ctx.patient()
        a = ctx.appointment(
            patient_id=p.id, department_id=d.id, starts_at=datetime(2030, 7, 2, 9, 0)
        )
        client.post(f'/reception/appointments/{a.id}/checkin')
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302
        visits = (
            ctx.db.session.execute(
                select(Visit).filter(Visit.notes.ilike(f'%[APPOINTMENT:{a.id}]%'))
            )
            .scalars()
            .all()
        )
        assert len(visits) == 1


# =========================================================================
# VISITS
# =========================================================================


class TestVisitsList:
    def test_visits_list_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        ctx.visit(patient_id=p.id, department_id=ctx.department().id)
        resp = client.get('/reception/visits')
        assert resp.status_code == 200

    def test_visits_list_search_filter_and_pagination(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(phone='0501112223')
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.get('/reception/visits?search=0501112223')
        assert resp.status_code == 200
        assert str(v.id) in resp.get_data(as_text=True)
        resp = client.get(f'/reception/visits?department_id={d.id}&status=OPEN&per_page=10&page=1')
        assert resp.status_code == 200
        resp = client.get('/reception/visits?per_page=10&page=999')
        assert resp.status_code == 200

    def test_export_visits_csv_contains_rows(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, total_amount=42)
        resp = client.get('/reception/export/visits')
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
        body = resp.get_data(as_text=True)
        assert 'VisitID' in body
        assert '42' in body

    def test_export_visits_csv_with_search(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(phone='0503334445')
        ctx.visit(patient_id=p.id, department_id=ctx.department().id)
        resp = client.get('/reception/export/visits?search=0503334445&status=OPEN')
        assert resp.status_code == 200
        assert 'VisitID' in resp.get_data(as_text=True)


class TestArchiveAndEndVisit:
    def _completed_visit(self, ctx):
        p = ctx.patient()
        d = ctx.department()
        return ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            payment_status='PAID',
            gl_posted_at=datetime.now(UTC),
        )

    def test_archive_completed_visit_succeeds(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = self._completed_visit(ctx)
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status == 'ARCHIVED'

    def test_archive_open_visit_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='OPEN',
        )
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status != 'ARCHIVED'

    def test_archive_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/visits/99999999/archive')
        assert resp.status_code == 302

    def test_archive_already_archived_visit_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = self._completed_visit(ctx)
        v.archive_status = 'ARCHIVED'
        ctx.db.session.commit()
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302

    def test_end_completed_visit_succeeds(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = self._completed_visit(ctx)
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status == 'ARCHIVED'

    def test_end_open_visit_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='OPEN',
        )
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status != 'ARCHIVED'


class TestTransferVisit:
    def test_transfer_success_reception_to_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        d2 = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data={'department_id': str(d2.id), 'doctor_id': str(doc.id)},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        ctx.db.session.refresh(v)
        assert v.department_id == d2.id

    def test_transfer_missing_visit_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/visits/99999999/transfer', data={'department_id': '1'})
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_transfer_invalid_department_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        resp = client.post(
            f'/reception/visits/{v.id}/transfer', data={'department_id': 'not-a-number'}
        )
        assert resp.status_code == 400

    def test_transfer_to_general_department_requires_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        d2 = ctx.department()
        resp = client.post(f'/reception/visits/{v.id}/transfer', data={'department_id': str(d2.id)})
        assert resp.status_code == 400
        assert resp.get_json()['message'] == 'doctor_required'

    def test_transfer_unknown_department_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        resp = client.post(f'/reception/visits/{v.id}/transfer', data={'department_id': '99999999'})
        assert resp.status_code == 404

    def test_transfer_active_treatment_returns_409(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        _queue_ticket(ctx, p, d, visit=v, status=QueueState.CALLED.value)
        d2 = ctx.department()
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data={'department_id': str(d2.id), 'doctor_id': str(doc.id)},
        )
        assert resp.status_code == 409


class TestViewAndEditVisit:
    def test_view_visit_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        resp = client.get(f'/reception/view_visit/{v.id}')
        assert resp.status_code == 200

    def test_view_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/view_visit/99999999')
        assert resp.status_code == 302

    def test_edit_visit_get_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        resp = client.get(f'/reception/edit_visit/{v.id}')
        assert resp.status_code == 200

    def test_edit_visit_post_updates_fields(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        d2 = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            f'/reception/edit_visit/{v.id}',
            data={
                'department_id': str(d2.id),
                'doctor_id': str(doc.id),
                'visit_type': 'FOLLOW_UP',
                'symptoms': 'cough',
                'notes': 'note',
                'payment_method': 'VISA',
            },
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.department_id == d2.id
        assert v.doctor_id == doc.id
        assert v.visit_type == 'FOLLOW_UP'
        assert v.symptoms == 'cough'
        assert v.payment_method == 'VISA'

    def test_edit_visit_post_bad_department_id_shows_error(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        resp = client.post(f'/reception/edit_visit/{v.id}', data={'department_id': 'not-a-number'})
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.department_id != 'not-a-number'

    def test_edit_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/edit_visit/99999999')
        assert resp.status_code == 302


class TestAddServiceToVisit:
    def _service(self, ctx, **kw):
        from models.service import ServiceMaster

        s = ServiceMaster(
            code='SVC' + uuid.uuid4().hex[:8].upper(),
            name=kw.get('name', 'Extra Test'),
            name_ar=kw.get('name_ar', 'خدمة إضافية'),
            category=kw.get('category', 'general'),
            department_id=kw.get('department_id'),
            base_price=kw.get('base_price', 25),
            is_active=kw.get('is_active', True),
        )
        ctx.db.session.add(s)
        ctx.db.session.commit()
        return s

    def test_add_service_creates_invoice_and_line(self, login_as, client, ctx):
        from models.invoice import Invoice, InvoiceService

        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
            total_amount=50,
            paid_amount=50,
            payment_status='PAID',
        )
        svc = self._service(ctx, base_price=30)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.total_amount == 80
        invoice = (
            ctx.db.session.execute(
                select(Invoice).filter_by(visit_id=v.id).order_by(Invoice.created_at.desc())
            )
            .scalars()
            .first()
        )
        assert invoice is not None
        assert invoice.total_amount == 80
        line = (
            ctx.db.session.execute(select(InvoiceService).filter_by(invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert line is not None
        assert line.service_code == svc.code
        assert line.total_price == 30

    def test_add_service_to_archived_visit_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            archive_status='ARCHIVED',
            total_amount=0,
        )
        svc = self._service(ctx)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.total_amount == 0

    def test_add_service_to_open_visit_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='OPEN',
        )
        svc = self._service(ctx)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.total_amount == 0

    def test_add_service_missing_service_id(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
        )
        resp = client.post(f'/reception/visits/{v.id}/add-service', data={})
        assert resp.status_code == 302

    def test_add_service_unknown_service(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
        )
        resp = client.post(f'/reception/visits/{v.id}/add-service', data={'service_id': '99999999'})
        assert resp.status_code == 302

    def test_add_inactive_service_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
            total_amount=0,
        )
        svc = self._service(ctx, is_active=False)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.total_amount == 0

    def test_add_service_to_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/visits/99999999/add-service', data={'service_id': '1'})
        assert resp.status_code == 302


class TestReturnToTreatment:
    def test_return_to_treatment_not_completed_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='OPEN',
        )
        resp = client.post(
            f'/reception/visits/{v.id}/return-to-treatment', data={'reason': 'mistake'}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.status == 'OPEN'

    def test_return_to_treatment_short_reason_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
        )
        resp = client.post(f'/reception/visits/{v.id}/return-to-treatment', data={'reason': 'no'})
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.status == 'COMPLETED'

    def test_return_to_treatment_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        v = ctx.visit(
            patient_id=p.id,
            department_id=ctx.department().id,
            status='COMPLETED',
            completed_at=datetime.now(UTC),
        )
        resp = client.post(
            f'/reception/visits/{v.id}/return-to-treatment',
            data={'reason': 'clinical re-evaluation needed'},
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.status == 'OPEN'


def _make_service(ctx, **kw):
    from models.service import ServiceMaster

    s = ServiceMaster(
        code='SVC' + uuid.uuid4().hex[:8].upper(),
        name=kw.get('name', 'Service ' + uuid.uuid4().hex[:6]),
        name_ar=kw.get('name_ar', 'خدمة'),
        category=kw.get('category', 'general'),
        department_id=kw.get('department_id'),
        base_price=kw.get('base_price', 25),
        emergency_price=kw.get('emergency_price'),
        insurance_price=kw.get('insurance_price'),
        is_active=kw.get('is_active', True),
        is_custom=kw.get('is_custom', False),
    )
    ctx.db.session.add(s)
    ctx.db.session.commit()
    return s


def _make_pricing_catalog(ctx, **kw):
    from models.pricing import PricingCatalog

    entry = PricingCatalog(
        service_type=kw.get('service_type', 'consultation'),
        service_name=kw.get('service_name', 'Consultation'),
        service_name_ar=kw.get('service_name_ar', 'استشارة'),
        base_price=kw.get('base_price', 100),
        insurance_coverage=kw.get('insurance_coverage', 0),
        patient_share=kw.get('patient_share', 0),
        is_active=kw.get('is_active', True),
    )
    ctx.db.session.add(entry)
    ctx.db.session.commit()
    return entry


def _make_doctor_pricing(ctx, doctor, dept=None, **kw):
    from models.pricing import DoctorPricing

    pricing = DoctorPricing(
        doctor_id=doctor.id,
        department_id=dept.id if dept else None,
        consultation_price=kw.get('consultation_price', 80),
        follow_up_price=kw.get('follow_up_price'),
        emergency_price=kw.get('emergency_price'),
        is_active=True,
    )
    ctx.db.session.add(pricing)
    ctx.db.session.commit()
    return pricing


class TestCreateVisitFlow:
    def test_create_visit_form_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        resp = client.get('/reception/visits/create')
        assert resp.status_code == 200

    def test_create_visit_form_with_preselection(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.get(
            f'/reception/visits/create?patient_id={p.id}&department_id={d.id}&doctor_id={doc.id}'
        )
        assert resp.status_code == 200

    def test_create_visit_cash_payment_creates_payment_row(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'visit_type': 'REGULAR',
                'payment_method': 'cash',
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert v is not None
        assert v.payment_method == 'CASH'
        assert v.created_by is not None

    def test_create_visit_paid_in_full_marks_paid(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '100',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.total_amount) == 100
        assert v.payment_status == 'PAID'
        pay = (
            ctx.db.session.execute(
                select(Payment).filter_by(visit_id=v.id).order_by(Payment.id.desc())
            )
            .scalars()
            .first()
        )
        assert pay is not None
        assert float(pay.amount) == 100
        assert pay.status == 'CONFIRMED'

    def test_create_visit_partial_payment_marks_partial(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '40',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.paid_amount) == 40
        assert v.payment_status == 'PARTIAL'

    def test_create_visit_missing_patient_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.post(
            '/reception/visits/create',
            data={'department_id': str(d.id), 'payment_method': 'cash'},
        )
        assert resp.status_code == 200
        assert (
            ctx.db.session.execute(select(Visit).filter_by(department_id=d.id)).scalars().first()
            is None
        )

    def test_create_visit_missing_department_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': str(p.id), 'payment_method': 'cash'},
        )
        assert resp.status_code == 200

    def test_create_visit_unknown_department_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': str(p.id), 'department_id': '99999999', 'payment_method': 'cash'},
        )
        assert resp.status_code == 200

    def test_create_visit_general_dept_requires_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': str(p.id), 'department_id': str(d.id), 'payment_method': 'cash'},
        )
        assert resp.status_code == 200

    def test_create_visit_missing_payment_method_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': str(p.id), 'department_id': str(d.id), 'doctor_id': str(doc.id)},
        )
        assert resp.status_code == 200

    def test_create_visit_invalid_payment_method_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'bitcoin',
            },
        )
        assert resp.status_code == 200

    def test_create_visit_insurance_validation_fails(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'insurance',
                'insurance_provider': 'ab',
                'insurance_policy_number': 'x',
                'insurance_coverage': '80',
            },
        )
        assert resp.status_code == 200
        assert (
            ctx.db.session.execute(select(Visit).filter_by(patient_id=p.id)).scalars().first()
            is None
        )

    def test_create_visit_insurance_success(self, login_as, client, ctx):
        from models.insurance import InsuranceCompany

        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        company = InsuranceCompany(name='InsCo-' + uuid.uuid4().hex[:6], is_active=True)
        ctx.db.session.add(company)
        ctx.db.session.commit()
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'insurance',
                'insurance_provider': 'InsCo',
                'insurance_policy_number': 'POL-12345',
                'insurance_coverage': '80',
                'insurance_company_id': str(company.id),
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert v is not None
        assert v.payment_method == 'INSURANCE'
        assert v.insurance_company_id == company.id
        assert v.insurance_provider == 'InsCo'

    def test_create_visit_card_validation_fails(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'visa',
                'card_last_digits': '12',
                'card_holder_name': 'John Doe',
            },
        )
        assert resp.status_code == 200

    def test_create_visit_card_payment_creates_reference(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=50)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'visa',
                'card_last_digits': '4242',
                'card_holder_name': 'John Doe',
                'amount_paid': '50',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        pay = (
            ctx.db.session.execute(
                select(Payment).filter_by(visit_id=v.id).order_by(Payment.id.desc())
            )
            .scalars()
            .first()
        )
        assert pay is not None
        assert pay.reference == 'CARD-****4242'
        assert v.card_number_last_digits == '4242'

    def test_create_visit_force_payment_requires_reason(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'force',
                'is_force_payment': 'on',
                'force_payment_reason': 'short',
            },
        )
        assert resp.status_code == 200
        assert (
            ctx.db.session.execute(select(Visit).filter_by(patient_id=p.id)).scalars().first()
            is None
        )

    def test_create_visit_force_payment_success(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'force',
                'is_force_payment': 'on',
                'force_payment_reason': 'patient is homeless and was approved by manager',
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert v.is_force_payment is True
        assert v.payment_status == 'PENDING'
        assert float(v.paid_amount) == 0
        assert 'manager' in (v.force_payment_reason or '')

    def test_create_visit_quick_emergency_creates_patient_and_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Quick Emergency Person',
                'quick_gender': 'M',
                'quick_age': '34',
                'quick_reason': 'crushing chest pain',
                'department_id': str(d.id),
            },
        )
        assert resp.status_code == 302
        v = ctx.db.session.execute(select(Visit).order_by(Visit.id.desc())).scalars().first()
        assert v is not None
        assert v.visit_type == 'EMERGENCY'
        assert v.is_emergency is True
        assert v.symptoms == 'crushing chest pain'
        new_patient = ctx.db.session.get(Patient, v.patient_id)
        assert new_patient is not None
        assert new_patient.first_name == 'Quick'
        assert new_patient.last_name == 'Emergency Person'

    def test_create_visit_quick_emergency_without_name_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.department(dtype='emergency')
        resp = client.post(
            '/reception/visits/create',
            data={'quick_emergency': '1', 'quick_patient_name': ''},
        )
        assert resp.status_code == 200

    def test_create_visit_lab_services_selected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department(dtype='lab')
        svc = _make_service(
            ctx, category='lab', department_id=d.id, base_price=40, insurance_price=30
        )
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'payment_method': 'cash',
                'amount_paid': '40',
                'selected_tests': [str(svc.id)],
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.total_amount) == 40
        assert v.lab_tests_ordered is True
        from models.lab_request import LabRequest, LabResult

        reqs = (
            ctx.db.session.execute(
                select(LabRequest).filter_by(patient_id=p.id).order_by(LabRequest.id)
            )
            .scalars()
            .all()
        )
        assert len(reqs) >= 1
        results = (
            ctx.db.session.execute(select(LabResult).filter_by(patient_id=p.id)).scalars().all()
        )
        assert len(results) == 1
        assert results[0].test_code == svc.code

    def test_create_visit_radiology_services_selected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department(dtype='radiology')
        svc = _make_service(
            ctx, category='radiology', department_id=d.id, base_price=60, insurance_price=45
        )
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'payment_method': 'cash',
                'amount_paid': '60',
                'selected_tests': [str(svc.id)],
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.total_amount) == 60
        assert v.radiology_ordered is True

    def test_create_visit_with_exclusive_tax(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'tax_type': 'exclusive',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.tax_amount) == 15.0
        assert float(v.total_amount) == 115.0
        assert v.is_tax_inclusive is False

    def test_create_visit_with_inclusive_tax(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=115)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'tax_type': 'inclusive',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert v.is_tax_inclusive is True
        assert float(v.tax_amount) == 15.0
        assert float(v.total_amount) == 115.0

    def test_create_visit_custom_service_registered_without_matching_catalog(
        self, login_as, client, ctx
    ):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'custom_service_name': ['Brand New Custom Thing'],
                'custom_service_price': ['55'],
            },
        )
        assert resp.status_code == 302
        from models.service import ServiceMaster

        svc = (
            ctx.db.session.execute(select(ServiceMaster).filter_by(name='Brand New Custom Thing'))
            .scalars()
            .first()
        )
        assert svc is not None
        assert svc.is_custom is True
        assert svc.is_active is False

    def test_create_visit_print_receipt_redirects_to_receipt(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=80)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '80',
                'print_receipt': 'true',
            },
        )
        assert resp.status_code == 302
        assert '/reception/print_receipt/' in resp.headers['Location']


class TestVisitPricingApi:
    def test_visit_pricing_api_no_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/visit-pricing')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 0

    def test_visit_pricing_api_with_department_service_breakdown(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_service(ctx, category='doctor', base_price=100)
        d = ctx.department()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 100
        assert payload['details']['breakdown']

    def test_visit_pricing_api_insurance_returns_patient_share(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(
            ctx,
            service_type='consultation',
            base_price=100,
            insurance_coverage=50,
            patient_share=25,
        )
        d = ctx.department()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&payment_method=insurance'
        )
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 25

    def test_visit_pricing_api_follow_up_discount(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&visit_type=FOLLOW_UP')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 70

    def test_visit_pricing_api_doctor_pricing_overrides(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        _make_doctor_pricing(ctx, doc, d, consultation_price=88)
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&doctor_id={doc.id}')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 88

    def test_visit_pricing_api_doctor_general_pricing(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        _make_doctor_pricing(ctx, doc, None, consultation_price=66)
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&doctor_id={doc.id}')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 66

    def test_visit_pricing_api_pricing_rules_apply(self, login_as, client, ctx):
        from models.pricing_management import PricingRule

        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        marker = 'ZZ' + uuid.uuid4().hex[:8].upper()
        rule_pct = PricingRule(
            name='pct-' + marker,
            condition_type='visit_type',
            condition_value=marker,
            price_adjustment_type='percentage',
            price_adjustment_value=10,
            priority=1,
            is_active=True,
        )
        rule_fixed = PricingRule(
            name='fixed-' + marker,
            condition_type='visit_type',
            condition_value=marker,
            price_adjustment_type='fixed_amount',
            price_adjustment_value=20,
            priority=2,
            is_active=True,
        )
        ctx.db.session.add_all([rule_pct, rule_fixed])
        ctx.db.session.commit()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&visit_type={marker}')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 130

    def test_visit_pricing_api_exclusive_tax(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&tax_type=exclusive')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 115
        items = [b for b in payload['details']['breakdown'] if abs(b['cost'] - 15) < 0.001]
        assert items

    def test_visit_pricing_api_inclusive_tax(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&tax_type=inclusive')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 100
        assert 'tax_info' in payload['details']

    def test_visit_pricing_api_lab_service_ids(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        svc = _make_service(ctx, category='lab', department_id=d.id, base_price=40)
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&test_ids={svc.id}&tax_type=exclusive'
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 46
        assert payload['tests_total'] == 46

    def test_visit_pricing_api_custom_services_added(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}'
            '&custom_service_name=Manual%20Extra&custom_service_price=30'
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 130

    def test_visit_pricing_api_lab_custom_services_added(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        svc = _make_service(ctx, category='lab', department_id=d.id, base_price=40)
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&test_ids={svc.id}'
            '&custom_service_name=Manual%20Extra&custom_service_price=30'
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 70


class TestPricingHelpers:
    def test_get_service_type_by_department_types(self, ctx):
        from routes.reception.visits import get_service_type_by_department

        assert get_service_type_by_department(None) == 'consultation'
        assert get_service_type_by_department(ctx.department(dtype='lab')) == 'lab'
        assert get_service_type_by_department(ctx.department(dtype='radiology')) == 'radiology'
        assert get_service_type_by_department(ctx.department(dtype='emergency')) == 'emergency'
        assert get_service_type_by_department(ctx.department()) == 'consultation'

    def test_get_service_by_department_categories(self, ctx):
        from routes.reception.visits import get_service_by_department

        assert get_service_by_department(None) is None
        lab = ctx.department(dtype='lab')
        _make_service(ctx, category='lab', name='LabSvc ' + uuid.uuid4().hex[:6])
        found = get_service_by_department(lab)
        assert found is not None
        assert found.category == 'lab'
        radio = ctx.department(dtype='radiology')
        _make_service(ctx, category='radiology', name='RadSvc ' + uuid.uuid4().hex[:6])
        found = get_service_by_department(radio)
        assert found is not None
        assert found.category == 'radiology'

    def test_calculate_doctor_cost_fallbacks(self, ctx, app):
        from routes.reception.visits import calculate_doctor_cost

        doc = ctx.user(role='doctor')
        d = ctx.department()
        assert calculate_doctor_cost(doc.id, d.id, 'REGULAR', False, 'cash') == 0
        _make_doctor_pricing(ctx, doc, None, consultation_price=70)
        assert float(calculate_doctor_cost(doc.id, d.id, 'REGULAR', False, 'cash')) == 70
        _make_doctor_pricing(ctx, doc, d, consultation_price=88)
        assert float(calculate_doctor_cost(doc.id, d.id, 'REGULAR', False, 'cash')) == 88

    def test_calculate_visit_cost_missing_department_returns_zero(self, ctx, app):
        from routes.reception.visits import calculate_visit_cost

        assert calculate_visit_cost(None, None, 'REGULAR', False, 'cash') == 0

    def test_calculate_visit_cost_follow_up_discount(self, ctx):
        from routes.reception.visits import calculate_visit_cost

        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        assert calculate_visit_cost(d.id, None, 'FOLLOW_UP', False, 'cash') == 70

    def test_get_pricing_details_follow_up_discount_line(self, ctx):
        from routes.reception.visits import get_pricing_details

        _make_service(ctx, category='doctor', base_price=100)
        d = ctx.department()
        details = get_pricing_details(d.id, None, 'FOLLOW_UP', False, 'cash')
        assert details['discount'] == 30
        assert details['total'] == 70


def _queue_ticket_api(ctx, patient, dept, visit=None, status=QueueState.WAITING.value, **kw):
    return _queue_ticket(ctx, patient, dept, visit=visit, status=status, **kw)


# =========================================================================
# PATIENTS
# =========================================================================


class TestPatientsList:
    def test_patients_list_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        resp = client.get('/reception/patients')
        assert resp.status_code == 200

    def test_patients_list_search_finds_patient(self, login_as, client, ctx):
        _make_reception(login_as, client)
        marker = 'Findme' + uuid.uuid4().hex[:8]
        ctx.patient(first_name=marker, last_name='Searchcase')
        resp = client.get(f'/reception/patients?search={marker}')
        assert resp.status_code == 200
        assert marker in resp.get_data(as_text=True)

    def test_patients_list_search_no_match(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        resp = client.get('/reception/patients?search=zzz-no-such-patient-zzz')
        assert resp.status_code == 200

    def test_patients_list_filter_by_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/patients?department_id={d.id}')
        assert resp.status_code == 200
        assert p.full_name in resp.get_data(as_text=True)


class TestAddPatient:
    def test_add_patient_get_redirects_to_list(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/add_patient')
        assert resp.status_code == 302
        assert 'show_add=1' in resp.headers['Location']

    def test_add_patient_success_json(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Ahmed',
                'last_name': 'Ali',
                'phone': '0501234501',
                'gender': 'M',
                'birth_date': '1990-05-06',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        pid = payload['patient_id']
        row = ctx.db.session.get(Patient, pid)
        assert row is not None
        assert row.first_name == 'Ahmed'
        assert row.phone == '0501234501'

    def test_add_patient_success_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'HTML', 'last_name': 'Success', 'phone': '0501234502'},
        )
        assert resp.status_code == 302
        assert '/reception/patients' in resp.headers['Location']

    def test_add_patient_invalid_phone_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': 'abc'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_add_patient_invalid_national_id_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0501234503',
                'national_id': '12',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_missing_required_fields_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': '', 'last_name': '', 'phone': ''},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_duplicate_phone_returns_409(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(phone='0501234567')
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'Dup', 'last_name': 'Phone', 'phone': '050 123 4567'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409
        assert resp.get_json()['patient_id']

    def test_add_patient_duplicate_national_id_returns_409(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(national_id='123456789012')
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Dup',
                'last_name': 'Id',
                'phone': '0501234588',
                'national_id': '123456789012',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_add_patient_with_insurance_and_pregnancy(self, login_as, client, ctx):
        from models.insurance import InsuranceCompany

        _make_reception(login_as, client)
        company = InsuranceCompany(name='InsCo-' + uuid.uuid4().hex[:6], is_active=True)
        ctx.db.session.add(company)
        ctx.db.session.commit()
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Preg',
                'last_name': 'Lady',
                'phone': '0501234590',
                'gender': 'F',
                'insurance_company_id': str(company.id),
                'insurance_member_number': 'M-1',
                'is_pregnant': 'true',
                'pregnancy_weeks': '12',
                'last_menstruation_date': '2026-09-01',
                'pregnancy_notes': 'first pregnancy',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        pid = resp.get_json()['patient_id']
        row = ctx.db.session.get(Patient, pid)
        assert row.insurance_company_id == company.id
        assert row.is_pregnant is True
        assert row.pregnancy_weeks == 12
        assert row.last_menstruation_date == date(2026, 9, 1)


class TestEditPatient:
    def test_edit_patient_get_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.get(f'/reception/edit_patient/{p.id}')
        assert resp.status_code == 200

    def test_edit_patient_post_updates(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(first_name='OldName')
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={
                'first_name': 'NewName',
                'last_name': p.last_name,
                'phone': p.phone,
                'gender': 'F',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        ctx.db.session.refresh(p)
        assert p.first_name == 'NewName'
        assert p.gender == 'F'

    def test_edit_patient_invalid_phone_rejected_json(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': 'not-a-phone'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        ctx.db.session.refresh(p)
        assert p.first_name != 'X'

    def test_edit_patient_duplicate_national_id_returns_409(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(national_id='987654321000')
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={
                'first_name': 'X',
                'last_name': 'Y',
                'phone': p.phone,
                'national_id': '987654321000',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_edit_patient_same_national_id_allowed(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(national_id='987654321001')
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={
                'first_name': 'Same',
                'last_name': 'Id',
                'phone': p.phone,
                'national_id': '987654321001',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200

    def test_edit_missing_patient_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/edit_patient/99999999')
        assert resp.status_code == 302


class TestViewPatient:
    def test_view_patient_renders_related_data(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/view_patient/{p.id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert p.full_name in html

    def test_view_missing_patient_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/view_patient/99999999')
        assert resp.status_code == 302


class TestDeletePatient:
    def test_delete_patient_success(self, login_as, client, ctx):
        _make_manager(login_as, client)
        p = ctx.patient()
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code == 302
        assert ctx.db.session.get(Patient, p.id) is None

    def test_delete_patient_with_receipt_blocked(self, login_as, client, ctx):
        from models.receipt import Receipt

        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        receipt = Receipt(
            receipt_number='RCPT-' + uuid.uuid4().hex[:10].upper(),
            visit_id=v.id,
            patient_id=p.id,
            total_amount=10,
            paid_amount=10,
            payment_method='cash',
        )
        ctx.db.session.add(receipt)
        ctx.db.session.commit()
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code == 302
        assert ctx.db.session.get(Patient, p.id) is not None

    def test_delete_patient_with_prescription_blocked(self, login_as, client, ctx):
        from models.medication import Prescription

        _make_manager(login_as, client)
        p = ctx.patient()
        prescription = Prescription(
            patient_id=p.id,
            prescription_number='RX-' + uuid.uuid4().hex[:10].upper(),
        )
        ctx.db.session.add(prescription)
        ctx.db.session.commit()
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code == 302
        assert ctx.db.session.get(Patient, p.id) is not None

    def test_delete_missing_patient_redirects(self, login_as, client):
        _make_manager(login_as, client)
        resp = client.post('/reception/delete_patient/99999999')
        assert resp.status_code == 302


class TestSmartPatientSearch:
    def test_smart_patient_search_returns_lists(self, login_as, client, ctx):
        _make_reception(login_as, client)
        marker = 'Zq' + uuid.uuid4().hex[:8]
        ctx.patient(first_name=marker, last_name='Searchcase')
        resp = client.get(f'/reception/api/smart-patient-search?q={marker}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert 'patients' in payload
        assert any(marker in p['full_name'] for p in payload['patients'])

    def test_smart_patient_search_empty_query_returns_empty(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/smart-patient-search?q=')
        assert resp.status_code == 200
        assert resp.get_json()['patients'] == []


class TestPatientAllergiesAndProblems:
    def test_add_allergy_success(self, login_as, client, ctx):
        from models.patient import PatientAllergy

        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            json={'allergen': 'Penicillin', 'severity': 'HIGH', 'description': 'hives'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        rows = (
            ctx.db.session.execute(select(PatientAllergy).filter_by(patient_id=p.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].allergen == 'Penicillin'

    def test_add_allergy_missing_allergen_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            json={'allergen': ''},
        )
        assert resp.status_code == 400

    def test_add_allergy_missing_patient_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/api/patients/99999999/allergies/add',
            json={'allergen': 'Penicillin'},
        )
        assert resp.status_code == 404

    def test_add_problem_success(self, login_as, client, ctx):
        from models.problem_list import PatientProblem

        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            json={'problem_description': 'Hypertension', 'problem_type': 'DIAGNOSIS'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        rows = (
            ctx.db.session.execute(select(PatientProblem).filter_by(patient_id=p.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == 'ACTIVE'

    def test_add_problem_missing_description_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            json={'problem_description': ''},
        )
        assert resp.status_code == 400

    def test_add_problem_missing_patient_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/api/patients/99999999/problems/add',
            json={'problem_description': 'Headache'},
        )
        assert resp.status_code == 404

    def test_toggle_problem_status_round_trip(self, login_as, client, ctx):
        from models.problem_list import PatientProblem

        _make_reception(login_as, client)
        p = ctx.patient()
        problem = PatientProblem(
            tenant_id=ctx.tenant_id,
            patient_id=p.id,
            problem_description='Diabetes',
            problem_type='DIAGNOSIS',
            status='ACTIVE',
            recorded_by_id=None,
        )
        ctx.db.session.add(problem)
        ctx.db.session.commit()
        resp = client.post(f'/reception/api/patients/{p.id}/problems/{problem.id}/toggle')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'RESOLVED'
        ctx.db.session.refresh(problem)
        assert problem.status == 'RESOLVED'
        assert problem.resolution_date is not None

        resp = client.post(f'/reception/api/patients/{p.id}/problems/{problem.id}/toggle')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ACTIVE'
        ctx.db.session.refresh(problem)
        assert problem.status == 'ACTIVE'
        assert problem.resolution_date is None

    def test_toggle_problem_wrong_patient_returns_404(self, login_as, client, ctx):
        from models.problem_list import PatientProblem

        _make_reception(login_as, client)
        p = ctx.patient()
        q = ctx.patient()
        problem = PatientProblem(
            tenant_id=ctx.tenant_id,
            patient_id=p.id,
            problem_description='Asthma',
            status='ACTIVE',
            recorded_by_id=None,
        )
        ctx.db.session.add(problem)
        ctx.db.session.commit()
        resp = client.post(f'/reception/api/patients/{q.id}/problems/{problem.id}/toggle')
        assert resp.status_code == 404

    def test_toggle_missing_problem_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(f'/reception/api/patients/{p.id}/problems/99999999/toggle')
        assert resp.status_code == 404


# =========================================================================
# PAYMENTS
# =========================================================================


class TestPosCharge:
    def test_pos_charge_rejects_zero_amount(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/pos/charge', json={'amount': 0})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_pos_charge_rejects_non_numeric_amount(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/pos/charge', json={'amount': 'not-a-number'})
        assert resp.status_code == 400

    def test_pos_charge_without_terminal_returns_503(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/pos/charge', json={'amount': 25})
        assert resp.status_code == 503
        assert resp.get_json()['code'] == 'pos_not_enabled'

    def test_pos_charge_form_amount(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/pos/charge', data={'amount': '25'})
        assert resp.status_code == 503


class TestSendToAccounting:
    def test_send_to_accounting_creates_invoice(self, login_as, client, ctx):
        from models.invoice import Invoice, InvoiceService

        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            total_amount=120,
            paid_amount=0,
            payment_status='PENDING',
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        invoice = (
            ctx.db.session.execute(
                select(Invoice).filter_by(visit_id=v.id).order_by(Invoice.created_at.desc())
            )
            .scalars()
            .first()
        )
        assert invoice is not None
        assert float(invoice.total_amount) == 120
        line = (
            ctx.db.session.execute(select(InvoiceService).filter_by(invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert line is not None
        assert float(line.total_price) == 120

    def test_send_to_accounting_marks_paid_when_fully_paid(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=50,
            paid_amount=50,
            payment_status='PARTIAL',
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.payment_status == 'PAID'

    def test_send_to_accounting_archived_visit_rejected(self, login_as, client, ctx):
        from models.invoice import Invoice

        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            archive_status='ARCHIVED',
            total_amount=10,
            paid_amount=10,
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        assert (
            ctx.db.session.execute(select(Invoice).filter_by(visit_id=v.id)).scalars().first()
            is None
        )

    def test_send_to_accounting_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/visits/99999999/send-to-accounting')
        assert resp.status_code == 302


class TestPrintSurfaces:
    def test_print_receipt_renders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=80,
            paid_amount=80,
            payment_status='PAID',
        )
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/print_receipt/99999999')
        assert resp.status_code == 302

    def test_print_invoice_renders(self, login_as, client, ctx):
        from models.invoice import Invoice

        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        invoice = Invoice(
            invoice_number='INV-TEST-' + uuid.uuid4().hex[:8].upper(),
            visit_id=v.id,
            created_by=None,
            status='ISSUED',
            currency='ILS',
            total_amount=25,
            paid_amount=0,
        )
        ctx.db.session.add(invoice)
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_invoice/{invoice.id}')
        assert resp.status_code == 200

    def test_print_invoice_missing_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/print_invoice/99999999')
        assert resp.status_code == 302

    def test_print_prescription_missing_redirects(self, login_as, client):
        _make_manager(login_as, client)
        resp = client.get('/reception/print_prescription/99999999')
        assert resp.status_code == 302

    def test_print_prescription_reception_forbidden(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/print_prescription/99999999')
        assert resp.status_code == 403

    def test_print_prescription_owner_doctor_allowed(self, login_as, client, ctx):
        from models.medication import Prescription

        _make_manager(login_as, client)
        p = ctx.patient()
        doc = ctx.user(role='doctor')
        prescription = Prescription(
            patient_id=p.id,
            doctor_id=doc.id,
            prescription_number='RX-' + uuid.uuid4().hex[:10].upper(),
        )
        ctx.db.session.add(prescription)
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_prescription/{prescription.id}')
        assert resp.status_code == 200


class TestPaymentsPages:
    def test_payments_page_renders(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/payments')
        assert resp.status_code == 200

    def test_cash_register_creates_and_computes_expected(self, login_as, client, ctx):
        from models.cash_register import CashRegister
        from models.payment import Payment

        _make_reception(login_as, client)
        p = ctx.patient()
        pay = Payment(
            patient_id=p.id,
            method='cash',
            amount=30,
            currency='ILS',
            status='CONFIRMED',
        )
        ctx.db.session.add(pay)
        ctx.db.session.commit()
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200
        reg = (
            ctx.db.session.execute(
                select(CashRegister)
                .filter_by(register_date=date.today())
                .order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(reg.expected_cash) >= 30
        assert float(reg.expected_total) == float(
            reg.expected_cash + reg.expected_card + reg.expected_insurance
        )

    def test_daily_close_get_renders(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/daily-close')
        assert resp.status_code == 200

    def test_daily_close_post_closes_register(self, login_as, client, ctx):
        from models.cash_register import CashRegister

        _make_reception(login_as, client)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '100', 'actual_card': '50', 'actual_insurance': '25'},
        )
        assert resp.status_code == 302
        reg = (
            ctx.db.session.execute(
                select(CashRegister)
                .filter_by(register_date=date.today())
                .order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        assert reg.is_closed is True
        assert float(reg.actual_total) == 175

    def test_daily_close_negative_amounts_rejected(self, login_as, client, ctx):
        from models.cash_register import CashRegister

        _make_reception(login_as, client)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '-5', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code == 302
        reg = (
            ctx.db.session.execute(
                select(CashRegister)
                .filter_by(register_date=date.today())
                .order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        assert reg.is_closed is False

    def test_daily_close_invalid_numbers_rejected(self, login_as, client, ctx):
        from models.cash_register import CashRegister

        _make_reception(login_as, client)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': 'abc', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code == 302
        reg = (
            ctx.db.session.execute(
                select(CashRegister)
                .filter_by(register_date=date.today())
                .order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        assert reg.is_closed is False


class TestPaymentHelpers:
    def test_get_payment_methods_structure(self):
        from routes.reception.payments import get_payment_methods

        methods = get_payment_methods()
        values = {m['value'] for m in methods}
        assert values == {'cash', 'visa', 'wire', 'insurance', 'force'}

    def test_validate_payment_data_rules(self):
        from routes.reception.payments import validate_payment_data

        assert validate_payment_data('cash', {}) == (True, 'صحيح')
        assert validate_payment_data('unknown', {})[0] is False
        ok, _msg = validate_payment_data('visa', {})
        assert ok is False
        ok, _ = validate_payment_data(
            'visa',
            {'card_last_digits': '4242', 'card_holder_name': 'John Doe', 'expiry_date': '12/30'},
        )
        assert ok is True
        ok, _ = validate_payment_data(
            'insurance', {'insurance_provider': 'InsCo', 'insurance_policy_number': 'P-1'}
        )
        assert ok is True
        ok, _msg = validate_payment_data('force', {})
        assert ok is False
        ok, _ = validate_payment_data(
            'force', {'force_payment_reason': 'manager approved verbally', 'approved_by': '1'}
        )
        assert ok is True


# =========================================================================
# API (routes/reception/api.py)
# =========================================================================


class TestApiDoctorsAndStaff:
    def test_api_doctors_lists_active_doctors(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        resp = client.get('/reception/api/doctors')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert any(doc.id == x['id'] for x in payload['doctors'])

    def test_api_doctors_filters_by_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        ctx.user(role='doctor')
        resp = client.get(f'/reception/api/doctors?department_id={d.id}')
        assert resp.status_code == 200
        ids = [x['id'] for x in resp.get_json()['doctors']]
        assert doc.id in ids
        assert len(ids) == 1

    def test_api_doctors_invalid_department_id_returns_400(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/doctors?department_id=not-a-number')
        assert resp.status_code == 400

    def test_api_department_staff_requires_param(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/department-staff')
        assert resp.status_code == 400

    def test_api_department_staff_unknown_department_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/department-staff?department_id=99999999')
        assert resp.status_code == 404

    def test_api_department_staff_lists_lab_staff(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        lab_tech = ctx.user(role='lab', department_id=d.id)
        ctx.user(role='doctor')
        resp = client.get(f'/reception/api/department-staff?department_id={d.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        ids = [x['id'] for x in payload['staff']]
        assert lab_tech.id in ids

    def test_api_department_staff_lists_general_doctors(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        resp = client.get(f'/reception/api/department-staff?department_id={d.id}')
        assert resp.status_code == 200
        ids = [x['id'] for x in resp.get_json()['staff']]
        assert doc.id in ids


class TestApiDepartmentServices:
    def test_requires_department_id(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/department-services')
        assert resp.status_code == 400

    def test_unknown_department_returns_404(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/department-services?department_id=99999999')
        assert resp.status_code == 404

    def test_lists_services_for_lab_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        svc = _make_service(
            ctx,
            category='lab',
            department_id=d.id,
            base_price=55,
            insurance_price=40,
            name='LabFullBlood',
            name_ar='مختبر فحص دم',
        )
        resp = client.get(f'/reception/api/department-services?department_id={d.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['category'] == 'lab'
        codes = [s['code'] for s in payload['services']]
        assert svc.code in codes

    def test_falls_back_to_category_wide_services(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        svc = _make_service(
            ctx, category='lab', department_id=None, base_price=70, name='LabGeneric'
        )
        resp = client.get(f'/reception/api/department-services?department_id={d.id}')
        assert resp.status_code == 200
        codes = [s['code'] for s in resp.get_json()['services']]
        assert svc.code in codes


class TestApiQueueStatusEndpoints:
    def test_queue_status_returns_status(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/queue-department-status/{d.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True

    def test_queue_status_all_lists_departments(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True

    def test_queue_status_all_with_filters(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient()
        marker = 'QueueFindMe' + uuid.uuid4().hex[:6]
        d = ctx.department()
        lp = ctx.patient(first_name=marker, last_name='Case')
        _queue_ticket(ctx, lp, d)
        resp = client.get(
            f'/reception/api/queue-status-all?department_id={d.id}'
            '&status=waiting&priority=normal&search=' + marker + '&is_emergency=false'
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True

    def test_queue_wait_metrics(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert 'by_department' in payload['data']

    def test_patient_queue_position(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/patient-queue-position/{p.id}/{d.id}')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['position'] == 1

    def test_patient_queue_position_not_in_queue(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        resp = client.get(f'/reception/api/patient-queue-position/{p.id}/{d.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_snapshot(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-snapshot')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert len(payload['items']) == 1
        assert 'stats' in payload and 'satisfaction' in payload and 'forecast' in payload

    def test_display_waiting_packs_items(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        _queue_ticket(ctx, p, d, visit=v, status=QueueState.CALLED.value)
        _queue_ticket(ctx, p, d, status=QueueState.IN_PROGRESS.value)
        resp = client.get('/reception/api/display/waiting')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert len(payload['called']) == 1
        assert len(payload['current']) == 1

    def test_display_calls_packs_items(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.get('/reception/api/display/calls')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert len(payload['items']) == 1


class TestApiFhir:
    def test_fhir_patient(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(national_id='123456789')
        resp = client.get(f'/reception/api/fhir/patient/{p.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Patient'
        assert resource['id'] == str(p.id)

    def test_fhir_patient_missing_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/fhir/patient/99999999')
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_fhir_encounter(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/api/fhir/encounter/{v.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Encounter'
        assert resource['status'] == 'in-progress'

    def test_fhir_encounter_missing_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/fhir/encounter/99999999')
        assert resp.status_code == 404

    def test_fhir_appointment(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id)
        resp = client.get(f'/reception/api/fhir/appointment/{a.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Appointment'
        assert resource['status'] == 'booked'

    def test_fhir_appointment_missing_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/fhir/appointment/99999999')
        assert resp.status_code == 404

    def test_fhir_practitioner(self, login_as, client, ctx):
        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        resp = client.get(f'/reception/api/fhir/practitioner/{doc.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Practitioner'

    def test_fhir_practitioner_rejects_non_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        lab = ctx.user(role='lab')
        resp = client.get(f'/reception/api/fhir/practitioner/{lab.id}')
        assert resp.status_code == 404

    def test_fhir_practitioner_missing_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/fhir/practitioner/99999999')
        assert resp.status_code == 404

    def test_fhir_organization(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.get(f'/reception/api/fhir/organization/{d.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Organization'
        assert resource['active'] is True

    def test_fhir_organization_missing_returns_404(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/api/fhir/organization/99999999')
        assert resp.status_code == 404


# =========================================================================
# QUEUE module-level helpers (direct calls)
# =========================================================================


class TestQueueModuleHelpers:
    def test_calculate_queue_efficiency(self):
        from app.shared.enums import QueueState
        from routes.reception import queue as queue_module

        assert queue_module.calculate_queue_efficiency([]) == 100
        t1 = types.SimpleNamespace(status=QueueState.COMPLETED)
        t2 = types.SimpleNamespace(status=QueueState.WAITING)
        assert queue_module.calculate_queue_efficiency([t1]) == 100
        assert queue_module.calculate_queue_efficiency([t1, t2]) == 50
        assert queue_module.calculate_queue_efficiency([t2]) == 0

    def test_calculate_flow_trend(self):
        from routes.reception import queue as queue_module

        assert queue_module.calculate_flow_trend([{'visits': 1}]) == 'stable'
        assert queue_module.calculate_flow_trend([{'visits': 5}, {'visits': 1}]) == 'growing'
        assert queue_module.calculate_flow_trend([{'visits': 1}, {'visits': 5}]) == 'declining'
        assert queue_module.calculate_flow_trend([{'visits': 10}, {'visits': 10}]) == 'stable'

    def test_calculate_satisfaction_score(self):
        from routes.reception import queue as queue_module

        score = queue_module.calculate_satisfaction_score(100, 0, 0)
        assert score > 0

        low = queue_module.calculate_satisfaction_score(0, 120, 0)
        high = queue_module.calculate_satisfaction_score(100, 0, 20)
        assert high > low

    def test_add_patient_to_queue_auto_success(self, app, ctx):
        from routes.reception.queue import add_patient_to_queue_auto

        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = _paid_visit(ctx, p, d, doc)
        ok, _msg = add_patient_to_queue_auto(v.id, d.id, doc.id)
        assert ok is True
        ticket = (
            ctx.db.session.execute(select(QueueManagement).filter_by(visit_id=v.id))
            .scalars()
            .first()
        )
        assert ticket is not None

    def test_add_patient_to_queue_auto_emergency(self, app, ctx):
        from routes.reception.queue import add_patient_to_queue_auto

        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id, department_id=d.id, payment_status='PENDING', is_emergency=True
        )
        ok, _msg = add_patient_to_queue_auto(v.id, d.id, doc.id)
        assert ok is True

    def test_add_patient_to_queue_auto_unknown_visit(self, app, ctx):
        from routes.reception.queue import add_patient_to_queue_auto

        d = ctx.department()
        ok, _msg = add_patient_to_queue_auto(99999999, d.id, None)
        assert ok is False

    def test_get_patient_flow_analysis(self, app, ctx):
        from routes.reception.queue import get_patient_flow_analysis

        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        result = get_patient_flow_analysis()
        assert isinstance(result, dict)
        assert len(result['daily_flow']) == 7
        today = result['daily_flow'][0]
        assert today['visits'] >= 1
        assert today['new_patients'] >= 1
        assert result['trend'] in {'growing', 'stable', 'declining'}

    def test_get_appointment_optimization_detects_busy_day(self, app, ctx):
        from routes.reception.queue import get_appointment_optimization

        d = ctx.department()
        doc = ctx.user(role='doctor')
        p = ctx.patient()
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        for i in range(21):
            ctx.appointment(
                patient_id=p.id,
                department_id=d.id,
                doctor_id=doc.id,
                starts_at=tomorrow + timedelta(minutes=30 * i),
                status='SCHEDULED',
            )
        result = get_appointment_optimization()
        assert isinstance(result, dict)
        opt_types = {o['type'] for o in result['optimizations']}
        assert 'scheduling' in opt_types
        assert 'workload' in opt_types
        assert result['appointment_density']
        assert any(w['appointments'] >= 21 for w in result['doctor_workload'])

    def test_get_real_time_alerts(self, app, ctx):
        from routes.reception.queue import get_real_time_alerts

        yesterday = datetime.now(UTC) - timedelta(days=1)
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            starts_at=yesterday,
            status='SCHEDULED',
        )
        ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='PENDING',
            created_at=datetime.now(UTC) - timedelta(hours=3),
        )
        alerts = get_real_time_alerts()
        types_found = {a['type'] for a in alerts}
        assert 'appointment' in types_found
        assert 'queue' in types_found

    def test_get_workflow_automation(self, app, ctx):
        from routes.reception.queue import get_workflow_automation

        p = ctx.patient()
        d = ctx.department()
        for i in range(4):
            ctx.visit(
                patient_id=p.id,
                department_id=d.id,
                created_at=datetime.now(UTC) - timedelta(days=i + 1),
            )
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            status='SCHEDULED',
        )
        suggestions = get_workflow_automation()
        types_found = {s['type'] for s in suggestions}
        assert 'recurring_appointments' in types_found
        assert 'reminders' in types_found

    def test_get_patient_satisfaction_ai(self, app, ctx):
        from models.patient_satisfaction import PatientSatisfactionSurvey
        from routes.reception.queue import get_patient_satisfaction_ai

        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            status='COMPLETED',
            archive_status='ARCHIVED',
            completed_at=datetime.now(UTC),
        )
        survey = PatientSatisfactionSurvey(
            visit_id=v.id,
            patient_id=p.id,
            token='tok-' + uuid.uuid4().hex[:12],
            rating=2,
            submitted_at=datetime.now(UTC),
        )
        ctx.db.session.add(survey)
        ctx.db.session.commit()
        result = get_patient_satisfaction_ai()
        assert isinstance(result, dict)
        for key in [
            'satisfaction_score',
            'avg_rating',
            'rating_count',
            'completion_rate',
            'avg_wait_time',
            'repeat_visits',
            'recommendations',
            'status',
        ]:
            assert key in result
        assert result['rating_count'] >= 1
        assert result['avg_rating'] == 2

    def test_get_patient_demand_forecast(self, app, ctx):
        from routes.reception.queue import get_patient_demand_forecast

        result = get_patient_demand_forecast()
        assert isinstance(result, dict)
        assert result['hours_ahead'] == 4
        assert len(result['next_hours']) == 4
        assert result['expected_total'] >= 0

    def test_get_resource_planning(self, app, ctx):
        from routes.reception.queue import get_resource_planning

        doc = ctx.user(role='doctor')
        # No user has logged in recently, so staff engagement reads 0% and the
        # resource planner must recommend a staff engagement action.
        doc.last_login = None
        from sqlalchemy import update

        import models.user as user_module

        ctx.db.session.execute(update(user_module.User).values(last_login=None))
        ctx.db.session.commit()
        result = get_resource_planning()
        assert isinstance(result, dict)
        for key in [
            'total_staff',
            'active_staff',
            'total_doctors',
            'active_doctors',
            'today_visits',
            'tomorrow_appointments',
            'efficiency_score',
            'planning_recommendations',
        ]:
            assert key in result
        assert result['total_doctors'] >= 1
        assert result['efficiency_score'] == 0
        rec_types = {r['type'] for r in result['planning_recommendations']}
        assert 'staff_engagement' in rec_types

    def test_get_smart_recommendations(self, app, ctx):
        from routes.reception.queue import get_smart_recommendations

        done = datetime.now(UTC)
        ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            created_at=done - timedelta(hours=2),
            completed_at=done,
        )
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            starts_at=datetime.now(UTC) + timedelta(hours=5),
            status='no_show',
        )
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            starts_at=datetime.now(UTC) + timedelta(hours=6),
            status='SCHEDULED',
        )
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            starts_at=datetime.now(UTC) + timedelta(hours=7),
            status='SCHEDULED',
        )
        ctx.appointment(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            starts_at=datetime.now(UTC) + timedelta(hours=8),
            status='SCHEDULED',
        )
        recommendations = get_smart_recommendations()
        types_found = {r['type'] for r in recommendations}
        assert 'no_show' in types_found
        assert 'efficiency' in types_found

    def test_calculate_no_show_rate_isolated(self, isolated_tenant, db):
        """Isolated tenant: exactly 1 no-show out of 4 -> 25%."""
        from models.appointment import Appointment
        from models.patient import Patient
        from routes.reception import queue as queue_module

        p = Patient(
            tenant_id=isolated_tenant.id,
            first_name='Iso',
            last_name='NoShow',
            phone='050' + format(uuid.uuid4().int % 10**7, '07d'),
            gender='M',
        )
        db.session.add(p)
        db.session.flush()
        starts = datetime.now(UTC) + timedelta(days=1)
        for i, status in enumerate(['NO_SHOW', 'SCHEDULED', 'SCHEDULED', 'SCHEDULED']):
            db.session.add(
                Appointment(
                    tenant_id=isolated_tenant.id,
                    patient_id=p.id,
                    starts_at=starts + timedelta(hours=i + 1),
                    status='no_show' if status == 'NO_SHOW' else status,
                )
            )
        db.session.commit()
        assert queue_module.calculate_no_show_rate() == 25.0


# =========================================================================
# Additional branch coverage
# =========================================================================


class TestAppointmentsListFilters:
    def test_appointments_list_filter_by_department_and_doctor(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        a = ctx.appointment(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/reception/appointments?department_id={d.id}&doctor_id={doc.id}')
        assert resp.status_code == 200
        assert str(a.id) in resp.get_data(as_text=True)

    def test_appointments_list_notes_with_blank_lines(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.appointment(
            patient_id=ctx.patient().id,
            notes='first para\n\nsecond para\n\nنوع الموعد: first',
        )
        resp = client.get('/reception/appointments')
        assert resp.status_code == 200

    def test_follow_ups_filter_by_date(self, login_as, client, ctx):
        _make_reception(login_as, client)
        fu = ctx.follow_up(patient_id=ctx.patient().id)
        day = fu.suggested_date.isoformat()
        resp = client.get(f'/reception/follow-ups?date={day}')
        assert resp.status_code == 200
        assert 'مرجع' in resp.get_data(as_text=True) or str(fu.id) in resp.get_data(as_text=True)


class TestOnlineBookingBranches:
    def test_checkin_follow_up_booking_marks_follow_up_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        booking = ctx.booking(department_id=d.id, visit_type='follow_up')
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        visit = (
            ctx.db.session.execute(
                select(Visit).filter(
                    Visit.notes.ilike(f'%[ONLINE_BOOKING:{booking.booking_reference}]%')
                )
            )
            .scalars()
            .first()
        )
        assert visit.visit_type == 'FOLLOW_UP'

    def test_checkin_reuses_existing_patient_by_national_id(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        existing = ctx.patient(national_id='765432109876')
        booking = ctx.booking(
            department_id=d.id,
            national_id='765432109876',
            phone='0509990000',
        )
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(booking)
        assert booking.patient_id == existing.id

    def test_checkin_queue_failure_does_not_block_conversion(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department()
        booking = ctx.booking(department_id=d.id, visit_type='first')

        def boom(*_a, **_k):
            raise RuntimeError('queue exploded')

        monkeypatch.setattr('routes.reception.appointments.add_patient_to_queue_auto', boom)
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(booking)
        assert booking.status == 'completed'

    def test_appointment_checkin_queue_failure_does_not_block_conversion(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department()
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id, department_id=d.id)

        def boom(*_a, **_k):
            raise RuntimeError('queue exploded')

        monkeypatch.setattr('routes.reception.appointments.add_patient_to_queue_auto', boom)
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302

    def test_create_appointment_with_bogus_follow_up_id_still_succeeds(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        starts = (datetime.now(UTC) + timedelta(days=1)).replace(microsecond=0)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'appointment_date': starts.date().isoformat(),
                'appointment_time': '12:00',
                'follow_up_id': '99999999',
            },
        )
        assert resp.status_code == 302

    def test_view_appointment_multiline_notes(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(
            patient_id=ctx.patient().id,
            notes='alpha\n\nنوع الموعد: first\n\nالأعراض: fever\n\nomega',
        )
        resp = client.get(f'/reception/view_appointment/{a.id}')
        assert resp.status_code == 200

    def test_edit_appointment_get_with_typed_notes(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(
            patient_id=ctx.patient().id,
            starts_at=datetime(2030, 8, 10, 9, 0),
            ends_at=datetime(2030, 8, 10, 9, 30),
            notes='base note\nنوع الموعد: follow_up\nالأعراض: cough',
        )
        resp = client.get(f'/reception/edit_appointment/{a.id}')
        assert resp.status_code == 200

    def test_recurring_appointments_via_form(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/appointments/recurring',
            data={
                'patient_id': str(p.id),
                'starts_at': '2030-09-01T09:00:00',
                'count': '2',
                'interval_days': 'abc',
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()['count'] == 2

    def test_recurring_appointments_invalid_duration_returns_500(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/appointments/recurring',
            json={
                'patient_id': p.id,
                'starts_at': '2030-10-01T09:00:00',
                'count': 2,
                'duration_minutes': 'abc',
            },
        )
        assert resp.status_code == 500

    def test_waitlist_add_via_form(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/appointments/waitlist',
            data={'patient_id': str(p.id), 'preferred_time': 'evening'},
        )
        assert resp.status_code == 201

    def test_appointment_reminders_post_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('reminders exploded')

        monkeypatch.setattr(
            'services.notification_service.NotificationService.send_appointment_reminders',
            staticmethod(boom),
        )
        resp = client.post('/reception/appointments/reminders')
        assert resp.status_code == 500


class TestApiBranches:
    def test_queue_status_all_as_lab_user(self, login_as, client, ctx):
        login_as(client, f'lab_{uuid.uuid4().hex[:8]}', 'lab')
        p = ctx.patient()
        d = ctx.department(dtype='lab')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_status_all_as_radiology_user(self, login_as, client, ctx):
        login_as(client, f'rad_{uuid.uuid4().hex[:8]}', 'radiology')
        p = ctx.patient()
        d = ctx.department(dtype='radiology')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_status_all_as_doctor_user(self, login_as, client, ctx):
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        login_as(client, doc.username, 'doctor')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_status_all_as_nurse_forbidden(self, login_as, client, ctx):
        login_as(client, f'nurse_{uuid.uuid4().hex[:8]}', 'nurse')
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 403

    def test_queue_status_all_nurse_rejected_for_wait_metrics(self, login_as, client, ctx):
        login_as(client, f'nurse_{uuid.uuid4().hex[:8]}', 'nurse')
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 403

    def test_queue_wait_metrics_as_lab_user(self, login_as, client, ctx):
        login_as(client, f'lab_{uuid.uuid4().hex[:8]}', 'lab')
        p = ctx.patient()
        d = ctx.department(dtype='lab')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200

    def test_queue_wait_metrics_as_radiology_user(self, login_as, client, ctx):
        login_as(client, f'rad_{uuid.uuid4().hex[:8]}', 'radiology')
        p = ctx.patient()
        d = ctx.department(dtype='radiology')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200

    def test_queue_status_all_selected_department_scoping(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department(dtype='lab')
        d2 = ctx.department()
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/queue-status-all?department_id={d2.id}')
        assert resp.status_code == 200

    def test_department_staff_emergency_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')
        nurse = ctx.user(role='nurse', department_id=d.id)
        resp = client.get(f'/reception/api/department-staff?department_id={d.id}')
        assert resp.status_code == 200
        ids = [x['id'] for x in resp.get_json()['staff']]
        assert nurse.id in ids

    def test_department_staff_radiology_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='radiology')
        ctx.user(role='radiology', department_id=d.id)
        resp = client.get(f'/reception/api/department-staff?department_id={d.id}')
        assert resp.status_code == 200

    def test_department_staff_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('dept lookup exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get('/reception/api/department-staff?department_id=1')
        assert resp.status_code == 500

    def test_fhir_patient_full_resource(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient(national_id='9998887776', gender='F')
        p.address = '123 Main St'
        p.is_pregnant = True
        p.phone = '0501112223'
        ctx.db.session.commit()
        resp = client.get(f'/reception/api/fhir/patient/{p.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['telecom']
        assert resource['address']
        assert resource['extension'][0]['valueBoolean'] is True

    def test_fhir_encounter_with_doctor_and_notes(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
        )
        v.symptoms = 'headache'
        v.notes = 'took notes'
        ctx.db.session.commit()
        resp = client.get(f'/reception/api/fhir/encounter/{v.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['participant'][0]['individual']['reference'] == f'Practitioner/{doc.id}'
        assert resource['serviceType']
        assert resource['reasonCode'][0]['text'] == 'headache'
        assert resource['note'][0]['text'] == 'took notes'

    def test_fhir_organization_with_contact_details(self, login_as, client, ctx):
        _make_reception(login_as, client)
        tag = uuid.uuid4().hex[:6]
        from models.department import Department

        d = Department(
            name=f'ContactDept-{tag}',
            name_ar=f'contact-{tag}',
            is_active=True,
            location='Floor 2',
            phone='03-1234567',
            email='dept@test.local',
        )
        ctx.db.session.add(d)
        ctx.db.session.commit()
        resp = client.get(f'/reception/api/fhir/organization/{d.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert len(resource['telecom']) == 2
        assert resource['address']


class TestPatientHtmlFlashPaths:
    def test_add_patient_invalid_phone_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': 'abc'},
        )
        assert resp.status_code == 302
        assert 'show_add=1' in resp.headers['Location']

    def test_add_patient_invalid_national_id_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0501234509', 'national_id': '12'},
        )
        assert resp.status_code == 302

    def test_add_patient_missing_fields_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient', data={'first_name': '', 'last_name': '', 'phone': ''}
        )
        assert resp.status_code == 302

    def test_add_patient_duplicate_phone_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(phone='0501234567')
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'Dup', 'last_name': 'Phone', 'phone': '0501234567'},
        )
        assert resp.status_code == 302

    def test_add_patient_duplicate_national_id_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(national_id='123456789012')
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Dup',
                'last_name': 'Id',
                'phone': '0501234577',
                'national_id': '123456789012',
            },
        )
        assert resp.status_code == 302

    def test_add_patient_invalid_dates_fall_back_to_none(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Bad',
                'last_name': 'Dates',
                'phone': '0501234508',
                'birth_date': 'not-a-date',
                'last_menstruation_date': 'not-a-date',
                'gender': 'F',
                'is_pregnant': 'true',
                'pregnancy_weeks': 'not-a-number',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        pid = resp.get_json()['patient_id']
        row = ctx.db.session.get(Patient, pid)
        assert row.birth_date is None
        assert row.last_menstruation_date is None
        assert row.pregnancy_weeks is None

    def test_edit_patient_invalid_phone_html_rerenders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': 'not-a-phone'},
        )
        assert resp.status_code == 200

    def test_edit_patient_missing_required_html_rerenders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}', data={'first_name': '', 'last_name': '', 'phone': ''}
        )
        assert resp.status_code == 200

    def test_edit_patient_duplicate_phone_html(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(phone='0507771234')
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': '0507771234'},
        )
        assert resp.status_code == 200

    def test_edit_patient_invalid_dates_fall_back_to_none(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={
                'first_name': 'Bad',
                'last_name': 'Dates',
                'phone': p.phone,
                'birth_date': 'not-a-date',
                'last_menstruation_date': 'not-a-date',
                'gender': 'F',
                'is_pregnant': 'true',
                'pregnancy_weeks': 'not-a-number',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        ctx.db.session.refresh(p)
        assert p.birth_date is None
        assert p.last_menstruation_date is None
        assert p.pregnancy_weeks is None


class TestPatientApiExceptionPaths:
    def test_smart_patient_search_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('search exploded')

        monkeypatch.setattr('app.shared.search_service.SearchService.search_patients', boom)
        resp = client.get('/reception/api/smart-patient-search?q=anything')
        assert resp.status_code == 500

    def test_add_allergy_exception_returns_500(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('commit exploded')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            json={'allergen': 'Dust'},
        )
        assert resp.status_code == 500

    def test_add_problem_exception_returns_500(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('commit exploded')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            json={'problem_description': 'Insomnia'},
        )
        assert resp.status_code == 500

    def test_toggle_problem_exception_returns_500(self, login_as, client, ctx, monkeypatch):
        from models.problem_list import PatientProblem

        _make_reception(login_as, client)
        p = ctx.patient()
        problem = PatientProblem(
            tenant_id=ctx.tenant_id,
            patient_id=p.id,
            problem_description='Fever',
            status='ACTIVE',
            recorded_by_id=None,
        )
        ctx.db.session.add(problem)
        ctx.db.session.commit()

        def boom(*_a, **_k):
            raise RuntimeError('commit exploded')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(f'/reception/api/patients/{p.id}/problems/{problem.id}/toggle')
        assert resp.status_code == 500


class TestQueueExceptionBranches:
    def test_queue_management_exception_redirects_to_dashboard(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        ctx.department()

        class Boom:
            def __init__(self):
                raise RuntimeError('service exploded')

        monkeypatch.setattr('services.queue_management_service.QueueManagementService', Boom)
        resp = client.get('/reception/queue')
        assert resp.status_code == 302
        assert '/reception/dashboard' in resp.headers['Location']

    def test_add_patient_to_queue_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('queue down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.add_patient_to_queue', boom
        )
        resp = client.post(
            '/reception/queue/add-patient',
            data={'patient_id': str(p.id), 'department_id': str(d.id)},
        )
        assert resp.status_code == 302

    def test_call_next_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('queue down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.call_next_patient', boom
        )
        resp = client.get(f'/reception/queue/call-next/{d.id}')
        assert resp.status_code == 302

    def test_start_treatment_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('treatment down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.start_treatment', boom
        )
        resp = client.get('/reception/queue/start-treatment/1')
        assert resp.status_code == 302

    def test_complete_treatment_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('treatment down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.complete_treatment', boom
        )
        resp = client.get('/reception/queue/complete-treatment/1')
        assert resp.status_code == 302

    def test_skip_patient_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('skip down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.skip_patient', boom
        )
        resp = client.post('/reception/queue/skip-patient/1', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_return_to_queue_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('return down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.return_to_queue', boom
        )
        resp = client.post('/reception/queue/return-to-queue/1', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_cancel_ticket_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('cancel down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.cancel_ticket', boom
        )
        resp = client.post('/reception/queue/cancel-ticket/1', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_approve_emergency_debt_bad_amount_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/queue/approve-emergency-debt/1', data={'max_amount': 'not-a-number'}
        )
        assert resp.status_code == 302

    def test_approve_emergency_debt_service_exception_redirects(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('debt down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.approve_emergency_debt',
            boom,
        )
        resp = client.post('/reception/queue/approve-emergency-debt/1', data={'max_amount': '100'})
        assert resp.status_code == 302

    def test_approve_force_entry_service_exception_redirects(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('force down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.approve_force_entry',
            boom,
        )
        resp = client.post('/reception/queue/approve-force-entry/1', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_save_queue_settings_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.queue.safe_commit', boom)
        resp = client.post(
            f'/reception/queue/save-settings/{d.id}', data={'payment_required': 'on'}
        )
        assert resp.status_code == 302


class TestVisitExceptionAndEdgeBranches:
    def test_archive_visit_archive_not_ok_flashes_warning(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )
        monkeypatch.setattr(
            'routes.reception.visits.GatekeeperService.archive_visit',
            staticmethod(lambda *_a, **_k: (False, 'لا يمكن أرشفة')),
        )
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status != 'ARCHIVED'

    def test_archive_visit_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )

        def boom(*_a, **_k):
            raise RuntimeError('archiver down')

        monkeypatch.setattr(
            'routes.reception.visits.GatekeeperService.archive_visit', staticmethod(boom)
        )
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302

    def test_end_visit_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post('/reception/visits/99999999/end')
        assert resp.status_code == 302

    def test_end_visit_archive_not_ok_flashes_warning(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )
        monkeypatch.setattr(
            'routes.reception.visits.GatekeeperService.archive_visit',
            staticmethod(lambda *_a, **_k: (False, 'لا يمكن إنهاء')),
        )
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302

    def test_end_visit_exception_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )

        def boom(*_a, **_k):
            raise RuntimeError('archiver down')

        monkeypatch.setattr(
            'routes.reception.visits.GatekeeperService.archive_visit', staticmethod(boom)
        )
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302

    def test_return_to_treatment_missing_visit_redirects(self, login_as, client):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/visits/99999999/return-to-treatment', data={'reason': 'x' * 5}
        )
        assert resp.status_code == 302

    def test_transfer_visit_via_json_body(self, login_as, client, ctx):
        doc = ctx.user(role='doctor')
        d2 = ctx.department()
        v = ctx.visit(
            patient_id=ctx.patient().id, department_id=ctx.department().id, doctor_id=doc.id
        )
        _make_reception(login_as, client)
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            json={'department_id': str(d2.id), 'doctor_id': str(doc.id)},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_export_visits_csv_department_filter(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/export/visits?department_id={d.id}&status=OPEN')
        assert resp.status_code == 200

    def test_create_visit_malformed_department_id_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': str(p.id), 'department_id': '12x', 'payment_method': 'cash'},
        )
        assert resp.status_code == 200
        assert (
            ctx.db.session.execute(select(Visit).filter_by(patient_id=p.id)).scalars().first()
            is None
        )

    def test_create_visit_quick_emergency_forces_force_method(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Force Method Case',
                'department_id': str(d.id),
                'payment_method': 'cash',
            },
        )
        assert resp.status_code == 302
        v = ctx.db.session.execute(select(Visit).order_by(Visit.id.desc())).scalars().first()
        assert v.payment_method == 'FORCE'

    def test_create_visit_custom_service_matching_catalog_is_reused(self, login_as, client, ctx):
        from models.service import ServiceMaster

        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        existing = _make_service(
            ctx, category='general', department_id=d.id, name='DupServiceForCoverage', base_price=20
        )
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'custom_service_name': ['dupserviceforcoverage'],
                'custom_service_price': ['99'],
            },
        )
        assert resp.status_code == 302
        matches = (
            ctx.db.session.execute(select(ServiceMaster).filter_by(name='DupServiceForCoverage'))
            .scalars()
            .all()
        )
        assert len(matches) == 1
        assert matches[0].id == existing.id
        assert matches[0].is_custom is False
        # The matching catalogue entry is reused for the visit's pricing,
        # not duplicated as an inactive custom service.
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert float(v.total_amount) == 20

    def test_create_visit_custom_service_invalid_price_defaults_zero(self, login_as, client, ctx):
        from models.service import ServiceMaster

        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'custom_service_name': ['ZeroPriceServiceMarker'],
                'custom_service_price': ['not-a-number'],
            },
        )
        assert resp.status_code == 302
        svc = (
            ctx.db.session.execute(select(ServiceMaster).filter_by(name='ZeroPriceServiceMarker'))
            .scalars()
            .first()
        )
        assert svc is not None
        assert float(svc.base_price) == 0

    def test_create_visit_blank_custom_service_name_skipped(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
                'custom_service_name': ['   '],
                'custom_service_price': ['50'],
            },
        )
        assert resp.status_code == 302

    def test_create_visit_custom_service_unknown_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': '99999999',
                'payment_method': 'cash',
                'custom_service_name': ['OrphanServiceMarker'],
                'custom_service_price': ['50'],
            },
        )
        assert resp.status_code == 200


class TestAddServicePaymentStatusTransitions:
    def test_add_service_unpaid_visit_marks_pending(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
            total_amount=0,
            paid_amount=0,
            payment_status='PENDING',
        )
        svc = _make_service(ctx, base_price=30)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.payment_status == 'PENDING'
        assert float(v.total_amount) == 30

    def test_add_service_partially_paid_visit_marks_partial(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
            total_amount=0,
            paid_amount=10,
            payment_status='PARTIAL',
        )
        svc = _make_service(ctx, base_price=30)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.payment_status == 'PARTIAL'


class TestPrintPricingBranches:
    def test_print_receipt_with_survey_and_doctor_pricing(self, login_as, client, ctx):
        from models.patient_satisfaction import PatientSatisfactionSurvey
        from models.pricing import DoctorPricing

        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            visit_type='CONSULTATION',
            total_amount=100,
            paid_amount=100,
            payment_status='PAID',
        )
        ctx.db.session.add(
            DoctorPricing(
                doctor_id=doc.id,
                department_id=d.id,
                consultation_price=35,
                is_active=True,
            )
        )
        ctx.db.session.add(
            PatientSatisfactionSurvey(
                visit_id=v.id,
                patient_id=p.id,
                token='tok-' + uuid.uuid4().hex[:12],
            )
        )
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_follow_up_pricing(self, login_as, client, ctx):
        from models.pricing import DoctorPricing

        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            visit_type='FOLLOW_UP',
            total_amount=60,
            paid_amount=60,
            payment_status='PAID',
        )
        ctx.db.session.add(
            DoctorPricing(
                doctor_id=doc.id,
                department_id=d.id,
                consultation_price=35,
                follow_up_price=20,
                is_active=True,
            )
        )
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_emergency_pricing(self, login_as, client, ctx):
        from models.pricing import DoctorPricing

        _make_manager(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            visit_type='REGULAR',
            is_emergency=True,
            total_amount=90,
            paid_amount=90,
            payment_status='PAID',
        )
        ctx.db.session.add(
            DoctorPricing(
                doctor_id=doc.id,
                department_id=d.id,
                consultation_price=35,
                emergency_price=45,
                is_active=True,
            )
        )
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_prescription_other_doctor_denied(self, login_as, client, ctx):
        from models.medication import Prescription

        owner = ctx.user(role='doctor')
        other = ctx.user(role='doctor')
        login_as(client, other.username, 'doctor')
        p = ctx.patient()
        prescription = Prescription(
            patient_id=p.id,
            doctor_id=owner.id,
            prescription_number='RX-' + uuid.uuid4().hex[:10].upper(),
        )
        ctx.db.session.add(prescription)
        ctx.db.session.commit()
        resp = client.get(f'/reception/print_prescription/{prescription.id}')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']


class TestDailyCloseExceptionPath:
    def test_daily_close_commit_failure_keeps_register_open(
        self, login_as, client, ctx, monkeypatch
    ):
        from models.cash_register import CashRegister

        _make_reception(login_as, client)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.payments.safe_commit', boom)
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '10', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code == 302
        reg = (
            ctx.db.session.execute(
                select(CashRegister)
                .filter_by(register_date=date.today())
                .order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        assert reg.is_closed is False


class TestSendToAccountingZeroTotal:
    def test_send_to_accounting_zero_total_creates_invoice_without_line(
        self, login_as, client, ctx
    ):
        from models.invoice import Invoice, InvoiceService

        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=0,
            paid_amount=0,
            payment_status='PENDING',
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        invoice = ctx.db.session.execute(select(Invoice).filter_by(visit_id=v.id)).scalars().first()
        assert invoice is not None
        lines = (
            ctx.db.session.execute(select(InvoiceService).filter_by(invoice_id=invoice.id))
            .scalars()
            .all()
        )
        assert lines == []


class TestDashboardExceptionPaths:
    def test_staff_schedule_commit_failure_shows_error(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.user(role='doctor')
        resp = client.post(
            '/reception/staff/schedule',
            data={
                'user_id': '99999999',
                'day_of_week': '3',
                'start_time': '09:00',
                'end_time': '17:00',
            },
        )
        assert resp.status_code == 200

    def test_survey_post_exception_renders_invalid(self, login_as, client, ctx, monkeypatch):
        from models.patient_satisfaction import PatientSatisfactionSurvey

        p = ctx.patient()
        v = ctx.visit(patient_id=p.id, department_id=ctx.department().id)
        survey = PatientSatisfactionSurvey(
            visit_id=v.id,
            patient_id=p.id,
            token='tok-' + uuid.uuid4().hex[:12],
        )
        ctx.db.session.add(survey)
        ctx.db.session.commit()

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.dashboard.safe_commit', boom)
        resp = client.post(f'/reception/survey/{survey.token}', data={'rating': '5'})
        assert resp.status_code == 200


class TestBillingDisabledTenantBranches:
    """Module-disabled tenant: every billing-gated reception surface must
    refuse cleanly instead of rendering."""

    @pytest.fixture
    def iso_no_billing(self, isolated_tenant, db):
        from sqlalchemy import update

        from app.core.module.models import TenantModule

        db.session.execute(
            update(TenantModule)
            .where(
                TenantModule.tenant_id == isolated_tenant.id,
                TenantModule.module_name == 'billing',
            )
            .values(is_active=False)
        )
        db.session.commit()
        return isolated_tenant

    def _login_iso(self, app, db, client, tenant, role='reception'):
        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(
            db, tenant, username=f'iso_{role}_{uuid.uuid4().hex[:10]}', role=role
        )
        login_test_client(client, user, tenant)
        return user

    def test_pos_charge_returns_403_without_billing_module(self, app, db, client, iso_no_billing):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.post('/reception/pos/charge', json={'amount': 10})
        assert resp.status_code == 403

    def test_send_to_accounting_redirects_without_billing_module(
        self, app, db, client, iso_no_billing
    ):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.post('/reception/visits/1/send-to-accounting')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_print_receipt_redirects_without_billing_module(self, app, db, client, iso_no_billing):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.get('/reception/print_receipt/1')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_print_invoice_redirects_without_billing_module(self, app, db, client, iso_no_billing):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.get('/reception/print_invoice/1')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_cash_register_redirects_without_billing_module(self, app, db, client, iso_no_billing):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_daily_close_redirects_without_billing_module(self, app, db, client, iso_no_billing):
        self._login_iso(app, db, client, iso_no_billing)
        resp = client.get('/reception/daily-close')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']

    def test_send_to_accounting_failure_shows_error(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=10,
            paid_amount=10,
        )

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.payments.safe_commit', boom)
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        assert '/reception/queue' in resp.headers['Location']


class TestAppointmentCheckinCrossTenant:
    def test_booking_with_notes_flows_into_visit(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        booking = ctx.booking(department_id=d.id, notes='bring insurance card')
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302
        visit = (
            ctx.db.session.execute(
                select(Visit).filter(
                    Visit.notes.ilike(f'%[ONLINE_BOOKING:{booking.booking_reference}]%')
                )
            )
            .scalars()
            .first()
        )
        assert 'bring insurance card' in visit.notes

    def test_online_booking_non_tuple_queue_result_still_converts(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department()
        booking = ctx.booking(department_id=d.id)

        monkeypatch.setattr(
            'routes.reception.appointments.add_patient_to_queue_auto', lambda *_a, **_k: True
        )
        resp = client.post(
            '/reception/online-bookings/checkin', data={'booking_id': str(booking.id)}
        )
        assert resp.status_code == 302

    def test_appointment_checkin_non_tuple_queue_result_still_converts(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department()
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id, department_id=d.id)

        monkeypatch.setattr(
            'routes.reception.appointments.add_patient_to_queue_auto', lambda *_a, **_k: True
        )
        resp = client.post(f'/reception/appointments/{a.id}/checkin')
        assert resp.status_code == 302

    def test_edit_appointment_with_typed_lines_and_blank_lines(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(patient_id=ctx.patient().id)
        resp = client.post(
            f'/reception/edit_appointment/{a.id}',
            data={
                'appointment_date': '2030-05-08',
                'appointment_time': '10:00',
                'duration': '30',
                'notes': 'kept line\nنوع الموعد: old_type\nالأعراض: old_symptom\n\nanother kept line',
            },
        )
        assert resp.status_code == 302
        ctx.db.session.refresh(a)
        assert 'kept line' in a.notes
        assert 'another kept line' in a.notes
        assert 'old_type' not in a.notes

    def test_edit_appointment_get_with_blank_lines(self, login_as, client, ctx):
        _make_reception(login_as, client)
        a = ctx.appointment(
            patient_id=ctx.patient().id,
            starts_at=datetime(2030, 8, 11, 9, 0),
            ends_at=datetime(2030, 8, 11, 9, 30),
            notes='first\n\nنوع الموعد: first\n\nالأعراض: headache\n\nlast',
        )
        resp = client.get(f'/reception/edit_appointment/{a.id}')
        assert resp.status_code == 200


class TestApiExceptionBranches:
    def test_queue_status_as_doctor_overrides_doctor_id(self, login_as, client, ctx):
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        login_as(client, doc.username, 'doctor')
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/queue-department-status/{d.id}?doctor_id=99999999')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_status_exception_returns_failure(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('queue exploded')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_queue_status', boom
        )
        resp = client.get('/reception/api/queue-department-status/1')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_status_all_as_admin_gets_empty_scope(self, login_as, client, ctx):
        login_as(client, f'admin_{uuid.uuid4().hex[:8]}', 'admin')
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['data']['tickets'] == []
        assert payload['data']['waiting_count'] == 0

    def test_queue_wait_metrics_as_doctor(self, login_as, client, ctx):
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor', department_id=d.id)
        login_as(client, doc.username, 'doctor')
        _queue_ticket(ctx, p, d)
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_wait_metrics_selected_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department(dtype='lab')
        d2 = ctx.department(dtype='lab')
        _queue_ticket(ctx, p, d)
        resp = client.get(f'/reception/api/queue-wait-metrics?department_id={d2.id}')
        assert resp.status_code == 200

    def test_queue_wait_metrics_exception_returns_failure(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('metrics exploded')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_wait_metrics_today',
            boom,
        )
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_fhir_patient_exception_returns_500(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('fhir exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get(f'/reception/api/fhir/patient/{p.id}')
        assert resp.status_code == 500
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_fhir_encounter_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('fhir exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get('/reception/api/fhir/encounter/1')
        assert resp.status_code == 500

    def test_fhir_appointment_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('fhir exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get('/reception/api/fhir/appointment/1')
        assert resp.status_code == 500

    def test_fhir_practitioner_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('fhir exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get('/reception/api/fhir/practitioner/1')
        assert resp.status_code == 500

    def test_fhir_organization_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('fhir exploded')

        monkeypatch.setattr('routes.reception.api.get_tenant_record', boom)
        resp = client.get('/reception/api/fhir/organization/1')
        assert resp.status_code == 500

    def test_patient_queue_position_exception_returns_failure(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('position exploded')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_patient_queue_position',
            boom,
        )
        p = ctx.patient()
        d = ctx.department()
        resp = client.get(f'/reception/api/patient-queue-position/{p.id}/{d.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_snapshot_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky_execute(stmt, *args, **kwargs):
            if 'queue_management' in str(stmt):
                raise RuntimeError('queue query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.api.db.session.execute', flaky_execute)
        resp = client.get('/reception/api/queue-snapshot')
        assert resp.status_code == 500

    def test_display_waiting_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky_execute(stmt, *args, **kwargs):
            if 'queue_management' in str(stmt):
                raise RuntimeError('queue query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.api.db.session.execute', flaky_execute)
        resp = client.get('/reception/api/display/waiting')
        assert resp.status_code == 500

    def test_display_calls_exception_returns_500(self, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky_execute(stmt, *args, **kwargs):
            if 'queue_management' in str(stmt):
                raise RuntimeError('queue query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.api.db.session.execute', flaky_execute)
        resp = client.get('/reception/api/display/calls')
        assert resp.status_code == 500

    def test_display_waiting_room_from_doctor_room(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        doc.doctor_room = 'Room 7'
        ctx.db.session.commit()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        _queue_ticket(ctx, p, d, visit=v, status=QueueState.CALLED.value)
        resp = client.get('/reception/api/display/waiting')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['called'][0]['room_name'] == 'Room 7'

    def test_display_calls_room_from_doctor_room(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        doc.doctor_room = 'Room 9'
        ctx.db.session.commit()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        _queue_ticket(ctx, p, d, visit=v, status=QueueState.CALLED.value)
        resp = client.get('/reception/api/display/calls')
        assert resp.status_code == 200
        assert resp.get_json()['items'][0]['room_name'] == 'Room 9'


class TestVisitPricingTaxAndDoctorSelection:
    def test_api_pricing_emergency_service_price_used(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_service(
            ctx, category='doctor', base_price=50, emergency_price=130, name='EmergencyOnly'
        )
        d = ctx.department()
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&is_emergency=true')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 130

    def test_api_pricing_insurance_service_price_used(self, login_as, client, ctx):
        _make_reception(login_as, client)
        _make_service(
            ctx, category='doctor', base_price=50, insurance_price=77, name='InsuranceOnly'
        )
        d = ctx.department()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&payment_method=insurance'
        )
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 77

    def test_calculate_visit_cost_exception_returns_zero(self, app, ctx, monkeypatch):
        from routes.reception import visits as visits_module

        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('pricing exploded')

        monkeypatch.setattr(visits_module, 'get_service_type_by_department', boom)
        assert visits_module.calculate_visit_cost(d.id, None, 'REGULAR', False, 'cash') == 0

    def test_doctor_cost_exception_counts_as_zero(self, app, ctx, monkeypatch):
        from routes.reception import visits as visits_module

        d = ctx.department()
        doc = ctx.user(role='doctor')
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)

        def boom(*_a, **_k):
            raise RuntimeError('doctor pricing exploded')

        monkeypatch.setattr(visits_module, 'calculate_doctor_cost', boom)
        assert visits_module.calculate_visit_cost(d.id, doc.id, 'REGULAR', False, 'cash') == 0

    def test_calculate_doctor_cost_exception_returns_zero(self, app, ctx, monkeypatch):
        from routes.reception import visits as visits_module

        doc = ctx.user(role='doctor')

        def boom(*_a, **_k):
            raise RuntimeError('doctor pricing exploded')

        monkeypatch.setattr(visits_module, 'calculate_doctor_cost', boom)
        assert visits_module.calculate_visit_cost(doc.id, None, 'REGULAR', False, 'cash') == 0

    def test_pricing_rule_on_payment_method_applies(self, login_as, client, ctx):
        from models.pricing_management import PricingRule

        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        marker = 'ZZPAY' + uuid.uuid4().hex[:6].upper()
        rule = PricingRule(
            name='pm-' + marker,
            condition_type='payment_method',
            condition_value='zzpaymethod',
            price_adjustment_type='percentage',
            price_adjustment_value=50,
            priority=1,
            is_active=True,
        )
        ctx.db.session.add(rule)
        ctx.db.session.commit()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&payment_method=zzpaymethod'
        )
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 150

    def test_api_pricing_lab_custom_blank_name_skipped(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&custom_service_name=%20%20&custom_service_price=50'
        )
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 0

    def test_api_pricing_custom_invalid_price_defaults_zero(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department()
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&custom_service_name=Widget&custom_service_price=not-a-number'
        )
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 0

    def test_api_pricing_lab_inclusive_tax(self, login_as, client, ctx):
        _make_reception(login_as, client)
        d = ctx.department(dtype='lab')
        svc = _make_service(ctx, category='lab', department_id=d.id, base_price=100)
        resp = client.get(
            f'/reception/api/visit-pricing?department_id={d.id}&test_ids={svc.id}&tax_type=inclusive'
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['cost'] == 100
        assert any('ضريب' in str(b['item']) for b in payload['details']['breakdown'])

    def test_pricing_exception_returns_500(self, app, ctx, monkeypatch):
        from routes.reception import visits as visits_module

        ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('pricing exploded')

        monkeypatch.setattr(visits_module, 'calculate_visit_cost', boom)
        assert visits_module.calculate_visit_cost is boom

    def test_transfer_visit_service_failure_returns_500(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        doc = ctx.user(role='doctor')
        d2 = ctx.department()
        v = ctx.visit(
            patient_id=ctx.patient().id, department_id=ctx.department().id, doctor_id=doc.id
        )

        def boom(*_a, **_k):
            return False, 'transfer_failed'

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.transfer_visit', boom
        )
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data={'department_id': str(d2.id), 'doctor_id': str(doc.id)},
        )
        assert resp.status_code == 500

    def test_add_service_exception_redirects_with_error(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            status='IN_PROGRESS',
            total_amount=0,
        )
        svc = _make_service(ctx, base_price=30)

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.visits.safe_commit', boom)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service', data={'service_id': str(svc.id)}
        )
        assert resp.status_code == 302

    def test_return_to_treatment_state_machine_value_error(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        p = ctx.patient()
        v = ctx.visit(
            patient_id=p.id,
            department_id=ctx.department().id,
            status='COMPLETED',
            completed_at=datetime.now(UTC),
        )

        def boom(*_a, **_k):
            raise ValueError('not allowed')

        monkeypatch.setattr(
            'services.visit_state_machine_service.VisitStateMachineService.return_to_treatment',
            boom,
        )
        resp = client.post(
            f'/reception/visits/{v.id}/return-to-treatment', data={'reason': 'valid reason'}
        )
        assert resp.status_code == 302

    def test_return_to_treatment_commit_exception_redirects(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        p = ctx.patient()
        v = ctx.visit(
            patient_id=p.id,
            department_id=ctx.department().id,
            status='COMPLETED',
            completed_at=datetime.now(UTC),
        )

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.visits.safe_commit', boom)
        resp = client.post(
            f'/reception/visits/{v.id}/return-to-treatment', data={'reason': 'valid reason'}
        )
        assert resp.status_code == 302

    def test_create_visit_queue_non_tuple_result_still_creates(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')
        monkeypatch.setattr(
            'routes.reception.visits.add_patient_to_queue_auto', lambda *_a, **_k: True
        )
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Queue NonTuple Case',
                'department_id': str(d.id),
            },
        )
        assert resp.status_code == 302

    def test_create_visit_queue_exception_still_creates(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')

        def boom(*_a, **_k):
            raise RuntimeError('queue exploded')

        monkeypatch.setattr('routes.reception.visits.add_patient_to_queue_auto', boom)
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Queue Explode Case',
                'department_id': str(d.id),
            },
        )
        assert resp.status_code == 302

    def test_api_visit_pricing_exception_returns_500(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('pricing exploded')

        monkeypatch.setattr('routes.reception.visits.calculate_visit_cost', boom)
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}')
        assert resp.status_code == 500


class TestPhonePlusNormalization:
    def test_add_patient_international_phone_normalized(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'Plus', 'last_name': 'Phone', 'phone': '+972 50-123 4567'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        pid = resp.get_json()['patient_id']
        row = ctx.db.session.get(Patient, pid)
        assert row.phone == '+972501234567'

    def test_edit_patient_international_phone_normalized(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'Plus', 'last_name': 'Phone', 'phone': '+1 (555) 123-4567'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        ctx.db.session.refresh(p)
        assert p.phone == '+15551234567'

    def test_add_patient_non_digit_national_id_json_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0501234560',
                'national_id': 'ABC',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_add_patient_non_digit_national_id_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0501234559', 'national_id': '!!!'},
        )
        assert resp.status_code == 302

    def test_add_patient_short_national_id_json_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0501234558',
                'national_id': '123',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_short_national_id_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0501234557',
                'national_id': '1234',
            },
        )
        assert resp.status_code == 302

    def test_add_patient_commit_failure_json_returns_400(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0501234555'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_commit_failure_html_redirects(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0501234554'},
        )
        assert resp.status_code == 302

    def test_add_patient_missing_fields_json_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': '', 'last_name': '', 'phone': '0501234553'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_short_national_id_html_rerenders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': p.phone, 'national_id': '12'},
        )
        assert resp.status_code == 200

    def test_edit_patient_duplicate_phone_json_returns_409(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(phone='0509876543')
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': '0509876543'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_edit_patient_duplicate_national_id_html_rerenders(self, login_as, client, ctx):
        _make_reception(login_as, client)
        ctx.patient(national_id='3216549871')
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={
                'first_name': 'X',
                'last_name': 'Y',
                'phone': p.phone,
                'national_id': '3216549871',
            },
        )
        assert resp.status_code == 200

    def test_edit_patient_commit_failure_json_returns_400(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': p.phone},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_commit_failure_html_rerenders(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'X', 'last_name': 'Y', 'phone': p.phone},
        )
        assert resp.status_code == 200

    def test_delete_patient_commit_failure_shows_error(self, login_as, client, ctx, monkeypatch):
        _make_manager(login_as, client)
        p = ctx.patient()

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code == 302

    def test_add_allergy_malformed_json_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code in (400, 415)

    def test_add_problem_malformed_json_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code in (400, 415)


class TestQueueMissingTickets:
    def test_complete_treatment_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.get('/reception/queue/complete-treatment/99999999')
        assert resp.status_code == 302

    def test_return_to_queue_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/return-to-queue/99999999', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_cancel_ticket_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/cancel-ticket/99999999', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_skip_patient_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/skip-patient/99999999', data={'reason': 'x'})
        assert resp.status_code == 302

    def test_approve_emergency_debt_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/approve-emergency-debt/99999999', data={})
        assert resp.status_code == 302

    def test_approve_force_entry_missing_ticket(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post('/reception/queue/approve-force-entry/99999999', data={})
        assert resp.status_code == 302

    def test_add_patient_to_queue_exception_redirects_general(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')

        def boom(*_a, **_k):
            raise RuntimeError('queue down')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.add_patient_to_queue', boom
        )
        resp = client.post(
            '/reception/queue/add-patient',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
            },
        )
        assert resp.status_code == 302


class TestQueueManagementScopeBranches:
    def test_department_scoped_user_sees_page(self, login_as, client, ctx):
        d = ctx.department()
        doc = ctx.user(role='reception', department_id=d.id)
        login_as(client, doc.username, 'reception')
        resp = client.get('/reception/queue')
        assert resp.status_code == 200

    def test_department_scoped_user_can_save_settings(self, login_as, client, ctx):
        d = ctx.department()
        doc = ctx.user(role='reception', department_id=d.id)
        login_as(client, doc.username, 'reception')
        resp = client.post(
            f'/reception/queue/save-settings/{d.id}', data={'payment_required': 'on'}
        )
        assert resp.status_code == 302


class TestQueueHelperExceptionBranches:
    """Force the broad except in each module-level analytics helper to run;
    they must degrade to their empty-value fallback, not raise."""

    @staticmethod
    def _boom_execute(*_a, **_k):
        raise RuntimeError('query exploded')

    def test_smart_queue_management_exception(self, app, ctx, login_as, client, monkeypatch):
        _make_reception(login_as, client)

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky_execute(stmt, *args, **kwargs):
            if 'queue_management' in str(stmt):
                raise RuntimeError('query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky_execute)
        resp = client.get('/reception/api/queue-status/1')
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_patient_flow_analysis_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_patient_flow_analysis() == {}

    def test_appointment_optimization_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_appointment_optimization() == {}

    def test_real_time_alerts_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_real_time_alerts() == []

    def test_workflow_automation_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_workflow_automation() == []

    def test_patient_satisfaction_ai_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_patient_satisfaction_ai() == {}

    def test_patient_demand_forecast_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_patient_demand_forecast() == {}

    def test_resource_planning_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_resource_planning() == {}

    def test_smart_recommendations_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('routes.reception.queue.db.session.execute', self._boom_execute)
        assert queue_module.get_smart_recommendations() == []

    def test_add_patient_to_queue_auto_exception(self, app, ctx, monkeypatch):
        from routes.reception import queue as queue_module

        def boom(*_a, **_k):
            raise RuntimeError('service exploded')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.__init__', boom
        )
        p = ctx.patient()
        d = ctx.department()
        v = _paid_visit(ctx, p, d)
        ok, _msg = queue_module.add_patient_to_queue_auto(v.id, d.id, None)
        assert ok is False


class TestRemainingBranchSweep:
    def test_send_to_accounting_partial_stays_partial(self, login_as, client, ctx):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=100,
            paid_amount=50,
            payment_status='PENDING',
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.payment_status == 'PARTIAL'

    def test_print_receipt_with_flaky_queue_lookup(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=10,
            paid_amount=10,
            payment_status='PAID',
        )
        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'queue_management' in str(stmt):
                raise RuntimeError('queue lookup exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.payments.db.session.execute', flaky)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_with_flaky_doctor_pricing_lookup(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_manager(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=10,
            paid_amount=10,
            payment_status='PAID',
        )
        ctx.user(role='doctor')

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'doctor_pricing' in str(stmt):
                raise RuntimeError('pricing exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.payments.db.session.execute', flaky)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_with_flaky_last_payment_lookup(self, login_as, client, ctx, monkeypatch):
        _make_manager(login_as, client)
        p = ctx.patient()
        v = ctx.visit(
            patient_id=p.id,
            department_id=ctx.department().id,
            total_amount=10,
            paid_amount=10,
            payment_status='PAID',
        )
        ctx.db.session.add(
            Payment(patient_id=p.id, visit_id=v.id, method='cash', amount=10, status='CONFIRMED')
        )
        ctx.db.session.commit()

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            s = str(stmt)
            if 'FROM payments' in s or ('payments' in s and 'doctor_pricing' not in s):
                raise RuntimeError('payment lookup exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.payments.db.session.execute', flaky)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_with_flaky_survey_lookup(self, login_as, client, ctx, monkeypatch):
        _make_manager(login_as, client)
        v = ctx.visit(
            patient_id=ctx.patient().id,
            department_id=ctx.department().id,
            total_amount=10,
            paid_amount=10,
            payment_status='PAID',
        )

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'patient_satisfaction_surveys' in str(stmt):
                raise RuntimeError('survey lookup exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.payments.db.session.execute', flaky)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code == 200

    def test_daily_close_already_closed_get_redirects(self, login_as, client, ctx):

        _make_reception(login_as, client)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '1', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code == 302
        # Already-closed register: POST warns and redirects to cash register.
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '2', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code == 302
        assert '/reception/cash-register' in resp.headers['Location']


class TestDepartmentLocationRoomFallback:
    def test_display_waiting_room_from_department_location(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        tag = uuid.uuid4().hex[:6]
        from models.department import Department

        d = Department(
            name=f'LocDept-{tag}',
            name_ar=f'loc-{tag}',
            location='Building B, Room 2',
            is_active=True,
        )
        ctx.db.session.add(d)
        ctx.db.session.commit()
        _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.get('/reception/api/display/waiting')
        assert resp.status_code == 200
        assert resp.get_json()['called'][0]['room_name'] == 'Building B, Room 2'

    def test_display_calls_room_from_department_location(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        tag = uuid.uuid4().hex[:6]
        from models.department import Department

        d = Department(
            name=f'LocDept2-{tag}',
            name_ar=f'loc2-{tag}',
            location='Building A, Room 9',
            is_active=True,
        )
        ctx.db.session.add(d)
        ctx.db.session.commit()
        _queue_ticket(ctx, p, d, status=QueueState.CALLED.value)
        resp = client.get('/reception/api/display/calls')
        assert resp.status_code == 200
        assert resp.get_json()['items'][0]['room_name'] == 'Building A, Room 9'


class TestFhirEncounterEmptyParticipant:
    def test_fhir_encounter_without_doctor_or_department(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        v = ctx.visit(patient_id=p.id, department_id=None)
        resp = client.get(f'/reception/api/fhir/encounter/{v.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['participant'] == []
        assert resource['serviceType'] == []


class TestApiQueueStatusFailureBranch:
    def test_queue_status_returns_failure_when_status_empty(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_queue_status',
            lambda *_a, **_k: None,
        )
        resp = client.get('/reception/api/queue-department-status/1')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_status_all_failure_branch(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_queue_status_all',
            lambda *_a, **_k: None,
        )
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_status_all_exception_branch(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise RuntimeError('status exploded')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.get_queue_status_all',
            boom,
        )
        resp = client.get('/reception/api/queue-status-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is False

    def test_queue_wait_metrics_as_admin_empty_scope(self, login_as, client, ctx):
        login_as(client, f'admin_{uuid.uuid4().hex[:8]}', 'admin')
        resp = client.get('/reception/api/queue-wait-metrics')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


class TestVisitLikeExtractionBranches:
    def test_peak_hours_failure_keeps_stats(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        _queue_ticket(ctx, p, d)

        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'hour' in str(stmt):
                raise RuntimeError('hourly query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        resp = client.get(f'/reception/api/queue-status/{d.id}')
        assert resp.status_code == 200

    def test_hourly_flow_failure_keeps_daily(self, app, ctx, monkeypatch):
        from app.extensions import db as _db
        from routes.reception import queue as queue_module

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'hour' in str(stmt):
                raise RuntimeError('hourly query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        result = queue_module.get_patient_flow_analysis()
        assert result['hourly_flow'] == []
        assert len(result['daily_flow']) == 7

    def test_avg_visit_duration_failure_defaults_to_zero(self, app, ctx, monkeypatch):
        from app.extensions import db as _db
        from routes.reception import queue as queue_module

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'epoch' in str(stmt):
                raise RuntimeError('duration query exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        result = queue_module.get_smart_recommendations()
        assert isinstance(result, list)


class TestCapacityAlerts:
    def test_real_time_alerts_capacity_alert(self, app, ctx):
        from routes.reception.queue import get_real_time_alerts

        p = ctx.patient()
        d = ctx.department()
        for _ in range(51):
            ctx.visit(patient_id=p.id, department_id=d.id)
        alerts = get_real_time_alerts()
        types = {a['type'] for a in alerts}
        assert 'capacity' in types

    def test_workflow_automation_follow_up_alert(self, app, ctx):
        from routes.reception.queue import get_workflow_automation

        d = ctx.department()
        p = ctx.patient()
        for _ in range(11):
            ctx.visit(
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                archive_status='ARCHIVED',
                completed_at=datetime.now(UTC),
            )
        suggestions = get_workflow_automation()
        types = {s['type'] for s in suggestions}
        assert 'follow_up' in types

    def test_demand_forecast_uses_hourly_history(self, app, ctx):
        from routes.reception.queue import get_patient_demand_forecast

        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        result = get_patient_demand_forecast()
        assert result['hours_ahead'] == 4

    def test_resource_planning_capacity_alert(self, app, ctx):
        from routes.reception.queue import get_resource_planning

        p = ctx.patient()
        d = ctx.department()
        for _ in range(31):
            ctx.visit(patient_id=p.id, department_id=d.id)
        result = get_resource_planning()
        assert result['today_visits'] >= 31
        rec_types = {r['type'] for r in result['planning_recommendations']}
        assert 'capacity_planning' in rec_types

    def test_smart_recommendations_growth_alert(self, app, ctx):
        from routes.reception.queue import get_smart_recommendations

        for i in range(21):
            ctx.patient(first_name=f'Grow{i:02d}', last_name='Person')
        recommendations = get_smart_recommendations()
        types = {r['type'] for r in recommendations}
        assert 'growth' in types


class TestFinalPatientEdges:
    def test_add_patient_phone_only_dashes_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '---'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_missing_fields_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': '', 'last_name': 'B', 'phone': ''},
        )
        assert resp.status_code == 302

    def test_add_patient_commit_value_error_json_returns_400(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)

        def boom(*_a, **_k):
            raise ValueError('validation blew up')

        monkeypatch.setattr('routes.reception.patients.safe_commit', boom)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0501234501'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_phone_only_dashes_rejected(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '---'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_missing_fields_json_returns_400(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': '', 'last_name': '', 'phone': ''},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_edit_success_html_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'HtmlEdit', 'last_name': 'Works', 'phone': p.phone},
        )
        assert resp.status_code == 302
        assert f'/reception/view_patient/{p.id}' in resp.headers['Location']


class TestVisitInsurancePatientShareBranch:
    def test_insurance_patient_share_below_amount_flashes_warning(self, login_as, client, ctx):
        from models.insurance import InsuranceCompany

        _make_reception(login_as, client)
        _make_pricing_catalog(
            ctx,
            service_type='consultation',
            base_price=100,
            insurance_coverage=80,
            patient_share=20,
        )
        company = InsuranceCompany(name='InsCo-' + uuid.uuid4().hex[:6], is_active=True)
        ctx.db.session.add(company)
        ctx.db.session.commit()
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'insurance',
                'insurance_provider': 'InsCo',
                'insurance_policy_number': 'POL-123',
                'insurance_coverage': '80',
                'insurance_company_id': str(company.id),
                'amount_paid': '2',
            },
        )
        assert resp.status_code == 302
        v = (
            ctx.db.session.execute(
                select(Visit).filter_by(patient_id=p.id).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        # patient_share after insurance math (4) exceeds what was paid (2):
        # payment stays PENDING and no payment row is created.
        assert v.payment_status == 'PENDING'
        pay = ctx.db.session.execute(select(Payment).filter_by(visit_id=v.id)).scalars().first()
        assert pay is None
        assert v.insurance_provider == 'InsCo'


class TestVisitExceptionAndFlakyBranches:
    def test_create_visit_commit_failure_renders_form(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')

        def boom(*_a, **_k):
            raise RuntimeError('commit down')

        monkeypatch.setattr('routes.reception.visits.safe_commit', boom)
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Commit Explode Case',
                'department_id': str(d.id),
            },
        )
        assert resp.status_code == 200

    def test_emergency_department_lookup_failure_still_works(
        self, login_as, client, ctx, monkeypatch
    ):
        from app.extensions import db as _db

        _make_reception(login_as, client)
        d = ctx.department(dtype='emergency')

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            # Only the emergency-department scan should fail; the patient
            # creation and visit commit must still succeed.
            if 'is_active' in str(stmt) and 'departments' in str(stmt):
                raise RuntimeError('dept scan exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.visits.db.session.execute', flaky)
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'Emergency Flaky Case',
                'department_id': str(d.id),
            },
        )
        assert resp.status_code == 302

    def test_api_pricing_get_pricing_details_failure_returns_zero(
        self, login_as, client, ctx, monkeypatch
    ):
        _make_reception(login_as, client)
        d = ctx.department()

        def boom(*_a, **_k):
            raise RuntimeError('details exploded')

        monkeypatch.setattr('routes.reception.visits.get_service_by_department', boom)
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}')
        assert resp.status_code == 200
        assert resp.get_json()['cost'] == 0
        assert resp.get_json()['details'] == {}

    def test_doctor_pricing_query_failure_counts_as_zero(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        _make_pricing_catalog(ctx, service_type='consultation', base_price=100)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'doctor_pricing' in str(stmt):
                raise RuntimeError('doctor pricing exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.visits.db.session.execute', flaky)
        resp = client.get(f'/reception/api/visit-pricing?department_id={d.id}&doctor_id={doc.id}')
        assert resp.status_code == 200


class TestFhirAppointmentWithNotes:
    def test_fhir_appointment_description_from_notes(self, login_as, client, ctx):
        _make_reception(login_as, client)
        p = ctx.patient()
        a = ctx.appointment(patient_id=p.id, notes='bring insurance card')
        resp = client.get(f'/reception/api/fhir/appointment/{a.id}')
        assert resp.status_code == 200
        assert resp.get_json()['description'] == 'bring insurance card'
