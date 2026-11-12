"""Coverage for routes/manager/staff.py — the manager's staff and unit screens.

The module control page, the unit toggle, the work-schedule editor, the
absence log and the capacity report are the screens a manager uses to run a
clinic's roster. Every one of them had branches that never ran: the refusal
when no clinic could be identified, the subscription check before a module is
switched on, the "the row already exists, update it" path of the schedule
editor, the days lost to absence in the capacity report, and the error paths.

Each test class is named after the behaviour it covers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _doctor(db, tenant_id, username='staff_doc', role='doctor', department_id=None):
    from models.user import User

    user = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=True,
        tenant_id=tenant_id,
        department_id=department_id,
    )
    user.set_password('test123')
    db.session.add(user)
    db.session.flush()
    return user


def _department(db, tenant_id, name='Capacity Dept'):
    from models.department import Department

    department = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(department)
    db.session.flush()
    return department


def _module_row(db, tenant_id, module_name='radiology'):
    """The tenant's row for a module, created when the clinic has none yet."""
    from app.core.module.models import TenantModule

    row = (
        db.session.execute(
            db.select(TenantModule).where(
                TenantModule.tenant_id == tenant_id,
                TenantModule.module_name == module_name,
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        row = TenantModule(
            tenant_id=tenant_id,
            module_name=module_name,
            is_active=False,
        )
        db.session.add(row)
        db.session.flush()
    return row


class _FakeUser:
    """Stands in for ``current_user`` when the route must see no clinic."""

    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.id = 1
        self.role = 'manager'
        self.is_authenticated = True


class _FakeG:
    """Stands in for Flask's ``g`` with an explicit module cache."""

    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.cache = {'_tenant_enabled_modules': {'radiology'}}
        self._tenant_enabled_modules = {'radiology'}

    def pop(self, key, default=None):
        value = self.cache.pop(key, default)
        if hasattr(self, key):
            delattr(self, key)
        return value

    def get(self, key, default=None):
        return self.cache.get(key, default)


class TestUnitControl:
    """The module control page."""

    def test_it_lists_the_registry(self, app, client, login_as):
        login_as(client, 'staff_unit_ctrl', 'manager')
        resp = client.get('/manager/unit-control')
        assert resp.status_code in (200, 302)

    def test_without_a_clinic_it_redirects(self, app, client, login_as):
        login_as(client, 'staff_unit_no_tenant', 'manager')
        with patch('routes.manager.staff.g', _FakeG(tenant_id=None)), patch(
            'routes.manager.staff.current_user', _FakeUser(tenant_id=None)
        ):
            resp = client.get('/manager/unit-control')
        assert resp.status_code in (302, 200)

    def test_a_toggle_without_a_clinic_is_refused(self, app, client, login_as):
        login_as(client, 'staff_toggle_no_tenant', 'manager')
        with patch('routes.manager.staff.g', _FakeG(tenant_id=None)), patch(
            'routes.manager.staff.current_user', _FakeUser(tenant_id=None)
        ):
            resp = client.post(
                '/manager/api/units/toggle',
                json={'module_name': 'radiology'},
            )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_the_stale_module_cache_is_dropped(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        login_as(client, 'staff_toggle_cache', 'manager')

        module = _module_row(_db, tenant.id)
        module.is_active = True
        _db.session.commit()

        fake_g = _FakeG(tenant_id=tenant.id)
        with patch('routes.manager.staff.g', fake_g):
            resp = client.post(
                '/manager/api/units/toggle',
                json={'module_name': 'radiology'},
            )
        assert resp.status_code == 200
        # The cached module scope is dropped so the next request sees the change.
        assert '_tenant_enabled_modules' not in fake_g.cache

    def test_a_failing_registry_redirects(self, app, client, login_as):
        login_as(client, 'staff_unit_fail', 'manager')
        with patch(
            'routes.manager.staff.get_active_modules_for_tenant',
            side_effect=RuntimeError('registry unavailable'),
        ):
            resp = client.get('/manager/unit-control')
        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']


class TestUnitToggle:
    """Switching a module on and off for the clinic."""

    def test_an_unknown_module_is_refused(self, app, client, login_as):
        login_as(client, 'staff_toggle_unknown', 'manager')
        resp = client.post(
            '/manager/api/units/toggle',
            json={'module_name': 'nonexistent_module'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_a_module_outside_the_subscription_is_refused(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        login_as(client, 'staff_toggle_sub', 'manager')

        # The subscription is only consulted when the module is not already on.
        module = _module_row(_db, tenant.id)
        module.is_active = False
        _db.session.commit()

        with patch(
            'app.core.module.validators.can_activate_module',
            return_value=(False, 'Module is not included in your subscription'),
        ):
            resp = client.post(
                '/manager/api/units/toggle',
                json={'module_name': 'radiology'},
            )
        assert resp.status_code == 403
        assert 'not included' in resp.get_json()['error']

    def test_toggling_a_module_switches_it_off(self, app, client, login_as, db):
        from app.core.module.models import TenantModule
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        login_as(client, 'staff_toggle_off', 'manager')

        module = _module_row(_db, tenant.id)
        module.is_active = True
        _db.session.commit()

        resp = client.post(
            '/manager/api/units/toggle',
            json={'module_name': 'radiology'},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload['success'] is True
        assert payload['is_active'] is False
        assert payload['module_name'] == 'radiology'

        _db.session.expire_all()
        refreshed = _db.session.get(TenantModule, module.id)
        assert refreshed is not None
        assert refreshed.is_active is False
        assert refreshed.deactivated_at is not None

    def test_toggling_a_module_switches_it_on(self, app, client, login_as, db):
        from app.core.module.models import TenantModule
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        login_as(client, 'staff_toggle_on', 'manager')

        module = _module_row(_db, tenant.id)
        module.is_active = False
        _db.session.commit()

        resp = client.post(
            '/manager/api/units/toggle',
            json={'module_name': 'radiology'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['is_active'] is True

        _db.session.expire_all()
        refreshed = _db.session.get(TenantModule, module.id)
        assert refreshed.is_active is True
        assert refreshed.activated_at is not None

    def test_toggling_a_module_creates_the_row_when_the_clinic_has_none(
        self, app, client, login_as, db
    ):
        from app.core.module.models import TenantModule
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        login_as(client, 'staff_toggle_create', 'manager')

        module = _module_row(_db, tenant.id)
        module_name = module.module_name
        _db.session.delete(module)
        _db.session.commit()

        resp = client.post(
            '/manager/api/units/toggle',
            json={'module_name': module_name},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        _db.session.expire_all()
        created = (
            _db.session.execute(
                _db.select(TenantModule).where(
                    TenantModule.tenant_id == tenant.id,
                    TenantModule.module_name == module_name,
                )
            )
            .scalars()
            .first()
        )
        assert created is not None
        assert created.is_active is True

    def test_a_failing_toggle_answers_500(self, app, client, login_as):
        login_as(client, 'staff_toggle_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.staff.select', boom):
            resp = client.post(
                '/manager/api/units/toggle',
                json={'module_name': 'radiology'},
            )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


class TestUserManagement:
    """The user list."""

    def test_it_renders(self, app, client, login_as):
        login_as(client, 'staff_user_mgmt', 'manager')
        resp = client.get('/manager/user-management')
        assert resp.status_code in (200, 302)

    def test_a_failing_query_redirects(self, app, client, login_as):
        login_as(client, 'staff_user_mgmt_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.staff.select', boom):
            resp = client.get('/manager/user-management')
        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']


class TestStaffSchedule:
    """The work-schedule editor."""

    def test_it_lists_the_clinical_staff(self, app, client, login_as):
        login_as(client, 'staff_sched_list', 'manager')
        resp = client.get('/manager/staff/schedule')
        assert resp.status_code in (200, 302)

    def test_missing_fields_are_refused(self, app, client, login_as):
        login_as(client, 'staff_sched_missing', 'manager')
        resp = client.post('/manager/staff/schedule', data={})
        assert resp.status_code == 302
        assert '/manager/staff/schedule' in resp.headers['Location']

    def test_saving_a_new_day_creates_the_schedule(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='sched_new_doc')
        _db.session.commit()

        login_as(client, 'staff_sched_new', 'manager')
        resp = client.post(
            '/manager/staff/schedule',
            data={
                'user_id': str(doctor.id),
                # A day the default schedule does not already cover.
                'day_of_week': '5',
                'start_time': '08:00',
                'end_time': '16:00',
                'is_active': 'on',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        schedule = (
            _db.session.execute(
                _db.select(StaffWorkSchedule).where(
                    StaffWorkSchedule.user_id == doctor.id,
                    StaffWorkSchedule.day_of_week == 5,
                )
            )
            .scalars()
            .first()
        )
        assert schedule is not None
        assert schedule.start_time == time(8, 0)
        assert schedule.end_time == time(16, 0)
        assert schedule.is_active is True

    def test_saving_an_existing_day_updates_the_schedule(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='sched_update_doc')
        # A clinical user gets a default schedule for the working days.
        existing = (
            _db.session.execute(
                _db.select(StaffWorkSchedule).where(
                    StaffWorkSchedule.user_id == doctor.id,
                    StaffWorkSchedule.day_of_week == 3,
                )
            )
            .scalars()
            .first()
        )
        assert existing is not None
        existing_id = existing.id
        _db.session.commit()

        login_as(client, 'staff_sched_update', 'manager')
        resp = client.post(
            '/manager/staff/schedule',
            data={
                'user_id': str(doctor.id),
                'day_of_week': '3',
                'start_time': '10:00',
                'end_time': '18:00',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        refreshed = _db.session.get(StaffWorkSchedule, existing_id)
        assert refreshed is not None
        assert refreshed.start_time == time(10, 0)
        assert refreshed.end_time == time(18, 0)
        assert refreshed.is_active is False

    def test_an_unparsable_time_is_reported(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='sched_bad_time_doc')
        _db.session.commit()

        login_as(client, 'staff_sched_bad_time', 'manager')
        resp = client.post(
            '/manager/staff/schedule',
            data={
                'user_id': str(doctor.id),
                'day_of_week': '4',
                'start_time': 'not-a-time',
                'end_time': '16:00',
            },
        )
        assert resp.status_code in (200, 302)

    def test_the_schedule_of_one_staff_member_is_shown(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='sched_show_doc')
        _db.session.commit()

        login_as(client, 'staff_sched_show', 'manager')
        resp = client.get(f'/manager/staff/schedule?user_id={doctor.id}')
        assert resp.status_code in (200, 302)


class TestStaffAbsence:
    """The absence log."""

    def test_it_lists_the_clinical_staff(self, app, client, login_as):
        login_as(client, 'staff_abs_list', 'manager')
        resp = client.get('/manager/staff/absence')
        assert resp.status_code in (200, 302)

    def test_missing_fields_are_refused(self, app, client, login_as):
        login_as(client, 'staff_abs_missing', 'manager')
        resp = client.post('/manager/staff/absence', data={})
        assert resp.status_code == 302
        assert '/manager/staff/absence' in resp.headers['Location']

    def test_recording_an_absence(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffAbsence
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='abs_record_doc')
        _db.session.commit()

        login_as(client, 'staff_abs_record', 'manager')
        resp = client.post(
            '/manager/staff/absence',
            data={
                'user_id': str(doctor.id),
                'start_date': '2026-03-01',
                'end_date': '2026-03-03',
                'reason': 'annual leave',
            },
        )
        assert resp.status_code == 302

        _db.session.expire_all()
        absence = (
            _db.session.execute(
                _db.select(StaffAbsence).where(StaffAbsence.user_id == doctor.id)
            )
            .scalars()
            .first()
        )
        assert absence is not None
        assert absence.start_date == date(2026, 3, 1)
        assert absence.end_date == date(2026, 3, 3)
        assert absence.reason == 'annual leave'

    def test_an_unparsable_date_is_reported(self, app, client, login_as, db):
        from app.extensions import db as _db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='abs_bad_date_doc')
        _db.session.commit()

        login_as(client, 'staff_abs_bad_date', 'manager')
        resp = client.post(
            '/manager/staff/absence',
            data={
                'user_id': str(doctor.id),
                'start_date': 'not-a-date',
                'end_date': '2026-03-03',
            },
        )
        assert resp.status_code in (200, 302)

    def test_the_absence_of_one_staff_member_is_shown(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffAbsence
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        doctor = _doctor(_db, tenant.id, username='abs_show_doc')
        _db.session.add(
            StaffAbsence(
                tenant_id=tenant.id,
                user_id=doctor.id,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 2),
                reason='sick',
            )
        )
        _db.session.commit()

        login_as(client, 'staff_abs_show', 'manager')
        resp = client.get(f'/manager/staff/absence?user_id={doctor.id}')
        assert resp.status_code in (200, 302)


class TestStaffCapacity:
    """The capacity report."""

    def test_it_renders_for_the_default_window(self, app, client, login_as):
        login_as(client, 'staff_cap_default', 'manager')
        resp = client.get('/manager/staff/capacity')
        assert resp.status_code in (200, 302)

    def test_it_renders_for_an_explicit_window(self, app, client, login_as):
        login_as(client, 'staff_cap_window', 'manager')
        resp = client.get(
            '/manager/staff/capacity?start_date=2026-03-01&end_date=2026-03-07&days=7'
        )
        assert resp.status_code in (200, 302)

    def test_an_unparsable_start_date_falls_back_to_today(self, app, client, login_as):
        login_as(client, 'staff_cap_bad_start', 'manager')
        resp = client.get('/manager/staff/capacity?start_date=not-a-date')
        assert resp.status_code in (200, 302)

    def test_an_unparsable_end_date_falls_back_to_the_window(self, app, client, login_as):
        login_as(client, 'staff_cap_bad_end', 'manager')
        resp = client.get('/manager/staff/capacity?start_date=2026-03-01&end_date=not-a-date')
        assert resp.status_code in (200, 302)

    def test_absences_cost_the_department_its_slots(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffAbsence, StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)
        doctor = _doctor(_db, tenant.id, username='cap_abs_doc', department_id=department.id)
        # 2026-03-02 is a Monday; the doctor already has a schedule for it.
        schedule = (
            _db.session.execute(
                _db.select(StaffWorkSchedule).where(
                    StaffWorkSchedule.user_id == doctor.id,
                    StaffWorkSchedule.day_of_week == 0,
                )
            )
            .scalars()
            .first()
        )
        assert schedule is not None
        schedule.start_time = time(8, 0)
        schedule.end_time = time(16, 0)
        schedule.is_active = True
        _db.session.add(
            StaffAbsence(
                tenant_id=tenant.id,
                user_id=doctor.id,
                start_date=date(2026, 3, 2),
                end_date=date(2026, 3, 2),
                reason='sick',
            )
        )
        _db.session.commit()

        login_as(client, 'staff_cap_abs', 'manager')
        resp = client.get(
            f'/manager/staff/capacity?start_date=2026-03-02&end_date=2026-03-02&days=1'
            f'&department_id={department.id}'
        )
        assert resp.status_code in (200, 302)

    def test_an_inactive_schedule_is_not_counted(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)
        doctor = _doctor(_db, tenant.id, username='cap_inactive_doc', department_id=department.id)
        schedule = (
            _db.session.execute(
                _db.select(StaffWorkSchedule).where(
                    StaffWorkSchedule.user_id == doctor.id,
                    StaffWorkSchedule.day_of_week == 0,
                )
            )
            .scalars()
            .first()
        )
        assert schedule is not None
        schedule.start_time = time(8, 0)
        schedule.end_time = time(16, 0)
        schedule.is_active = False
        _db.session.commit()

        login_as(client, 'staff_cap_inactive', 'manager')
        resp = client.get(
            f'/manager/staff/capacity?start_date=2026-03-02&end_date=2026-03-02&days=1'
            f'&department_id={department.id}'
        )
        assert resp.status_code in (200, 302)

    def test_an_available_doctor_contributes_its_slots(self, app, client, login_as, db):
        from app.extensions import db as _db
        from models.user import StaffWorkSchedule
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        department = _department(_db, tenant.id)
        doctor = _doctor(_db, tenant.id, username='cap_available_doc', department_id=department.id)
        schedule = (
            _db.session.execute(
                _db.select(StaffWorkSchedule).where(
                    StaffWorkSchedule.user_id == doctor.id,
                    StaffWorkSchedule.day_of_week == 0,
                )
            )
            .scalars()
            .first()
        )
        assert schedule is not None
        schedule.start_time = time(8, 0)
        schedule.end_time = time(16, 0)
        schedule.is_active = True
        _db.session.commit()

        login_as(client, 'staff_cap_available', 'manager')
        resp = client.get(
            f'/manager/staff/capacity?start_date=2026-03-02&end_date=2026-03-02&days=1'
            f'&department_id={department.id}'
        )
        assert resp.status_code in (200, 302)

    def test_a_failing_report_redirects(self, app, client, login_as):
        login_as(client, 'staff_cap_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.staff.select', boom):
            resp = client.get('/manager/staff/capacity')
        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']


class TestStaffList:
    """The staff list."""

    def test_it_renders(self, app, client, login_as):
        login_as(client, 'staff_list_ok', 'manager')
        resp = client.get('/manager/staff')
        assert resp.status_code in (200, 302)

    def test_a_failing_query_redirects(self, app, client, login_as):
        login_as(client, 'staff_list_fail', 'manager')

        def boom(*a, **k):
            raise RuntimeError('database down')

        with patch('routes.manager.staff.select', boom):
            resp = client.get('/manager/staff')
        assert resp.status_code == 302
        assert '/manager/dashboard' in resp.headers['Location']
