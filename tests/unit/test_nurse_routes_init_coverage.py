"""Coverage for routes/nurse_routes/__init__.py — the nursing analytics API.

The nursing module's analytics helpers calculate the scores the dashboard
shows: how efficient the ward is, how well the vital signs are monitored,
how much of the medication round is automated. Every one of those
calculations, and every error path of the analytics that read them, had
never run.

Each test class is named after the helper or the endpoint it covers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestNursingEfficiency:
    """``calculate_nursing_efficiency``."""

    def test_no_tasks_means_no_efficiency(self):
        from routes.nurse_routes import calculate_nursing_efficiency

        assert calculate_nursing_efficiency(0, 0, 0) == 0

    def test_a_fully_completed_ward_is_at_the_top(self):
        from routes.nurse_routes import calculate_nursing_efficiency

        assert calculate_nursing_efficiency(100, 0, 10) == 100

    def test_a_half_completed_ward_is_in_between(self):
        from routes.nurse_routes import calculate_nursing_efficiency

        score = calculate_nursing_efficiency(50, 5, 10)
        assert 0 < score < 100

    def test_a_non_numeric_rate_is_refused(self):
        from routes.nurse_routes import calculate_nursing_efficiency

        assert calculate_nursing_efficiency('not a number', 0, 10) == 0


class TestPatientCareSuggestions:
    """``generate_patient_care_optimization_suggestions``."""

    def test_a_calm_ward_is_reported_as_healthy(self):
        from routes.nurse_routes import generate_patient_care_optimization_suggestions

        suggestions = generate_patient_care_optimization_suggestions(0, 0, 10)
        assert len(suggestions) == 1

    def test_many_urgent_tasks_produce_a_suggestion(self):
        from routes.nurse_routes import generate_patient_care_optimization_suggestions

        suggestions = generate_patient_care_optimization_suggestions(5, 0, 10)
        assert len(suggestions) == 1

    def test_many_high_priority_tasks_produce_a_suggestion(self):
        from routes.nurse_routes import generate_patient_care_optimization_suggestions

        suggestions = generate_patient_care_optimization_suggestions(0, 5, 10)
        assert len(suggestions) == 1

    def test_a_broken_input_still_produces_a_suggestion(self):
        from routes.nurse_routes import generate_patient_care_optimization_suggestions

        suggestions = generate_patient_care_optimization_suggestions('x', None, 10)
        assert len(suggestions) == 1


class TestCareEfficiency:
    """``calculate_patient_care_efficiency``."""

    def test_no_tasks_means_no_efficiency(self):
        from routes.nurse_routes import calculate_patient_care_efficiency

        assert calculate_patient_care_efficiency(0, 0) == 0

    def test_every_task_completed(self):
        from routes.nurse_routes import calculate_patient_care_efficiency

        assert calculate_patient_care_efficiency(10, 10) == 100

    def test_half_of_the_tasks_completed(self):
        from routes.nurse_routes import calculate_patient_care_efficiency

        assert calculate_patient_care_efficiency(5, 10) == 50

    def test_a_non_numeric_count_is_refused(self):
        from routes.nurse_routes import calculate_patient_care_efficiency

        assert calculate_patient_care_efficiency('x', 10) == 0


class TestVitalSignsScore:
    """``calculate_vital_signs_monitoring_score``."""

    def test_no_readings_scores_full_marks(self):
        from routes.nurse_routes import calculate_vital_signs_monitoring_score

        assert calculate_vital_signs_monitoring_score(0, 0, 0) == 100

    def test_everything_normal_scores_full_marks(self):
        from routes.nurse_routes import calculate_vital_signs_monitoring_score

        assert calculate_vital_signs_monitoring_score(0, 0, 10) == 100

    def test_abnormal_readings_lower_the_score(self):
        from routes.nurse_routes import calculate_vital_signs_monitoring_score

        score = calculate_vital_signs_monitoring_score(5, 2, 10)
        assert score < 100

    def test_a_non_numeric_count_is_refused(self):
        from routes.nurse_routes import calculate_vital_signs_monitoring_score

        assert calculate_vital_signs_monitoring_score('x', 0, 10) == 0


class TestMedicationEfficiency:
    """``calculate_medication_efficiency``."""

    def test_no_tasks_means_no_efficiency(self):
        from routes.nurse_routes import calculate_medication_efficiency

        assert calculate_medication_efficiency(0, 0) == 0

    def test_every_task_completed(self):
        from routes.nurse_routes import calculate_medication_efficiency

        assert calculate_medication_efficiency(10, 10) == 100

    def test_a_non_numeric_count_is_refused(self):
        from routes.nurse_routes import calculate_medication_efficiency

        assert calculate_medication_efficiency('x', 10) == 0


class TestAutomationScore:
    """``calculate_nursing_automation_score``."""

    def test_no_tasks_at_all(self):
        from routes.nurse_routes import calculate_nursing_automation_score

        assert calculate_nursing_automation_score(0, 0) == 0

    def test_everything_automated(self):
        from routes.nurse_routes import calculate_nursing_automation_score

        assert calculate_nursing_automation_score(10, 0) == 100

    def test_a_non_numeric_count_is_refused(self):
        from routes.nurse_routes import calculate_nursing_automation_score

        assert calculate_nursing_automation_score('x', 1) == 0


class TestWorkloadForecast:
    """``calculate_workload_forecast_accuracy``."""

    def test_it_reports_a_fixed_accuracy(self):
        from routes.nurse_routes import calculate_workload_forecast_accuracy

        assert calculate_workload_forecast_accuracy() == 85


class TestNursingProtocols:
    """``_get_nursing_protocols`` — the stored protocol list."""

    def test_the_defaults_are_stored_when_there_is_no_config(self, app, db, test_tenant):
        from routes.nurse_routes import _get_nursing_protocols, _nursing_protocols_key

        protocols = _get_nursing_protocols()
        assert isinstance(protocols, list)
        assert protocols

        from models.system_config import SystemConfig

        stored = (
            db.session.execute(
                db.select(SystemConfig).filter_by(config_key=_nursing_protocols_key())
            )
            .scalars()
            .first()
        )
        assert stored is not None
        assert stored.config_type == 'json'

    def test_a_broken_config_is_repaired(self, app, db, test_tenant):
        from routes.nurse_routes import _get_nursing_protocols, _nursing_protocols_key

        from models.system_config import SystemConfig

        config = SystemConfig(
            tenant_id=test_tenant.id,
            config_key=_nursing_protocols_key(),
            config_type='json',
            config_value='not json at all',
            category='system',
            is_system=False,
            is_encrypted=False,
        )
        db.session.add(config)
        db.session.flush()

        protocols = _get_nursing_protocols()
        assert isinstance(protocols, list)
        assert protocols


class TestAccessibleDepartments:
    """``_accessible_department_ids`` — the nurse's departments."""

    def test_a_broken_access_check_yields_no_departments(self, app):
        from routes.nurse_routes import _accessible_department_ids

        with patch(
            'services.access_control_service.AccessControlService.get_accessible_department_ids',
            side_effect=RuntimeError('access service down'),
        ):
            assert _accessible_department_ids() == []


class TestNursingAnalytics:
    """The analytics endpoints and their error paths."""

    ENDPOINTS = [
        'get_nursing_smart_analytics',
        'get_patient_care_optimization',
        'get_vital_signs_monitoring',
        'get_medication_management',
        'get_nursing_workflow_automation',
        'get_nursing_predictive_insights',
        'get_nursing_quality_indicators',
        'get_nursing_workload_prediction',
        'get_nursing_smart_recommendations',
    ]

    @pytest.mark.parametrize('name', ENDPOINTS)
    def test_the_analytics_are_produced(self, app, db, test_tenant, name):
        import routes.nurse_routes as nurse_routes

        with app.test_request_context():
            result = getattr(nurse_routes, name)()
        assert isinstance(result, dict)

    @pytest.mark.parametrize('name', ENDPOINTS)
    def test_a_failing_query_yields_an_empty_result(self, app, db, test_tenant, name):
        import routes.nurse_routes as nurse_routes

        def boom(*a, **k):
            raise RuntimeError('database down')

        with app.test_request_context():
            with patch.object(nurse_routes.db.session, 'execute', boom):
                result = getattr(nurse_routes, name)()
        assert result == {}
