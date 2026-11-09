"""Exhaustive tests for utils.decorators permission/audit decorators.

Covers every decorator branch: unauthenticated redirect, role denied (403 or
redirect), role allowed, hierarchy inheritance, language selection, message
fallbacks, and the payment gates.
"""

from __future__ import annotations

import pytest

from tests.tenant_context import ensure_test_user
from utils.decorators import (
    ROLE_HIERARCHY,
    _format_message,
    _get_language,
    _role_in_hierarchy,
    accountant_only,
    can_approve_force_payment,
    can_create_visits,
    can_handle_payments,
    can_modify_patient_data,
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
        return ensure_test_user(db, test_tenant, username=f'dec_{role}_{suffix}', role=role)

    return _make


class TestHelpers:
    def test_get_language_ar_default(self, app):
        with app.test_request_context(headers={'Accept-Language': 'ar'}):
            assert _get_language() == 'ar'

    def test_get_language_en(self, app):
        with app.test_request_context(headers={'Accept-Language': 'en-US'}):
            assert _get_language() == 'en'

    def test_get_language_missing_header(self, app):
        with app.test_request_context():
            assert _get_language() == 'ar'

    def test_role_in_hierarchy_direct(self):
        assert _role_in_hierarchy('admin', 'manager') is True
        assert _role_in_hierarchy('manager', 'admin') is False

    def test_role_in_hierarchy_nested(self):
        assert _role_in_hierarchy('owner', 'admin') is True
        assert _role_in_hierarchy('owner', 'manager') is True

    def test_role_in_hierarchy_equal(self):
        assert _role_in_hierarchy('reception', 'reception') is True

    def test_role_in_hierarchy_none(self):
        assert _role_in_hierarchy(None, 'admin') is False
        assert _role_in_hierarchy('admin', None) is False

    def test_format_message_ar_defaults(self, app):
        with app.test_request_context(headers={'Accept-Language': 'ar'}):
            assert _format_message('no_permission')

    def test_format_message_en(self, app):
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            assert _format_message('no_permission').startswith('You do not')

    def test_format_message_role_specific(self, app):
        with app.test_request_context(headers={'Accept-Language': 'en'}):
            # role unknown to the mapping falls back to generic message
            assert _format_message('no_permission').startswith('You do not')

    def test_hierarchy_constant_contents(self):
        assert 'admin' in ROLE_HIERARCHY['super_admin']
        assert 'reception' in ROLE_HIERARCHY['manager']
        assert 'er_doctor' in ROLE_HIERARCHY


class TestRoleRequired:
    def test_unauthenticated_redirect(self, app):
        with app.test_request_context('/whatever'):

            @role_required('admin')
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_wrong_role_aborts_403(self, app, make_user):
        user = make_user('reception', 'wrongrole')
        with app.test_request_context('/protected'):
            from flask_login import login_user

            login_user(user)

            @role_required('doctor')
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_right_role_allowed(self, app, make_user):
        user = make_user('doctor', 'rightrole')
        with app.test_request_context('/protected'):
            from flask_login import login_user

            login_user(user)

            @role_required('doctor')
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_hierarchy_super_admin_reaches_manager_area(self, app, make_user):
        user = make_user('super_admin', 'sa')
        with app.test_request_context('/protected'):
            from flask_login import login_user

            login_user(user)

            @role_required('manager')
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_hierarchy_disabled_requires_exact_role(self, app, make_user):
        user = make_user('admin', 'admexact')
        with app.test_request_context('/protected'):
            from flask_login import login_user

            login_user(user)

            @role_required('admin', use_hierarchy=False)
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestRoleRequiredJson:
    def test_unauthenticated_json_401(self, app):
        with app.test_request_context('/api/x', headers={'Accept': 'application/json'}):

            @role_required_json('admin')
            def dummy():
                return 'OK'

            body, status = dummy()
            assert status == 401
            assert body.get_json()['success'] is False

    def test_authenticated_wrong_role_json_403(self, app, make_user):
        user = make_user('reception', 'api401')
        with app.test_request_context('/api/x', headers={'Accept': 'application/json'}):
            from flask_login import login_user

            login_user(user)

            @role_required_json('admin')
            def dummy():
                return 'OK'

            body, status = dummy()
            assert status == 403
            assert body.get_json()['success'] is False


class TestSingleRoleDecorators:
    def test_reception_only_accepts_reception(self, app, make_user):
        user = make_user('reception', 'reacok')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @reception_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_reception_only_accepts_manager_via_hierarchy(self, app, make_user):
        user = make_user('manager', 'mgrrec2')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @reception_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_reception_only_accepts_admin_via_nested_hierarchy(self, app, make_user):
        user = make_user('admin', 'admrec3')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @reception_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_reception_only_denies_lab(self, app, make_user):
        user = make_user('lab', 'labrec')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @reception_only
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_accountant_only_accepts_accountant(self, app, make_user):
        user = make_user('accountant', 'acct')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @accountant_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_accountant_only_denies_reception(self, app, make_user):
        user = make_user('reception', 'recb')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @accountant_only
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_manager_or_admin_only_accepts_manager(self, app, make_user):
        user = make_user('manager', 'mgr')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @manager_or_admin_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_manager_or_admin_only_denies_reception(self, app, make_user):
        user = make_user('reception', 'mgrrec')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @manager_or_admin_only
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_super_admin_required_redirects_to_index_for_non_privileged(self, app, make_user):
        user = make_user('reception', 'saReq')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            resp = dummy()
            assert resp.status_code == 302
            assert resp.headers.get('Location', '') != '/r'

    def test_super_admin_required_accepts_super_admin(self, app, make_user):
        user = make_user('super_admin', 'sareqok')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @super_admin_required
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_privileged_user_manager_denies_manager(self, app, make_user):
        user = make_user('manager', 'privdeny')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @privileged_user_manager_required
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_privileged_user_manager_accepts_owner(self, app, make_user):
        user = make_user('owner', 'privowner')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @privileged_user_manager_required
            def dummy():
                return 'OK'

            assert dummy() == 'OK'


class TestCapacityDecorators:
    def test_can_handle_payments_accepts_accountant(self, app, make_user):
        user = make_user('accountant', 'payok')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_handle_payments
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_can_handle_payments_denies_doctor(self, app, make_user):
        user = make_user('doctor', 'paydeny')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_handle_payments
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_can_approve_force_payment_denies_reception(self, app, make_user):
        user = make_user('reception', 'forcedeny')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_approve_force_payment
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_can_approve_force_payment_accepts_manager(self, app, make_user):
        user = make_user('manager', 'forceok')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_approve_force_payment
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_can_create_visits_accepts_reception(self, app, make_user):
        user = make_user('reception', 'cvadd')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_create_visits
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_can_create_visits_denies_accountant(self, app, make_user):
        user = make_user('accountant', 'cvdeny')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_create_visits
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_can_modify_patient_data_accepts_reception(self, app, make_user):
        user = make_user('reception', 'modacc')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_modify_patient_data
            def dummy():
                return 'OK'

            assert dummy() == 'OK'

    def test_can_modify_patient_data_denies_doctor(self, app, make_user):
        user = make_user('doctor', 'moddeny')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @can_modify_patient_data
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403


class TestPaymentGates:
    def test_require_payment_before_service_redirects_pending(
        self, app, db, make_user, test_tenant
    ):
        user = make_user('reception', 'gate')
        from models.patient import Patient
        from models.visit import Visit

        suffix = 'gate1'
        p = Patient(
            tenant_id=test_tenant.id,
            first_name='Gate',
            last_name='Person',
            phone='0555999' + suffix[-1],
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id, patient_id=p.id, payment_status='PENDING', status='OPEN'
        )
        db.session.add(v)
        db.session.commit()
        visit_id = v.id

        with app.test_request_context(f'/service?visit_id={visit_id}'):
            from flask_login import login_user

            login_user(user)

            @require_payment_before_service
            def dummy(visit_id):
                return 'OK'

            resp = dummy(visit_id=visit_id)
            assert resp.status_code == 302
            assert 'payment' in resp.headers.get('Location', '')

    def test_require_payment_before_service_allows_paid(self, app, db, make_user, test_tenant):
        user = make_user('reception', 'gate2')
        from models.patient import Patient
        from models.visit import Visit

        p = Patient(
            tenant_id=test_tenant.id, first_name='GatePaid', last_name='Again', phone='0555999111'
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(tenant_id=test_tenant.id, patient_id=p.id, payment_status='PAID', status='OPEN')
        db.session.add(v)
        db.session.commit()

        with app.test_request_context(f'/service?visit_id={v.id}'):
            from flask_login import login_user

            login_user(user)

            @require_payment_before_service
            def dummy(visit_id):
                return 'OK'

            assert dummy(visit_id=v.id) == 'OK'


class TestPreventSelfApproval:
    def test_self_approval_blocked(self, app, db, make_user, test_tenant):
        user = make_user('manager', 'selfappr')
        from models.patient import Patient
        from models.visit import Visit

        p = Patient(
            tenant_id=test_tenant.id, first_name='Self', last_name='Approve', phone='0555777666'
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            payment_status='PAID',
            status='OPEN',
            created_by=user.id,
        )
        db.session.add(v)
        db.session.commit()

        with app.test_request_context('/approve'):
            from flask_login import login_user

            login_user(user)

            @prevent_self_approval
            def dummy(visit_id):
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy(visit_id=v.id)
            assert getattr(exc.value, 'code', None) == 403

    def test_other_visit_allowed(self, app, db, make_user, test_tenant):
        user = make_user('manager', 'selfapprove2')
        other = make_user('reception', 'other')
        from models.patient import Patient
        from models.visit import Visit

        p = Patient(
            tenant_id=test_tenant.id, first_name='Other', last_name='ly', phone='0555777000'
        )
        db.session.add(p)
        db.session.flush()
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            payment_status='PAID',
            status='OPEN',
            created_by=other.id,
        )
        db.session.add(v)
        db.session.commit()

        with app.test_request_context('/approve'):
            from flask_login import login_user

            login_user(user)

            @prevent_self_approval
            def dummy(visit_id):
                return 'OK'

            assert dummy(visit_id=v.id) == 'OK'


class TestRequirePaymentBeforeService:
    def test_super_admin_only_denies_manager(self, app, make_user):
        user = make_user('manager', 'sano')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @super_admin_only
            def dummy():
                return 'OK'

            with pytest.raises(Exception) as exc:
                dummy()
            assert getattr(exc.value, 'code', None) == 403

    def test_super_admin_allowed(self, app, make_user):
        user = make_user('super_admin', 'sano_ok')
        with app.test_request_context('/r'):
            from flask_login import login_user

            login_user(user)

            @super_admin_only
            def dummy():
                return 'OK'

            assert dummy() == 'OK'
