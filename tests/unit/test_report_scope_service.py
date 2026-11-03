"""Tests for services.report_scope_service module - 100% coverage target."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from services.report_scope_service import ReportScopeService


class TestReportScopeService:
    """Tests for ReportScopeService class."""

    def test_get_report_data_unknown_type(self):
        """Test get_report_data with unknown report type returns empty dict."""
        result = ReportScopeService.get_report_data('unknown_type')
        assert result == {}

    def test_get_report_data_visit_stats(self):
        """Test get_report_data with visit_stats type."""
        with patch('services.report_scope_service.ReportScopeService._visit_stats') as mock:
            mock.return_value = {'total_visits': 10, 'by_status': {}}
            result = ReportScopeService.get_report_data('visit_stats', tenant_id=1)
            assert result == {'total_visits': 10, 'by_status': {}}

    def test_get_report_data_lab_volume(self):
        """Test get_report_data with lab_volume type."""
        with patch('services.report_scope_service.ReportScopeService._lab_volume') as mock:
            mock.return_value = {'total_lab_requests': 5, 'by_status': {}}
            result = ReportScopeService.get_report_data('lab_volume', tenant_id=1)
            assert result == {'total_lab_requests': 5, 'by_status': {}}

    def test_get_report_data_revenue(self):
        """Test get_report_data with revenue type."""
        with patch('services.report_scope_service.ReportScopeService._revenue') as mock:
            mock.return_value = {'total_revenue': 1000.0}
            result = ReportScopeService.get_report_data('revenue', tenant_id=1)
            assert result == {'total_revenue': 1000.0}

    def test_get_report_data_inventory(self):
        """Test get_report_data with inventory type."""
        with patch('services.report_scope_service.ReportScopeService._inventory') as mock:
            mock.return_value = {'total_medications': 10, 'low_stock': 2}
            result = ReportScopeService.get_report_data('inventory', tenant_id=1)
            assert result == {'total_medications': 10, 'low_stock': 2}

    def test_get_report_data_referral(self):
        """Test get_report_data with referral type."""
        with patch('services.report_scope_service.ReportScopeService._referral') as mock:
            mock.return_value = {'total_referrals': 3, 'total_visits': 10}
            result = ReportScopeService.get_report_data('referral', tenant_id=1)
            assert result == {'total_referrals': 3, 'total_visits': 10}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])