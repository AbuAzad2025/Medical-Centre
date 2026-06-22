"""Tests for S0-000: ProductProfile catalog consistency."""

import pytest

from app.shared.enums import ProductProfile
from app.core.tenant.models import Tenant, _PRODUCT_PROFILE_SEED


class TestProductProfileConsistency:
    def test_all_seed_profiles_have_canonical_mapping(self):
        """Every seeded bundle profile code must map to a canonical ProductProfile."""
        for code in _PRODUCT_PROFILE_SEED:
            canonical = Tenant.canonical_profile_for(code)
            assert canonical is not None, f"Missing canonical mapping for {code}"
            assert isinstance(canonical, ProductProfile)

    def test_canonical_enum_values_are_seed_keys(self):
        """The 7 canonical ProductProfile values are also valid seed keys."""
        for member in ProductProfile:
            assert member.value in _PRODUCT_PROFILE_SEED, f"{member.value} not in seed"

    def test_tenant_accepts_non_enum_seed_profile_code(self, app, test_tenant):
        """product_profile_code column must accept a seed code not in the enum."""
        from app_factory import db as _db

        test_tenant.product_profile_code = "clinic_with_lab"
        _db.session.commit()
        _db.session.refresh(test_tenant)
        assert test_tenant.product_profile_code == "clinic_with_lab"
        assert test_tenant.product_profile is None  # not a canonical enum value
        assert test_tenant.canonical_profile_for("clinic_with_lab") == ProductProfile.SMALL_CLINIC

    def test_tenant_property_returns_enum_for_canonical_code(self, app, test_tenant):
        from app_factory import db as _db

        test_tenant.product_profile_code = ProductProfile.STANDALONE_PHARMACY.value
        _db.session.commit()
        _db.session.refresh(test_tenant)
        assert test_tenant.product_profile == ProductProfile.STANDALONE_PHARMACY
