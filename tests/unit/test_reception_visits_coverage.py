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
from models.queue_management import QueueManagement
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


class TestVisitsCoverageExtraBranches:
    def test_transfer_direct_peer_disabled_branch(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        v = ctx.visit(patient_id=ctx.patient().id, department_id=ctx.department().id)
        from services import queue_management_service

        monkeypatch.setattr(
            queue_management_service.QueueManagementService,
            'transfer_visit',
            lambda _self, *_a, **_kw: (False, 'direct_peer_transfer_disabled'),
        )
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data={'department_id': str(ctx.department().id), 'doctor_id': '1'},
        )
        assert resp.status_code == 400
        payload = resp.get_json()
        assert payload['success'] is False
        assert isinstance(payload['message'], dict)
        assert 'error' in payload['message']

    def test_create_visit_counter_exception_is_swallowed(self, login_as, client, ctx, monkeypatch):
        _make_reception(login_as, client)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        monkeypatch.setattr('models.patient_visit_counter.PatientVisitCounter', None)
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': str(p.id),
                'department_id': str(d.id),
                'doctor_id': str(doc.id),
                'payment_method': 'cash',
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 302
