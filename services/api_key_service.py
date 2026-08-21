"""
ApiKeyService — create, validate, and revoke API keys.
Also provides the /api/* authentication + per-endpoint rate limiting middleware.
"""

import logging
from datetime import UTC, datetime

from flask import g, jsonify, request
from sqlalchemy import select

from app.core.rate_limiter import RateLimiter
from app.extensions import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)

# Default per-endpoint-class rate limits for /api/* (requests, window seconds).
# Applied to session-authenticated users; API-key requests use their own limits.
DEFAULT_API_RATE_LIMITS = {
    'search': (60, 60),      # /api/search — frequent but light
    'dashboard': (120, 60),  # /api/dashboard — polling dashboards
    'user': (30, 60),        # /api/user — preferences updates
    'lab': (120, 60),        # /api/lab — worklist refresh
    'radiology': (120, 60),  # /api/radiology — worklist refresh
    'fhir': (60, 60),        # /api/fhir — standards-based integrations
    '_default': (90, 60),
}


class ApiKeyService:
    @staticmethod
    def create_key(
        tenant_id: int,
        name: str,
        scopes: str = 'read',
        created_by: int | None = None,
        expires_at=None,
        rate_limit_max: int = 100,
        rate_limit_window: int = 60,
    ) -> tuple['object | None', str | None]:
        """Create an API key. Returns (record, raw_key) — raw key shown once."""
        from models.api_key import ApiKey

        if not name or not name.strip():
            return None, 'اسم المفتاح مطلوب'

        raw, prefix, _ = ApiKey.generate_raw_key()
        from models.api_key import _hash_key

        key = ApiKey(
            tenant_id=tenant_id,
            name=name.strip(),
            key_prefix=prefix,
            key_hash=_hash_key(raw),
            scopes=scopes,
            created_by=created_by,
            expires_at=expires_at,
            rate_limit_max=max(1, int(rate_limit_max)),
            rate_limit_window=max(1, int(rate_limit_window)),
        )
        db.session.add(key)
        safe_commit(db.session, error_message='Failed to create API key', reraise=True)
        return key, raw

    @staticmethod
    def authenticate(raw_key: str) -> 'object | None':
        """Validate a presented raw key; returns the ApiKey record or None.

        Updates last_used_at on success. Tenant context is NOT bound here —
        callers must bind via bind_g_tenant after loading the key's tenant.
        """
        from models.api_key import ApiKey, _hash_key

        if not raw_key:
            return None
        rec = (
            db.session.execute(select(ApiKey).filter_by(key_hash=_hash_key(raw_key)))
            .scalars()
            .first()
        )
        if rec is None or not rec.is_valid():
            return None
        try:
            rec.last_used_at = datetime.now(UTC)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            db.session.rollback()
        return rec

    @staticmethod
    def revoke_key(key_id: int) -> bool:
        from models.api_key import ApiKey

        key = db.session.get(ApiKey, key_id)
        if not key:
            return False
        key.revoke()
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return True

    @staticmethod
    def list_keys(tenant_id: int | None = None) -> list:
        from models.api_key import ApiKey

        query = select(ApiKey).order_by(ApiKey.created_at.desc())
        if tenant_id is not None:
            query = query.filter_by(tenant_id=tenant_id)
        return list(db.session.execute(query).scalars().all())


def api_middleware() -> None:
    """before_request hook for all /api/* paths.

    1. If an X-API-Key header is present → authenticate machine request,
       apply the KEY's own rate limit, and stash g.api_key for scopes.
    2. Otherwise → apply default per-endpoint-class rate limit keyed by user/IP.
    """
    path = request.path or ''
    if not path.startswith('/api/'):
        return
    # Health endpoints are exempt (used by load balancers)
    if path.startswith('/api/health'):
        return

    raw_key = request.headers.get('X-API-Key') or ''

    if raw_key:
        rec = ApiKeyService.authenticate(raw_key)
        if rec is None:
            g.api_key = None
            response = jsonify(success=False, error='Invalid or expired API key'), 401
            raise _ApiAuthError(response)

        limiter = RateLimiter(
            max_requests=rec.rate_limit_max,
            window_seconds=rec.rate_limit_window,
            namespace='apikey',
        )
        allowed = limiter.is_allowed(f'key{rec.id}')
        g.api_key = rec
        if not allowed:
            resp = jsonify(
                success=False,
                error='API key rate limit exceeded',
                retry_after=rec.rate_limit_window,
            )
            resp.headers['Retry-After'] = str(rec.rate_limit_window)
            raise _ApiAuthError((resp, 429))
        return

    # Session-authenticated default limiting
    max_reqs, window = DEFAULT_API_RATE_LIMITS.get('_default')
    for prefix, limits in DEFAULT_API_RATE_LIMITS.items():
        if prefix != '_default' and path.startswith(f'/api/{prefix}'):
            max_reqs, window = limits
            break

    identity = getattr(getattr(g, '_login_user', None), 'id', None) or request.remote_addr or 'anon'
    limiter = RateLimiter(max_requests=max_reqs, window_seconds=window, namespace='apirl')
    if not limiter.is_allowed(f'{identity}:{request.endpoint}'):
        resp = jsonify(
            success=False, error='Too many requests', retry_after=window
        )
        resp.headers['Retry-After'] = str(window)
        raise _ApiAuthError((resp, 429))


class _ApiAuthError(Exception):
    def __init__(self, payload):
        self.payload = payload
        super().__init__('api auth/rate-limit short-circuit')
