"""Coverage tests for services/permission_scope_service.py"""

from services.permission_scope_service import PermissionScopeService


class TestPermissionScopeService:
    def test_get_accessible_tenant_ids_no_context(self, app, db):
        result = PermissionScopeService.get_accessible_tenant_ids(999999)
        assert isinstance(result, list)

    def test_get_accessible_tenant_ids_with_context(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g
        from models.user import User

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            # Create a user
            user = User(
                tenant_id=test_tenant.id,
                username='perm_scope_user',
                email='perm_scope@test.com',
                password_hash='hash',
                full_name='Perm Scope User',
                role='doctor',
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()
            result = PermissionScopeService.get_accessible_tenant_ids(user.id)
            assert isinstance(result, list)
            assert test_tenant.id in result

    def test_get_accessible_module_names_no_context(self, app, db):
        result = PermissionScopeService.get_accessible_module_names(999999)
        assert isinstance(result, list)

    def test_get_accessible_module_names_with_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = PermissionScopeService.get_accessible_module_names(
                999999, tenant_id=test_tenant.id
            )
        assert isinstance(result, list)

    def test_get_accessible_module_names_with_user(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g
        from models.user import User
        from app.core.tenant.models import TenantFeatureFlag

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            # Create feature flag
            flag = TenantFeatureFlag(
                tenant_id=test_tenant.id,
                module='reception',
                is_active=True,
            )
            db.session.add(flag)
            db.session.flush()

            user = User(
                tenant_id=test_tenant.id,
                username='perm_scope_user2',
                email='perm_scope2@test.com',
                password_hash='hash',
                full_name='Perm Scope User 2',
                role='doctor',
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()

            result = PermissionScopeService.get_accessible_module_names(user.id, tenant_id=test_tenant.id)
            assert isinstance(result, list)
