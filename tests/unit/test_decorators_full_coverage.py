"""
Full-coverage tests for utils.decorators.

Complements tests/unit/test_decorators_permissions.py (44 tests) without
duplicating it. Covers every remaining decorator/branch:

* previously untested decorators: super_admin_required, can_delete_patient,
  can_access_financial_reports, can_archive_visits, handle_route_errors
* unauthenticated redirect branch of every single-role / capacity decorator
* _format_message role-specific (doctor/nurse/lab/radiology) and the
  current_user.role access except-fallback branches
* require_payment_before_service: no visit_id, missing visit, and the
  force-payment-unapproved branch
* prevent_self_approval: no visit_id and missing visit
* role_required / role_required_json: non-JSON branches and multi-role use
"""

from __future__ import annotations

import pytest
from flask_login import login_user
from werkzeug.exceptions import HTTPException

from tests.tenant_context import ensure_test_user
from utils.decorators import (
    _format_message,
    accountant_only,
    can_access_financial_reports,
    can_approve_force_payment,
    can_archive_visits,
    can_create_visits,
    can_delete_patient,
    can_handle_payments,
    can_modify_patient_data,
    handle_route_errors,
    manager_or_admin_only,
    prevent_self_approval,
    privileged_user_manager_required,
    reception_only,
    require_payment_before_service,
    role_required,
    role_required_json,
    super_admin_only,
    super_admin_required,
)


@pytest.fixture
def make_user(app, db, test_tenant):
    def _make(role, suffix='1'):
        return ensure_test_user(db, test_tenant, username=f'full_{role}_{suffix}', role=role)

    return _make


class TestHelpersExtra:
    def test_format_message_doctor_role(self, app, make_user):
        user = make_user('doctor', 'docmsg')
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            login_user(user)
            assert 'clinical' in _format_message('no_permission')

    def test_format_message_nurse_role(self, app, make_user):
        user = make_user('nurse', 'nursemsg')
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            login_user(user)
            assert 'nursing' in _format_message('no_permission')

    def test_format_message_lab_role(self, app, make_user):
        user = make_user('lab', 'labmsg')
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            login_user(user)
            assert 'laboratory' in _format_message('no_permission')

    def test_format_message_radiology_role(self, app, make_user):
        user = make_user('radiology', 'radmsg')
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            login_user(user)
            assert 'imaging' in _format_message('no_permission')

    def test_format_message_unknown_key_fallback(self, app):
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            assert _format_message('does_not_exist').startswith('You do not')

    def test_format_message_current_user_role_raises(self, app, monkeypatch):
        from utils import decorators

        class _RoleRaises:
            is_authenticated = True

            @property
            def role(self):
                raise RuntimeError('no role')

        monkeypatch.setattr(decorators, 'current_user', _RoleRaises())
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            assert _format_message('no_permission').startswith('You do not')


class TestSuperAdminRequired:
    def test_unauthenticated_redirect(self, app):
        with app.test_request_context('/r'):

            @super_admin_required
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_manager_redirected_to_index(self, app, make_user):
        user = make_user('manager', 'samgr')
        with app.test_request_context('/r'):
            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert resp.headers.get('Location', '') != '/r'

    def test_super_admin_allowed(self, app, make_user):
        user = make_user('super_admin', 'sasuper')
        with app.test_request_context('/r'):
            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_admin_allowed(self, app, make_user):
        user = make_user('admin', 'saadmin')
        with app.test_request_context('/r'):
            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_owner_allowed(self, app, make_user):
        user = make_user('owner', 'saowner')
        with app.test_request_context('/r'):
            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestCanDeletePatient:
    def test_unauthenticated_redirect(self, app):
        with app.test_request_context('/r'):

            @can_delete_patient
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_reception_denied(self, app, make_user):
        user = make_user('reception', 'delrec')
        with app.test_request_context('/r'):
            login_user(user)

            @can_delete_patient
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_doctor_denied(self, app, make_user):
        user = make_user('doctor', 'deldoc')
        with app.test_request_context('/r'):
            login_user(user)

            @can_delete_patient
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_manager_allowed(self, app, make_user):
        user = make_user('manager', 'delmgr')
        with app.test_request_context('/r'):
            login_user(user)

            @can_delete_patient
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_super_admin_allowed(self, app, make_user):
        user = make_user('super_admin', 'delsa')
        with app.test_request_context('/r'):
            login_user(user)

            @can_delete_patient
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_owner_allowed(self, app, make_user):
        user = make_user('owner', 'delown')
        with app.test_request_context('/r'):
            login_user(user)

            @can_delete_patient
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestCanAccessFinancialReports:
    def test_unauthenticated_redirect(self, app):
        with app.test_request_context('/r'):

            @can_access_financial_reports
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_reception_denied(self, app, make_user):
        user = make_user('reception', 'finrec')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_doctor_denied(self, app, make_user):
        user = make_user('doctor', 'findoc')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_owner_denied(self, app, make_user):
        user = make_user('owner', 'finown')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_accountant_allowed(self, app, make_user):
        user = make_user('accountant', 'finacct')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_manager_allowed(self, app, make_user):
        user = make_user('manager', 'finmgr')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_super_admin_allowed(self, app, make_user):
        user = make_user('super_admin', 'finsa')
        with app.test_request_context('/r'):
            login_user(user)

            @can_access_financial_reports
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestCanArchiveVisits:
    def test_unauthenticated_redirect(self, app):
        with app.test_request_context('/r'):

            @can_archive_visits
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_reception_allowed(self, app, make_user):
        user = make_user('reception', 'arcrec')
        with app.test_request_context('/r'):
            login_user(user)

            @can_archive_visits
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_manager_allowed(self, app, make_user):
        user = make_user('manager', 'arcmgr')
        with app.test_request_context('/r'):
            login_user(user)

            @can_archive_visits
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_super_admin_allowed(self, app, make_user):
        user = make_user('super_admin', 'arcsa')
        with app.test_request_context('/r'):
            login_user(user)

            @can_archive_visits
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_doctor_denied(self, app, make_user):
        user = make_user('doctor', 'arcdoc')
        with app.test_request_context('/r'):
            login_user(user)

            @can_archive_visits
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403


class TestRequirePaymentBeforeServiceExtra:
    def test_no_visit_id_calls_view(self, app):
        with app.test_request_context('/service'):

            @require_payment_before_service
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_missing_visit_calls_view(self, app, db):
        with app.test_request_context('/service?visit_id=999999'):

            @require_payment_before_service
            def dummy(visit_id):
                return 'OK'

            assert dummy(visit_id=999999) == 'OK'

    def test_force_payment_unapproved_redirects(self, app, db, make_user, test_tenant):
        user = make_user('reception', 'forcebuild')
        from models.patient import Patient
        from models.visit import Visit

        p = Patient(
            tenant_id=test_tenant.id,
            first_name='Force',
            last_name='Build',
            phone='0555123456',
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            payment_status='PENDING',
            status='OPEN',
            is_force_payment=True,
            force_payment_approved_by=None,
        )
        db.session.add(v)
        db.session.commit()
        visit_id = v.id

        with app.test_request_context(f'/service?visit_id={visit_id}'):
            login_user(user)

            @require_payment_before_service
            def dummy(visit_id):
                return 'OK'

            resp = dummy(visit_id=visit_id)
            assert resp.status_code == 302
            assert '/visits' in resp.headers.get('Location', '')


class TestPreventSelfApprovalExtra:
    def test_no_visit_id_calls_view(self, app):
        with app.test_request_context('/approve'):

            @prevent_self_approval
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_missing_visit_calls_view(self, app, db):
        with app.test_request_context('/approve'):

            @prevent_self_approval
            def dummy(visit_id):
                return 'OK'

            assert dummy(visit_id=999999) == 'OK'


class TestHandleRouteErrors:
    def test_passthrough_on_success(self, app):
        @handle_route_errors
        def dummy():
            return 'OK'

        assert dummy() == 'OK'

    def test_http_exception_re_raised(self, app):
        from werkzeug.exceptions import abort

        @handle_route_errors
        def dummy():
            abort(404)

        with pytest.raises(HTTPException) as exc:
            dummy()
        assert exc.value.code == 404

    def test_unexpected_error_returns_json_500(self, app, db):
        @handle_route_errors
        def dummy():
            raise RuntimeError('boom')

        with app.test_request_context('/x', headers={'Accept': 'application/json'}):
            body, status = dummy()
            assert status == 500
            assert body.get_json()['success'] is False

    def test_unexpected_error_redirects_to_referrer(self, app, db):
        @handle_route_errors
        def dummy():
            raise RuntimeError('boom')

        with app.test_request_context('/x', headers={'Referer': 'http://example.com/prev'}):
            resp = dummy()
            assert resp.status_code == 302
            assert resp.headers.get('Location') == 'http://example.com/prev'

    def test_unexpected_error_redirects_to_dashboard(self, app, db):
        @handle_route_errors
        def dummy():
            raise RuntimeError('boom')

        with app.test_request_context('/x'):
            resp = dummy()
            assert resp.status_code == 302
            assert resp.headers.get('Location', '').endswith('/dashboard')


class TestRoleRequiredJsonExtra:
    def test_unauthenticated_non_json_redirects(self, app):
        with app.test_request_context('/api/x'):

            @role_required_json('admin')
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_authenticated_wrong_role_non_json_aborts_403(self, app, make_user):
        user = make_user('reception', 'apinjson')
        with app.test_request_context('/api/x'):
            login_user(user)

            @role_required_json('admin')
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403


class TestRoleRequiredExtra:
    def test_multi_role_matches_second_role(self, app, make_user):
        user = make_user('doctor', 'multirole')
        with app.test_request_context('/protected'):
            login_user(user)

            @role_required('nurse', 'doctor')
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_use_hierarchy_false_denied(self, app, make_user):
        user = make_user('reception', 'noexact')
        with app.test_request_context('/protected'):
            login_user(user)

            @role_required('admin', use_hierarchy=False)
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403


class TestSingleRoleUnauthRedirects:
    @pytest.mark.parametrize(
        'decorator',
        [
            reception_only,
            accountant_only,
            manager_or_admin_only,
            can_handle_payments,
            can_approve_force_payment,
            can_create_visits,
            can_modify_patient_data,
            privileged_user_manager_required,
            super_admin_only,
        ],
    )
    def test_unauthenticated_redirects_to_login(self, app, decorator):
        with app.test_request_context('/r'):

            @decorator
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')
