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
from app.core.saas.legacy_adapter import LegacyEntitlementAdapter


HARD_LIMIT_KEYS = frozenset({"max_users", "max_patients", "api_calls_per_month"})
WARN_LIMIT_KEYS = frozenset({"storage_gb"})


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

        status_raw = getattr(tenant.status, "value", tenant.status)
        status_norm = str(status_raw or "").lower()
        if status_norm not in (TenantStatus.ACTIVE.value, TenantStatus.TRIAL.value):
            return False, f"tenant_status_{status_norm}"

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
            if LegacyEntitlementAdapter.is_entitled(tenant, capability_key):
                return True, ""
            return False, "capability_not_entitled"

        return True, ""

    @classmethod
    def get_effective_limits(cls, tenant_id: int, at: Optional[datetime] = None) -> dict[str, Optional[int]]:
        """Merged limits from active subscription package versions, legacy bundle fallback."""
        if at is None:
            at = datetime.now(timezone.utc)

        cache_key = ("limits", tenant_id)
        if _has_request_context():
            cache = getattr(g, "_entitlement_limit_cache", None)
            if cache is None:
                cache = {}
                g._entitlement_limit_cache = cache
            if cache_key in cache:
                return cache[cache_key]

        from app.core.saas.models import PackageVersionLimit, SubscriptionLine, SubscriptionLineStatus

        limits: dict[str, Optional[int]] = {}
        lines = (
            SubscriptionLine.query.filter_by(tenant_id=tenant_id)
            .filter(
                SubscriptionLine.status.in_(
                    [SubscriptionLineStatus.ACTIVE, SubscriptionLineStatus.SCHEDULED]
                ),
                SubscriptionLine.effective_from <= at,
            )
            .filter(
                (SubscriptionLine.effective_to.is_(None))
                | (SubscriptionLine.effective_to >= at)
            )
            .all()
        )
        for line in lines:
            version = line.package_version
            if version is None:
                continue
            for lim in version.limits:
                prev = limits.get(lim.limit_key)
                if prev is None or (lim.limit_value is not None and (prev is None or lim.limit_value > prev)):
                    limits[lim.limit_key] = lim.limit_value

        if not limits:
            limits = LegacyEntitlementAdapter.get_limits(tenant_id)

        if _has_request_context():
            g._entitlement_limit_cache[cache_key] = limits
        return limits

    @classmethod
    def get_limit(cls, tenant_id: int, limit_key: str, at: Optional[datetime] = None) -> Optional[int]:
        return cls.get_effective_limits(tenant_id, at=at).get(limit_key)

    @classmethod
    def check_limit(
        cls,
        tenant_id: int,
        limit_key: str,
        current_count: int,
        *,
        increment: int = 0,
    ) -> tuple[bool, str]:
        """Return (ok, reason). Hard limits block; storage_gb warns only (always ok)."""
        if limit_key in WARN_LIMIT_KEYS:
            return True, ""
        cap = cls.get_limit(tenant_id, limit_key)
        if cap is None:
            return True, ""
        if current_count + increment > cap:
            return False, f"limit_exceeded_{limit_key}"
        return True, ""

    @classmethod
    def check_usage_limits(cls, tenant_id: int) -> dict[str, bool]:
        """Snapshot of tenant usage vs limits (storage is warn-only, never False)."""
        from app.core.tenant.models import ResourceUsage

        latest = ResourceUsage.query.filter_by(tenant_id=tenant_id).order_by(
            ResourceUsage.recorded_at.desc()
        ).first()
        if not latest:
            latest = ResourceUsage.record_snapshot(tenant_id)

        limits = cls.get_effective_limits(tenant_id)
        users_cap = limits.get("max_users")
        patients_cap = limits.get("max_patients")
        storage_cap = limits.get("storage_gb")
        api_cap = limits.get("api_calls_per_month")

        users_ok = latest.total_users <= (users_cap if users_cap is not None else float("inf"))
        patients_ok = latest.total_patients <= (patients_cap if patients_cap is not None else float("inf"))
        storage_ok = True
        if storage_cap is not None:
            storage_gb = float(latest.storage_mb or 0) / 1024
            if storage_gb > storage_cap:
                storage_ok = True  # warn-only per S0-004 decision #22
        api_monthly = int(latest.api_calls_24h or 0) * 30
        api_ok = api_monthly <= (api_cap if api_cap is not None else float("inf"))

        return {
            "users_ok": users_ok,
            "patients_ok": patients_ok,
            "storage_ok": storage_ok,
            "api_ok": api_ok,
            "storage_warning": (
                storage_cap is not None
                and (float(latest.storage_mb or 0) / 1024) > storage_cap
            ),
        }

    @classmethod
    def assert_within_limit(
        cls,
        tenant_id: int,
        limit_key: str,
        current_count: int,
        *,
        increment: int = 0,
    ) -> None:
        ok, reason = cls.check_limit(tenant_id, limit_key, current_count, increment=increment)
        if not ok:
            raise EntitlementDeniedError(tenant_id, limit_key, reason)

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
