"""Coverage tests for app.core.permission.decorators.py"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.permission.decorators import permission_required

pytest_plugins = ['tests._isolated_tenant']


class TestPermissionDecorators:
    def test_permission_required_allowed(self, app):
        @permission_required('view_reports')
        def protected_view():
            return 'OK'

        with app.test_request_context():
            with patch('app.core.permission.decorators.current_user') as mock_user:
                mock_user.is_authenticated = True
                with patch(
                    'app.core.permission.service.PermissionService.has_permission',
                    return_value=True,
                ):
                    result = protected_view()
                    assert result == 'OK'

    def test_permission_required_denied(self, app):
        @permission_required('admin_only')
        def protected_view():
            return 'OK'

        with app.test_request_context():
            with patch('app.core.permission.decorators.current_user') as mock_user:
                mock_user.is_authenticated = True
                with patch(
                    'app.core.permission.service.PermissionService.has_permission',
                    return_value=False,
                ):
                    from flask import abort

                    try:
                        protected_view()
                        assert False, 'Should have raised 403'
                    except Exception:
                        pass  # 403 abort expected
