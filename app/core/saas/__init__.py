"""SaaS core package."""

from app.core.saas.resolver import EntitlementResolver
from app.core.saas.decorators import require_entitlement
from app.core.saas.exceptions import EntitlementDeniedError
from app.core.saas.projection import EntitlementProjectionService
from app.core.saas.lifecycle import TenantProvisioningService, ProvisioningError
from app.core.saas.seed import seed_packages_from_product_bundles, SeedError
from app.core.saas.migration import migrate_legacy_tenant_to_package, LegacyMigrationError

__all__ = [
    "EntitlementResolver",
    "require_entitlement",
    "EntitlementDeniedError",
    "EntitlementProjectionService",
    "TenantProvisioningService",
    "ProvisioningError",
    "seed_packages_from_product_bundles",
    "SeedError",
    "migrate_legacy_tenant_to_package",
    "LegacyMigrationError",
]
