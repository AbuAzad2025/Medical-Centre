"""Render smoke for the mojibake-cleaned templates via the test client.

Every Arabic string that was corrupted by the double gettext expansion
(`_("_(" ... ")")") has been repaired to plain gettext form. These tests
render real pages and assert the rendered HTML carries no residual garbage.
"""

import types
import uuid

import pytest

from models.user import User


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )


@pytest.fixture
def ctx(app, db, test_tenant):
    tenant_id = test_tenant.id
    db_ = db

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=f'{role}_{uuid.uuid4().hex[:6]}',
            email=f'{uuid.uuid4().hex[:8]}@test.local',
            full_name=kw.get('full_name', 'Test User'),
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        u.set_password('test123')
        db_.session.add(u)
        db_.session.commit()
        return u

    return types.SimpleNamespace(db=db_, tenant_id=tenant_id, user=_user)


def _make_role(login_as, client, ctx, role):
    u = ctx.user(role=role)
    login_as(client, u.username, role)
    return u


class TestMojibakeEradicated:
    @pytest.mark.parametrize(
        'path',
        [
            '/super-admin/dashboard',
            '/super-admin/users',
            '/super-admin/roles',
            '/super-admin/reports',
            '/super-admin/permissions',
            '/super-admin/security-logs',
            '/super-admin/audit-trail',
            '/super-admin/system/maintenance',
            '/super-admin/system-config',
            '/super-admin/backup',
            '/super-admin/departments',
            '/super-admin/pricing',
            '/super-admin/services',
            '/manager/dashboard',
            '/manager/analytics',
            '/manager/reports',
            '/manager/reports-center',
            '/manager/staff',
            '/manager/budget',
            '/manager/pricing',
            '/manager/settlements',
            '/manager/settings',
            '/manager/departments',
            '/manager/exchange-rates',
        ],
    )
    def test_page_renders_clean(self, login_as, client, ctx, path):
        _make_role(
            login_as, client, ctx, 'super_admin' if path.startswith('/super-admin') else 'manager'
        )
        resp = client.get(path)
        assert resp.status_code in (200, 302), path
        if resp.status_code != 200:
            return
        text = resp.get_data(as_text=True)
        assert '_("_(' not in text, f'residual mojibake in {path}'
        assert '"_("' not in text, f'residual mojibake in {path}'

    @pytest.mark.parametrize(
        'path, role',
        [
            ('/reception/dashboard', 'reception'),
            ('/doctor/dashboard', 'doctor'),
            ('/nurse/dashboard', 'nurse'),
            ('/lab/dashboard', 'lab'),
            ('/radiology/dashboard', 'radiology'),
            ('/emergency/dashboard', 'emergency'),
            ('/accountant/dashboard', 'accountant'),
            ('/medication/dashboard', 'pharmacist'),
        ],
    )
    def test_role_dashboards_render_clean(self, login_as, client, ctx, path, role):
        _make_role(login_as, client, ctx, role)
        resp = client.get(path)
        assert resp.status_code == 200, path
        text = resp.get_data(as_text=True)
        assert '_("_(' not in text, f'residual mojibake in {path}'
        assert '"_("' not in text, f'residual mojibake in {path}'
