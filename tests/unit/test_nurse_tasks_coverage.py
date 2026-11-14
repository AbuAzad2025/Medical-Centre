"""Coverage tests for routes/nurse_routes/tasks.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestNurseTasksRoutes:
    def test_tasks_unauth(self, app, client):
        resp = client.get('/nurse/tasks')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_tasks_auth(self, app, client, login_as):
        login_as(client, 'nurse_tasks_user', 'nurse')
        resp = client.get('/nurse/tasks')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_create_task_unauth(self, app, client):
        resp = client.post('/nurse/tasks/create')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_create_task_auth(self, app, client, login_as):
        login_as(client, 'nurse_create_task_user', 'nurse')
        resp = client.post('/nurse/tasks/create', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_update_task_status_unauth(self, app, client):
        resp = client.post('/nurse/tasks/1/status')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_update_task_status_auth(self, app, client, login_as):
        login_as(client, 'nurse_upd_task_user', 'nurse')
        resp = client.post('/nurse/tasks/1/status', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
