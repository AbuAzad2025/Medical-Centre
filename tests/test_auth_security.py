"""P0 security: profile self-service must not permit role escalation."""

import pytest

from app_factory import db as _db
from models.user import User


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


class TestProfileRoleEscalationBlocked:
    def test_profile_ignores_role_spoof_payload(self, auth_client, test_user, test_tenant):
        original_role = test_user.role
        resp = auth_client.post('/auth/profile', data={
            'full_name': test_user.full_name,
            'email': test_user.email or 'pharmacist@test.local',
            'phone': test_user.phone or '',
            'department_id': '',
            'role': 'super_admin',
        }, follow_redirects=False)

        assert resp.status_code in (200, 302)
        _db.session.refresh(test_user)
        assert test_user.role == original_role
        assert test_user.role != 'super_admin'

    def test_profile_post_without_role_keeps_role(self, auth_client, test_user):
        before = test_user.role
        page = auth_client.get('/auth/profile')
        assert page.status_code == 200
        assert b'name="role"' not in page.data

        auth_client.post('/auth/profile', data={
            'full_name': 'صيدلي محدّث',
            'email': test_user.email or 'pharmacist@test.local',
            'phone': '0500000001',
            'department_id': '',
        }, follow_redirects=True)

        _db.session.refresh(test_user)
        assert test_user.role == before
        assert test_user.full_name == 'صيدلي محدّث'


class TestPrivilegedUserManagement:
    def test_manager_cannot_open_user_create(self, manager_auth_client):
        resp = manager_auth_client.get('/super-admin/users/create', follow_redirects=False)
        assert resp.status_code == 403

    def test_pharmacist_cannot_open_user_edit(self, auth_client, test_user):
        resp = auth_client.get(f'/super-admin/users/{test_user.id}/edit', follow_redirects=False)
        assert resp.status_code in (302, 403)
