"""
Legacy-to-SaaS migration utilities — S0-006

Provides controlled migration of legacy tenants (which only have a
product_profile_code and/or SubscriptionPlan) onto the new Package/SubscriptionLine
model without data loss.
"""

from typing import Optional

from app.extensions import db
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import SubscriptionLine


class LegacyMigrationError(Exception):
    """Raised when a legacy migration precondition is violated."""


def migrate_legacy_tenant_to_package(
    tenant_id: int,
    package_version_id: int,
    billing_type: str,
    *,
    performed_by_user_id: Optional[int] = None,
) -> SubscriptionLine:
    """Attach a new base SubscriptionLine to an existing legacy tenant.

    Preconditions:
      - Tenant exists.
      - Tenant has no active subscription lines (to keep migration explicit and reversible).
      - Target PackageVersion is available.

    Postconditions:
      - Tenant status becomes ACTIVE (or TRIAL if version has trial_days).
      - Base SubscriptionLine created.
      - Entitlement grants and projection materialized.
      - TenantModule records activated for included modules.
      - Audit and history records created.
    """
    from app.core.tenant.models import Tenant

    tenant = Tenant.query.get(tenant_id)
    if not tenant:
        raise LegacyMigrationError(f"Tenant {tenant_id} not found.")

    active_lines = SubscriptionLine.query.filter_by(
        tenant_id=tenant_id, status="active"
    ).count()
    if active_lines > 0:
        raise LegacyMigrationError(
            f"Tenant {tenant_id} already has active subscription lines."
        )

    line = TenantProvisioningService._create_base_line(
        tenant.id,
        TenantProvisioningService._require_available_package_version(package_version_id),
        billing_type,
    )
    db.session.add(line)
    db.session.flush()

    TenantProvisioningService._create_line_grants(
        line,
        TenantProvisioningService._require_available_package_version(package_version_id),
    )
    db.session.commit()

    from app.core.saas.projection import EntitlementProjectionService

    EntitlementProjectionService.calculate(tenant.id)
    TenantProvisioningService._ensure_modules_for_package(
        tenant.id,
        TenantProvisioningService._require_available_package_version(package_version_id),
    )
    TenantProvisioningService._record_history(
        tenant.id,
        "MIGRATE_TO_PACKAGE",
        notes=f"Migrated to package_version={package_version_id}, billing={billing_type}",
        performed_by_user_id=performed_by_user_id,
    )
    TenantProvisioningService._audit(
        tenant.id,
        "MIGRATE_TO_PACKAGE",
        entity_type="tenant",
        entity_id=tenant.id,
        details=f"package_version={package_version_id}, billing={billing_type}",
        user_id=performed_by_user_id,
    )
    return line
