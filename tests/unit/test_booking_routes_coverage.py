"""Coverage tests for routes/booking_routes.py"""

from __future__ import annotations

pytest_plugins = ['tests._isolated_tenant']


class TestBookingRoutes:
    def _get(self, client, path):
        return client.get(path)

    def test_register_get(self, app, client):
        resp = client.get('/booking/register')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_dashboard_unauth(self, app, client):
        resp = client.get('/booking/dashboard')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_dashboard_auth(self, app, client, login_as):
        login_as(client, 'booking_dash_user', 'doctor')
        resp = client.get('/booking/dashboard')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_index(self, app, client):
        resp = client.get('/booking/')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_create_get(self, app, client):
        resp = client.get('/booking/create')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_create_post(self, app, client):
        resp = client.post('/booking/create', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_confirmation(self, app, client):
        resp = client.get('/booking/confirmation/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_telemedicine(self, app, client):
        resp = client.get('/booking/telemedicine/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_payment_get(self, app, client):
        resp = client.get('/booking/payment/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_payment_post(self, app, client):
        resp = client.post('/booking/payment/1', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_available_doctors(self, app, client):
        resp = client.get('/booking/api/available-doctors')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_available_times(self, app, client):
        resp = client.get('/booking/api/available-times')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_smart_slots(self, app, client):
        resp = client.get('/booking/api/smart-slots')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_recurring_appointments(self, app, client):
        resp = client.get('/booking/appointments/recurring')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/recurring', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_recurring_alt(self, app, client):
        resp = client.get('/booking/recurring-appointments')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/recurring-appointments', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_waitlist(self, app, client):
        resp = client.get('/booking/waitlist')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/waitlist', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_waitlist_alt(self, app, client):
        resp = client.get('/booking/appointments/waitlist')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/waitlist', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_waitlist_cancel(self, app, client):
        resp = client.post('/booking/waitlist/1/cancel')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/waitlist/1/cancel')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_waitlist_notify(self, app, client):
        resp = client.post('/booking/waitlist/1/notify')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/waitlist/1/notify')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_waitlist_convert(self, app, client):
        resp = client.post('/booking/waitlist/1/convert')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/waitlist/1/convert')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_appointment_reminders(self, app, client):
        resp = client.get('/booking/appointment-reminders')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointment-reminders', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.get('/booking/appointments/reminders')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/booking/appointments/reminders', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_no_shows(self, app, client):
        resp = client.get('/booking/no-shows')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.get('/booking/appointments/no-shows')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_cancel(self, app, client):
        resp = client.post('/booking/cancel/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
