"""
EntitlementResolver — S0-004 Combined Access Contract

Entitlement ≠ Authorization. This resolver answers only:
"Does the tenant currently have an effective grant for this capability?"

It does NOT check user roles, branch scope, resource ownership, or API scopes.
Those remain the responsibility of the existing permission/ownership layers.
"""

from datetime import datetime, timezone
from typing import Optional

from flask import g
from flask_login import current_user

from app.extensions import db
from app.core.saas.exceptions import EntitlementDeniedError


class EntitlementResolver:
    """Resolve whether a tenant is entitled to a capability."""

    @classmethod
    def is_entitled(
        cls,
        tenant_id: int,
        capability_key: str,
        at: Optional[datetime] = None,
        audit: bool = True,
    ) -> bool:
        """Return True if tenant has an active, effective entitlement for capability_key."""
        if at is None:
            at = datetime.now(timezone.utc)

        from app.core.tenant.models import Tenant

        tenant = Tenant.query.get(tenant_id)
        tenant_status = tenant.status if tenant else None

        # Request-local memoization: resolve once per request per (tenant, status, capability)
        cache_key = ("entitlement", tenant_id, capability_key, tenant_status)
        if _has_request_context():
            cache = getattr(g, "_entitlement_cache", None)
            if cache is None:
                cache = {}
                g._entitlement_cache = cache
            if cache_key in cache:
                return cache[cache_key]

        result, reason = cls._evaluate(tenant, capability_key, at)

        if _has_request_context():
            g._entitlement_cache[cache_key] = result

        if audit and not result:
            cls._audit_denial(tenant_id, capability_key, reason)

        return result

    @classmethod
    def assert_entitled(
        cls,
        tenant_id: int,
        capability_key: str,
        at: Optional[datetime] = None,
    ) -> None:
        """Raise EntitlementDeniedError if tenant is not entitled."""
        from app.core.tenant.models import Tenant

        tenant = Tenant.query.get(tenant_id)
        if not cls.is_entitled(tenant_id, capability_key, at=at, audit=True):
            _, reason = cls._evaluate(tenant, capability_key, at or datetime.now(timezone.utc))
            raise EntitlementDeniedError(tenant_id, capability_key, reason)

    @classmethod
    def _evaluate(
        cls,
        tenant: Optional,
        capability_key: str,
        at: datetime,
    ) -> tuple[bool, str]:
        from app.core.saas.models import TenantEntitlement
        from app.core.tenant.models import TenantStatus

        if tenant is None:
            return False, "tenant_not_found"

        if tenant.status not in (TenantStatus.ACTIVE, TenantStatus.TRIAL):
            return False, f"tenant_status_{tenant.status.value}"

        if not tenant.is_active_and_paid():
            return False, "subscription_expired"

        projection = (
            TenantEntitlement.query.filter_by(
                tenant_id=tenant.id,
                capability_key=capability_key,
                is_effective=True,
            )
            .filter(TenantEntitlement.effective_from <= at)
            .filter(
                (TenantEntitlement.effective_to.is_(None))
                | (TenantEntitlement.effective_to >= at)
            )
            .first()
        )

        if projection is None:
            return False, "capability_not_entitled"

        return True, ""

    @classmethod
    def _audit_denial(cls, tenant_id: int, capability_key: str, reason: str) -> None:
        """Log denied entitlement attempts to PlatformAuditLog.

        Uses a request-local deduplication set to avoid flooding the audit log
        when templates check the same capability repeatedly.
        """
        if _has_request_context():
            seen = getattr(g, "_entitlement_audit_seen", None)
            if seen is None:
                seen = set()
                g._entitlement_audit_seen = seen
            key = (tenant_id, capability_key)
            if key in seen:
                return
            seen.add(key)

        try:
            from app.core.tenant.models import PlatformAuditLog

            log = PlatformAuditLog(
                user_id=getattr(current_user, "id", None) if _has_request_context() else None,
                tenant_id=tenant_id,
                action="ENTITLEMENT_DENIED",
                entity_type="capability",
                entity_id=None,
                details=f"capability={capability_key}, reason={reason}",
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()


def _has_request_context() -> bool:
    try:
        from flask import has_request_context
        return has_request_context()
    except Exception:
        return False
