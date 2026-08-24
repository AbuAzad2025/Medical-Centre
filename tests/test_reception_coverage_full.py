"""Reception visits + queue full coverage (41-62% → target 95%)."""

import pytest


@pytest.fixture()
def rc(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='vis_cov', role='reception')
    login_test_client(client, u, test_tenant)
    return client


class TestVisitsList:
    def test_visits_page(self, rc):
        assert rc.get('/reception/visits').status_code == 200

    def test_visits_with_search(self, rc):
        assert rc.get('/reception/visits?search=test').status_code == 200

    def test_visits_pagination(self, rc):
        assert rc.get('/reception/visits?page=1&per_page=10').status_code == 200

    def test_export_visits(self, rc):
        resp = rc.get('/reception/export/visits')
        assert resp.status_code in (200, 302)


class TestQueueManagement:
    def test_queue_page(self, rc):
        assert rc.get('/reception/queue').status_code == 200

    def test_add_patient_form_get(self, rc):
        resp = rc.get('/reception/queue/add-patient')
        assert resp.status_code in (200, 302)

    def test_call_next_empty_queue(self, rc):
        resp = rc.get('/reception/queue/call-next/99999')
        assert resp.status_code in (200, 302)

    def test_waiting_display(self, client):
        assert client.get('/reception/display/waiting').status_code in (200, 302)


class TestDashboard:
    def test_reception_dashboard(self, rc):
        assert rc.get('/reception/dashboard').status_code == 200

    def test_appointments_list(self, rc):
        assert rc.get('/reception/appointments').status_code == 200
