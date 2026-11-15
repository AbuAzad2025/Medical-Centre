"""Coverage tests for models/ai_analytics.py"""

from datetime import date

pytest_plugins = ['tests._isolated_tenant']


class TestAIAnalyticsModels:
    def test_ai_recommendation_repr(self, app, db, test_tenant):
        from models.ai_analytics import AIRecommendation
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            obj = AIRecommendation(
                tenant_id=test_tenant.id,
                recommendation_type='treatment',
                title='Test Rec',
                description='Test desc',
                confidence_score=0.9,
            )
            db.session.add(obj)
            db.session.flush()
            assert obj.id is not None
            assert 'AIRecommendation' in repr(obj)
            assert obj.get_recommendation_type_display() is not None
            assert obj.get_confidence_display() is not None
            assert obj.get_confidence_color() is not None
            d = obj.to_dict()
            assert isinstance(d, dict)

    def test_disease_pattern(self, app, db, test_tenant):
        from models.ai_analytics import DiseasePattern
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            obj = DiseasePattern(
                tenant_id=test_tenant.id,
                disease_name='Test Pattern',
                icd_code='A00',
                severity_level='high',
            )
            db.session.add(obj)
            db.session.flush()
            assert obj.id is not None
            assert 'DiseasePattern' in repr(obj)
            assert obj.get_severity_display() is not None
            assert obj.get_severity_color() is not None
            d = obj.to_dict()
            assert isinstance(d, dict)

    def test_performance_analytics(self, app, db, test_tenant):
        from models.ai_analytics import PerformanceAnalytics
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            obj = PerformanceAnalytics(
                tenant_id=test_tenant.id,
                metric_name='Revenue',
                metric_type='revenue',
                metric_value=100.0,
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
            )
            db.session.add(obj)
            db.session.flush()
            assert obj.id is not None
            assert 'PerformanceAnalytics' in repr(obj)
            assert obj.get_metric_type_display() is not None
            assert obj.get_performance_status() is not None
            assert obj.get_performance_color() is not None
            d = obj.to_dict()
            assert isinstance(d, dict)

    def test_patient_insight(self, app, db, test_tenant):
        from models.ai_analytics import PatientInsight
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(test_tenant, db_session=db.session)
            from models.patient import Patient

            patient = Patient(
                tenant_id=test_tenant.id,
                first_name='Test',
                last_name='Patient',
                date_of_birth=date(1990, 1, 1),
                gender='male',
            )
            db.session.add(patient)
            db.session.flush()
            obj = PatientInsight(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                insight_type='risk',
                title='Test Insight',
                description='Test desc',
            )
            db.session.add(obj)
            db.session.flush()
            assert obj.id is not None
            assert 'PatientInsight' in repr(obj)
            assert obj.get_insight_type_display() is not None
            d = obj.to_dict()
            assert isinstance(d, dict)
