"""Coverage-focused HTTP tests for routes/super_admin/analytics.py.

Real Flask test-client requests as an authenticated super_admin, plus direct
calls to the module-level stat helpers. Mutating endpoints run under
``rollback_db`` so the shared test schema is not polluted.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from tests.tenant_context import tenant_test_context


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


@pytest.fixture
def sa_client(app, client, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(
        db, test_tenant, username='super_admin_analytics_cov', role='super_admin'
    )
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


def _make_department(db, name: str | None = None):
    from models.department import Department

    dept = Department(
        name=name or _uniq('Dept'),
        name_ar=_uniq('قسم'),
        is_active=True,
    )
    db.session.add(dept)
    db.session.commit()
    return dept


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        if isinstance(self._value, list):
            return 0
        return self._value

    def all(self):
        if isinstance(self._value, list):
            return self._value
        return []

    def scalars(self):
        return self

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


class TestAnalyticsHttpEndpoints:
    def test_performance_api_success(self, sa_client):
        resp = sa_client.get('/super-admin/api/performance')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['cpu_percent'] >= 0
        assert body['memory_percent'] >= 0
        assert body['uptime_hours'] >= 0

    def test_performance_api_scalar_exception(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('execute failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        resp = sa_client.get('/super-admin/api/performance')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['active_db_connections'] is None

    def test_performance_api_outer_exception(self, sa_client, monkeypatch):
        import psutil

        def _boom(*a, **k):
            raise RuntimeError('cpu failed')

        monkeypatch.setattr(psutil, 'cpu_percent', _boom)
        resp = sa_client.get('/super-admin/api/performance')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_performance_page_success(self, sa_client):
        assert sa_client.get('/super-admin/performance').status_code == 200

    def test_performance_page_exception(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        calls = {'n': 0}
        real_render = mod.render_template

        def _flaky(*a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('render failed')
            return real_render(*a, **k)

        monkeypatch.setattr(mod, 'render_template', _flaky)
        resp = sa_client.get('/super-admin/performance', follow_redirects=False)
        assert resp.status_code == 302

    def test_reports_page_renders(self, sa_client):
        assert sa_client.get('/super-admin/reports').status_code == 200

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
    def test_reports_each_report_type(self, sa_client, report):
        resp = sa_client.get(
            f'/super-admin/reports?report={report}&start_date=2026-01-01&end_date=2026-12-31'
        )
        assert resp.status_code == 200

    def test_reports_with_department_filter(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.get(f'/super-admin/reports?report=compare_month&department_id={dept.id}')
        assert resp.status_code == 200

    def test_reports_bad_dates_still_renders(self, sa_client):
        resp = sa_client.get(
            '/super-admin/reports?report=booking&start_date=bogus&end_date=alsbogus'
        )
        assert resp.status_code == 200

    def test_reports_compare_month_december_branch(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        class FakeDate:
            @staticmethod
            def today():
                return date(2026, 12, 15)

        monkeypatch.setattr(mod, 'date', FakeDate)
        resp = sa_client.get('/super-admin/reports?report=compare_month')
        assert resp.status_code == 200

    def test_reports_compare_month_january_branch(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        class FakeDate:
            @staticmethod
            def today():
                return date(2026, 1, 15)

        monkeypatch.setattr(mod, 'date', FakeDate)
        resp = sa_client.get('/super-admin/reports?report=compare_month')
        assert resp.status_code == 200

    def test_reports_exception(self, sa_client, monkeypatch):

        class FakeReportCenterService:
            @staticmethod
            def _parse_dates(*a, **k):
                raise RuntimeError('parse failed')

        monkeypatch.setattr(
            'services.report_center_service.ReportCenterService', FakeReportCenterService
        )
        resp = sa_client.get('/super-admin/reports?report=booking')
        assert resp.status_code == 200

    def test_analytics_page(self, sa_client, db, test_tenant):
        from app.shared.enums import VisitState
        from models.patient import Patient
        from models.visit import Visit

        patient = Patient(
            first_name='Test',
            last_name='Patient',
            phone='0599000001',
            gender='M',
            tenant_id=test_tenant.id,
        )
        db.session.add(patient)
        db.session.flush()
        db.session.add(
            Visit(
                patient_id=patient.id,
                status=VisitState.OPEN.value,
                payment_status='PENDING',
                total_amount=0,
                visit_type='REGULAR',
                payment_method='cash',
                visit_date=date.today(),
                tenant_id=test_tenant.id,
            )
        )
        db.session.commit()
        resp = sa_client.get('/super-admin/analytics')
        assert resp.status_code == 200

    def test_analytics_page_exception(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('db down')

        monkeypatch.setattr(
            mod, 'select', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('db down'))
        )
        resp = sa_client.get('/super-admin/analytics')
        assert resp.status_code == 200

    def test_system_monitor_page(self, sa_client):
        assert sa_client.get('/super-admin/system-monitor').status_code == 200

    def test_system_monitor_outer_exception(self, sa_client, monkeypatch):
        import routes.super_admin.analytics as mod

        calls = {'n': 0}
        real_render = mod.render_template

        def _flaky(*a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('render failed')
            return real_render(*a, **k)

        monkeypatch.setattr(mod, 'render_template', _flaky)
        resp = sa_client.get('/super-admin/system-monitor', follow_redirects=False)
        # render_template in try raises -> except calls flash + render_template (succeeds)
        assert resp.status_code == 200

    def test_system_monitor_psutil_exception(self, sa_client, monkeypatch):
        import psutil

        monkeypatch.setattr(
            psutil,
            'cpu_percent',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('psutil failed')),
        )
        resp = sa_client.get('/super-admin/system-monitor')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Helper direct calls
# ---------------------------------------------------------------------------


class TestAnalyticsHelpers:
    def _ctx(self, app, test_tenant):
        return tenant_test_context(app, test_tenant)

    def test_get_total_users_and_active_inactive_admin(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import (
            get_active_sessions,
            get_active_users,
            get_admin_users,
            get_inactive_users,
            get_total_users,
        )

        with self._ctx(app, test_tenant):
            assert get_total_users() >= 0
            assert get_active_users() >= 0
            assert get_inactive_users() >= 0
            assert get_admin_users() >= 0
            assert get_active_sessions() >= 0

    def test_get_security_events_returns_int(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_security_events

        with self._ctx(app, test_tenant):
            assert isinstance(get_security_events(), int)

    def test_get_system_uptime_constant(self):
        from routes.super_admin.analytics import get_system_uptime

        assert get_system_uptime() == '99.9%'

    def test_get_daily_usage_series(self):
        from routes.super_admin.analytics import get_daily_usage

        assert get_daily_usage() == [100, 95, 88, 92, 98]

    def test_get_ai_insights_shape(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_ai_insights

        with self._ctx(app, test_tenant):
            insights = get_ai_insights()
            assert isinstance(insights, dict)
            for key in (
                'total_recommendations',
                'pending_recommendations',
                'accepted_recommendations',
                'high_confidence_recommendations',
                'recent_insights',
            ):
                assert key in insights

    def test_get_smart_recommendations_returns_list(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_smart_recommendations

        with self._ctx(app, test_tenant):
            assert isinstance(get_smart_recommendations(), list)

    def test_get_smart_recommendations_branches(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        values = iter([101, 6, 11])

        def _execute(*a, **k):
            return _FakeResult(next(values))

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            recs = mod.get_smart_recommendations()
        assert isinstance(recs, list)
        assert len(recs) >= 3, f'recs={recs}'

    def test_get_predictive_analytics_keys(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_predictive_analytics

        with self._ctx(app, test_tenant):
            result = get_predictive_analytics()
            assert isinstance(result, dict)
            assert 'growth_rate' in result
            assert 'trend' in result
            assert result['trend'] in ('growing', 'stable', 'declining')

    def test_get_predictive_peak_inner_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        n = {'i': 0}

        def _execute(*a, **k):
            n['i'] += 1
            if n['i'] == 4:
                raise RuntimeError('peak failed')
            return _FakeResult(0)

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            result = mod.get_predictive_analytics()
        assert isinstance(result, dict)

    def test_get_system_health_score(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_system_health_score

        with self._ctx(app, test_tenant):
            result = get_system_health_score()
            assert isinstance(result, dict)
            assert 0 <= result['score'] <= 100
            assert result['color'] in ('success', 'warning', 'danger', 'secondary')

    def test_get_system_health_score_disk_low(self, app, db, test_tenant, rollback_db, monkeypatch):
        import shutil

        import routes.super_admin.analytics as mod

        class LowDisk:
            total = 100
            free = 5
            used = 95

        monkeypatch.setattr(shutil, 'disk_usage', lambda *_a, **_k: LowDisk())
        with tenant_test_context(app, test_tenant):
            result = mod.get_system_health_score()
        assert isinstance(result, dict)

    def test_get_system_health_score_disk_mid(self, app, db, test_tenant, rollback_db, monkeypatch):
        import shutil

        import routes.super_admin.analytics as mod

        class MidDisk:
            total = 100
            free = 15
            used = 85

        monkeypatch.setattr(shutil, 'disk_usage', lambda *_a, **_k: MidDisk())
        with tenant_test_context(app, test_tenant):
            result = mod.get_system_health_score()
        assert isinstance(result, dict)

    def test_get_system_health_score_disk_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import shutil

        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('disk failed')

        monkeypatch.setattr(shutil, 'disk_usage', _boom)
        with tenant_test_context(app, test_tenant):
            result = mod.get_system_health_score()
        assert isinstance(result, dict)

    def test_get_system_health_score_files_missing(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):

        import routes.super_admin.analytics as mod

        real_exists = os.path.exists

        def _exists(p):
            if p in ('app.py', 'config.py', 'requirements.txt'):
                return False
            return real_exists(p)

        monkeypatch.setattr(os.path, 'exists', _exists)
        with tenant_test_context(app, test_tenant):
            result = mod.get_system_health_score()
        assert isinstance(result, dict)

    def test_get_security_threats_returns_list(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_security_threats

        with self._ctx(app, test_tenant):
            assert isinstance(get_security_threats(), list)

    def test_get_security_threats_medium_branch(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        values = iter([11, 0])

        def _execute(*a, **k):
            return _FakeResult(next(values))

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            threats = mod.get_security_threats()
        assert isinstance(threats, list)
        assert any(t.get('type') == 'medium' for t in threats)

    def test_get_security_threats_branches(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        values = iter([21, 1])

        def _execute(*a, **k):
            return _FakeResult(next(values))

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            threats = mod.get_security_threats()
        assert isinstance(threats, list)
        assert len(threats) >= 2, f'threats={threats}'

    def test_get_performance_optimization_returns_list(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_performance_optimization

        with self._ctx(app, test_tenant):
            assert isinstance(get_performance_optimization(), list)

    def test_get_performance_optimization_branches(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        peak_row = SimpleNamespace(hour=1, count=16)
        dept_row = SimpleNamespace(count=21, department_id=1)
        values = iter([[peak_row], [dept_row]])

        def _execute(*a, **k):
            return _FakeResult(next(values))

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            opts = mod.get_performance_optimization()
        assert isinstance(opts, list)
        assert len(opts) >= 2, f'opts={opts}'

    def test_get_performance_optimization_peak_inner_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        n = {'i': 0}

        def _execute(*a, **k):
            n['i'] += 1
            if n['i'] == 1:
                raise RuntimeError('peak failed')
            return _FakeResult([])

        with tenant_test_context(app, test_tenant):
            monkeypatch.setattr(mod.db.session, 'execute', _execute, raising=False)
            opts = mod.get_performance_optimization()
        assert isinstance(opts, list)

    def test_get_user_behavior_analysis_shape(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_user_behavior_analysis
        from tests.tenant_context import ensure_test_user

        with self._ctx(app, test_tenant):
            u = ensure_test_user(db, test_tenant, username='ub_cov_user', role='doctor')
            u.last_login = datetime.now()
            u2 = ensure_test_user(db, test_tenant, username='ub_cov_user2', role='doctor')
            u2.last_login = None
            db.session.commit()
            result = get_user_behavior_analysis()
            assert isinstance(result, dict)
            assert 'role_distribution' in result
            assert 'engagement_rate' in result

    def test_get_resource_utilization_keys(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.analytics import get_resource_utilization

        with self._ctx(app, test_tenant):
            result = get_resource_utilization()
            assert isinstance(result, dict)
            for key in ('memory', 'cpu', 'disk', 'database', 'status'):
                assert key in result
            assert result['database']['total_users'] >= 0

    # ---------------------------------------------------------------------------
    # Exception paths for helpers
    # ---------------------------------------------------------------------------

    def test_get_total_users_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_total_users() == 0

    def test_get_active_users_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_active_users() == 0

    def test_get_inactive_users_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_inactive_users() == 0

    def test_get_admin_users_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_admin_users() == 0

    def test_get_active_sessions_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        monkeypatch.setattr(
            mod, 'get_active_users', lambda: (_ for _ in ()).throw(RuntimeError('x'))
        )
        with tenant_test_context(app, test_tenant):
            assert mod.get_active_sessions() == 0

    def test_get_security_events_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_security_events() == 0

    def test_get_ai_insights_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_ai_insights() == {}

    def test_get_smart_recommendations_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_smart_recommendations() == []

    def test_get_predictive_analytics_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_predictive_analytics() == {}

    def test_get_system_health_score_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            result = mod.get_system_health_score()
        assert result == {'score': 0, 'status': 'غير محدد', 'color': 'secondary'}

    def test_get_security_threats_exception(self, app, db, test_tenant, rollback_db, monkeypatch):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_security_threats() == []

    def test_get_performance_optimization_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_performance_optimization() == []

    def test_get_user_behavior_analysis_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_user_behavior_analysis() == {}

    def test_get_resource_utilization_psutil_and_db_exception(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        import psutil

        import routes.super_admin.analytics as mod

        def _boom(*a, **k):
            raise RuntimeError('q failed')

        monkeypatch.setattr(
            psutil,
            'virtual_memory',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('psutil failed')),
        )
        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        with tenant_test_context(app, test_tenant):
            assert mod.get_resource_utilization() == {}
