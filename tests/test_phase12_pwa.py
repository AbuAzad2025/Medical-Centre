"""Tests for phase 12 — PWA, mobile, kiosk (§25, §28)."""

from pathlib import Path


class TestPWAAssets:
    def test_unified_service_worker_exists(self):
        path = Path(__file__).parent.parent / 'static' / 'pwa' / 'sw.js'
        assert path.exists()
        text = path.read_text(encoding='utf-8')
        assert 'azad-med-pwa' in text
        assert '/pwa/offline' in text

    def test_mobile_css_touch_targets(self):
        css = (Path(__file__).parent.parent / 'static' / 'css' / 'mobile.css').read_text(encoding='utf-8')
        assert 'min-height: 48px' in css

    def test_touch_css_kiosk_targets(self):
        css = (Path(__file__).parent.parent / 'static' / 'css' / 'touch.css').read_text(encoding='utf-8')
        assert '48px' in css
        assert '[data-kiosk="true"]' in css


class TestPWARoutes:
    def test_manifest_route(self, client):
        resp = client.get('/pwa/manifest.webmanifest')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['display'] == 'standalone'
        assert data['icons']

    def test_offline_page(self, client):
        resp = client.get('/pwa/offline')
        assert resp.status_code == 200
        assert 'غير متصل' in resp.get_data(as_text=True)


class TestKioskCheckIn:
    def test_kiosk_page_loads(self, client):
        resp = client.get('/kiosk/check-in')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'تسجيل الوصول الذاتي' in text
        assert 'kiosk-key' in text

    def test_kiosk_api_rejects_empty_id(self, client):
        resp = client.post('/kiosk/api/check-in', json={'national_id': ''})
        assert resp.status_code == 400


class TestStaffShellPWA:
    def test_base_html_has_manifest_and_mobile_css(self, auth_client):
        resp = auth_client.get('/medication/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'manifest.webmanifest' in text
        assert 'mobile.css' in text
        assert 'pwa-install.js' in text

    def test_mobile_bottom_nav_for_reception(self, app, client, test_tenant):
        from app.extensions import db
        from models.user import User
        u = User.query.filter_by(username='reception_p12').first()
        if not u:
            u = User(
                username='reception_p12',
                email='reception_p12@test.local',
                full_name='استقبال P12',
                role='reception',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            db.session.add(u)
            db.session.commit()
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': 'reception_p12',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        resp = client.get('/reception/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'mobile-bottom-nav' in text
