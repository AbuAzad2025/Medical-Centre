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


def enforce_medical_privacy_guard(user) -> None:
    """Raise 403 if user is platform_owner/super_admin trying to access medical data.

    Call this from medical routes or as a before_request. Raises an exception
    that the caller should translate to abort(403).
    """
    role = getattr(user, 'role', None) or getattr(user, 'username', '')
    if role not in ('platform_owner', 'super_admin', 'owner'):
        return

    # platform_owner and super_admin in platform context must be blocked
    # super_admin who is tenant-scoped (has tenant_id matching a real tenant)
    # and is acting within that tenant is NOT blocked for that tenant's data
    # But global platform owners (tenant_id is platform tenant or None) are blocked
    from flask import request, g

    # If request is not available (e.g., in tests with direct call), use g
    path = ''
    try:
        path = request.path if request else ''
    except Exception:
        path = getattr(g, '_medical_guard_path', '') or ''

    # If no path can be determined, assume medical and block to be safe when guard is called explicitly
    if not path:
        abort(403, description='403 Forbidden - Access Denied (Medical Privacy Guard)')

    if is_medical_endpoint(path):
        abort(403, description='403 Forbidden - Access Denied (Medical Privacy Guard)')
