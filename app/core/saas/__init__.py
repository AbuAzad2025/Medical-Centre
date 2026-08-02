"""SaaS core package."""

from app.core.saas.decorators import require_entitlement
from app.core.saas.exceptions import EntitlementDeniedError
from app.core.saas.legacy_adapter import LegacyEntitlementAdapter
from app.core.saas.lifecycle import ProvisioningError, TenantProvisioningService
from app.core.saas.migration import LegacyMigrationError, migrate_legacy_tenant_to_package
from app.core.saas.projection import EntitlementProjectionService
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.seed import SeedError, seed_packages_from_product_bundles

__all__ = [
    'EntitlementDeniedError',
    'EntitlementProjectionService',
    'EntitlementResolver',
    'LegacyEntitlementAdapter',
    'LegacyMigrationError',
    'ProvisioningError',
    'SeedError',
    'TenantProvisioningService',
    'migrate_legacy_tenant_to_package',
    'require_entitlement',
    'seed_packages_from_product_bundles',
]
