"""
Permission subsystem — centralized action-based permission service
"""
from app.core.permission.service import PermissionService
from app.core.permission.decorators import permission_required

__all__ = ["PermissionService", "permission_required"]
