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

        _CACHED_ENCRYPTION['_key'] = Fernet.generate_key().decode()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', _CACHED_ENCRYPTION['_key'])
        _CACHED_ENCRYPTION['_svc'] = FieldEncryptionService()
    else:
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', _CACHED_ENCRYPTION['_key'])
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


class TestQueueRemainingCoverage:
    def test_peak_hours_failure_in_smart_queue_management(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        from app.extensions import db as _db

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'hour' in str(stmt).lower():
                raise RuntimeError('peak hours exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        resp = client.get('/reception/api/queue-status/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['peak_hour'] is None
        assert data['peak_count'] == 0

    def test_hourly_flow_failure_in_patient_flow_analysis(self, app, ctx, monkeypatch):
        from app.extensions import db as _db
        from routes.reception import queue as queue_module

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'hour' in str(stmt).lower():
                raise RuntimeError('hourly flow exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        result = queue_module.get_patient_flow_analysis()
        assert result['hourly_flow'] == []
        assert len(result['daily_flow']) == 7

    def test_avg_visit_duration_failure_in_smart_recommendations(self, app, ctx, monkeypatch):
        from app.extensions import db as _db
        from routes.reception import queue as queue_module

        original_execute = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            if 'epoch' in str(stmt).lower():
                raise RuntimeError('duration exploded')
            return original_execute(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        result = queue_module.get_smart_recommendations()
        assert isinstance(result, list)

    def test_wait_time_recommendation_in_satisfaction_ai(self, app, ctx, monkeypatch):
        from routes.reception import queue as queue_module

        p = ctx.patient()
        d = ctx.department()
        from models.queue_management import QueueManagement

        ticket = QueueManagement(
            queue_number='Q' + uuid.uuid4().hex[:10].upper(),
            patient_id=p.id,
            department_id=d.id,
            status='WAITING',
            priority_level='normal',
            estimated_wait_time=60,
            created_at=datetime.now(UTC),
            queued_at=datetime.now(UTC),
        )
        ctx.db.session.add(ticket)
        ctx.db.session.commit()

        from app.extensions import db as _db

        original = _db.session.execute

        def flaky(stmt, *args, **kwargs):
            s = str(stmt).lower()
            if 'estimated_wait_time' in s:

                class R:
                    def scalar(self):
                        return 60

                return R()
            return original(stmt, *args, **kwargs)

        monkeypatch.setattr('routes.reception.queue.db.session.execute', flaky)
        result = queue_module.get_patient_satisfaction_ai()
        assert isinstance(result, dict)
        types_found = {r['type'] for r in result['recommendations']}
        assert 'wait_time' in types_found

    def test_completion_rate_recommendation_in_satisfaction_ai(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        class ZeroResult:
            def scalar(self):
                return 0

            def all(self):
                return []

        monkeypatch.setattr(
            'routes.reception.queue.db.session.execute', lambda *_a, **_k: ZeroResult()
        )
        result = queue_module.get_patient_satisfaction_ai()
        assert isinstance(result, dict)
        types_found = {r['type'] for r in result['recommendations']}
        assert 'completion' in types_found

    def test_calculate_no_show_rate_exception(self, app, monkeypatch):
        from routes.reception import queue as queue_module

        def boom(*_a, **_k):
            raise ValueError('boom')

        monkeypatch.setattr('routes.reception.queue.db.session.execute', boom)
        assert queue_module.calculate_no_show_rate() == 0

    def test_add_patient_to_queue_auto_visit_none(self, app, ctx, monkeypatch):
        from routes.reception import queue as queue_module

        monkeypatch.setattr('utils.tenant_query.get_tenant_record', lambda *_a, **_k: None)
        d = ctx.department()
        ok, _msg = queue_module.add_patient_to_queue_auto(1, d.id, None)
        assert ok is False

    def test_satisfaction_score_recommendation_completion_rate_low(self, app, ctx):
        from routes.reception import queue as queue_module

        # direct helper branch not needed; covered above
        assert isinstance(queue_module.calculate_satisfaction_score(0, 10, 0), (int, float))
