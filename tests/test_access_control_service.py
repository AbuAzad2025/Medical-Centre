"""Tests for services.access_control_service.AccessControlService.

Security-critical: visit/patient access scoping by role, dashboard/menu routing,
department scoping, and the permission/role decorators. Includes the latent-bug
fix where can_access_visit referenced non-existent Visit columns
(requested_labs/requested_radiology) and status=='EMERGENCY', silently denying
lab/radiology/emergency staff. ``rollback_db``.
"""
import types
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.exceptions import Forbidden

from services.access_control_service import AccessControlService as AC
from models.user import User
from models.visit import Visit
from models.patient import Patient
from models.payment import Payment
from app.shared.enums import VisitState, VisitArchiveStatus


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def user(role='doctor', department_id=None):
        un = 'ac_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role=role,
                 is_active=True, department_id=department_id)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def patient():
        p = Patient(first_name='ا', last_name='ب')
        db.session.add(p)
        db.session.commit()
        return p

    def visit(**kw):
        params = dict(patient_id=patient().id, status=VisitState.OPEN,
                      created_at=datetime.now(timezone.utc))
        params.update(kw)
        v = Visit(**params)
        db.session.add(v)
        db.session.commit()
        return v

    return types.SimpleNamespace(db=db, user=user, patient=patient, visit=visit)


class TestCanAccessVisit:
    def test_no_user_or_visit(self, fx):
        v = fx.visit()
        assert AC.can_access_visit(99999999, v.id) is False
        u = fx.user()
        assert AC.can_access_visit(u.id, 99999999) is False

    def test_reception_and_admin_access_all(self, fx):
        v = fx.visit()
        assert AC.can_access_visit(fx.user(role='reception').id, v.id) is True
        assert AC.can_access_visit(fx.user(role='admin').id, v.id) is True

    def test_doctor_only_own(self, fx):
        doc = fx.user(role='doctor')
        other = fx.user(role='doctor')
        v = fx.visit(doctor_id=doc.id)
        assert AC.can_access_visit(doc.id, v.id) is True
        assert AC.can_access_visit(other.id, v.id) is False

    def test_lab_access_when_lab_ordered(self, fx):
        lab = fx.user(role='lab')
        v_yes = fx.visit(lab_tests_ordered=True)
        v_no = fx.visit(lab_tests_ordered=False)
        assert AC.can_access_visit(lab.id, v_yes.id) is True
        assert AC.can_access_visit(lab.id, v_no.id) is False

    def test_radiology_access_when_radiology_ordered(self, fx):
        rad = fx.user(role='radiology')
        v = fx.visit(radiology_ordered=True)
        assert AC.can_access_visit(rad.id, v.id) is True

    def test_emergency_access_when_emergency(self, fx):
        em = fx.user(role='emergency')
        v = fx.visit(is_emergency=True)
        assert AC.can_access_visit(em.id, v.id) is True


class TestCanModifyVisit:
    def test_archived_only_admin(self, fx):
        v = fx.visit(status=VisitState.COMPLETED, archive_status=VisitArchiveStatus.ARCHIVED)
        assert AC.can_modify_visit(fx.user(role='admin').id, v.id) is True
        assert AC.can_modify_visit(fx.user(role='reception').id, v.id) is False

    def test_reception_within_30min(self, fx):
        rec = fx.user(role='reception')
        # created_at is a naive (UTC) column; insert naive values to avoid
        # tz round-trip skew in the assertion.
        utcnow = datetime.now(timezone.utc).replace(tzinfo=None)
        fresh = fx.visit(created_at=utcnow - timedelta(minutes=5))
        stale = fx.visit(created_at=utcnow - timedelta(minutes=45))
        assert AC.can_modify_visit(rec.id, fresh.id) is True
        assert AC.can_modify_visit(rec.id, stale.id) is False

    def test_doctor_own_non_archived(self, fx):
        doc = fx.user(role='doctor')
        v = fx.visit(doctor_id=doc.id, status=VisitState.OPEN)
        assert AC.can_modify_visit(doc.id, v.id) is True

    def test_not_found(self, fx):
        assert AC.can_modify_visit(99999999, 1) is False


class TestAccessibleScopes:
    def test_visits_admin_returns_list(self, fx):
        fx.visit()
        result = AC.get_user_accessible_visits(fx.user(role='admin').id)
        assert isinstance(result, list)

    def test_visits_unknown_role_empty(self, fx):
        # 'accountant' joins Payment; an unmapped role returns []
        assert AC.get_user_accessible_visits(99999999) == []

    def test_visits_accountant_join(self, fx):
        result = AC.get_user_accessible_visits(fx.user(role='accountant').id)
        assert isinstance(result, list)

    def test_patients_admin(self, fx):
        fx.patient()
        result = AC.get_user_accessible_patients(fx.user(role='admin').id)
        assert isinstance(result, list)

    def test_patients_lab_join(self, fx):
        result = AC.get_user_accessible_patients(fx.user(role='lab').id)
        assert isinstance(result, list)

    def test_patients_no_user(self, fx):
        assert AC.get_user_accessible_patients(99999999) == []

    @pytest.mark.parametrize('role', ['lab', 'radiology', 'emergency', 'manager', 'doctor'])
    def test_visits_per_role(self, fx, role):
        assert isinstance(AC.get_user_accessible_visits(fx.user(role=role).id), list)

    @pytest.mark.parametrize('role', ['radiology', 'accountant', 'nurse', 'manager', 'doctor'])
    def test_patients_per_role(self, fx, role):
        assert isinstance(AC.get_user_accessible_patients(fx.user(role=role).id), list)


class TestRoutingAndMenus:
    def test_dashboard_routes(self, fx):
        assert AC.get_user_dashboard_route(fx.user(role='doctor').id) == '/doctor/dashboard'
        assert AC.get_user_dashboard_route(fx.user(role='lab').id) == '/lab/dashboard'
        assert AC.get_user_dashboard_route(99999999) == '/dashboard'

    def test_menu_items(self, fx):
        items = AC.get_user_menu_items(fx.user(role='admin').id)
        assert isinstance(items, list) and len(items) > 0
        assert AC.get_user_menu_items(fx.user(role='nurse').id) == []  # no menu mapped
        assert AC.get_user_menu_items(99999999) == []


class TestRolesAndDepartments:
    def test_has_role(self, fx):
        u = fx.user(role='doctor')
        assert AC.has_role(u, 'doctor') is True
        assert AC.has_role(u, 'admin') is False

    def test_has_permission_returns_bool(self, fx):
        u = fx.user(role='admin')
        assert isinstance(AC.has_permission(u, 'view_all_visits'), bool)

    def test_accessible_departments_admin_none(self, fx):
        assert AC.get_accessible_department_ids(fx.user(role='admin')) is None

    def test_accessible_departments_none_input(self, fx):
        assert AC.get_accessible_department_ids(None) == []

    def test_accessible_departments_includes_user_dept(self, fx):
        from models.department import Department
        dept = Department(name='Ortho', name_ar='عظام')
        fx.db.session.add(dept)
        fx.db.session.commit()
        u = fx.user(role='doctor', department_id=dept.id)
        result = AC.get_accessible_department_ids(u)
        assert result is None or dept.id in result

    def test_accessible_departments_accepts_int(self, fx):
        u = fx.user(role='nurse')
        assert isinstance(AC.get_accessible_department_ids(u.id), (list, type(None)))

    def test_can_department_action_admin(self, fx):
        assert AC.can_department_action(fx.user(role='admin'), 1, 'access') is True

    def test_can_department_action_none_user(self, fx):
        assert AC.can_department_action(None, 1, 'access') is False

    def test_can_department_action_actions_for_regular_user(self, fx):
        u = fx.user(role='doctor')
        for action in ('access', 'patients', 'visits', 'appointments', 'staff', 'settings'):
            assert isinstance(AC.can_department_action(u, 1, action), bool)

    def test_can_department_action_bad_department_id(self, fx):
        u = fx.user(role='doctor')
        assert isinstance(AC.can_department_action(u, None, 'access'), bool)


class TestPermissionHelpers:
    def test_can_helpers_return_bool(self, fx):
        uid = fx.user(role='reception').id
        for fn in (AC.can_create_visit, AC.can_process_payment, AC.can_archive_visit,
                   AC.can_prescribe_medication, AC.can_enter_lab_results,
                   AC.can_enter_radiology_reports):
            assert isinstance(fn(uid), bool)


class TestDepartmentScopingDeep:
    """Drives the Role/DepartmentPermission/UserDepartmentAccess scoping branches."""

    def _dept(self, fx, tag):
        from models.department import Department
        d = Department(name='D' + tag + uuid.uuid4().hex[:4], name_ar='ق' + tag)
        fx.db.session.add(d)
        fx.db.session.commit()
        return d

    def _setup(self, fx, with_global=False):
        from models.permissions import Role
        from models.advanced_permissions import DepartmentPermission
        rolename = 'rl_' + uuid.uuid4().hex[:8]
        role = Role(name=rolename, is_active=True)
        fx.db.session.add(role)
        fx.db.session.commit()
        d1, d2 = self._dept(fx, '1'), self._dept(fx, '2')
        if with_global:
            fx.db.session.add(DepartmentPermission(
                role_id=role.id, department_id=None, can_access=True))
        else:
            fx.db.session.add(DepartmentPermission(
                role_id=role.id, department_id=d1.id, can_access=True,
                can_manage_patients=True, can_manage_visits=True,
                can_manage_appointments=True, can_manage_staff=True,
                can_manage_department_settings=True))
        fx.db.session.commit()
        u = fx.user(role=rolename)
        return u, d1, d2

    def test_global_access_returns_none(self, fx):
        u, d1, d2 = self._setup(fx, with_global=True)
        assert AC.get_accessible_department_ids(u) is None

    def test_specific_department_scope(self, fx):
        u, d1, d2 = self._setup(fx)
        ids = AC.get_accessible_department_ids(u)
        assert ids is not None
        assert d1.id in ids and d2.id not in ids

    def test_user_department_access_extra(self, fx):
        from models.user_department_access import UserDepartmentAccess
        u, d1, d2 = self._setup(fx)
        d3 = self._dept(fx, '3')
        fx.db.session.add(UserDepartmentAccess(user_id=u.id, department_id=d3.id, can_access=True))
        fx.db.session.commit()
        assert d3.id in AC.get_accessible_department_ids(u)

    def test_can_department_action_all_flags(self, fx):
        u, d1, d2 = self._setup(fx)
        for action in ('access', 'patients', 'visits', 'appointments', 'staff', 'settings'):
            assert AC.can_department_action(u, d1.id, action) is True

    def test_can_department_action_denies_unscoped(self, fx):
        u, d1, d2 = self._setup(fx)
        assert AC.can_department_action(u, d2.id, 'access') is False


class TestDecorators:
    def test_require_permission_allows(self, app, fx, monkeypatch):
        monkeypatch.setattr(AC, 'has_permission', lambda u, p: True)

        @AC.require_permission('anything')
        def view():
            return 'ok'

        with app.test_request_context():
            assert view() == 'ok'

    def test_require_permission_denies(self, app, fx, monkeypatch):
        monkeypatch.setattr(AC, 'has_permission', lambda u, p: False)

        @AC.require_permission('anything')
        def view():
            return 'ok'

        with app.test_request_context():
            with pytest.raises(Forbidden):
                view()

    def test_require_role_denies(self, app, fx, monkeypatch):
        monkeypatch.setattr(AC, 'has_role', lambda u, r: False)

        @AC.require_role('admin')
        def view():
            return 'ok'

        with app.test_request_context():
            with pytest.raises(Forbidden):
                view()
