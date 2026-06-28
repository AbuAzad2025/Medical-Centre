"""Role assignment policy — clinical staff roles vs privileged operators."""
from __future__ import annotations

# Roles that may be assigned through admin user-management endpoints.
ASSIGNABLE_ROLES: frozenset[str] = frozenset({
    'super_admin',
    'owner',
    'admin',
    'manager',
    'doctor',
    'nurse',
    'reception',
    'accountant',
    'pharmacist',
    'lab',
    'radiology',
    'emergency',
    'technician',
    'user',
    'patient',
})

# Only these operators may create users or change role fields.
PRIVILEGED_ROLE_MANAGERS: frozenset[str] = frozenset({'super_admin', 'owner'})

# Elevated roles — only super_admin may grant (owner cannot create another owner).
ELEVATED_ROLES: frozenset[str] = frozenset({'super_admin', 'owner', 'admin'})


def normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    value = str(role).strip().lower()
    return value or None


def is_assignable_role(role: str | None) -> bool:
    normalized = normalize_role(role)
    return normalized in ASSIGNABLE_ROLES if normalized else False


def can_manage_user_roles(actor_role: str | None) -> bool:
    return normalize_role(actor_role) in PRIVILEGED_ROLE_MANAGERS


def actor_may_assign_role(actor_role: str | None, target_role: str | None) -> bool:
    """Return True when actor may set target_role on another user."""
    if not can_manage_user_roles(actor_role):
        return False
    if not is_assignable_role(target_role):
        return False
    actor = normalize_role(actor_role)
    target = normalize_role(target_role)
    if target in ELEVATED_ROLES and actor != 'super_admin':
        return False
    return True
