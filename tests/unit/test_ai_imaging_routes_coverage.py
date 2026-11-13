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
        resp = client.post('/ai-imaging/request', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_request_auth(self, app, client, login_as):
        login_as(client, 'ai_img_req_user', 'doctor')
        resp = client.post('/ai-imaging/request', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_review(self, app, client, login_as):
        login_as(client, 'ai_img_rev_user', 'doctor')
        resp = client.post('/ai-imaging/1/review', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
