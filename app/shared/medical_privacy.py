"""Medical Privacy Guard — strict separation between platform and tenant clinical data.

Platform owners (platform_owner, super_admin when acting globally) must NEVER
access tenant medical records. Permitted scope: tenant provisioning, billing,
telemetry, health, package configs.

Any attempt to access a medical endpoint must return 403 Forbidden (Medical Privacy Guard).
"""

from flask import abort

# Medical endpoints are all tenant clinical routes. This list is intentionally
# explicit to avoid accidental leakage via new routes. Add new clinical
# blueprints here as they are created.
_MEDICAL_PREFIXES = (
    '/doctor/',
    '/lab/',
    '/radiology/',
    '/emergency/',
    '/nurse/',
    '/pharmacy/',
    '/medication/',
    '/pharmacist/',
    '/patient/',
    '/visit/',
    '/prescription/',
    '/patients/',
    '/visits/',
    '/invoices/',
    '/doctor/patient-details',
    '/doctor/medical-history',
    '/lab/requests',
    '/lab/results',
    '/radiology/requests',
    '/accountant/patient',  # accountant has financial view, not clinical notes, but treat as medical
)

_MEDICAL_ENDPOINT_SUBSTRINGS = (
    'patient',
    'visit',
    'prescription',
    'lab_result',
    'radiology_result',
    'medical_history',
    'clinical_note',
    'diagnosis',
)

# Endpoints that platform owners ARE allowed to access (even though they contain tenant_id)
_ALLOWED_FOR_PLATFORM = (
    '/owner/',
    '/super-admin/',
    '/api/billing/',
    '/health',
    '/__health',
    '/auth/',
    '/t/',  # tenant resolution is allowed, but medical data still blocked
)


def is_medical_endpoint(path: str) -> bool:
    """Return True if the path is a medical endpoint that must be guarded."""
    if not path:
        return False
    # Explicit allowlist first
    for allowed in _ALLOWED_FOR_PLATFORM:
        if path.startswith(allowed) and not any(
            med in path for med in ('/patient', '/visit', '/prescription', '/lab', '/radiology')
        ):
            # If path is exactly an allowed platform path, not medical
            if (
                path.startswith('/owner/')
                or path.startswith('/super-admin/')
                or path.startswith('/api/billing/')
            ):
                return False
    # Check medical prefixes
    for prefix in _MEDICAL_PREFIXES:
        if path.startswith(prefix):
            return True
    # Fallback: check substrings in endpoint name (for url_for endpoint checks)
    low = path.lower()
    for substr in _MEDICAL_ENDPOINT_SUBSTRINGS:
        if substr in low and (
            'owner' not in low and 'super-admin' not in low and 'billing' not in low
        ):
            # But ensure not a platform billing endpoint
            return True
    return False


def _has_active_assumption(user, tenant_id) -> bool:
    """True when *user* holds a live, audited assumption for *tenant_id*.

    This is the "explicit clinical context" of MC-005: a time-bound, reasoned,
    revocable record created through the owner API, not a role check. Everything
    that can make it true is checked here — the user id, the tenant in scope, the
    active flag, the expiry and the revocation — because the guard below is the
    last thing between an administrative role and a patient's record.
    """
    if user is None or tenant_id is None:
        return False
    uid = getattr(user, 'id', None)
    if uid is None:
        return False
    try:
        from app.core.tenant.assumption_service import PlatformAssumptionService

        return bool(PlatformAssumptionService.has_valid_assumption(int(uid), int(tenant_id)))
    except Exception:
        # Fail closed: an unreachable or erroring assumption service is not a
        # clinical context.
        return False


def enforce_medical_privacy_guard(user) -> None:
    """Zero-trust guard for clinical PHI: an administrative role gets in only
    through an explicit, audited tenant assumption.

    ``platform_owner``, ``super_admin`` and ``owner`` are refused on every
    medical endpoint *unless* they hold a live assumption for the tenant in
    scope. The previous rule refused them unconditionally, which contradicted
    its own comment two lines up ("super_admin who is tenant-scoped ... and is
    acting within that tenant is NOT blocked for that tenant's data") and made
    the whole MC-005 assumption mechanism unreachable: the assumption could be
    created, audited and valid, and the request still answered 403.

    Roles outside that set are not this guard's business — they are authorised by
    the permission system and the tenant boundary.
    """
    role = getattr(user, 'role', None) or getattr(user, 'username', '')
    if role not in ('platform_owner', 'super_admin', 'owner'):
        return

    from flask import g, request

    # If request is not available (e.g., in tests with direct call), use g
    path = ''
    try:
        path = request.path if request else ''
    except Exception:
        path = getattr(g, '_medical_guard_path', '') or ''

    # If no path can be determined, assume medical and block to be safe when guard is called explicitly
    if not path:
        abort(403, description='403 Forbidden - Access Denied (Medical Privacy Guard)')

    if not is_medical_endpoint(path):
        return

    if _has_active_assumption(user, g.get('tenant_id')):
        return

    abort(403, description='403 Forbidden - Access Denied (Medical Privacy Guard)')
