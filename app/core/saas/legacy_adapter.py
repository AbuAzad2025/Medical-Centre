"""
LegacyEntitlementAdapter — bridges ProductBundle / TenantModule to S0-004 contract.

Used as a controlled fallback while tenants migrate from product_profile_code
bundles to PackageVersion subscription lines. Same capability vocabulary as
EntitlementResolver; does not check subscription payment state (caller handles).
"""

from __future__ import annotations

import json
from typing import Optional

from app.core.module.registry import MODULE_REGISTRY


class LegacyEntitlementAdapter:
    """Map legacy bundle/module data to capability keys and usage limits."""

    @classmethod
    def is_entitled(cls, tenant, capability_key: str) -> bool:
        if tenant is None:
            return False
        # Cross-check: the capability's owning module must be in the tenant's bundle
        if not cls._bundle_allows_capability(tenant, capability_key):
            return False
        for module_name in cls._active_module_names(tenant.id, tenant):
            meta = MODULE_REGISTRY.get(module_name)
            if meta and capability_key in meta.capabilities:
                return True
        return False

    @classmethod
    def _bundle_allows_capability(cls, tenant, capability_key: str) -> bool:
        """Return False if the tenant's product bundle excludes the capability's module."""
        # Determine which module owns this capability
        module_name = None
        for name, meta in MODULE_REGISTRY.items():
            if capability_key in meta.capabilities:
                module_name = name
                break
        if module_name is None:
            return True  # Unknown capability — don't block

        profile_code = getattr(tenant, "product_profile_code", None)
        if not profile_code:
            return True  # No profile — don't block

        from app.core.tenant.models import get_bundle_for_profile, _PRODUCT_PROFILE_SEED

        bundle = get_bundle_for_profile(profile_code)
        if bundle:
            bundle_modules = bundle.get_modules()
        else:
            profile = _PRODUCT_PROFILE_SEED.get(profile_code, {})
            bundle_modules = profile.get("modules", [])

        return module_name in bundle_modules

    @classmethod
    def get_limits(cls, tenant_id: int) -> dict[str, Optional[int]]:
        from app.core.tenant.models import Tenant, get_bundle_for_profile

        tenant = Tenant.query.get(tenant_id)
        if tenant is None or not tenant.product_profile_code:
            return {}
        bundle = get_bundle_for_profile(tenant.product_profile_code)
        if bundle is None:
            return {}
        return {
            "max_users": bundle.max_users,
            "max_patients": bundle.max_patients,
            "storage_gb": bundle.storage_gb,
            "api_calls_per_month": bundle.api_calls_per_month,
        }

    @classmethod
    def _active_module_names(cls, tenant_id: int, tenant) -> set[str]:
        names: set[str] = set()
        try:
            from app.core.module.models import TenantModule

            rows = TenantModule.query.filter_by(tenant_id=tenant_id, is_active=True).all()
            names.update(r.module_name for r in rows if r.module_name)
        except Exception:
            pass

        profile = getattr(tenant, "product_profile_code", None)
        if profile:
            from app.core.tenant.models import get_bundle_for_profile

            bundle = get_bundle_for_profile(profile)
            if bundle:
                names.update(bundle.get_modules())

        plan_id = getattr(tenant, "plan_id", None)
        if plan_id:
            try:
                from app.core.tenant.models import SubscriptionPlan

                plan = SubscriptionPlan.query.get(plan_id)
                raw = getattr(plan, "modules_included", None) if plan else None
                if raw:
                    mods = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(mods, list):
                        names.update(mods)
            except Exception:
                pass

        return names
