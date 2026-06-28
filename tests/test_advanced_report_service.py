"""Smoke tests for wired AdvancedReportService analytics (manager reports)."""
from datetime import datetime, timedelta, timezone

import pytest

from services.advanced_report_service import AdvancedReportService


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


class TestAdvancedReportService:
    def test_patient_analytics_shape(self, rollback_db):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        res = AdvancedReportService.generate_patient_analytics(start, end)
        assert res.get('success') is True
        assert 'analytics' in res
        assert 'total_patients' in res['analytics']

    def test_visit_analytics_shape(self, rollback_db):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        res = AdvancedReportService.generate_visit_analytics(start, end)
        assert res.get('success') is True
        assert 'analytics' in res

    def test_financial_analytics_shape(self, rollback_db):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        res = AdvancedReportService.generate_financial_analytics(start, end)
        assert res.get('success') is True

    def test_department_analytics_shape(self, rollback_db):
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        res = AdvancedReportService.generate_department_analytics(start, end)
        assert res.get('success') is True
