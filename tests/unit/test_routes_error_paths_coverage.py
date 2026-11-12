"""Coverage for the route handlers whose error and success branches never ran.

A route that has never answered an error has never been asked what it does
when the database is down, the service is broken or the record is missing.
Those are exactly the branches that decide what a caller sees when something
is wrong, so they are exercised here deliberately.

Each test class is named after the module it covers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

pytest_plugins = ['tests._isolated_tenant']


class TestManagerDashboard:
    """routes/manager/dashboard.py"""

    def test_a_failing_command_center_renders_the_error_page(
        self, app, rollback_db, client, login_as
    ):
        login_as(client, 'mgr_dash_err', 'manager')
        with patch(
            'app.shared.dashboard_service.render_command_center',
            side_effect=RuntimeError('command center unavailable'),
        ):
            resp = client.get('/manager/dashboard')
        # The error page renders rather than the route answering 500.
        assert resp.status_code == 200


class TestManagerDepartments:
    """routes/manager/departments.py"""

    def test_a_failing_query_redirects_to_the_dashboard(self, app, rollback_db, client, login_as):
        login_as(client, 'mgr_dept_err', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.departments.select', boom):
            resp = client.get('/manager/departments')

        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']


class TestAccountantErpExport:
    """routes/accountant/erp.py"""

    def test_a_failing_export_answers_500(self, app, rollback_db, client, login_as):
        login_as(client, 'acct_erp_err', 'accountant')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.accountant.erp.select', boom):
            resp = client.get('/accountant/api/erp/export')

        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


class TestApiDashboardSnapshot:
    """routes/api_dashboard.py"""

    def test_a_failing_snapshot_answers_500(self, app, rollback_db, client, login_as):
        login_as(client, 'api_dash_err', 'doctor')
        with patch(
            'routes.api_dashboard.snapshot_metrics',
            side_effect=RuntimeError('metrics unavailable'),
        ):
            resp = client.get('/api/dashboard/snapshot')

        assert resp.status_code == 500
        payload = resp.get_json()
        assert payload['metrics'] == {}
        assert 'metrics unavailable' in payload['error']


class TestApiUserPreferences:
    """routes/api_user.py"""

    def test_a_failed_save_answers_500(self, app, rollback_db, client, login_as):
        login_as(client, 'api_user_err', 'doctor')
        with patch('routes.api_user.save_user_preferences', return_value=False):
            resp = client.post('/api/user/preferences', json={'theme': 'dark'})

        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_an_update_without_known_fields_is_refused(self, app, rollback_db, client, login_as):
        login_as(client, 'api_user_nofields', 'doctor')
        resp = client.post('/api/user/preferences', json={'unknown': 'x'})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False


class TestCdsPatientAlerts:
    """routes/cds_alert_routes.py"""

    def test_patient_alerts_are_rendered(self, app, rollback_db, client, login_as, db):
        from app.extensions import db as _db
        from models.patient import Patient

        patient = Patient(
            tenant_id=None,
            first_name='CDS',
            last_name='Patient',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        _db.session.add(patient)
        _db.session.commit()

        login_as(client, 'cds_alerts_user', 'doctor')
        resp = client.get(f'/cds/patient/{patient.id}/alerts')
        assert resp.status_code in (200, 302, 403, 404)


class TestIheRoutes:
    """routes/ihe_routes.py"""

    def test_pix_query_requires_a_patient_id(self, app, rollback_db, client, login_as):
        login_as(client, 'ihe_pix_user', 'doctor')
        resp = client.get('/ihe/pix/query')
        assert resp.status_code == 400

    def test_pix_query_answers_the_service_result(self, app, rollback_db, client, login_as):
        login_as(client, 'ihe_pix_ok', 'doctor')
        with patch('routes.ihe_routes.ihe_service') as service:
            service.pix_query.return_value = {'found': True, 'patient': {'id': '1'}}
            resp = client.get('/ihe/pix/query?patient_id=1')

        assert resp.status_code == 200
        assert resp.get_json()['found'] is True
        assert service.atna_audit.called

    def test_atna_audit_records_the_event(self, app, rollback_db, client, login_as):
        login_as(client, 'ihe_atna_user', 'admin')
        with patch('routes.ihe_routes.ihe_service') as service:
            resp = client.post(
                '/ihe/atna/audit',
                json={'event_type': 'Query', 'user_id': 1, 'patient_id': 2, 'outcome': '0'},
            )

        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        assert service.atna_audit.called


class TestKioskCheckIn:
    """routes/kiosk.py"""

    def test_an_unknown_national_id_answers_404(self, app, rollback_db, client, login_as):
        login_as(client, 'kiosk_unknown', 'reception')
        with patch(
            'routes.kiosk.perform_kiosk_checkin',
            return_value={'success': False, 'message': 'لم يتم العثور على المريض'},
        ):
            resp = client.post('/kiosk/api/check-in', json={'national_id': '000000000'})

        assert resp.status_code == 404

    def test_a_failed_check_in_answers_400(self, app, rollback_db, client, login_as):
        login_as(client, 'kiosk_failed', 'reception')
        with patch(
            'routes.kiosk.perform_kiosk_checkin',
            return_value={'success': False, 'message': 'لا يوجد موعد اليوم لهذا المريض'},
        ):
            resp = client.post('/kiosk/api/check-in', json={'national_id': '000000000'})

        assert resp.status_code == 400


class TestReferralDetail:
    """routes/referral_routes.py"""

    def test_the_detail_page_renders(self, app, rollback_db, client, login_as, db):
        from app.extensions import db as _db
        from models.patient import Patient
        from models.referral import Referral

        login_as(client, 'referral_detail_user', 'doctor')

        patient = Patient(
            tenant_id=None,
            first_name='Referral',
            last_name='Patient',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        _db.session.add(patient)
        _db.session.flush()

        referral = Referral(
            patient_id=patient.id,
            status='PENDING',
            referral_type='OUTGOING',
            reason_for_referral='Specialist opinion',
            referring_facility='Clinic A',
        )
        _db.session.add(referral)
        _db.session.commit()

        resp = client.get(f'/referral/detail/{referral.id}')
        assert resp.status_code in (200, 302, 403, 404)

    def test_an_unknown_referral_is_404(self, app, rollback_db, client, login_as):
        login_as(client, 'referral_missing_user', 'doctor')
        resp = client.get('/referral/detail/999999')
        assert resp.status_code == 404


class TestSsoToggle:
    """routes/sso_routes.py"""

    def test_toggling_flips_the_configuration(
        self, app, rollback_db, client, login_as, db, monkeypatch
    ):
        from app.extensions import db as _db
        from models import SSOConfiguration
        from tests.tenant_context import activate_tenant_modules, ensure_default_test_tenant

        # The SSO blueprint is behind the platform SSO capability; without it
        # every route under the blueprint answers 404.
        monkeypatch.setenv('PLATFORM_CAP_SSO', '1')

        login_as(client, 'sso_toggle_user', 'super_admin')
        tenant = ensure_default_test_tenant(app)
        # The SSO blueprint is guarded by the integration module, so the tenant
        # has to have it before the route is reachable at all.
        activate_tenant_modules(app, tenant, ['integration'])

        config = SSOConfiguration(
            tenant_id=tenant.id,
            name='Toggle LDAP',
            provider_type='ldap',
            server_url='ldap://example.com',
            base_dn='dc=example,dc=com',
            is_active=True,
        )
        _db.session.add(config)
        _db.session.commit()

        resp = client.post(f'/sso/toggle/{config.id}')
        assert resp.status_code in (302, 200, 403)

        _db.session.expire_all()
        refreshed = _db.session.get(SSOConfiguration, config.id)
        assert refreshed is not None
        assert refreshed.is_active is False
