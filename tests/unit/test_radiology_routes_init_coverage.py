"""Coverage for routes/radiology/__init__.py — the radiology analytics API.

The radiology module has the same shape as the nursing one: a set of
analytics that read the worklist, a set of stored report templates, and the
calculations the dashboard shows. The templates, the calculations and every
error path of the analytics had never been exercised.

Each test class is named after the helper or the endpoint it covers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestRadiologyEfficiency:
    """``calculate_radiology_efficiency``."""

    def test_a_fully_completed_department_keeps_its_score(self):
        from routes.radiology import calculate_radiology_efficiency

        assert calculate_radiology_efficiency(100, 0) == 100

    def test_pending_requests_lower_the_score(self):
        from routes.radiology import calculate_radiology_efficiency

        assert calculate_radiology_efficiency(100, 4) == 90

    def test_the_penalty_is_capped(self):
        from routes.radiology import calculate_radiology_efficiency

        assert calculate_radiology_efficiency(100, 100) == 75

    def test_a_non_numeric_rate_is_refused(self):
        from routes.radiology import calculate_radiology_efficiency

        assert calculate_radiology_efficiency('x', 0) == 0


class TestImagingEfficiency:
    """``calculate_imaging_efficiency``."""

    @pytest.mark.parametrize(
        'avg_time,expected',
        [(1, 95), (2, 85), (4, 75), (6, 60)],
    )
    def test_the_score_follows_the_average_time(self, avg_time, expected):
        from routes.radiology import calculate_imaging_efficiency

        assert calculate_imaging_efficiency(avg_time, 10) == expected

    def test_a_non_numeric_average_is_refused(self):
        from routes.radiology import calculate_imaging_efficiency

        assert calculate_imaging_efficiency('x', 10) == 0


class TestImagingSuggestions:
    """``generate_imaging_optimization_suggestions``."""

    def test_a_fast_imaging_room_has_no_suggestions(self):
        from routes.radiology import generate_imaging_optimization_suggestions

        assert generate_imaging_optimization_suggestions(1) == []

    def test_a_slow_room_produces_suggestions(self):
        from routes.radiology import generate_imaging_optimization_suggestions

        suggestions = generate_imaging_optimization_suggestions(6)
        assert len(suggestions) == 3


class TestRadiologyReportTemplates:
    """The stored report templates and macros."""

    def test_the_default_templates_are_stored_when_there_is_none(self, app, db, test_tenant):
        from routes.radiology import _get_radiology_report_templates

        templates = _get_radiology_report_templates()
        assert isinstance(templates, list)
        assert templates

    def test_the_default_macros_are_stored_when_there_are_none(self, app, db, test_tenant):
        from routes.radiology import _get_radiology_report_macros

        macros = _get_radiology_report_macros()
        assert isinstance(macros, list)
        assert macros

    def test_a_broken_template_config_is_repaired(self, app, client, db, test_tenant, login_as):
        login_as(client, 'radiology_templates_user', 'radiology')
        from models.system_config import SystemConfig
        from routes.radiology import _get_radiology_report_templates

        login_as(client, 'radiology_templates_user', 'radiology')

        key = 'radiology_report_templates'

        config = SystemConfig(
            tenant_id=test_tenant.id,
            config_key=key,
            config_type='json',
            config_value='not json at all',
            category='system',
            is_system=False,
            is_encrypted=False,
        )
        db.session.add(config)
        db.session.flush()

        with app.test_request_context():
            templates = _get_radiology_report_templates()
            assert isinstance(templates, list)
            assert templates


class TestRadiologyAnalytics:
    """The analytics endpoints and their error paths."""

    ENDPOINTS = [
        'get_radiology_smart_analytics',
        'get_radiology_imaging_optimization',
        'get_radiology_quality_assurance',
        'get_radiology_equipment_status',
        'get_radiology_report_analysis',
        'get_radiology_workflow_automation',
        'get_radiology_predictive_insights',
    ]

    @pytest.mark.parametrize('name', ENDPOINTS)
    def test_the_analytics_are_produced(self, app, db, test_tenant, name):
        import routes.radiology as radiology_routes

        with app.test_request_context():
            result = getattr(radiology_routes, name)()
        assert isinstance(result, dict)

    @pytest.mark.parametrize('name', ENDPOINTS)
    def test_a_failing_query_yields_an_empty_result(self, app, db, test_tenant, name):
        import routes.radiology as radiology_routes

        def boom(*a, **k):
            raise RuntimeError('database down')

        with app.test_request_context():
            with patch.object(radiology_routes.db.session, 'execute', boom):
                result = getattr(radiology_routes, name)()
        assert isinstance(result, dict)
