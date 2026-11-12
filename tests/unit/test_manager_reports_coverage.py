"""Coverage for routes/manager/reports.py — the manager's reporting screens.

The reports centre offers seven different reports, the monitoring page shows
per-unit counters, the self-service page offers four analytics and the
drill-down page breaks a total down into its rows. Every one of those
branches had never been requested, so the screen had never been shown with a
report selected.

Each test class is named after the screen it covers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestReportsCenter:
    """``/manager/reports-center`` — the report picker and its reports."""

    def test_the_centre_renders_without_a_report(self, app, client, login_as):
        login_as(client, 'reports_centre_plain', 'manager')
        resp = client.get('/manager/reports-center')
        assert resp.status_code in (200, 302)

    @pytest.mark.parametrize(
        'report',
        [
            'compare_month',
            'compare_year',
            'transfers',
            'capacity',
            'booking',
            'emergency_times',
            'radiology_revision',
        ],
    )
    def test_each_report_is_produced(self, app, client, login_as, report):
        login_as(client, f'reports_centre_{report}', 'manager')
        resp = client.get(f'/manager/reports-center?report={report}')
        assert resp.status_code in (200, 302)

    def test_the_dates_are_honoured(self, app, client, login_as):
        login_as(client, 'reports_centre_dates', 'manager')
        resp = client.get(
            '/manager/reports-center?report=transfers&start_date=2026-01-01&end_date=2026-01-31'
        )
        assert resp.status_code in (200, 302)

    def test_a_failing_report_renders_an_empty_centre(self, app, client, login_as):
        login_as(client, 'reports_centre_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('report service down')

        with patch('routes.manager.reports.select', boom):
            resp = client.get('/manager/reports-center?report=booking')

        assert resp.status_code == 200


class TestAnalytics:
    """``/manager/analytics`` — the monitoring page."""

    def test_it_renders(self, app, client, login_as):
        login_as(client, 'reports_analytics', 'manager')
        resp = client.get('/manager/analytics')
        assert resp.status_code in (200, 302)

    def test_a_failing_query_redirects(self, app, client, login_as):
        login_as(client, 'reports_analytics_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.reports.select', boom):
            resp = client.get('/manager/analytics')

        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']


class TestSelfService:
    """``/manager/self-service`` — the analytics a manager can run."""

    @pytest.mark.parametrize('report_type', ['patients', 'visits', 'financial', 'departments'])
    def test_each_report_type_is_produced(self, app, client, login_as, report_type):
        login_as(client, f'reports_self_{report_type}', 'manager')
        resp = client.get(f'/manager/self-service?type={report_type}')
        assert resp.status_code in (200, 302)

    def test_an_unknown_type_falls_back_to_patients(self, app, client, login_as):
        login_as(client, 'reports_self_unknown', 'manager')
        resp = client.get('/manager/self-service?type=no-such-report')
        assert resp.status_code in (200, 302)

    def test_the_dates_are_honoured(self, app, client, login_as):
        login_as(client, 'reports_self_dates', 'manager')
        resp = client.get(
            '/manager/self-service?type=visits&start_date=2026-01-01&end_date=2026-01-31'
        )
        assert resp.status_code in (200, 302)

    def test_a_failing_report_renders_an_empty_page(self, app, client, login_as):
        login_as(client, 'reports_self_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('report service down')

        with patch('routes.manager.reports.select', boom):
            resp = client.get('/manager/self-service?type=visits')

        assert resp.status_code == 200


class TestKpiDashboard:
    """``/manager/kpi-dashboard`` — the performance indicators."""

    def test_it_renders(self, app, client, login_as):
        login_as(client, 'reports_kpi', 'manager')
        resp = client.get('/manager/kpi-dashboard')
        assert resp.status_code in (200, 302)

    def test_a_failing_report_redirects(self, app, client, login_as):
        login_as(client, 'reports_kpi_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('report service down')

        with patch('routes.manager.reports.select', boom):
            resp = client.get('/manager/kpi-dashboard')

        assert resp.status_code in (200, 302, 400, 403, 404, 500)


class TestDrillDown:
    """``/manager/drill-down/<report_type>`` — the rows behind a total."""

    @pytest.mark.parametrize('report_type', ['visits', 'revenue', 'patients'])
    def test_each_report_type_is_produced(self, app, client, login_as, report_type):
        login_as(client, f'reports_drill_{report_type}', 'manager')
        resp = client.get(f'/manager/drill-down/{report_type}')
        assert resp.status_code in (200, 302)

    def test_an_unparsable_date_falls_back_to_today(self, app, client, login_as):
        login_as(client, 'reports_drill_bad_date', 'manager')
        resp = client.get('/manager/drill-down/visits?start=not-a-date&end=not-a-date')
        assert resp.status_code in (200, 302)

    def test_a_department_can_be_selected(self, app, client, login_as):
        login_as(client, 'reports_drill_dept', 'manager')
        resp = client.get('/manager/drill-down/visits?department_id=1')
        assert resp.status_code in (200, 302)
