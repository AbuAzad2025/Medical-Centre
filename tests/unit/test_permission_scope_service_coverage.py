"""Coverage tests for services/permission_scope_service.py"""

from services.permission_scope_service import PermissionScopeService


class TestPermissionScopeService:
    def test_get_accessible_tenant_ids_no_context(self, app, db):
        result = PermissionScopeService.get_accessible_tenant_ids(999999)
        assert isinstance(result, list)

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
