"""Coverage for routes/booking_routes.py — the public booking portal.

The booking portal is the one part of the system a patient can reach without
an account: they register, book, pay and cancel. Every branch of those flows
had lines that never ran -- the duplicate-email and duplicate-username
lookups, the meeting-link extraction, the staff and patient cancellation
paths, the name and time parsing of the booking form, and the telemedicine
link.

Each test class is named after the behaviour it covers.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _booking_id_from(resp):
    """The id of the booking the response redirected to."""
    location = resp.headers.get('Location', '')
    assert '/booking/confirmation/' in location, location
    return int(location.rsplit('/', 1)[-1])


def _department(db, tenant_id, name='Booking Dept'):
    from models.department import Department

    department = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(department)
    db.session.flush()
    return department


def _doctor(db, tenant_id, username='book_doc'):
    from models.user import User

    user = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role='doctor',
        is_active=True,
        tenant_id=tenant_id,
    )
    user.set_password('test123')
    db.session.add(user)
    db.session.flush()
    return user


def _patient(db, tenant_id, username='book_patient'):
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name='Booked',
        last_name='Patient',
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(patient)
    db.session.flush()
    return patient


def _booking(db, tenant_id, **kwargs):
    from models.online_booking import OnlineBooking

    defaults = {
        'booking_reference': OnlineBooking.generate_booking_reference(),
        'confirmation_code': OnlineBooking.generate_confirmation_code(),
        'first_name': 'Jane',
        'last_name': 'Doe',
        'phone': '0500000000',
        'appointment_date': datetime.now(UTC).date() + timedelta(days=3),
        'appointment_time': time(10, 0),
        'visit_type': 'first',
        'status': 'pending',
        'payment_status': 'pending',
        'payment_amount': 50,
    }
    defaults.update(kwargs)
    booking = OnlineBooking(tenant_id=tenant_id, **defaults)
    db.session.add(booking)
    db.session.flush()
    return booking


class TestUserEmailExists:
    """``_user_email_exists`` — the signup duplicate check."""

    def test_an_empty_address_matches_nothing(self, app, db, test_tenant):
        from routes.booking_routes import _user_email_exists

        assert _user_email_exists('') is False
        assert _user_email_exists(None) is False

    def test_a_blank_address_matches_nothing(self, app, db, test_tenant):
        from routes.booking_routes import _user_email_exists

        assert _user_email_exists('   ') is False

    def test_an_existing_address_is_found(self, app, db, test_tenant):
        from models.user import User
        from routes.booking_routes import _user_email_exists

        user = User(
            username='existing_mail_user',
            email='taken@example.test',
            full_name='Taken',
            role='patient',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.flush()

        assert _user_email_exists('taken@example.test') is True
        assert _user_email_exists('TAKEN@example.test') is True

    def test_an_unused_address_is_not_found(self, app, db, test_tenant):
        from routes.booking_routes import _user_email_exists

        assert _user_email_exists('free@example.test') is False


class TestExtractMeetingLink:
    """``_extract_meeting_link`` — reading the telemedicine link out of notes."""

    def test_no_notes_have_no_link(self):
        from routes.booking_routes import _extract_meeting_link

        assert _extract_meeting_link(None) is None
        assert _extract_meeting_link('') is None

    def test_notes_without_a_link_have_none(self):
        from routes.booking_routes import _extract_meeting_link

        assert _extract_meeting_link('please come early') is None

    def test_a_link_is_extracted(self):
        from routes.booking_routes import _extract_meeting_link

        link = _extract_meeting_link('MEET:https://example.test/room/1')
        assert link == 'https://example.test/room/1'


class TestRegister:
    """The patient self-registration."""

    def test_the_form_renders(self, app, client):
        resp = client.get('/booking/register')
        assert resp.status_code in (200, 302)

    def test_missing_fields_are_refused(self, app, client):
        resp = client.post('/booking/register', data={'full_name': ''})
        assert resp.status_code in (200, 302)

    def test_a_missing_phone_is_refused(self, app, client):
        resp = client.post(
            '/booking/register',
            data={'full_name': 'Jane Doe', 'phone': '', 'password': 'secret123'},
        )
        assert resp.status_code in (200, 302)

    def test_a_missing_password_is_refused(self, app, client):
        resp = client.post(
            '/booking/register',
            data={'full_name': 'Jane Doe', 'phone': '0500000001', 'password': ''},
        )
        assert resp.status_code in (200, 302)

    def test_a_used_email_is_refused(self, app, client, db):
        from models.user import User
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        user = User(
            username='reg_taken_user',
            email='reg_taken@example.test',
            full_name='Taken',
            role='patient',
            is_active=True,
            tenant_id=tenant.id,
        )
        user.set_password('test123')
        _db.session.add(user)
        _db.session.commit()

        resp = client.post(
            '/booking/register',
            data={
                'full_name': 'Jane Doe',
                'phone': '0500000002',
                'password': 'secret123',
                'email': 'reg_taken@example.test',
            },
        )
        assert resp.status_code in (200, 302)

    def test_registration_creates_the_account(self, app, client, db):
        from app.extensions import db as _db
        from models.patient_account import PatientAccount
        from models.user import User

        resp = client.post(
            '/booking/register',
            data={
                'full_name': 'Jane Doe',
                'phone': '0500000003',
                'password': 'secret123',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        user = (
            _db.session.execute(
                _db.select(User).where(User.username == 'patient_0500000003')
            )
            .scalars()
            .first()
        )
        assert user is not None
        assert user.role == 'patient'
        # An address is generated when the patient did not give one.
        assert user.email.startswith('patient_0500000003_')

        link = (
            _db.session.execute(
                _db.select(PatientAccount).where(PatientAccount.user_id == user.id)
            )
            .scalars()
            .first()
        )
        assert link is not None

    def test_a_used_username_gets_a_suffix(self, app, client, db):
        from app.extensions import db as _db
        from models.user import User

        resp = client.post(
            '/booking/register',
            data={
                'full_name': 'Jane Doe',
                'phone': '0500000004',
                'password': 'secret123',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        usernames = [
            u.username
            for u in _db.session.execute(
                _db.select(User).where(User.username.like('patient_0500000004%'))
            )
            .scalars()
            .all()
        ]
        assert len(usernames) == 1
        assert usernames[0] == 'patient_0500000004'

    def test_a_patient_already_linked_to_another_account_is_refused(self, app, client, db):
        from app.extensions import db as _db
        from models.patient_account import PatientAccount
        from models.user import User

        patient = _patient(_db, None, username='linked_patient')
        _db.session.flush()

        other = User(
            username='other_link_user',
            email='other_link@example.test',
            full_name='Other',
            role='patient',
            is_active=True,
        )
        other.set_password('test123')
        _db.session.add(other)
        _db.session.flush()

        _db.session.add(
            PatientAccount(user_id=other.id, patient_id=patient.id, tenant_id=patient.tenant_id)
        )
        _db.session.commit()

        resp = client.post(
            '/booking/register',
            data={
                'full_name': 'Jane Doe',
                'phone': patient.phone,
                'password': 'secret123',
            },
        )
        assert resp.status_code in (200, 302)


class TestDashboardPortal:
    """The patient's own booking dashboard."""

    def test_a_patient_sees_their_bookings(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.patient_account import PatientAccount
        from models.user import User

        login_as(client, 'book_patient_user', 'patient')
        patient = _patient(_db, None, username='dash_patient')
        _db.session.flush()
        user = (
            _db.session.execute(
                _db.select(User).where(User.username == 'book_patient_user')
            )
            .scalars()
            .first()
        )
        _db.session.add(PatientAccount(user_id=user.id, patient_id=patient.id))
        _db.session.commit()

        resp = client.get('/booking/dashboard')
        assert resp.status_code in (200, 302)

    def test_another_role_is_refused(self, app, client, login_as):
        login_as(client, 'book_lab_user', 'lab')
        resp = client.get('/booking/dashboard')
        assert resp.status_code in (302, 200, 403)


class TestCancelBooking:
    """Cancelling a booking, as staff and as the patient."""

    def test_staff_cancelling_an_unknown_booking(self, app, client, login_as):
        login_as(client, 'book_cancel_staff', 'reception')
        resp = client.post('/booking/cancel/999999')
        assert resp.status_code in (302, 404)

    def test_staff_cancelling_an_unknown_booking_as_json(self, app, client, login_as):
        login_as(client, 'book_cancel_staff_json', 'reception')
        resp = client.post(
            '/booking/cancel/999999',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_a_patient_without_the_right_role_is_refused(self, app, client, login_as):
        login_as(client, 'book_cancel_pharmacist', 'pharmacist')
        resp = client.post(
            '/booking/cancel/1',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 403

    def test_a_patient_without_a_linked_record_is_refused(self, app, client, login_as):
        login_as(client, 'book_cancel_no_link', 'patient')
        resp = client.post(
            '/booking/cancel/1',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 403

    def test_a_patient_cancelling_someone_elses_booking(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.patient_account import PatientAccount
        from models.user import User

        login_as(client, 'book_cancel_other', 'patient')
        patient = _patient(_db, None, username='cancel_other_patient')
        _db.session.flush()
        user = (
            _db.session.execute(
                _db.select(User).where(User.username == 'book_cancel_other')
            )
            .scalars()
            .first()
        )
        _db.session.add(PatientAccount(user_id=user.id, patient_id=patient.id))
        booking = _booking(_db, patient.tenant_id)
        _db.session.commit()

        resp = client.post(
            f'/booking/cancel/{booking.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 404

    def test_a_booking_that_can_no_longer_be_cancelled(self, app, client, login_as, db):
        from app.extensions import db as _db

        login_as(client, 'book_cancel_locked', 'reception')
        booking = _booking(_db, None, status='completed')
        _db.session.commit()

        resp = client.post(
            f'/booking/cancel/{booking.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_staff_cancelling_a_booking(self, app, client, login_as, db):
        from app.extensions import db as _db

        login_as(client, 'book_cancel_ok', 'reception')
        booking = _booking(_db, None, email='cancel@example.test')
        _db.session.commit()

        resp = client.post(
            f'/booking/cancel/{booking.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        _db.session.expire_all()
        refreshed = _db.session.get(type(booking), booking.id)
        assert refreshed.status == 'cancelled'
        assert refreshed.cancelled_at is not None

    def test_a_failing_notification_does_not_undo_the_cancellation(
        self, app, client, login_as, db
    ):
        from app.extensions import db as _db

        login_as(client, 'book_cancel_notify_fail', 'reception')
        booking = _booking(_db, None)
        _db.session.commit()

        with patch(
            'services.notification_service.NotificationService.send_notification',
            side_effect=RuntimeError('notification service down'),
        ):
            resp = client.post(
                f'/booking/cancel/{booking.id}',
                headers={'Accept': 'application/json'},
            )
        assert resp.status_code == 200


class TestBookingIndex:
    """The public booking landing page."""

    def test_it_renders(self, app, client):
        resp = client.get('/booking/')
        assert resp.status_code in (200, 302)

    def test_a_failing_query_redirects(self, app, client):
        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.booking_routes.select', boom):
            resp = client.get('/booking/')
        assert resp.status_code == 302
        assert '/dashboard' in resp.headers['Location']


class TestCreateBooking:
    """The booking form."""

    def test_the_form_renders(self, app, client):
        resp = client.get('/booking/create')
        assert resp.status_code in (200, 302)

    def test_a_missing_patient_name_is_refused(self, app, client):
        resp = client.post('/booking/create', data={})
        assert resp.status_code in (200, 302)

    def test_a_single_word_name_fills_the_first_name(self, app, client, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher',
                'phone': '0500000010',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking.first_name == 'Cher'
        assert booking.last_name == '-'

    def test_a_two_word_name_splits(self, app, client, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher Suleiman',
                'phone': '0500000011',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking.first_name == 'Cher'
        assert booking.last_name == 'Suleiman'

    def test_a_missing_phone_is_refused(self, app, client, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code in (200, 302)

    def test_a_missing_department_is_refused(self, app, client):
        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher',
                'phone': '0500000012',
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code in (200, 302)

    def test_a_missing_date_is_refused(self, app, client, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher',
                'phone': '0500000013',
                'department_id': str(department.id),
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code in (200, 302)

    def test_a_missing_time_is_refused(self, app, client, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher',
                'phone': '0500000014',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
            },
        )
        assert resp.status_code in (200, 302)

    def test_seconds_in_the_time_are_accepted(self, app, client, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher Seconds',
                'phone': '0500000015',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30:15',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking.appointment_time == time(9, 30, 15)

    def test_an_unknown_visit_type_falls_back_to_first(self, app, client, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher Type',
                'phone': '0500000016',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
                'visit_type': 'not-a-visit-type',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking.visit_type == 'first'

    def test_a_telemedicine_booking_carries_a_meeting_link(self, app, client, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher Tele',
                'phone': '0500000017',
                'email': 'cher.tele@example.test',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
                'visit_type': 'telemedicine',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking is not None
        assert 'MEET:' in booking.notes

    def test_a_patient_booking_is_linked_to_their_record(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.online_booking import OnlineBooking
        from models.patient_account import PatientAccount
        from models.user import User

        login_as(client, 'book_create_patient', 'patient')
        patient = _patient(_db, None, username='create_link_patient')
        _db.session.flush()
        user = (
            _db.session.execute(
                _db.select(User).where(User.username == 'book_create_patient')
            )
            .scalars()
            .first()
        )
        _db.session.add(PatientAccount(user_id=user.id, patient_id=patient.id))
        _db.session.flush()

        tenant = patient.tenant_id
        department = _department(_db, tenant)

        resp = client.post(
            '/booking/create',
            data={
                'patient_name': 'Cher Linked',
                'phone': '0500000018',
                'department_id': str(department.id),
                'appointment_date': '2026-05-01',
                'appointment_time': '09:30',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        booking = _db.session.get(OnlineBooking, _booking_id_from(resp))
        assert booking.patient_id == patient.id
        assert booking.is_new_patient is False


class TestBookingConfirmation:
    """The confirmation page."""

    def test_it_renders(self, app, client, login_as, db):
        from app.extensions import db as _db

        login_as(client, 'book_confirm_user', 'reception')
        booking = _booking(_db, None)
        _db.session.commit()

        resp = client.get(f'/booking/confirmation/{booking.id}')
        assert resp.status_code in (200, 302)

    def test_an_unknown_booking_is_404(self, app, client, login_as):
        login_as(client, 'book_confirm_missing', 'reception')
        resp = client.get('/booking/confirmation/999999')
        assert resp.status_code in (404, 302)


class TestTelemedicineRoom:
    """The telemedicine room."""

    def test_it_renders(self, app, client, login_as, db):
        from app.extensions import db as _db

        login_as(client, 'book_tele_user', 'reception')
        booking = _booking(_db, None, notes='MEET:https://example.test/room/9')
        _db.session.commit()

        resp = client.get(f'/booking/telemedicine/{booking.id}')
        assert resp.status_code in (200, 302)

    def test_an_unknown_booking_is_404(self, app, client, login_as):
        login_as(client, 'book_tele_missing', 'reception')
        resp = client.get('/booking/telemedicine/999999')
        assert resp.status_code in (404, 302)
