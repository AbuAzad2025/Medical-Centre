"""Coverage tests for services.sso_service.py."""

from __future__ import annotations

import sys

from models.user import User
from services.sso_service import SSOService

pytest_plugins = ['tests._isolated_tenant']


def _make_user(db, tenant_id, username, role='doctor', is_active=True, department_id=None):
    u = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=is_active,
        tenant_id=tenant_id,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.flush()
    return u


class TestSSOService:
    def test_get_configs_empty(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = SSOService.get_configs()
        assert result == []

    def test_get_active_configs_empty(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = SSOService.get_active_configs()
        assert result == []

    def test_create_config(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        cfg = SSOService.create_config(
            name='Test LDAP',
            provider_type='ldap',
            server_url='ldap://example.com',
            base_dn='dc=example,dc=com',
            bind_dn='cn=admin,dc=example,dc=com',
            bind_password='secret',
            auto_create_user=True,
            default_role='user',
        )
        assert cfg is not None
        assert cfg.name == 'Test LDAP'
        assert cfg.provider_type == 'ldap'

    def test_create_config_commit_failure(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)

        def commit_false(*a, **k):
            return False

        sso_module = sys.modules['services.sso_service']
        monkeypatch.setattr(sso_module, 'safe_commit', commit_false)

        result = SSOService.create_config(
            name='Bad LDAP',
            provider_type='ldap',
        )
        assert result is None

    def test_get_config_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g
        from utils.tenant_query import TenantContextError

        bind_tenant_on_g(test_tenant, db_session=db.session)
        try:
            SSOService.get_config(99999)
            raise AssertionError('Should have raised TenantContextError')
        except TenantContextError:
            pass  # Expected - get_config doesn't catch TenantContextError

    def test_toggle_config_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = SSOService.toggle_config(config_id=99999)
        assert result is False

    def test_toggle_config_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from models import SSOConfiguration

        cfg = SSOConfiguration(
            tenant_id=test_tenant.id,
            name='Toggle Test',
            provider_type='ldap',
            server_url='ldap://example.com',
            base_dn='dc=example,dc=com',
            is_active=True,
        )
        db.session.add(cfg)
        db.session.flush()

        result = SSOService.toggle_config(config_id=cfg.id)
        assert result is True
        db.session.refresh(cfg)
        assert cfg.is_active is False

    def test_delete_config_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = SSOService.delete_config(config_id=99999)
        assert result is False

    def test_delete_config_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from models import SSOConfiguration

        cfg = SSOConfiguration(
            tenant_id=test_tenant.id,
            name='Delete Test',
            provider_type='ldap',
            server_url='ldap://example.com',
            base_dn='dc=example,dc=com',
            is_active=True,
        )
        db.session.add(cfg)
        db.session.flush()

        result = SSOService.delete_config(config_id=cfg.id)
        assert result is True
