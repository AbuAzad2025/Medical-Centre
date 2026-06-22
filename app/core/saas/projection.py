"""
EntitlementProjectionService — S0-005

Materializes the effective tenant capability set from all active entitlement
sources (subscription lines, enterprise contracts, tenant overrides, feature flags)
into the read-only `tenant_entitlements` projection table.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, Set

from app.extensions import db
from app.core.saas.models import (
    EntitlementGrant,
    EnterpriseContract,
    OverrideType,
    SubscriptionLine,
    SubscriptionLineStatus,
    TenantEntitlement,
    TenantOverride,
)


class EntitlementProjectionService:
    """Build and persist the effective capability projection for a tenant."""

    CALCULATION_VERSION = 1

    @classmethod
    def calculate(cls, tenant_id: int, as_of: Optional[datetime] = None) -> Set[str]:
        """Recompute tenant_entitlements and return the effective capability set."""
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        # Several grant tables store naive UTC datetimes; normalize for comparison.
        as_of_naive = as_of.replace(tzinfo=None)

        capabilities: dict[str, tuple[datetime, Optional[datetime]]] = {}
        sources: dict[str, list[str]] = defaultdict(list)

        cls._apply_subscription_lines(tenant_id, as_of, as_of_naive, capabilities, sources)
        cls._apply_enterprise_contracts(tenant_id, as_of_naive, capabilities, sources)
        cls._apply_tenant_overrides(tenant_id, as_of_naive, capabilities, sources)
        cls._apply_feature_flag_grants(tenant_id, as_of_naive, capabilities, sources)

        # Materialize projection
        TenantEntitlement.query.filter_by(tenant_id=tenant_id).delete(
            synchronize_session=False
        )

        for capability_key, (effective_from, effective_to) in capabilities.items():
            projection = TenantEntitlement(
                tenant_id=tenant_id,
                capability_key=capability_key,
                module_name=None,
                effective_from=effective_from or as_of,
                effective_to=effective_to,
                is_effective=True,
                source_summary=", ".join(sources.get(capability_key, [])),
                calculated_at=as_of,
                calculation_version=cls.CALCULATION_VERSION,
            )
            db.session.add(projection)

        db.session.commit()
        return set(capabilities.keys())

    @classmethod
    def _active_lines(cls, tenant_id: int, as_of: datetime):
        return (
            SubscriptionLine.query.filter(
                SubscriptionLine.tenant_id == tenant_id,
                SubscriptionLine.status.in_(
                    [SubscriptionLineStatus.ACTIVE, SubscriptionLineStatus.SCHEDULED]
                ),
                SubscriptionLine.effective_from <= as_of,
            )
            .filter(
                (SubscriptionLine.effective_to.is_(None))
                | (SubscriptionLine.effective_to >= as_of)
            )
            .all()
        )

    @classmethod
    def _apply_subscription_lines(cls, tenant_id, as_of, as_of_naive, capabilities, sources):
        for line in cls._active_lines(tenant_id, as_of):
            for grant in line.entitlement_grants:
                if grant.effective_from > as_of_naive:
                    continue
                if grant.effective_to and grant.effective_to < as_of_naive:
                    continue
                capabilities[grant.capability_key] = (
                    grant.effective_from,
                    grant.effective_to,
                )
                sources[grant.capability_key].append(f"subscription_line:{line.id}")

    @classmethod
    def _apply_enterprise_contracts(cls, tenant_id, as_of_naive, capabilities, sources):
        today = as_of_naive.date()
        contracts = EnterpriseContract.query.filter(
            EnterpriseContract.tenant_id == tenant_id,
            EnterpriseContract.start_date <= today,
            EnterpriseContract.end_date >= today,
        ).all()
        for contract in contracts:
            for entitlement in contract.entitlements:
                if entitlement.revoked_at:
                    continue
                if entitlement.effective_from > as_of_naive:
                    continue
                if entitlement.effective_to and entitlement.effective_to < as_of_naive:
                    continue
                capabilities[entitlement.capability_key] = (
                    entitlement.effective_from,
                    entitlement.effective_to,
                )
                sources[entitlement.capability_key].append(
                    f"enterprise_contract:{contract.id}"
                )

    @classmethod
    def _apply_tenant_overrides(cls, tenant_id, as_of_naive, capabilities, sources):
        overrides = TenantOverride.query.filter(
            TenantOverride.tenant_id == tenant_id,
            TenantOverride.effective_from <= as_of_naive,
        ).filter(
            (TenantOverride.effective_to.is_(None)) | (TenantOverride.effective_to >= as_of_naive)
        ).all()
        for override in overrides:
            if override.override_type == OverrideType.GRANT:
                capabilities[override.capability_key] = (
                    override.effective_from,
                    override.effective_to,
                )
                sources[override.capability_key].append(
                    f"tenant_override:{override.id}"
                )
            elif override.override_type == OverrideType.REVOKE:
                capabilities.pop(override.capability_key, None)
                sources.pop(override.capability_key, None)

    @classmethod
    def _apply_feature_flag_grants(cls, tenant_id, as_of_naive, capabilities, sources):
        flag_grants = (
            EntitlementGrant.query.filter(
                EntitlementGrant.tenant_id == tenant_id,
                EntitlementGrant.tenant_feature_flag_id.isnot(None),
                EntitlementGrant.effective_from <= as_of_naive,
            )
            .filter(
                (EntitlementGrant.effective_to.is_(None))
                | (EntitlementGrant.effective_to >= as_of_naive)
            )
            .all()
        )
        for grant in flag_grants:
            flag = grant.tenant_feature_flag
            if not flag or not flag.is_enabled:
                continue
            capabilities[grant.capability_key] = (
                grant.effective_from,
                grant.effective_to,
            )
            sources[grant.capability_key].append(f"feature_flag:{flag.id}")
