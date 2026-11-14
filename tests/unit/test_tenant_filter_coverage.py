"""Coverage tests for app/shared/tenant_filter.py"""


class TestTenantFilter:
    def test_is_saas_mode(self):
        from app.shared.tenant_filter import _is_saas_mode

        result = _is_saas_mode()
        assert isinstance(result, bool)

    def test_skip_table(self):
        from app.shared.tenant_filter import _skip_table
        from models.user import User

        result = _skip_table(User)
        assert isinstance(result, bool)

    def test_model_has_tenant_column(self):
        from app.shared.tenant_filter import _model_has_tenant_column
        from models.user import User

        result = _model_has_tenant_column(User)
        assert isinstance(result, bool)

    def test_model_has_soft_delete(self):
        from app.shared.tenant_filter import _model_has_soft_delete
        from models.user import User

        result = _model_has_soft_delete(User)
        assert isinstance(result, bool)

    def test_invalidate_module_scope(self):
        from app.shared.tenant_filter import invalidate_module_scope

        invalidate_module_scope()

    def test_current_tenant_id_no_context(self):
        from app.shared.tenant_filter import _current_tenant_id

        result = _current_tenant_id()
        assert result is None or isinstance(result, int)

    def test_is_tenant_bypass(self):
        from app.shared.tenant_filter import _is_tenant_bypass

        result = _is_tenant_bypass()
        assert isinstance(result, bool)
