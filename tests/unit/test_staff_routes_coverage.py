"""Coverage tests for routes.manager.staff.py"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestStaffRoutes:
    def test_unit_control(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_unit', 'manager')
        resp = client.get('/manager/unit-control')
        assert resp.status_code in (200, 302)

    def test_unit_toggle_unknown_module(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_toggle', 'manager')
        resp = client.post(
            '/manager/api/units/toggle',
            json={'module_name': 'nonexistent_module'},
        )
        assert resp.status_code == 400

    def test_user_management(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_user_mgmt', 'manager')
        resp = client.get('/manager/user-management')
        assert resp.status_code in (200, 302)

    def test_staff_schedule_get(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_sched', 'manager')
        resp = client.get('/manager/staff/schedule')
        assert resp.status_code in (200, 302)

    def test_staff_schedule_post_missing_fields(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_sched_post', 'manager')
        resp = client.post(
            '/manager/staff/schedule',
            data={},
        )
        assert resp.status_code in (200, 302)

    def test_staff_absence_get(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_absence', 'manager')
        resp = client.get('/manager/staff/absence')
        assert resp.status_code in (200, 302)

    def test_staff_absence_post_missing_fields(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_absence_post', 'manager')
        resp = client.post(
            '/manager/staff/absence',
            data={},
        )
        assert resp.status_code in (200, 302)

    def test_staff_capacity(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_cap', 'manager')
        resp = client.get('/manager/staff/capacity')
        assert resp.status_code in (200, 302)

    def test_staff_list(self, app, client, test_tenant, login_as):
        login_as(client, 'mgr_staff_list', 'manager')
        resp = client.get('/manager/staff')
        assert resp.status_code in (200, 302)
