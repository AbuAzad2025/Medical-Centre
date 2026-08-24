"""Doctor routes coverage (diagnosis 32%, notes 38%, dashboard 52%)."""

import pytest


@pytest.fixture()
def dr(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='dr_cov', role='doctor')
    login_test_client(client, u, test_tenant)
    return client


class TestDoctorDashboard:
    def test_dashboard(self, dr):
        assert dr.get('/doctor/dashboard').status_code in (200, 302)

    def test_patient_queue_page(self, dr):
        resp = dr.get('/doctor/patient-queue', follow_redirects=True)
        assert resp.status_code in (200, 302)


class TestDoctorVisits:
    def test_visits_list(self, dr):
        assert dr.get('/doctor/visits').status_code in (200, 302)

    def test_appointments(self, dr):
        assert dr.get('/doctor/appointments').status_code in (200, 302)


class TestDoctorNotes:
    def test_notes_for_visit(self, dr):
        # Nonexistent visit → redirect or flash
        resp = dr.get('/doctor/notes/99999')
        assert resp.status_code in (200, 302, 404)


class TestDoctorPrescriptions:
    def test_prescription_nonexistent_visit(self, dr):
        resp = dr.get('/doctor/prescription/99999')
        assert resp.status_code in (200, 302, 404)
