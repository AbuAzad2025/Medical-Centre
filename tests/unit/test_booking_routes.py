"""HTTP route tests for the online booking blueprint."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.extensions import db
from models.department import Department
from models.patient import Patient
from models.user import User


@pytest.fixture
def patient(app, test_tenant):
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    p = Patient(
        tenant_id=test_tenant.id,
        first_name=f'WaitPatient{suffix}',
        last_name='Test',
        phone=f'0507{suffix[-6:]}',
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def dept(app, test_tenant):
    tag = datetime.now(UTC).strftime('%H%M%S%f')
    d = Department(
        name=f'Booking-{tag}',
        name_ar='قسم الحجز',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db.session.add(d)
    db.session.commit()
    return d


@pytest.fixture
def doctor(app, test_tenant, dept):
    d = User(
        username=f'doc_book_{datetime.now(UTC).strftime("%H%M%S%f")}',
        email=f'doc_book_{datetime.now(UTC).strftime("%H%M%S%f")}@test.local',
        full_name='Doctor Booking',
        role='doctor',
        is_active=True,
        tenant_id=test_tenant.id,
        department_id=dept.id,
    )
    d.set_password('test123')
    db.session.add(d)
    db.session.commit()
    return d


def _register_patient(client, name='Test Patient', phone='0500000123', password='SecretPass123!'):
    return client.post(
        '/booking/register',
        data={
            'full_name': name,
            'phone': phone,
            'email': f'{phone}@booking.test',
            'password': password,
        },
        follow_redirects=False,
    )


class TestRegister:
    def test_register_get_renders(self, client):
        resp = client.get('/booking/register')
        assert resp.status_code == 200

    def test_register_success_redirects_to_dashboard(self, client):
        resp = _register_patient(client)
        assert resp.status_code == 302
        assert '/booking/dashboard' in resp.headers.get('Location', '')

    def test_register_missing_name(self, client):
        resp = _register_patient(client, name='')
        assert resp.status_code == 200  # re-renders with error flash

    def test_register_missing_phone(self, client):
        resp = client.post(
            '/booking/register',
            data={'full_name': 'Test', 'phone': '', 'password': 'X123456!'},
        )
        assert resp.status_code == 200

    def test_register_missing_password(self, client):
        resp = client.post(
            '/booking/register',
            data={'full_name': 'Test', 'phone': '0500000124', 'password': ''},
        )
        assert resp.status_code == 200


class TestBookingCreate:
    def test_create_booking_get_renders(self, client, dept, doctor):
        resp = client.get('/booking/create')
        assert resp.status_code == 200

    def test_create_booking_success(self, client, dept, doctor):
        dt = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
        resp = client.post(
            '/booking/create',
            data={
                'first_name': 'Booked',
                'last_name': 'Patient',
                'phone': '0500001111',
                'email': 'booked@test.local',
                'department_id': str(dept.id),
                'doctor_id': str(doctor.id),
                'appointment_date': dt,
                'appointment_time': '10:00',
                'visit_type': 'first',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert '/confirmation' in resp.headers.get('Location', '')

    def test_create_booking_missing_phone(self, client, dept):
        dt = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
        resp = client.post(
            '/booking/create',
            data={
                'first_name': 'Booked',
                'last_name': 'Patient',
                'department_id': str(dept.id),
                'appointment_date': dt,
                'appointment_time': '10:00',
            },
        )
        assert resp.status_code == 200  # re-renders with error flash

    def test_create_booking_missing_department(self, client):
        dt = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
        resp = client.post(
            '/booking/create',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0500003333',
                'appointment_date': dt,
                'appointment_time': '10:00',
            },
        )
        assert resp.status_code == 200

    def test_create_booking_missing_date(self, client, dept):
        resp = client.post(
            '/booking/create',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0500004444',
                'department_id': str(dept.id),
                'appointment_time': '10:00',
            },
        )
        assert resp.status_code == 200

    def test_create_booking_missing_time(self, client, dept):
        dt = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
        resp = client.post(
            '/booking/create',
            data={
                'first_name': 'A',
                'last_name': 'B',
                'phone': '0500005555',
                'department_id': str(dept.id),
                'appointment_date': dt,
            },
        )
        assert resp.status_code == 200


class TestBookingRead:
    def test_dashboard_renders_for_anonymous(self, client):
        resp = client.get('/booking/')
        assert resp.status_code in (200, 302)

    def test_dashboard_renders_for_registered(self, client):
        _register_patient(client, name='Dash Patient', phone='0500001111')
        resp = client.get('/booking/dashboard')
        assert resp.status_code in (200, 302)

    def test_available_doctors_api(self, client, dept, doctor):
        resp = client.get(f'/booking/api/available-doctors?department_id={dept.id}')
        assert resp.status_code == 200
        body = resp.get_json() if resp.is_json else {}
        assert body.get('success') is True
        assert any(d['id'] == doctor.id for d in body['doctors'])

    def test_available_times_api(self, client, dept, doctor):
        resp = client.get(f'/booking/api/available-times?doctor_id={doctor.id}&date={date.today()}')
        assert resp.status_code == 200
        body = resp.get_json() if resp.is_json else {}
        assert body.get('success') is True
        assert isinstance(body.get('available_times'), list)

    def test_available_times_missing_params(self, client):
        resp = client.get('/booking/api/available-times')
        assert resp.status_code == 400

    def test_smart_slots_api(self, client, dept, doctor):
        resp = client.get(f'/booking/api/smart-slots?doctor_id={doctor.id}&date={date.today()}')
        assert resp.status_code == 200
        body = resp.get_json() if resp.is_json else {}
        assert body.get('success') is True
        assert isinstance(body.get('available_times'), list)

    def test_smart_slots_missing_params(self, client):
        resp = client.get('/booking/api/smart-slots')
        assert resp.status_code == 400


class TestWaitlistLifecycle:
    def _login_reception(self, login_as, client):
        return login_as(
            client, f'wl_reception_{datetime.now(UTC).strftime("%H%M%S%f")}', 'reception'
        )

    def test_waitlist_add_list_and_convert(self, login_as, client, patient, doctor):
        self._login_reception(login_as, client)
        resp = client.post(
            '/booking/waitlist',
            json={'patient_id': patient.id, 'doctor_id': doctor.id, 'preferred_time': 'morning'},
        )
        assert resp.status_code == 201
        entry = resp.get_json()['data']
        assert entry['status'] == 'WAITING'
        assert entry['doctor_id'] == doctor.id

        resp = client.get('/booking/waitlist')
        body = resp.get_json()
        assert body['success'] is True
        assert any(item['id'] == entry['id'] for item in body['waitlist'])

        resp = client.post(
            f'/booking/waitlist/{entry["id"]}/convert',
            json={'starts_at': (datetime.now(UTC) + timedelta(days=3)).isoformat()},
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['appointment']['status'] == 'SCHEDULED'
        assert body['data']['status'] == 'CONVERTED'
        assert body['data']['converted_appointment_id'] is not None

    def test_waitlist_duplicate_rejected(self, login_as, client, patient):
        self._login_reception(login_as, client)
        first = client.post('/booking/waitlist', json={'patient_id': patient.id})
        assert first.status_code == 201
        dup = client.post('/booking/waitlist', json={'patient_id': patient.id})
        assert dup.status_code == 409
        assert dup.get_json()['success'] is False

    def test_waitlist_cancel(self, login_as, client, patient):
        self._login_reception(login_as, client)
        created = client.post('/booking/waitlist', json={'patient_id': patient.id})
        entry_id = created.get_json()['data']['id']
        resp = client.post(f'/booking/waitlist/{entry_id}/cancel')
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'CANCELLED'
        active = client.get('/booking/waitlist').get_json()['waitlist']
        assert all(item['id'] != entry_id for item in active)

    def test_waitlist_notify_marks_entry(self, login_as, client, patient):
        self._login_reception(login_as, client)
        created = client.post('/booking/waitlist', json={'patient_id': patient.id})
        entry_id = created.get_json()['data']['id']
        resp = client.post(f'/booking/waitlist/{entry_id}/notify')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['status'] == 'NOTIFIED'
        assert 'sms_queued' in body

    def test_waitlist_add_missing_patient_id(self, login_as, client):
        self._login_reception(login_as, client)
        resp = client.post('/booking/waitlist', json={})
        assert resp.status_code == 400

    def test_waitlist_add_unknown_patient(self, login_as, client):
        self._login_reception(login_as, client)
        resp = client.post('/booking/waitlist', json={'patient_id': 99999999})
        assert resp.status_code == 404

    def test_waitlist_entry_of_other_tenant_hidden(self, login_as, client, patient, test_tenant):
        """The service refuses an entry whose tenant does not match the caller."""
        self._login_reception(login_as, client)
        created = client.post('/booking/waitlist', json={'patient_id': patient.id})
        entry_id = created.get_json()['data']['id']
        from services import waitlist_service

        with pytest.raises(waitlist_service.WaitlistError) as excinfo:
            waitlist_service.cancel_waitlist_entry(entry_id, test_tenant.id + 999)
        assert excinfo.value.status == 404

    def test_reception_waitlist_add_and_remove(self, login_as, client, patient):
        login_as(client, f'wl_reception2_{datetime.now(UTC).strftime("%H%M%S%f")}', 'reception')
        resp = client.post(
            '/reception/appointments/waitlist',
            json={'patient_id': patient.id, 'preferred_time': 'evening'},
        )
        assert resp.status_code == 201
        entry_id = resp.get_json()['data']['id']
        listing = client.get('/reception/appointments/waitlist')
        assert listing.status_code == 200
        assert any(i['id'] == entry_id for i in listing.get_json()['waitlist'])
        removed = client.delete(f'/reception/appointments/waitlist/{entry_id}')
        assert removed.status_code == 200


class TestBookingFallback:
    def test_recurring_appointments_get(self, client):
        resp = client.get('/booking/recurring-appointments')
        assert resp.status_code in (200, 302)

    def test_waitlist_get(self, client):
        resp = client.get('/booking/waitlist')
        assert resp.status_code in (200, 302)

    def test_reminders_get(self, client):
        resp = client.get('/booking/appointments/reminders')
        assert resp.status_code in (200, 302)

    def test_no_shows_get(self, client):
        resp = client.get('/booking/no-shows')
        assert resp.status_code in (200, 302)
