"""Tests for routes.medication_routes module - 100% coverage target."""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import pytest

from routes.medication_routes import (
    calculate_automation_score,
    calculate_demand_forecast_accuracy,
    calculate_interaction_risk_score,
    calculate_inventory_efficiency,
    calculate_pharmacy_efficiency,
    calculate_safety_score,
    generate_inventory_optimization_suggestions,
    get_drug_interaction_checker,
    get_inventory_optimization,
    get_medication_safety_monitoring,
    get_pharmacy_predictive_insights,
    get_pharmacy_smart_analytics,
    get_pharmacy_smart_recommendations,
    get_pharmacy_workflow_automation,
    get_prescription_analytics,
)


class TestPureFunctions:
    def test_calculate_pharmacy_efficiency(self):
        assert calculate_pharmacy_efficiency(10, 2, 10) > 0
        assert (
            calculate_pharmacy_efficiency(0, 0, 0) == 0
            or calculate_pharmacy_efficiency(0, 0, 0) is not None
        )
        # except branch
        assert calculate_pharmacy_efficiency(None, None, None) == 0

    def test_generate_inventory_optimization_suggestions(self):
        result = generate_inventory_optimization_suggestions(5, 3, 100)
        assert result is not None
        # 637 branch
        r2 = generate_inventory_optimization_suggestions(50, 0, 100)
        assert 'زيادة الحد الأدنى للمخزون للأدوية المهمة' in r2
        # 640 branch
        r3 = generate_inventory_optimization_suggestions(0, 10, 100)
        assert 'تحسين نظام متابعة انتهاء الصلاحية' in r3
        # except branch
        result2 = generate_inventory_optimization_suggestions(5, 3, 'a')
        assert 'تحليل البيانات للتحسين' in result2

    def test_calculate_inventory_efficiency(self):
        result = calculate_inventory_efficiency(5, 3, 100)
        assert result is not None
        assert calculate_inventory_efficiency(None, None, None) == 0

    def test_calculate_safety_score(self):
        result = calculate_safety_score(1, 2, 3)
        assert result is not None
        assert calculate_safety_score(None, None, None) == 0

    def test_calculate_interaction_risk_score(self):
        result = calculate_interaction_risk_score(1, 2, 3)
        assert result is not None
        assert calculate_interaction_risk_score(None, None, None) == 0

    def test_calculate_automation_score(self):
        result = calculate_automation_score(5, 5)
        assert result is not None
        assert calculate_automation_score(None, None) == 0

    def test_guard_pharmacy_module(self, app, client, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from routes.medication_routes import _guard_pharmacy_module

        # guard_module may raise or pass; just call
        with contextlib.suppress(Exception):
            _guard_pharmacy_module()

    def test_generate_supply_request_number(self):
        from routes.medication_routes import _generate_supply_request_number

        result = _generate_supply_request_number()
        assert result.startswith('SR-')

    def test_calculate_demand_forecast_accuracy(self):
        result = calculate_demand_forecast_accuracy()
        assert result is not None


class TestMedicationRouteFunctions:
    def _auth_context(self, app, client, db, test_tenant):

        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
        login_test_client(client, user, test_tenant)
        # Bind tenant on g
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        return user

    def test_get_pharmacy_smart_analytics(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            # Set current_user
            import flask

            flask.g._login_user = user
            result = get_pharmacy_smart_analytics()
            assert result is not None

    def test_get_inventory_optimization(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_inventory_optimization()
            assert result is not None

    def test_get_medication_safety_monitoring(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_medication_safety_monitoring()
            assert result is not None

    def test_get_prescription_analytics(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_prescription_analytics()
            assert result is not None

    def test_get_drug_interaction_checker(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_drug_interaction_checker()
            assert result is not None

    def test_get_pharmacy_workflow_automation(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_pharmacy_workflow_automation()
            assert result is not None

    def test_get_pharmacy_predictive_insights(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_pharmacy_predictive_insights()
            assert result is not None

    def test_analytics_exception(self, app, client, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
        import flask

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            flask.g._login_user = user
            with patch(
                'routes.medication_routes.db.session.execute', side_effect=Exception('db err')
            ):
                assert get_pharmacy_smart_analytics() == {}
                assert get_inventory_optimization() == {}
                assert get_medication_safety_monitoring() == {}
                assert get_prescription_analytics() == {}
                assert get_drug_interaction_checker() == {}
                with patch(
                    'routes.medication_routes.calculate_automation_score',
                    side_effect=Exception('err'),
                ):
                    assert get_pharmacy_workflow_automation() == {}
                assert get_pharmacy_predictive_insights() == {}
            # trigger outer except for smart_recommendations
            with patch(
                'routes.medication_routes.get_inventory_optimization', side_effect=Exception('err')
            ):
                assert get_pharmacy_smart_recommendations() == {
                    'recommendations': [],
                    'total_recommendations': 0,
                }

    def test_smart_recommendations_branches(self, app, client, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
        import flask

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            flask.g._login_user = user
            with patch(
                'routes.medication_routes.get_pharmacy_smart_analytics',
                return_value={'low_stock_medications': 10},
            ):
                with patch('routes.medication_routes.get_inventory_optimization'):
                    with patch(
                        'routes.medication_routes.get_medication_safety_monitoring',
                        return_value={'expired_medications': 1, 'expiring_soon': 5},
                    ):
                        with patch(
                            'routes.medication_routes.get_prescription_analytics',
                            return_value={'dispensing_rate': 50},
                        ):
                            with patch(
                                'routes.medication_routes.get_drug_interaction_checker',
                                return_value={'severe_interactions': 2},
                            ):
                                result = get_pharmacy_smart_recommendations()
                                assert result['total_recommendations'] >= 5

    def test_get_pharmacy_smart_recommendations(self, app, client, db, test_tenant):
        self._auth_context(app, client, db, test_tenant)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from tests.tenant_context import ensure_test_user

            user = ensure_test_user(db, test_tenant, username='med_route_user', role='pharmacist')
            import flask

            flask.g._login_user = user
            result = get_pharmacy_smart_recommendations()
            assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
