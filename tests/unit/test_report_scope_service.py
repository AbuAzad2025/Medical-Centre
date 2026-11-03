"""Tests for services.report_scope_service module - 100% coverage target."""

from __future__ import annotations

import pytest

from services.report_scope_service import ReportScopeService


class TestReportScopeService:
    """Tests for ReportScopeService class."""

    def test_get_report_data_unknown_type(self):
        result = ReportScopeService.get_report_data('unknown_type')
        assert result == {}

    def test_visit_stats_no_tenant(self, app, db):
        result = ReportScopeService.get_report_data('visit_stats')
        assert 'total_visits' in result
        assert 'by_status' in result

    def test_visit_stats_with_tenant(self, app, db, test_tenant):
        result = ReportScopeService.get_report_data('visit_stats', tenant_id=test_tenant.id)
        assert 'total_visits' in result

    def test_visit_stats_with_filters(self, app, db, test_tenant):
        from datetime import datetime, timedelta

        now = datetime.now()
        result = ReportScopeService.get_report_data(
            'visit_stats',
            tenant_id=test_tenant.id,
            date_from=now - timedelta(days=1),
            date_to=now + timedelta(days=1),
        )
        assert 'total_visits' in result

    def test_lab_volume_no_tenant(self, app, db):
        result = ReportScopeService.get_report_data('lab_volume')
        assert 'total_lab_requests' in result
        assert 'by_status' in result

    def test_lab_volume_with_tenant(self, app, db, test_tenant):
        result = ReportScopeService.get_report_data('lab_volume', tenant_id=test_tenant.id)
        assert 'total_lab_requests' in result

    def test_revenue_no_tenant(self, app, db):
        result = ReportScopeService.get_report_data('revenue')
        assert 'total_revenue' in result

    def test_revenue_with_tenant(self, app, db, test_tenant):
        result = ReportScopeService.get_report_data('revenue', tenant_id=test_tenant.id)
        assert 'total_revenue' in result

    def test_inventory_no_tenant(self, app, db):
        result = ReportScopeService.get_report_data('inventory')
        assert 'total_medications' in result
        assert 'low_stock' in result

    def test_inventory_with_tenant(self, app, db, test_tenant):
        result = ReportScopeService.get_report_data('inventory', tenant_id=test_tenant.id)
        assert 'total_medications' in result

    def test_referral_no_tenant(self, app, db):
        result = ReportScopeService.get_report_data('referral')
        assert 'total_referrals' in result
        assert 'total_visits' in result

    def test_referral_with_tenant(self, app, db, test_tenant):
        result = ReportScopeService.get_report_data('referral', tenant_id=test_tenant.id)
        assert 'total_referrals' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
