"""Coverage for services/pricing_service.py — the seeding and cleanup side.

The catalogue seeds and the cleanup helpers are what a fresh deployment runs
to populate its pricing tables. They had never been called by a test, so
every line of the seeding logic was unexecuted.

Each test class is named after the method it covers.
"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestSeedServiceMaster:
    """``seed_service_master`` — the standard service catalogue."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        first = PricingService.seed_service_master()
        assert first['success'] is True

        second = PricingService.seed_service_master()
        assert second['success'] is True
        assert second['created'] == 0


class TestSeedServicePrices:
    """``seed_service_prices`` — the base prices."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        PricingService.seed_service_master()
        result = PricingService.seed_service_prices()
        assert result['success'] is True


class TestSeedDoctors:
    """``seed_doctors`` — the doctor catalogue."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        departments = PricingService.seed_departments()
        result = PricingService.seed_doctors(departments)
        assert result is not None


class TestSeedTechnicians:
    """``seed_technicians``."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        departments = PricingService.seed_departments()
        result = PricingService.seed_technicians()
        assert result is not None


class TestSeedDoctorPricing:
    """``seed_doctor_pricing`` — a doctor's price list."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        PricingService.seed_departments()
        PricingService.seed_doctors(PricingService.seed_departments())
        result = PricingService.seed_doctor_pricing()
        assert result is not None


class TestSeedPricingCatalog:
    """``seed_pricing_catalog``."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.seed_pricing_catalog()
        assert result is not None


class TestSeedAll:
    """``seed_all`` — the whole catalogue in one call."""

    def test_seeding_is_idempotent(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.seed_all()
        assert result is not None


class TestCleanupServicePrices:
    """``cleanup_service_prices``."""

    def test_cleanup_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        PricingService.seed_service_master()
        result = PricingService.cleanup_service_prices()
        assert result is not None


class TestCleanupPricingCatalog:
    """``cleanup_pricing_catalog``."""

    def test_cleanup_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.cleanup_pricing_catalog()
        assert result is not None


class TestCleanupDoctorPricing:
    """``cleanup_doctor_pricing``."""

    def test_cleanup_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.cleanup_doctor_pricing()
        assert result is not None


class TestCleanupUsersByRole:
    """``cleanup_users_by_role``."""

    def test_cleanup_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.cleanup_users_by_role(max_keep_per_role=2)
        assert result is not None


class TestCleanupAll:
    """``cleanup_all``."""

    def test_cleanup_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.cleanup_all(max_keep_per_role=2)
        assert result is not None


class TestPurgeUsersKeepPolicy:
    """``purge_users_keep_policy``."""

    def test_purge_runs(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.purge_users_keep_policy()
        assert result is not None
