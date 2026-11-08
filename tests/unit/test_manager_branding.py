"""Behavioural tests for routes.manager.branding (manager role + CSRF)."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from models.branding import BrandingSettings
from tests.tenant_context import ensure_test_user, login_test_client


@pytest.fixture
def manager_client(app, client, db, test_tenant):
    user = ensure_test_user(db, test_tenant, username='mgr_branding_admin', role='manager')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


def _csrf(client):
    resp = client.get('/manager/branding')
    if b'csrf_token' in resp.data:
        m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', resp.data)
        if m:
            return m.group(1).decode()
    m = re.search(rb'name="csrf-token"[^>]*content="([^"]+)"', resp.data)
    if m:
        return m.group(1).decode()
    return ''


class TestManagerBranding:
    def test_page_renders(self, manager_client):
        resp = manager_client.get('/manager/branding')
        assert resp.status_code == 200

    def test_preview_renders_for_each_doc_type(self, manager_client):
        for doc_type in ('invoice', 'receipt', 'prescription', 'report', 'bogus'):
            resp = manager_client.get(f'/manager/branding/preview?doc_type={doc_type}')
            assert resp.status_code == 200, doc_type

    def test_update_persists_fields(self, manager_client, db):
        token = _csrf(manager_client)
        resp = manager_client.post(
            '/manager/branding',
            data={
                'csrf_token': token,
                'organization_name': 'مركز اختبار المدير',
                'organization_email': 'mgr-branding@test.local',
                'primary_color': '#1a2b3c',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 200)
        branding = db.session.execute(select(BrandingSettings).limit(1)).scalars().first()
        assert branding is not None
        assert branding.primary_color == '#1a2b3c'

    def test_update_rejects_bad_csrf(self, manager_client):
        resp = manager_client.post(
            '/manager/branding',
            data={'csrf_token': 'definitely-not-a-token'},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 400)

    def test_anonymous_redirected(self, client):
        resp = client.get('/manager/branding')
        assert resp.status_code in (302, 401)
