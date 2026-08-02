"""
Permission subsystem — centralized action-based permission service
"""

from app.core.permission.decorators import permission_required
from app.core.permission.service import PermissionService

__all__ = ['PermissionService', 'permission_required']
