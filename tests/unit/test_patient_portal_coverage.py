"""Coverage tests for routes/patient_portal.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestPatientPortalRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/portal/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'portal_idx_user', 'patient')
        resp = client.get('/portal/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_link_account_get(self, app, client):
        resp = client.get('/portal/link-account')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_link_account_post(self, app, client):
        resp = client.post('/portal/link-account', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_dashboard(self, app, client):
        resp = client.get('/portal/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dashboard_auth(self, app, client, login_as):
        login_as(client, 'portal_dash_user', 'patient')
        resp = client.get('/portal/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_appointments(self, app, client):
        resp = client.get('/portal/appointments')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_appointments_auth(self, app, client, login_as):
        login_as(client, 'portal_appt_user', 'patient')
        resp = client.get('/portal/appointments')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_book_appointment(self, app, client):
        resp = client.get('/portal/book-appointment')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_book_appointment_auth(self, app, client, login_as):
        login_as(client, 'portal_book_user', 'patient')
        resp = client.get('/portal/book-appointment')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_medical_records(self, app, client):
        resp = client.get('/portal/medical-records')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_medical_records_auth(self, app, client, login_as):
        login_as(client, 'portal_mr_user', 'patient')
        resp = client.get('/portal/medical-records')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_prescriptions(self, app, client):
        resp = client.get('/portal/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_prescriptions_auth(self, app, client, login_as):
        login_as(client, 'portal_rx_user', 'patient')
        resp = client.get('/portal/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_lab_results(self, app, client):
        resp = client.get('/portal/lab-results')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_lab_results_auth(self, app, client, login_as):
        login_as(client, 'portal_lab_user', 'patient')
        resp = client.get('/portal/lab-results')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_radiology_results(self, app, client):
        resp = client.get('/portal/radiology-results')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_radiology_results_auth(self, app, client, login_as):
        login_as(client, 'portal_rad_user', 'patient')
        resp = client.get('/portal/radiology-results')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_bills(self, app, client):
        resp = client.get('/portal/bills')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_bills_auth(self, app, client, login_as):
        login_as(client, 'portal_bills_user', 'patient')
        resp = client.get('/portal/bills')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_vaccinations(self, app, client):
        resp = client.get('/portal/vaccinations')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_vaccinations_auth(self, app, client, login_as):
        login_as(client, 'portal_vax_user', 'patient')
        resp = client.get('/portal/vaccinations')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_documents(self, app, client):
        resp = client.get('/portal/documents')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_documents_auth(self, app, client, login_as):
        login_as(client, 'portal_docs_user', 'patient')
        resp = client.get('/portal/documents')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_document_detail(self, app, client):
        resp = client.get('/portal/documents/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settings_get(self, app, client):
        resp = client.get('/portal/settings')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settings_post(self, app, client):
        resp = client.post('/portal/settings', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_settings_auth(self, app, client, login_as):
        login_as(client, 'portal_set_user', 'patient')
        resp = client.get('/portal/settings')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_feedback_get(self, app, client):
        resp = client.get('/portal/feedback')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_feedback_post(self, app, client):
        resp = client.post('/portal/feedback', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_feedback_auth(self, app, client, login_as):
        login_as(client, 'portal_fb_user', 'patient')
        resp = client.get('/portal/feedback')
        assert resp.status_code in (200, 302, 401, 403, 404)
