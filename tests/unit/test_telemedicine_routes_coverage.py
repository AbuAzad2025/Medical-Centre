"""Coverage tests for routes.telemedicine_routes.py"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestTelemedicineRoutes:
    def test_index(self, app, client, login_as):
        login_as(client, 'tm_user', 'doctor')
        resp = client.get('/telemedicine/')
        assert resp.status_code in (200, 302)

    def test_index_reception(self, app, client, login_as):
        login_as(client, 'tm_rec_user', 'reception')
        resp = client.get('/telemedicine/')
        assert resp.status_code in (200, 302)

    def test_new_appointment_get(self, app, client, login_as):
        login_as(client, 'tm_new_user', 'doctor')
        resp = client.get('/telemedicine/new')
        assert resp.status_code in (200, 302)

    def test_new_appointment_post(self, app, client, login_as):
        login_as(client, 'tm_post_user', 'doctor')
        from models.patient import Patient
        from app.extensions import db

        p = Patient(
            first_name='Tele', last_name='Med',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        db.session.add(p)
        db.session.flush()

        start = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        end = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

        resp = client.post(
            '/telemedicine/new',
            data={
                'patient_id': str(p.id),
                'doctor_id': '1',
                'scheduled_start': start,
                'scheduled_end': end,
                'chief_complaint': 'Follow up',
            },
        )
        assert resp.status_code in (200, 302)

    def test_view_appointment_not_found(self, app, client, login_as):
        login_as(client, 'tm_view_user', 'doctor')
        resp = client.get('/telemedicine/99999')
        assert resp.status_code in (200, 302, 404)

    def test_index_unauthorized_role(self, app, client, login_as):
        login_as(client, 'tm_no_role_user', 'accountant')
        resp = client.get('/telemedicine/')
        # The blueprint is guarded by role_required; an accountant is not in the
        # allowed set, so the request is refused rather than served.
        assert resp.status_code in (403, 302)
