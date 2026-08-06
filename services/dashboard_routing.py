"""
Dashboard Routing Service — Strict Role + Bundle Scoped Routing
Maps user role to dashboard endpoint ONLY if the required module is active in tenant.
"""

from flask import current_app, g

from app.core.module.registry import MODULE_REGISTRY

ROLE_TO_MODULE_MAP = {
    'doctor': 'doctor',
    'pharmacist': 'pharmacy',
    'reception': 'reception',
    'receptionist': 'reception',
    'lab': 'lab',
    'lab_tech': 'lab',
    'radiology': 'radiology',
    'emergency': 'emergency',
    'nurse': 'nursing',
    'accountant': 'billing',
    'manager': 'reporting',
    'owner': 'owner',
    'super_admin': 'owner',
    'platform_owner': 'owner',
    'patient': 'portal',
    'technician': 'lab',
}

MODULE_TO_DASHBOARD_ENDPOINT = {
    'reception': 'reception.dashboard',
    'doctor': 'doctor.dashboard',
    'pharmacy': 'medication.dashboard',
    'lab': 'lab.dashboard',
    'radiology': 'radiology.dashboard',
    'emergency': 'emergency.dashboard',
    'nursing': 'nurse.dashboard',
    'billing': 'accountant.dashboard',
    'reporting': 'manager.dashboard',
    'owner': 'owner.owner_dashboard',
    'portal': 'portal.dashboard',
    'appointments': 'booking.dashboard',
}


def get_active_modules_for_current_tenant() -> set:
    """Get active modules for current tenant from g context or session."""
    # First try g context (set by middleware)
    enabled = getattr(g, 'enabled_modules', None)
    if enabled:
        return enabled

    # Fallback: try to get from session (useful during login before middleware runs)
    try:
        from flask import session

        tenant_id = session.get('tenant_id')
        if tenant_id:
            from app.core.module.validators import get_active_modules_for_tenant

            return get_active_modules_for_tenant(int(tenant_id))
    except Exception:
        pass

    return set()


def resolve_dashboard_for_user(user, tenant_id: int | None = None) -> str:
    """
    Resolve the correct dashboard endpoint for a user based on:
    1. User's role
    2. Tenant's active modules (from g.enabled_modules)

    Accepts either a user object (with .role attribute) or a role string.
    Returns the Flask endpoint name (e.g., 'doctor.dashboard')
    If role doesn't match active modules, returns 'main.package_restricted'
    """
    # Extract role from user object or use string directly
    if hasattr(user, 'role'):
        user_role = user.role
        if tenant_id is None:
            tenant_id = getattr(user, 'tenant_id', None)
    else:
        user_role = user

    if not user_role:
        return 'auth.login'

    # Platform owners (super_admin, owner, platform_owner) always go to owner dashboard
    if user_role in ('super_admin', 'owner', 'platform_owner'):
        return 'owner.owner_dashboard'

    # Patient always goes to portal
    if user_role == 'patient':
        return 'portal.dashboard'

    # Get required module for this role
    required_module = ROLE_TO_MODULE_MAP.get(user_role)
    if not required_module:
        current_app.logger.warning(f"Unknown role '{user_role}'")
        return 'main.package_restricted'

    # Check if required module is active in tenant
    active_modules = get_active_modules_for_current_tenant()

    if required_module in active_modules:
        endpoint = MODULE_TO_DASHBOARD_ENDPOINT.get(required_module)
        if endpoint:
            return endpoint

    # Role's required module is not active - access denied
    current_app.logger.info(
        f'Access denied: role={user_role} requires module={required_module} '
        f'but active_modules={active_modules}'
    )
    return 'main.package_restricted'


def get_package_restricted_context(user) -> dict:
    """Build context for package_restricted template."""
    role = getattr(user, 'role', 'unknown') if user else 'unknown'
    active_modules = get_active_modules_for_current_tenant()
    required_module = ROLE_TO_MODULE_MAP.get(role)

    required_module_ar = None
    if required_module:
        meta = MODULE_REGISTRY.get(required_module)
        if meta:
            required_module_ar = meta.name_ar

    return {
        'user_role': role,
        'active_modules': sorted(active_modules) if active_modules else [],
        'required_module': required_module,
        'required_module_ar': required_module_ar,
    }
