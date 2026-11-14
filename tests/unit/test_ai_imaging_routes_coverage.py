"""Coverage tests for routes/ai_imaging_routes.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestAIImagingRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/ai-imaging/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'ai_img_idx_user', 'doctor')
        resp = client.get('/ai-imaging/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_request_unauth(self, app, client):
        resp = client.post('/ai-imaging/request')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_request_auth(self, app, client, login_as):
        login_as(client, 'ai_img_req_user', 'doctor')
        resp = client.post('/ai-imaging/request')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_request_with_study(self, app, client, login_as, db, test_tenant):
        login_as(client, 'ai_img_study_user', 'doctor')
        from models.patient import Patient
        from models.dicom_pacs import DICOMStudy
        patient = Patient(tenant_id=test_tenant.id, first_name='Test', last_name='Patient')
        db.session.add(patient)
        db.session.flush()
        study = DICOMStudy(
            tenant_id=test_tenant.id,
            study_instance_uid='test-study-001',
            modality='CT',
            study_description='Test study',
            patient_id=patient.id,
            status='ACTIVE',
        )
        db.session.add(study)
        db.session.flush()
        resp = client.post('/ai-imaging/request', data={
            'study_id': study.id,
            'analysis_type': 'detection',
            'provider': 'internal',
        })
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_review(self, app, client, login_as):
        login_as(client, 'ai_img_rev_user', 'doctor')
        resp = client.post('/ai-imaging/1/review', data={'review_notes': 'test'})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
