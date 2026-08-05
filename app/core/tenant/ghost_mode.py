"""
Ghost Mode — Master Impersonation Middleware (platform owner only).

Allows a ``platform_owner`` (or ``super_admin``/``owner``) to impersonate any
user within any tenant for the lifetime of a single request, without the normal
tenant scoping. This is the "Master Impersonation" capability.

Security model
---------------
Impersonation is only honoured when ALL of the following hold:

1. The authenticated actor's role is in ``PLATFORM_OWNER_ROLES``.
2. The three impersonation headers are present:
     * ``X-Impersonate-Tenant-Id``
     * ``X-Impersonate-User-Id``
     * ``X-Impersonate-Timestamp``
     * ``X-Impersonate-Signature``
3. The HMAC-SHA256 signature (keyed with ``PLATFORM_OWNER_SECRET``) over
   ``<tenant_id>:<user_id>:<timestamp>`` is valid AND the timestamp is within
   the replay window.

When valid, the request context is rebound to the target tenant + user
(``g.tenant_id``, ``g.current_user``, Flask-Login ``g._login_user``), which
effectively bypasses Row-Level Security scoping for that request. Every
impersonated request is written to the ``AuditTrail`` table.
"""

import hashlib
import hmac
import json
import os
import time

from flask import current_app, g, request

from app.core.tenant.models import Tenant

# Header names (kept stable on purpose — clients sign against these).
HEADER_TENANT_ID = 'X-Impersonate-Tenant-Id'
HEADER_USER_ID = 'X-Impersonate-User-Id'
HEADER_TIMESTAMP = 'X-Impersonate-Timestamp'
HEADER_SIGNATURE = 'X-Impersonate-Signature'

# Roles permitted to use Ghost Mode.
PLATFORM_OWNER_ROLES = frozenset({'platform_owner', 'super_admin', 'owner'})

# Signed requests older than this are rejected (replay protection).
REPLAY_WINDOW_SECONDS = 300


def _get_secret() -> str | None:
    return current_app.config.get('PLATFORM_OWNER_SECRET') or os.environ.get(
        'PLATFORM_OWNER_SECRET'
    )


def _canonical_payload(tenant_id: str, user_id: str, timestamp: str) -> bytes:
    return f'{tenant_id}:{user_id}:{timestamp}'.encode()


def sign_impersonation(tenant_id, user_id, secret: str, timestamp: str | None = None):
    """Return ``(signature_hex, timestamp_str)`` for the given impersonation target."""
    if timestamp is None:
        timestamp = str(int(time.time()))
    payload = _canonical_payload(str(tenant_id), str(user_id), timestamp)
    signature = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    return signature, timestamp


def verify_ghost_signature(tenant_id, user_id, timestamp, signature) -> bool:
    """Validate an impersonation signature (key, shape, and replay window)."""
    secret = _get_secret()
    if not secret or not signature:
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > REPLAY_WINDOW_SECONDS:
        return False
    payload = _canonical_payload(str(tenant_id), str(user_id), str(timestamp))
    expected = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _impersonation_headers_present() -> bool:
    return bool(
        request.headers.get(HEADER_TENANT_ID)
        and request.headers.get(HEADER_USER_ID)
        and request.headers.get(HEADER_TIMESTAMP)
        and request.headers.get(HEADER_SIGNATURE)
    )


def _current_actor():
    from flask_login import current_user

    actor = getattr(g, 'current_user', None)
    if actor is not None:
        return actor
    try:
        if current_user.is_authenticated:
            # Return the REAL user object, not the LocalProxy. The proxy
            # re-resolves to ``g._login_user`` and would pick up the
            # impersonated target after we rebind context below.
            return current_user._get_current_object()
    except Exception:
        pass
    return None


def ghost_mode_middleware() -> None:
    """Flask before_request handler. Run AFTER ``set_tenant_context``."""
    # Only inspect the authenticated actor when an impersonation is actually
    # attempted. Touching current_user here on every request runs Flask-Login's
    # session-protection reload before the route's @login_required check, which
    # can mask strong-protection rejections (e.g. a missing session _id).
    if not _impersonation_headers_present():
        return
    actor = _current_actor()
    if actor is None or getattr(actor, 'role', None) not in PLATFORM_OWNER_ROLES:
        return

    tenant_id = request.headers.get(HEADER_TENANT_ID)
    user_id = request.headers.get(HEADER_USER_ID)
    timestamp = request.headers.get(HEADER_TIMESTAMP)
    signature = request.headers.get(HEADER_SIGNATURE)

    if not verify_ghost_signature(tenant_id, user_id, timestamp, signature):
        current_app.logger.warning(
            'Ghost Mode: rejected request with invalid signature (actor=%s)',
            getattr(actor, 'id', None),
        )
        return

    try:
        target_tenant_id = int(tenant_id)
        target_user_id = int(user_id)
    except (TypeError, ValueError):
        current_app.logger.warning('Ghost Mode: malformed tenant/user id')
        return

    from app.extensions import db
    from models.user import User

    target_user = db.session.get(User, target_user_id)
    target_tenant = db.session.get(Tenant, target_tenant_id)
    if target_user is None or target_tenant is None:
        current_app.logger.warning(
            'Ghost Mode: target not found tenant=%s user=%s',
            target_tenant_id,
            target_user_id,
        )
        return

    # Rebind request context to the impersonated tenant + user.
    # bind_g_tenant also sets the PostgreSQL RLS session variable.
    from app.core.tenant.middleware import bind_g_tenant

    bind_g_tenant(target_tenant)

    g.current_user = target_user
    g._login_user = target_user  # Flask-Login cache → current_user resolves to target
    g.ghost_mode = True
    g.ghost_actor_id = actor.id

    try:
        from app.core.module.validators import get_active_modules_for_tenant

        g.enabled_modules = get_active_modules_for_tenant(target_tenant.id)
    except Exception:
        g.enabled_modules = getattr(g, 'enabled_modules', set())

    _write_audit_trail(actor, target_tenant, target_user)


def _write_audit_trail(actor, target_tenant, target_user) -> None:
    """Best-effort audit log of an impersonated request."""
    try:
        from app.extensions import db
        from models.audit_trail import AuditTrail

        details = json.dumps(
            {
                'real_actor_id': actor.id,
                'real_actor_username': actor.username,
                'impersonated_user_id': target_user.id,
                'impersonated_username': target_user.username,
                'impersonated_tenant_id': target_tenant.id,
                'impersonated_tenant_name': target_tenant.name,
                'path': request.path,
                'method': request.method,
            },
            ensure_ascii=False,
        )
        entry = AuditTrail(
            tenant_id=target_tenant.id,
            user_id=target_user.id,
            entity_type='user',
            entity_id=target_user.id,
            action='IMPERSONATE',
            description=(
                f'Platform owner {actor.username} impersonated user '
                f'{target_user.username} in tenant {target_tenant.id}'
            ),
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            new_values=details,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:  # never break a request because of audit logging
        current_app.logger.exception('Ghost Mode: audit trail write failed: %s')
