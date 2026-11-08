"""Behavioural tests for routes.super_admin.branding (real login + CSRF)."""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.extensions import db
from models.branding import BrandingSettings, SystemTheme
from tests.tenant_context import ensure_test_user, login_test_client


@pytest.fixture
def admin_client(app, client, db, test_tenant):
    user = ensure_test_user(db, test_tenant, username='branding_admin', role='super_admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


def _csrf(client):
    resp = client.get('/super-admin/branding')
    if b'csrf_token' in resp.data:
        m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', resp.data)
        if m:
            return m.group(1).decode()
    m = re.search(rb'name="csrf-token"[^>]*content="([^"]+)"', resp.data)
    if m:
        return m.group(1).decode()
    return ''


class TestBrandingPage:
    def test_page_renders(self, admin_client):
        resp = admin_client.get('/super-admin/branding')
        assert resp.status_code == 200

    def test_anonymous_redirected(self, client):
        resp = client.get('/super-admin/branding')
        assert resp.status_code in (302, 401)

    def test_preview_renders_for_each_doc_type(self, admin_client):
        for doc_type in ('invoice', 'receipt', 'prescription', 'report', 'bogus'):
            resp = admin_client.get(f'/super-admin/branding/preview?doc_type={doc_type}')
            assert resp.status_code == 200, doc_type


class TestApplyTheme:
    def test_apply_existing_theme(self, admin_client, db):
        theme = db.session.execute(select(SystemTheme).limit(1)).scalars().first()
        if theme is None:
            theme = SystemTheme(
                name='Test Theme',
                name_ar='ثيم الاختبار',
                primary_color='#112233',
                secondary_color='#445566',
                accent_color='#778899',
                background_color='#ffffff',
                text_color='#000000',
                is_active=True,
            )
            db.session.add(theme)
            db.session.commit()
        token = _csrf(admin_client)
        resp = admin_client.post(
            f'/super-admin/branding/apply-theme/{theme.id}',
            data={'csrf_token': token},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
        body = resp.get_json()
        assert body['success'] is True
        assert body['colors']['primary_color'] == theme.primary_color

    def test_apply_missing_theme_404(self, admin_client):
        token = _csrf(admin_client)
        resp = admin_client.post(
            '/super-admin/branding/apply-theme/999999',
            data={'csrf_token': token},
        )
        assert resp.status_code == 404


class TestUpdateBranding:
    def test_update_persists_fields(self, admin_client, db):
        token = _csrf(admin_client)
        resp = admin_client.post(
            '/super-admin/branding/update',
            data={
                'csrf_token': token,
                'organization_name': 'مستشفى الاختبار',
                'organization_email': 'branding@test.local',
                'primary_color': '#123456',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 200)
        branding = db.session.execute(select(BrandingSettings).limit(1)).scalars().first()
        assert branding is not None
        assert branding.primary_color == '#123456'

    def test_update_rejects_bad_csrf(self, admin_client):
        resp = admin_client.post(
            '/super-admin/branding/update',
            data={'csrf_token': 'definitely-not-a-valid-token'},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 400)
