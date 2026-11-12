"""Coverage tests for services.permission_scope_service.py."""

from __future__ import annotations

from models.user import User
from services.permission_scope_service import PermissionScopeService

pytest_plugins = ['tests._isolated_tenant']


_NOT_PROVIDED = object()


def _make_user(
    db,
    tenant_id,
    username,
    role='doctor',
    is_active=True,
    department_id=None,
    tenant_id_col=_NOT_PROVIDED,
):
    actual_tenant_id = tenant_id if tenant_id_col is _NOT_PROVIDED else tenant_id_col
    u = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=is_active,
        tenant_id=actual_tenant_id,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.flush()
    return u


class TestPermissionScopeService:
    def test_get_accessible_tenant_ids_user_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = PermissionScopeService.get_accessible_tenant_ids(user_id=99999)
        assert result == []

    def test_get_accessible_tenant_ids_regular_user(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        user = _make_user(db, test_tenant.id, 'reg_user', role='doctor')
        user.is_super_admin = False

        result = PermissionScopeService.get_accessible_tenant_ids(user_id=user.id)
        assert result == [test_tenant.id]

    def test_get_accessible_module_names_user_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = PermissionScopeService.get_accessible_module_names(user_id=99999)
        assert result == []

    def test_get_accessible_module_names_super_admin(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        user = _make_user(db, test_tenant.id, 'super_mod_user')
        user.is_super_admin = True

        result = PermissionScopeService.get_accessible_module_names(user_id=user.id)
        assert isinstance(result, list)
        assert 'reception' in result
        assert 'doctor' in result
        assert 'manager' in result

    def test_get_accessible_module_names_no_tenant_id(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        user = _make_user(db, test_tenant.id, 'super_no_tenant')
        user.is_super_admin = True

        result = PermissionScopeService.get_accessible_module_names(user_id=user.id)
        assert isinstance(result, list)
