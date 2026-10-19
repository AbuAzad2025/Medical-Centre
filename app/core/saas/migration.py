"""
Legacy-to-SaaS migration utilities — S0-006

Provides controlled migration of legacy tenants (which only have a
product_profile_code and/or SubscriptionPlan) onto the new Package/SubscriptionLine
model without data loss.
"""

from sqlalchemy import func, select

from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import SubscriptionLine
from app.extensions import db
from utils.db_safety import safe_commit


class LegacyMigrationError(Exception):
    """Raised when a legacy migration precondition is violated."""


def migrate_legacy_tenant_to_package(
    tenant_id: int,
    package_version_id: int,
    billing_type: str,
    *,
    performed_by_user_id: int | None = None,
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

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        raise LegacyMigrationError(f'Tenant {tenant_id} not found.')

    # The whole migration acts for one tenant, so that tenant has to be the one
    # bound. subscription_lines and the grants, history and audit rows it writes
    # all carry a WITH CHECK policy naming the bound tenant, and the
    # precondition below reads those same rows - so an unbound or
    # differently-bound caller both fails the write and miscounts the
    # precondition, which is how "tenant already has active lines" could never
    # be reported.
    from app.core.tenant.middleware import bound_tenant_scope

    with bound_tenant_scope(tenant):
        return _migrate_in_scope(tenant, package_version_id, billing_type, performed_by_user_id)


def _migrate_in_scope(tenant, package_version_id: int, billing_type: str, performed_by_user_id):
    """Do the migration with *tenant* bound as the RLS subject."""
    from app.core.tenant.models import Tenant  # noqa: F401  (re-exported for callers)

    active_lines = db.session.execute(
        select(func.count())
        .select_from(SubscriptionLine)
        .filter_by(tenant_id=tenant.id, status='active')
    ).scalar()
    if active_lines > 0:
        raise LegacyMigrationError(f'Tenant {tenant.id} already has active subscription lines.')

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
    safe_commit(db.session, error_message='database commit failed', reraise=True)

    from app.core.saas.projection import EntitlementProjectionService

    EntitlementProjectionService.calculate(tenant.id)
    TenantProvisioningService._ensure_modules_for_package(
        tenant.id,
        TenantProvisioningService._require_available_package_version(package_version_id),
    )
    TenantProvisioningService._record_history(
        tenant.id,
        'MIGRATE_TO_PACKAGE',
        notes=f'Migrated to package_version={package_version_id}, billing={billing_type}',
        performed_by_user_id=performed_by_user_id,
    )
    TenantProvisioningService._audit(
        tenant.id,
        'MIGRATE_TO_PACKAGE',
        entity_type='tenant',
        entity_id=tenant.id,
        details=f'package_version={package_version_id}, billing={billing_type}',
        user_id=performed_by_user_id,
    )
    # The commit expired the row's attributes. Load them while the tenant is
    # still bound - once the scope restores, the caller's first attribute read
    # refreshes the row under a different tenant, and SQLAlchemy reports the
    # row that is present as deleted.
    db.session.refresh(line)
    return line
