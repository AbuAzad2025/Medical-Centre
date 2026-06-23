"""Tests for Gate 6b — manager sidebar + nav audit (G-142, G-143, G-147)."""

from __future__ import annotations

from flask import url_for

from app.shared.manager_nav_registry import REQUIRED_MANAGER_ENDPOINTS, resolve_manager_nav_sections
from app.shared.nav_audit import audit_manager_nav_coverage, audit_nav_link_endpoints, manager_nav_endpoints
from app.shared.nav_resolver import resolve_nav_for_user


class TestManagerNavRegistry:
    def test_required_endpoints_count(self):
        assert len(REQUIRED_MANAGER_ENDPOINTS) >= 14

    def test_all_required_endpoints_resolve(self, app):
        with app.app_context():
            for ep in REQUIRED_MANAGER_ENDPOINTS:
                if ep == 'manager.drill_down':
                    url_for(ep, report_type='visits')
                else:
                    url_for(ep)

    def test_manager_nav_sections_have_three_groups(self, app):
        with app.app_context():
            sections = resolve_manager_nav_sections()
            titles = {s.title_ar for s in sections}
            assert 'مالية' in titles
            assert 'موارد بشرية' in titles
            assert 'تقارير' in titles
            total_items = sum(len(s.items) for s in sections)
            assert total_items == len(REQUIRED_MANAGER_ENDPOINTS)


class TestNavResolverManager:
    def test_manager_role_gets_manager_sections(self, app, manager_user, test_tenant):
        with app.app_context():
            from flask import g
            g.current_tenant = test_tenant
            g.enabled_modules = {'reporting', 'billing', 'reception', 'appointments', 'inventory'}
            sections = resolve_nav_for_user(manager_user)
            titles = [s.title_ar for s in sections]
            assert 'مالية' in titles
            assert 'تقارير' in titles

    def test_super_admin_nav_has_no_owner_endpoints(self, app, client, test_tenant):
        from models.user import User
        from app.core.rate_limiter import _shared_store

        u = User.query.filter_by(username='sa_gate6b').first()
        if not u:
            u = User(
                username='sa_gate6b',
                email='sa_gate6b@test.local',
                full_name='سوبر أدمن',
                role='super_admin',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            from app.extensions import db
            db.session.add(u)
            db.session.commit()
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': 'sa_gate6b',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        with app.app_context():
            from flask_login import login_user
            sections = resolve_nav_for_user(u)
            for section in sections:
                for item in section.items:
                    assert '/owner/' not in (item.href or '')


class TestManagerNavPages:
    """G-147 — sidebar targets return 200 for manager."""

    def _paths(self, app):
        with app.app_context():
            paths = []
            for section in resolve_manager_nav_sections():
                for item in section.items:
                    paths.append(item.href)
            return paths

    def test_manager_sidebar_pages_not_404(self, manager_auth_client, app):
        paths = self._paths(app)
        assert len(paths) >= 14
        for path in paths:
            resp = manager_auth_client.get(path, follow_redirects=True)
            assert resp.status_code == 200, f'{path} -> {resp.status_code}'


class TestNavAudit:
    def test_audit_nav_links_zero_broken(self, app):
        with app.app_context():
            broken = audit_nav_link_endpoints(app)
            assert broken == [], f'broken nav links: {broken}'

    def test_manager_route_coverage(self, app):
        with app.app_context():
            missing = audit_manager_nav_coverage(app)
            assert missing == [], f'manager routes not in nav: {missing}'

    def test_manager_nav_endpoints_match_registry(self):
        assert manager_nav_endpoints() == set(REQUIRED_MANAGER_ENDPOINTS)


class TestMobileNavManager:
    def test_manager_mobile_nav_analytics_endpoint(self, app):
        with app.app_context():
            url_for('manager.analytics')
