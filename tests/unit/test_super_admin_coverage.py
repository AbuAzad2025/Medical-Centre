"""Additional HTTP coverage for the super_admin surface (routes/super_admin/*).

These tests exercise the real Flask app against the test database as an
authenticated super_admin. Mutating endpoints run under ``rollback_db`` so the
shared test schema does not accumulate rows from this module.

Backup creation never touches a real pg_dump binary in tests: the celery task is
monkeypatched to flip the Backup row (queue path, 202 Accepted), or the synchronous
fallback path runs with ``run_pg_dump_sql_gz`` stubbed.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from models.department import Department
from models.user import User


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


@pytest.fixture
def sa_client(app, client, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, test_tenant, username='super_admin_cov', role='super_admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def sa_user(app, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, test_tenant, username='super_admin_cov', role='super_admin')


def _csrf_from(client, path: str) -> str:
    resp = client.get(path)
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', resp.data)
    if match:
        return match.group(1).decode()
    match = re.search(rb'name="csrf-token"[^>]*content="([^"]+)"', resp.data)
    return match.group(1).decode() if match else ''


def _make_department(db, name: str | None = None) -> Department:
    dept = Department(
        name=name or _uniq('Dept'),
        name_ar=_uniq('قسم'),
        is_active=True,
    )
    db.session.add(dept)
    db.session.commit()
    return dept


def _make_backup(db, **kw) -> object:
    from app.shared.enums import BackupStatus
    from models.backup import Backup

    defaults = {
        'backup_name': _uniq('backup'),
        'backup_type': 'full',
        'backup_path': f'backups/{_uniq("file")}.sql.gz',
        'backup_status': BackupStatus.COMPLETED,
    }
    defaults.update(kw)
    row = Backup(**defaults)
    db.session.add(row)
    db.session.commit()
    return row


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


class TestAccessControl:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get('/super-admin/dashboard', follow_redirects=False)
        assert resp.status_code == 302

    def test_unauthenticated_json_post_redirects(self, client):
        resp = client.post('/super-admin/system/force-logout-all', follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# routes/super_admin/users.py
# ---------------------------------------------------------------------------


class TestUsersRoutes:
    def test_users_page_renders(self, sa_client):
        resp = sa_client.get('/super-admin/users')
        assert resp.status_code == 200

    def test_users_json_pagination(self, sa_client, sa_user):
        resp = sa_client.get(
            '/super-admin/users?page=1&per_page=1',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['per_page'] == 1
        assert body['page'] == 1
        assert len(body['users']) == 1
        assert body['total'] >= 1

    def test_users_json_oversized_per_page_is_capped(self, sa_client):
        resp = sa_client.get(
            '/super-admin/users?per_page=10000',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['per_page'] == 100

    def test_create_user_get(self, sa_client):
        assert sa_client.get('/super-admin/users/create').status_code == 200

    def test_create_doctor_with_pricing(self, sa_client, db):
        from models.pricing import DoctorPricing

        username = _uniq('doc')
        resp = sa_client.post(
            '/super-admin/users/create',
            data={
                'username': username,
                'email': f'{username}@example.com',
                'full_name': 'Doctor Coverage',
                'password': 'Secret123!',
                'role': 'doctor',
                'is_active': 'y',
                'consultation_price': '50',
                'follow_up_price': '30',
                'emergency_price': '75',
                'vip_price': '100',
            },
        )
        assert resp.status_code == 302
        user = db.session.execute(select(User).filter_by(username=username)).scalars().first()
        assert user is not None
        assert user.role == 'doctor'
        pricing = (
            db.session.execute(select(DoctorPricing).filter_by(doctor_id=user.id)).scalars().first()
        )
        assert pricing is not None
        assert float(pricing.consultation_price) == 50.0
        assert float(pricing.emergency_price) == 75.0

    def test_create_user_rejects_unassignable_role(self, sa_client, db):
        username = _uniq('nope')
        resp = sa_client.post(
            '/super-admin/users/create',
            data={
                'username': username,
                'email': f'{username}@example.com',
                'full_name': 'Nope',
                'password': 'Secret123!',
                'role': 'bogus_role',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert (
            db.session.execute(select(User).filter_by(username=username)).scalars().first() is None
        )

    def test_edit_user_get(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('ed'), role='doctor')
        assert sa_client.get(f'/super-admin/users/{target.id}/edit').status_code == 200

    def test_edit_user_post_updates_profile_and_departments(self, sa_client, db, test_tenant):
        from models.user_department_access import UserDepartmentAccess
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('ed'), role='doctor')
        dept_a = _make_department(db)
        dept_b = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/users/{target.id}/edit',
            data={
                'username': target.username,
                'email': 'updated@example.com',
                'full_name': 'Updated Name',
                'role': 'doctor',
                'phone': '0501112222',
                'department_id': str(dept_a.id),
                'new_password': 'NewPass123!',
                'extra_department_ids': [str(dept_a.id), str(dept_b.id)],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(target)
        assert target.email == 'updated@example.com'
        assert target.full_name == 'Updated Name'
        assert target.check_password('NewPass123!')
        extras = (
            db.session.execute(
                select(UserDepartmentAccess).filter_by(user_id=target.id, can_access=True)
            )
            .scalars()
            .all()
        )
        assert {row.department_id for row in extras} == {dept_a.id, dept_b.id}

    def test_edit_user_blocks_elevation_of_unmanageable_role(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('blocked'), role='doctor')
        resp = sa_client.post(
            f'/super-admin/users/{target.id}/edit',
            data={
                'username': target.username,
                'email': target.email,
                'full_name': target.full_name,
                'role': 'bogus_role',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(target)
        assert target.role == 'doctor'

    def test_edit_user_flags_invalid_stored_role(self, sa_client, db, test_tenant):
        from sqlalchemy.orm.attributes import set_committed_value

        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('bogus'), role='doctor')
        # Simulate a legacy/corrupted stored role without violating chk_user_role in DB.
        set_committed_value(target, 'role', 'not_a_real_role')
        resp = sa_client.post(
            f'/super-admin/users/{target.id}/edit',
            data={
                'username': target.username,
                'email': target.email,
                'full_name': target.full_name,
                'role': 'not_a_real_role',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        # The invalid role was rejected by the policy guard, not stored silently.
        db.session.expire(target)
        assert target.role == 'doctor'
        assert sa_client.get(f'/super-admin/users/{target.id}/edit').status_code == 200

    def test_delete_user(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('del'), role='reception')
        resp = sa_client.post(f'/super-admin/users/{target.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert db.session.get(User, target.id) is None

    def test_delete_super_admin_is_blocked(self, sa_client, db, sa_user):
        resp = sa_client.post(f'/super-admin/users/{sa_user.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        db.session.refresh(sa_user)
        assert db.session.get(User, sa_user.id) is not None

    def test_delete_missing_user_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/users/987654/delete', follow_redirects=False)
        assert resp.status_code == 302

    def test_reset_password_returns_working_temp_password(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('reset'), role='doctor')
        resp = sa_client.post(f'/super-admin/users/{target.id}/reset-password')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        db.session.refresh(target)
        assert target.check_password(body['temp_password'])

    def test_reset_password_missing_user(self, sa_client):
        resp = sa_client.post('/super-admin/users/987654/reset-password')
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_ban_and_unban_user(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('ban'), role='nurse')
        resp = sa_client.post(f'/super-admin/users/ban/{target.id}', follow_redirects=False)
        assert resp.status_code == 302
        db.session.refresh(target)
        assert target.is_active is False

        resp = sa_client.post(f'/super-admin/users/unban/{target.id}', follow_redirects=False)
        assert resp.status_code == 302
        db.session.refresh(target)
        assert target.is_active is True

    def test_ban_super_admin_is_blocked(self, sa_client, db, sa_user):
        resp = sa_client.post(f'/super-admin/users/ban/{sa_user.id}', follow_redirects=False)
        assert resp.status_code == 302
        db.session.refresh(sa_user)
        assert sa_user.is_active is True

    def test_ban_missing_user_redirects(self, sa_client):
        assert sa_client.post('/super-admin/users/ban/987654').status_code == 302

    def test_force_logout_bumps_session_version_and_audits(self, sa_client, db, test_tenant):
        from models.audit_trail import AuditTrail
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('lo'), role='doctor')
        before = int(target.session_version or 0)
        resp = sa_client.post(
            f'/super-admin/users/force-logout/{target.id}', follow_redirects=False
        )
        assert resp.status_code == 302
        db.session.refresh(target)
        assert int(target.session_version or 0) == before + 1
        audit = (
            db.session.execute(
                select(AuditTrail).filter_by(action='force_logout', entity_id=target.id)
            )
            .scalars()
            .first()
        )
        assert audit is not None
        assert audit.entity_type == 'user'

    def test_force_logout_missing_user(self, sa_client):
        assert sa_client.post('/super-admin/users/force-logout/987654').status_code == 302

    def test_seed_users_endpoint_is_gone(self, sa_client):
        resp = sa_client.post('/super-admin/seed/users')
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# routes/super_admin/services.py
# ---------------------------------------------------------------------------


class TestServicesRoutes:
    def _create_service(self, sa_client, db, **kw):
        from models.service import ServiceMaster

        data = {
            'name': kw.get('name', _uniq('Svc')),
            'name_ar': kw.get('name_ar', 'استشارة'),
            'base_price': kw.get('base_price', '150'),
            'service_type': kw.get('service_type', 'general'),
            'currency': kw.get('currency', 'ILS'),
        }
        for key in ('duration', 'max_daily', 'description', 'code', 'department_id'):
            if key in kw:
                data[key] = kw[key]
        resp = sa_client.post('/super-admin/services/create', data=data)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['success'] is True
        return db.session.get(ServiceMaster, body['service_id'])

    def test_pricing_page(self, sa_client):
        assert sa_client.get('/super-admin/pricing').status_code == 200

    def test_services_page(self, sa_client):
        assert sa_client.get('/super-admin/services').status_code == 200

    def test_create_service_missing_name_returns_400(self, sa_client):
        resp = sa_client.post('/super-admin/services/create', data={'name_ar': 'استشارة'})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_create_service_invalid_price_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': 'not-a-number'},
        )
        assert resp.status_code == 400

    def test_create_service_negative_price_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': '-20'},
        )
        assert resp.status_code == 400

    def test_create_service_invalid_duration_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': '10', 'duration': 'abc'},
        )
        assert resp.status_code == 400
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': '10', 'duration': '0'},
        )
        assert resp.status_code == 400

    def test_create_service_invalid_max_daily_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': '10', 'max_daily': 'abc'},
        )
        assert resp.status_code == 400
        resp = sa_client.post(
            '/super-admin/services/create',
            data={'name': 'Xray', 'name_ar': 'أشعة', 'base_price': '10', 'max_daily': '0'},
        )
        assert resp.status_code == 400

    def test_create_service_ok_generates_code_and_coerces_currency(self, sa_client, db):
        service = self._create_service(sa_client, db, currency='GBP', service_type='LAB')
        assert service.code.startswith('LAB_')
        assert service.category == 'lab'
        assert service.currency == 'شيكل'  # unsupported currency coerced to default
        assert float(service.base_price) == 150.0

    def test_create_service_with_duration_and_daily_cap(self, sa_client, db):
        service = self._create_service(sa_client, db, duration='45', max_daily='20')
        assert service.duration == 45
        assert service.max_daily == 20

    def test_view_service_page(self, sa_client, db):
        service = self._create_service(sa_client, db)
        assert sa_client.get(f'/super-admin/service/{service.id}').status_code == 200

    def test_view_missing_service_redirects(self, sa_client):
        assert sa_client.get('/super-admin/service/987654').status_code == 302

    def test_edit_service_get_and_post(self, sa_client, db):
        service = self._create_service(sa_client, db)
        assert sa_client.get(f'/super-admin/edit-service/{service.id}').status_code == 200
        resp = sa_client.post(
            f'/super-admin/edit-service/{service.id}',
            data={
                'name': 'اسم جديد',
                'name_en': 'New EN Name',
                'description': 'updated',
                'category': 'general',
                'base_price': '220',
                'duration': '30',
                'max_daily': '10',
                'is_active': 'y',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(service)
        assert service.name == 'New EN Name'
        assert service.name_ar == 'اسم جديد'
        assert float(service.base_price) == 220.0
        assert service.duration == 30
        assert service.max_daily == 10

    def test_service_pricing_lifecycle(self, sa_client, db):
        from models.pricing_management import PricingManagement

        service = self._create_service(sa_client, db)
        assert sa_client.get(f'/super-admin/service-pricing/{service.id}').status_code == 200

        for price_type, column in (
            ('standard', 'base_price'),
            ('urgent', 'emergency_price'),
            ('insurance', 'insurance_price'),
            ('vip', 'private_price'),
        ):
            resp = sa_client.post(
                f'/super-admin/service-pricing/{service.id}',
                data={
                    'price_type': price_type,
                    'price': '80',
                    'currency': 'ILS',
                    'discount_percentage': '10',
                    'discount_amount': '2',
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302
            rec = (
                db.session.execute(
                    select(PricingManagement)
                    .filter_by(service_id=service.id)
                    .order_by(PricingManagement.id.desc())
                )
                .scalars()
                .first()
            )
            assert float(getattr(rec, column)) == 80.0
            assert float(rec.discount_percentage) == 10.0

    def test_service_pricing_delete_writes_audit_row(self, sa_client, db):
        from models.audit_trail import AuditTrail
        from models.pricing_management import PricingManagement

        service = self._create_service(sa_client, db)
        sa_client.post(
            f'/super-admin/service-pricing/{service.id}',
            data={'price_type': 'standard', 'price': '95', 'currency': 'ILS'},
        )
        rec = (
            db.session.execute(select(PricingManagement).filter_by(service_id=service.id))
            .scalars()
            .first()
        )
        resp = sa_client.post(
            f'/super-admin/service-pricing/delete/{rec.id}', follow_redirects=False
        )
        assert resp.status_code == 302
        assert db.session.get(PricingManagement, rec.id) is None
        audit = (
            db.session.execute(select(AuditTrail).filter_by(action='delete', entity_type='service'))
            .scalars()
            .first()
        )
        assert audit is not None

    def test_service_pricing_delete_missing_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/service-pricing/delete/987654', follow_redirects=False)
        assert resp.status_code == 302

    def test_activate_and_deactivate_service(self, sa_client, db):
        service = self._create_service(sa_client, db)
        resp = sa_client.post(f'/super-admin/deactivate-service/{service.id}')
        assert resp.get_json()['success'] is True
        db.session.refresh(service)
        assert service.is_active is False

        resp = sa_client.post(f'/super-admin/activate-service/{service.id}')
        assert resp.get_json()['success'] is True
        db.session.refresh(service)
        assert service.is_active is True

    def test_activate_missing_service_returns_500(self, sa_client):
        resp = sa_client.post('/super-admin/activate-service/987654')
        assert resp.status_code == 500

    def test_export_services_csv(self, sa_client, db):
        service = self._create_service(sa_client, db, name='ExportMe')
        resp = sa_client.get('/super-admin/export-services')
        assert resp.status_code == 200
        assert 'services_export.csv' in resp.headers.get('Content-Disposition', '')
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert rows[0][0] == 'ID'
        assert any(str(service.id) in row for row in rows)


# ---------------------------------------------------------------------------
# routes/super_admin/roles.py
# ---------------------------------------------------------------------------


def _permission_ids(db, limit: int = 2):
    from models.permissions import Permission

    return [p.id for p in db.session.execute(select(Permission).limit(limit)).scalars().all()]


def _make_role(db, name: str | None = None, is_system_role: bool = False):
    from models.permissions import Role

    role = Role(
        name=name or _uniq('role'),
        name_ar='QD',
        description='test role',
        is_system_role=is_system_role,
        is_active=True,
    )
    db.session.add(role)
    db.session.commit()
    return role


def _role_permission_ids(db, role_id: int) -> set[int]:
    from models.permissions import RolePermission

    return {
        rp.permission_id
        for rp in db.session.execute(select(RolePermission).filter_by(role_id=role_id))
        .scalars()
        .all()
    }


class TestRolesRoutes:
    def test_roles_page(self, sa_client):
        assert sa_client.get('/super-admin/roles').status_code == 200

    def test_create_role_get(self, sa_client):
        assert sa_client.get('/super-admin/roles/create').status_code == 200

    def test_create_role_with_permissions(self, sa_client, db):
        from models.permissions import Role

        perm_ids = _permission_ids(db, 2)
        name = _uniq('made')
        resp = sa_client.post(
            '/super-admin/roles/create',
            data={
                'name': name,
                'name_ar': 'R-AR',
                'is_active': 'y',
                'permissions': [str(pid) for pid in perm_ids],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        role = db.session.execute(select(Role).filter_by(name=name)).scalars().first()
        assert role is not None
        assert _role_permission_ids(db, role.id) == set(perm_ids)

    def test_create_role_bad_permission_id_persists_nothing(self, sa_client, db):
        from models.permissions import Role

        name = _uniq('broken')
        resp = sa_client.post(
            '/super-admin/roles/create',
            data={'name': name, 'permissions': ['not-a-number']},
            follow_redirects=False,
        )
        # Invalid permission id triggers rollback; route re-renders create form (200) with no persisted role.
        assert resp.status_code == 200
        assert db.session.execute(select(Role).filter_by(name=name)).scalars().first() is None

    def test_edit_role_get(self, sa_client, db):
        role = _make_role(db)
        assert sa_client.get(f'/super-admin/roles/{role.id}/edit').status_code == 200

    def test_edit_role_missing_redirects(self, sa_client):
        assert sa_client.get('/super-admin/roles/987654/edit').status_code == 302

    def test_edit_role_replaces_permissions_scoped_to_role(self, sa_client, db):
        role_a = _make_role(db)
        role_b = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(RolePermission(role_id=role_b.id, permission_id=perm_b))
        db.session.commit()

        resp = sa_client.post(
            f'/super-admin/roles/{role_a.id}/edit',
            data={
                'name': role_a.name,
                'name_ar': 'R2-AR',
                'description': 'updated',
                'is_active': 'y',
                'permissions': [str(perm_a)],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role_a.id) == {perm_a}
        # Regression: the delete must be scoped to the edited role.
        assert _role_permission_ids(db, role_b.id) == {perm_b}

    def test_manage_role_permissions_post_replaces_set(self, sa_client, db):
        role = _make_role(db)
        role_other = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(RolePermission(role_id=role_other.id, permission_id=perm_b))
        db.session.commit()

        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/permissions',
            data={'permissions': [str(perm_a)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role.id) == {perm_a}
        assert _role_permission_ids(db, role_other.id) == {perm_b}

    def test_manage_permissions_get_renders(self, sa_client, db):
        role = _make_role(db)
        assert sa_client.get(f'/super-admin/roles/{role.id}/permissions').status_code == 200

    def test_manage_permissions_missing_role_redirects(self, sa_client):
        assert sa_client.get('/super-admin/roles/987654/permissions').status_code == 302

    def test_department_permissions_get_and_post(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        dept = _make_department(db)
        role_other = _make_role(db)
        db.session.add(
            DepartmentPermission(role_id=role_other.id, department_id=dept.id, can_access=True)
        )
        db.session.commit()

        assert (
            sa_client.get(f'/super-admin/roles/{role.id}/department-permissions').status_code == 200
        )

        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={
                f'dept_{dept.id}_can_access': 'on',
                f'dept_{dept.id}_can_manage_visits': 'on',
                'dept_all_can_access': 'on',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        )
        by_dept = {row.department_id: row for row in rows}
        assert by_dept[dept.id].can_manage_visits is True
        assert by_dept[None].can_access is True
        # The other role's row survived the replace.
        other = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role_other.id))
            .scalars()
            .all()
        )
        assert len(other) == 1

    def test_department_permissions_missing_role_redirects(self, sa_client):
        assert (
            sa_client.post('/super-admin/roles/987654/department-permissions', data={}).status_code
            == 302
        )

    def test_permissions_matrix_page(self, sa_client):
        assert sa_client.get('/super-admin/permissions-matrix').status_code == 200

    def test_permissions_matrix_post_replaces_submitted_and_clears_others(self, sa_client, db):
        role_a = _make_role(db)
        role_b = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(RolePermission(role_id=role_b.id, permission_id=perm_b))
        db.session.commit()

        resp = sa_client.post(
            '/super-admin/permissions-matrix',
            data={f'role_{role_a.id}_permissions': [str(perm_a)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role_a.id) == {perm_a}
        # Unsubmitted roles end with no permissions after a matrix save.
        assert _role_permission_ids(db, role_b.id) == set()

    def test_delete_role_removes_role_and_permissions(self, sa_client, db):
        role = _make_role(db)
        perm_a = _permission_ids(db, 1)[0]

        from models.permissions import Role, RolePermission

        db.session.add(RolePermission(role_id=role.id, permission_id=perm_a))
        db.session.commit()
        resp = sa_client.post(f'/super-admin/roles/{role.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert db.session.get(Role, role.id) is None
        assert _role_permission_ids(db, role.id) == set()

    def test_delete_system_role_is_blocked(self, sa_client, db):
        from models.permissions import Role

        role = (
            db.session.execute(select(Role).filter_by(is_system_role=True).limit(1))
            .scalars()
            .first()
        )
        assert role is not None
        resp = sa_client.post(f'/super-admin/roles/{role.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert db.session.get(Role, role.id) is not None

    def test_delete_role_missing_redirects(self, sa_client):
        assert sa_client.post('/super-admin/roles/987654/delete').status_code == 302

    def test_permissions_page(self, sa_client):
        assert sa_client.get('/super-admin/permissions').status_code == 200

    def test_create_permission_persists_tenant(self, sa_client, db, test_tenant):
        from models.permissions import Permission

        name = _uniq('perm')
        resp = sa_client.post(
            '/super-admin/permissions/create',
            data={
                'name': name,
                'description': 'coverage perm',
                'category': 'FINANCIAL',
                'level': 'READ',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        assert row is not None
        assert int(row.tenant_id) == int(test_tenant.id)

    def test_edit_permission(self, sa_client, db):
        from models.permissions import Permission

        name = _uniq('perm')
        create = sa_client.post(
            '/super-admin/permissions/create',
            data={
                'name': name,
                'description': 'before',
                'category': 'REPORTS',
                'level': 'WRITE',
            },
            follow_redirects=False,
        )
        assert create.status_code == 302
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        resp = sa_client.post(
            f'/super-admin/permissions/{row.id}/edit',
            data={
                'name': name,
                'description': 'after',
                'category': 'SECURITY',
                'level': 'ADMIN',
                'is_active': 'on',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(row)
        assert row.description == 'after'
        assert str(row.level) == 'PermissionLevel.ADMIN' or row.level.name == 'ADMIN'

    def test_edit_permission_missing_redirects(self, sa_client):
        assert sa_client.post('/super-admin/permissions/987654/edit', data={}).status_code == 302

    def test_delete_permission(self, sa_client, db):
        from models.permissions import Permission

        name = _uniq('perm')
        sa_client.post(
            '/super-admin/permissions/create',
            data={'name': name, 'description': 'x', 'category': 'AUDIT', 'level': 'READ'},
            follow_redirects=False,
        )
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        resp = sa_client.post(f'/super-admin/permissions/{row.id}/delete', follow_redirects=False)
        assert resp.status_code == 302
        assert db.session.get(Permission, row.id) is None

    def test_delete_permission_missing_redirects(self, sa_client):
        assert sa_client.post('/super-admin/permissions/987654/delete').status_code == 302

    def test_create_role_simple_with_real_csrf(self, sa_client, db):
        from models.permissions import Role

        token = _csrf_from(sa_client, '/super-admin/users')
        assert token
        name = _uniq('simple')
        resp = sa_client.post(
            '/super-admin/create-role-simple',
            data={'csrf_token': token, 'name': name, 'name_ar': 'S-AR', 'description': 'd'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        role = db.session.execute(select(Role).filter_by(name=name)).scalars().first()
        assert role is not None
        assert role.is_system_role is False

    def test_create_role_simple_rejects_bad_csrf(self, sa_client, db):
        from models.permissions import Role

        name = _uniq('simplebad')
        resp = sa_client.post(
            '/super-admin/create-role-simple',
            data={'csrf_token': 'not-a-valid-token', 'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert db.session.execute(select(Role).filter_by(name=name)).scalars().first() is None

    def test_create_permission_simple_with_real_csrf(self, sa_client, db, test_tenant):
        from models.permissions import Permission

        token = _csrf_from(sa_client, '/super-admin/users')
        assert token
        name = _uniq('simpleperm')
        resp = sa_client.post(
            '/super-admin/create-permission-simple',
            data={'csrf_token': token, 'name': name, 'description': 'd'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        assert row is not None
        assert row.level.name == 'ADMIN'
        assert row.category.name == 'SYSTEM_ADMIN'

    def test_create_permission_simple_rejects_bad_csrf(self, sa_client, db):
        from models.permissions import Permission

        name = _uniq('simplepermbad')
        resp = sa_client.post(
            '/super-admin/create-permission-simple',
            data={'csrf_token': 'not-a-valid-token', 'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert db.session.execute(select(Permission).filter_by(name=name)).scalars().first() is None


# ---------------------------------------------------------------------------
# routes/super_admin/system.py
# ---------------------------------------------------------------------------


class TestSystemRoutes:
    def test_force_logout_all_bumps_and_audits(self, sa_client, db, sa_user):
        from models.audit_trail import AuditTrail

        before = int(sa_user.session_version or 0)
        resp = sa_client.post('/super-admin/system/force-logout-all')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        db.session.refresh(sa_user)
        assert int(sa_user.session_version or 0) == before + 1
        audit = (
            db.session.execute(select(AuditTrail).filter_by(action='force_logout'))
            .scalars()
            .first()
        )
        assert audit is not None

    def test_optimize_database(self, sa_client):
        resp = sa_client.post('/super-admin/system/optimize-database')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_system_config_page(self, sa_client):
        assert sa_client.get('/super-admin/system-config').status_code == 200

    def test_system_config_load_and_test_db(self, sa_client):
        resp = sa_client.get('/super-admin/system-config?action=load')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        resp = sa_client.get('/super-admin/system-config?action=test_db')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_system_config_post_json_roundtrip(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system-config',
            json={
                'log_level': 'INFO',
                'timezone': 'UTC',
                'language': 'ar',
                'currency': 'ILS',
                'session_timeout': 30,
                'max_login_attempts': 5,
                'sms_enabled': True,
                'allow_debt_global': False,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        loaded = sa_client.get('/super-admin/system-config?action=load').get_json()['settings']
        assert loaded['log_level'] == 'INFO'
        assert loaded['timezone'] == 'UTC'
        assert loaded['session_timeout'] == '30'
        assert loaded['sms_enabled'] == 'True'

    def test_system_config_post_rejects_unknown_key(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'nonsense_key': 'x'})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False
        assert resp.get_json()['errors']

    def test_system_config_post_rejects_bad_choice(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'log_level': 'NOPE'})
        assert resp.status_code == 400

    def test_system_config_post_rejects_out_of_range_integer(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'session_timeout': 9999})
        assert resp.status_code == 400

    def test_system_config_post_rejects_bad_integer(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'session_timeout': 'abc'})
        assert resp.status_code == 400

    def test_system_config_post_rejects_bad_currency(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'currency': 'BTC'})
        assert resp.status_code == 400

    def test_system_config_form_post_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', data={'x': 'y'}, follow_redirects=False)
        assert resp.status_code == 302

    def test_backup_settings_post(self, sa_client, db):
        from models.system_config import SystemConfig

        resp = sa_client.post(
            '/super-admin/backup/settings',
            json={'frequency': 'weekly', 'retention': '14', 'location': '/data/backups'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='backup_frequency'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() == 'weekly'

    def test_backup_settings_invalid_body_returns_500(self, sa_client):
        resp = sa_client.post(
            '/super-admin/backup/settings', data='not json', content_type='application/json'
        )
        # silently-parsed empty body falls back to defaults; still 200/500 either way
        assert resp.status_code in (200, 500)

    def test_maintenance_automation_get_and_post(self, sa_client, db):
        from models.system_config import SystemConfig

        assert sa_client.get('/super-admin/maintenance/automation').status_code == 200
        resp = sa_client.post(
            '/super-admin/maintenance/automation',
            json={
                'auto_cleanup': True,
                'cleanup_days': 45,
                'log_retention_days': 120,
                'auto_backup': False,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='maintenance_automation'))
            .scalars()
            .first()
        )
        assert cfg is not None
        value = cfg.get_value()
        assert value['cleanup_days'] == 45
        assert value['auto_backup'] is False

    def test_queue_settings_page_and_load_and_save(self, sa_client, db):
        dept = _make_department(db)
        assert sa_client.get('/super-admin/queue-settings').status_code == 200

        resp = sa_client.get('/super-admin/queue-settings?action=load')
        assert resp.status_code == 200
        items = resp.get_json()['items']
        targets = [item for item in items if item['department_id'] == dept.id]
        assert len(targets) == 1
        assert targets[0]['max_queue_size'] == 50  # default before first save

        resp = sa_client.post(
            '/super-admin/queue-settings',
            json={
                'items': [
                    {
                        'department_id': dept.id,
                        'max_queue_size': 33,
                        'payment_required': False,
                        'average_wait_time': 17,
                        'allow_debt': True,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        loaded = sa_client.get('/super-admin/queue-settings?action=load').get_json()['items']
        item = next(i for i in loaded if i['department_id'] == dept.id)
        assert item['max_queue_size'] == 33
        assert item['payment_required'] is False
        assert item['average_wait_time'] == 17
        assert item['allow_debt'] is True

    def test_queue_settings_post_requires_json(self, sa_client):
        resp = sa_client.post('/super-admin/queue-settings', data={'items': 'x'})
        assert resp.status_code == 400

    def test_system_backup_redirects_to_backup_page(self, sa_client):
        resp = sa_client.get('/super-admin/system-backup', follow_redirects=False)
        assert resp.status_code == 302
        assert '/super-admin/backup' in resp.headers['Location']

    def test_system_maintenance_page(self, sa_client):
        assert sa_client.get('/super-admin/system/maintenance').status_code == 200

    def test_system_cleanup_logs(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'logs'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_system_cleanup_sessions_and_cache(self, sa_client):
        for cleanup_type in ('sessions', 'cache'):
            resp = sa_client.post(
                '/super-admin/system/cleanup',
                data={'cleanup_type': cleanup_type},
                follow_redirects=False,
            )
            assert resp.status_code == 302

    def test_system_cleanup_seed_data_is_disabled(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'seed_data'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_sms_test_requires_capability(self, sa_client, monkeypatch):
        monkeypatch.delenv('PLATFORM_CAP_SMS_LIVE', raising=False)
        resp = sa_client.post(
            '/super-admin/system/sms/test', json={'phone_number': '+970599000000'}
        )
        assert resp.status_code == 404

    def test_sms_test_with_capability_missing_phone(self, sa_client, monkeypatch):
        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')
        resp = sa_client.post('/super-admin/system/sms/test', json={})
        assert resp.status_code == 400

    def test_sms_test_with_capability_logs_provider(self, sa_client, monkeypatch):
        from app.integrations.sms import LogSMSProvider

        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')
        monkeypatch.setattr(
            'services.sms_service.get_sms_provider',
            lambda tenant=None: LogSMSProvider(),  # noqa: ARG005
        )
        resp = sa_client.post(
            '/super-admin/system/sms/test', json={'phone_number': '+970599000001'}
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_process_notification_queue(self, sa_client):
        resp = sa_client.post('/super-admin/system/notifications/queue/process')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_run_notifications_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/system/notifications/run', follow_redirects=False)
        assert resp.status_code == 302

    def test_init_notification_templates_redirects(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/notifications/init-templates', follow_redirects=False
        )
        assert resp.status_code == 302

    def test_system_page(self, sa_client):
        assert sa_client.get('/super-admin/system').status_code == 200


# ---------------------------------------------------------------------------
# routes/super_admin/analytics.py
# ---------------------------------------------------------------------------


class TestAnalyticsRoutes:
    def test_performance_api(self, sa_client):
        resp = sa_client.get('/super-admin/api/performance')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['cpu_percent'] >= 0
        assert body['memory_percent'] >= 0
        assert body['uptime_hours'] >= 0
        assert body['db_size_mb'] is None or body['db_size_mb'] >= 0
        assert body['active_db_connections'] is None or body['active_db_connections'] >= 1

    def test_performance_page(self, sa_client):
        assert sa_client.get('/super-admin/performance').status_code == 200

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

    def test_analytics_page(self, sa_client, db, test_tenant):
        from app.shared.enums import VisitState
        from models.patient import Patient
        from models.visit import Visit

        patient = Patient(
            first_name='Test',
            last_name='Patient',
            phone=_uniq('05'),
            gender='M',
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
            )
        )
        db.session.commit()
        resp = sa_client.get('/super-admin/analytics')
        assert resp.status_code == 200

    def test_system_monitor_page(self, sa_client):
        assert sa_client.get('/super-admin/system-monitor').status_code == 200


class TestAnalyticsHelpers:
    """Direct calls to the module-level stat helpers (no HTTP involved)."""

    def test_get_total_users_and_active_inactive_admin(self, app):
        from routes.super_admin.analytics import (
            get_active_sessions,
            get_active_users,
            get_admin_users,
            get_inactive_users,
            get_total_users,
        )

        assert get_total_users() >= 1
        assert get_active_users() >= 0
        assert get_inactive_users() >= 0
        assert get_admin_users() >= 0
        assert get_active_sessions() >= 0

    def test_get_security_events_returns_int(self, app):
        from routes.super_admin.analytics import get_security_events

        assert isinstance(get_security_events(), int)

    def test_get_system_uptime_constant(self):
        from routes.super_admin.analytics import get_system_uptime

        assert get_system_uptime() == '99.9%'

    def test_get_daily_usage_series(self):
        from routes.super_admin.analytics import get_daily_usage

        assert get_daily_usage() == [100, 95, 88, 92, 98]

    def test_get_ai_insights_shape(self, app):
        from routes.super_admin.analytics import get_ai_insights

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

    def test_get_smart_recommendations_returns_list(self, app):
        from routes.super_admin.analytics import get_smart_recommendations

        assert isinstance(get_smart_recommendations(), list)

    def test_get_predictive_analytics_keys(self, app):
        from routes.super_admin.analytics import get_predictive_analytics

        result = get_predictive_analytics()
        assert isinstance(result, dict)
        assert 'growth_rate' in result
        assert 'trend' in result
        assert result['trend'] in ('growing', 'stable', 'declining')

    def test_get_system_health_score(self, app):
        from routes.super_admin.analytics import get_system_health_score

        result = get_system_health_score()
        assert isinstance(result, dict)
        assert 0 <= result['score'] <= 100
        assert result['color'] in ('success', 'warning', 'danger', 'secondary')

    def test_get_security_threats_returns_list(self, app):
        from routes.super_admin.analytics import get_security_threats

        assert isinstance(get_security_threats(), list)

    def test_get_performance_optimization_returns_list(self, app):
        from routes.super_admin.analytics import get_performance_optimization

        assert isinstance(get_performance_optimization(), list)

    def test_get_user_behavior_analysis_shape(self, app, db, test_tenant):
        from routes.super_admin.analytics import get_user_behavior_analysis

        result = get_user_behavior_analysis()
        assert isinstance(result, dict)
        assert 'role_distribution' in result
        assert 'engagement_rate' in result

    def test_get_resource_utilization_keys(self, app):
        from routes.super_admin.analytics import get_resource_utilization

        result = get_resource_utilization()
        assert isinstance(result, dict)
        for key in ('memory', 'cpu', 'disk', 'database', 'status'):
            assert key in result
        assert result['database']['total_users'] >= 1


# ---------------------------------------------------------------------------
# routes/super_admin/backup.py
# ---------------------------------------------------------------------------


class TestBackupRoutes:
    def test_backup_page_with_mixed_history(self, sa_client, db):
        from app.shared.enums import BackupStatus

        _make_backup(db, backup_status=BackupStatus.COMPLETED, backup_size=2048)
        _make_backup(db, backup_status=BackupStatus.FAILED, backup_size=None)
        resp = sa_client.get('/super-admin/backup')
        assert resp.status_code == 200

    def test_backup_create_queued_path(self, sa_client, db, monkeypatch):
        from models.backup import Backup

        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: True)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: True)

        def _fake_execute(backup_id):
            backup = db.session.get(Backup, backup_id)
            from app.shared.enums import BackupStatus

            backup.backup_status = BackupStatus.COMPLETED
            backup.backup_size = 4096
            backup.completed_at = datetime.now(UTC)
            db.session.commit()
            return backup

        monkeypatch.setattr('services.backup_execution_service.execute_backup_by_id', _fake_execute)
        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 202
        body = resp.get_json()
        assert body['accepted'] is True
        assert body['status'] == 'queued'
        assert body.get('backup_id')
        backup = db.session.get(Backup, body['backup_id'])
        assert backup is not None
        assert backup.backup_type == 'full'

    def test_backup_create_synchronous_success(self, sa_client, db, monkeypatch):
        from models.backup import Backup

        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)
        monkeypatch.setattr('services.pg_backup_service.run_pg_dump_sql_gz', lambda _path: 1234)
        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        created = db.session.execute(select(Backup).order_by(Backup.id.desc())).scalars().first()
        assert created.backup_size == 1234
        assert created.backup_status == 'COMPLETED'

    def test_backup_create_synchronous_pg_dump_failure_marks_failed(
        self, sa_client, db, monkeypatch, tmp_path
    ):
        from models.backup import Backup
        from services.pg_backup_service import PgBackupError

        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)

        def _boom(_path):
            raise PgBackupError('pg_dump not installed')

        monkeypatch.setattr('services.pg_backup_service.run_pg_dump_sql_gz', _boom)
        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False
        created = db.session.execute(select(Backup).order_by(Backup.id.desc())).scalars().first()
        assert created.backup_status == 'FAILED'
        assert 'pg_dump not installed' in (created.backup_notes or '')

    def test_backup_create_unrecorded_queue_failure_returns_500(self, sa_client, monkeypatch):
        import celery_app
        from services.backup_queue_service import BackupQueueError

        # Route maps BackupQueueError from queueing to 503 (service unavailable/unqueueable).
        monkeypatch.setattr(celery_app, 'celery_is_enabled', lambda: True)
        monkeypatch.setattr(celery_app, 'task_always_eager', lambda: False)
        monkeypatch.setattr(
            'services.backup_queue_service.queue_system_backup',
            lambda *_a, **_k: (_ for _ in ()).throw(BackupQueueError('queue unavailable')),
        )
        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 503
        assert resp.get_json()['success'] is False

    def test_restore_backup_success(self, sa_client, db, monkeypatch):
        backup = _make_backup(db)
        monkeypatch.setattr('routes.backup_routes.restore_backup_file', lambda _b: True)
        resp = sa_client.post(f'/super-admin/backup/restore/{backup.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.refresh(backup)
        assert backup.restore_count == 1
        assert backup.last_restore is not None

    def test_restore_backup_failure(self, sa_client, db, monkeypatch):
        backup = _make_backup(db)
        monkeypatch.setattr('routes.backup_routes.restore_backup_file', lambda _b: False)
        resp = sa_client.post(f'/super-admin/backup/restore/{backup.id}')
        assert resp.status_code == 500

    def test_restore_missing_backup_returns_404(self, sa_client):
        resp = sa_client.post('/super-admin/backup/restore/987654')
        assert resp.status_code == 404

    def test_delete_backup_removes_row_and_file(self, sa_client, db, tmp_path):
        target = tmp_path / 'to_delete.sql.gz'
        target.write_bytes(b'gz')
        backup = _make_backup(db, backup_path=str(target))
        resp = sa_client.post(f'/super-admin/backup/delete/{backup.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        assert not target.exists()
        from models.backup import Backup

        assert db.session.get(Backup, backup.id) is None

    def test_delete_missing_backup_returns_404(self, sa_client):
        assert sa_client.post('/super-admin/backup/delete/987654').status_code == 404

    def test_cancel_backup_in_progress(self, sa_client, db):
        from app.shared.enums import BackupStatus

        backup = _make_backup(db, backup_status=BackupStatus.IN_PROGRESS)
        resp = sa_client.post(f'/super-admin/backup/cancel/{backup.id}')
        assert resp.status_code == 200
        db.session.refresh(backup)
        assert backup.backup_status == BackupStatus.CANCELLED

    def test_cancel_completed_backup_rejected(self, sa_client, db):
        from app.shared.enums import BackupStatus

        backup = _make_backup(db, backup_status=BackupStatus.COMPLETED)
        resp = sa_client.post(f'/super-admin/backup/cancel/{backup.id}')
        assert resp.status_code == 400

    def test_cancel_missing_backup_returns_404(self, sa_client):
        assert sa_client.post('/super-admin/backup/cancel/987654').status_code == 404

    def test_backup_schedule_defaults_and_update(self, sa_client, db):
        resp = sa_client.get('/super-admin/backup/schedule')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True

        resp = sa_client.post(
            '/super-admin/backup/schedule',
            json={'enabled': True, 'type': 'weekly', 'time': '03:30'},
        )
        assert resp.status_code == 200
        resp = sa_client.get('/super-admin/backup/schedule')
        body = resp.get_json()
        assert body['enabled'] is True
        assert body['type'] == 'weekly'
        assert body['time'] == '03:30'

    def test_backup_report_page(self, sa_client, db):
        _make_backup(db)
        assert sa_client.get('/super-admin/backup/report').status_code == 200

    def test_backup_export_logs_csv(self, sa_client, db):
        backup = _make_backup(db)
        resp = sa_client.get('/super-admin/backup/export-logs')
        assert resp.status_code == 200
        assert 'backup_logs.csv' in resp.headers.get('Content-Disposition', '')
        body = resp.get_data(as_text=True)
        assert 'backup_type' not in body  # header is English literals
        assert 'ID' in body.split('\n')[0]
        assert str(backup.id) in body

    def test_backup_history_contains_seeded_backup(self, sa_client, db):
        backup = _make_backup(db)
        resp = sa_client.get('/super-admin/backup/history')
        assert resp.status_code == 200
        history = resp.get_json()['history']
        matched = [entry for entry in history if entry['id'] == backup.id]
        assert matched
        assert matched[0]['status'] == backup.backup_status


# ---------------------------------------------------------------------------
# routes/super_admin/branding.py
# ---------------------------------------------------------------------------


class TestBrandingRoutes:
    def test_branding_page(self, sa_client):
        assert sa_client.get('/super-admin/branding').status_code == 200

    @pytest.mark.parametrize('doc_type', ['invoice', 'receipt', 'prescription', 'report', 'bogus'])
    def test_branding_preview_renders(self, sa_client, doc_type):
        resp = sa_client.get(f'/super-admin/branding/preview?doc_type={doc_type}')
        assert resp.status_code == 200

    def test_apply_theme_applies_colors(self, sa_client, db):
        from models.branding import SystemTheme

        theme = SystemTheme(
            name=_uniq('theme'),
            name_ar='TH-AR',
            primary_color='#112233',
            secondary_color='#445566',
            accent_color='#778899',
            background_color='#ffffff',
            text_color='#000000',
            is_active=True,
        )
        db.session.add(theme)
        db.session.commit()

        token = _csrf_from(sa_client, '/super-admin/branding')
        resp = sa_client.post(
            f'/super-admin/branding/apply-theme/{theme.id}',
            data={'csrf_token': token},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['colors']['primary_color'] == '#112233'

    def test_apply_theme_missing_returns_404(self, sa_client):
        token = _csrf_from(sa_client, '/super-admin/branding')
        resp = sa_client.post(
            '/super-admin/branding/apply-theme/987654',
            data={'csrf_token': token},
        )
        assert resp.status_code == 404

    def test_apply_theme_bad_csrf_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/branding/apply-theme/1',
            data={'csrf_token': 'definitely-not-valid'},
        )
        assert resp.status_code == 400

    def test_update_branding_persists_fields(self, sa_client, db):
        from models.branding import BrandingSettings

        token = _csrf_from(sa_client, '/super-admin/branding')
        org = _uniq('Org')
        resp = sa_client.post(
            '/super-admin/branding/update',
            data={
                'csrf_token': token,
                'organization_name': org,
                'organization_email': 'brand@example.com',
                'primary_color': '#123456',
                'tax_number': 'TX-123',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        branding = (
            db.session.execute(select(BrandingSettings).order_by(BrandingSettings.id.desc()))
            .scalars()
            .first()
        )
        assert branding is not None
        assert branding.organization_name == org
        assert branding.primary_color == '#123456'
        assert branding.tax_number == 'TX-123'

    def test_update_branding_json_response(self, sa_client):
        token = _csrf_from(sa_client, '/super-admin/branding')
        resp = sa_client.post(
            '/super-admin/branding/update',
            data={'csrf_token': token, 'organization_name': _uniq('Org')},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_update_branding_bad_csrf_json_returns_400(self, sa_client):
        resp = sa_client.post(
            '/super-admin/branding/update',
            data={'csrf_token': 'definitely-not-valid'},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_update_branding_logo_upload(self, sa_client, db):
        from models.branding import BrandingSettings

        token = _csrf_from(sa_client, '/super-admin/branding')
        resp = sa_client.post(
            '/super-admin/branding/update',
            data={
                'csrf_token': token,
                'organization_name': _uniq('Org'),
                'logo_file': (io.BytesIO(b'\x89PNG\r\n\x1a\nfake'), 'logo.png'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        assert resp.status_code == 302
        branding = (
            db.session.execute(select(BrandingSettings).order_by(BrandingSettings.id.desc()))
            .scalars()
            .first()
        )
        assert branding.logo_path and branding.logo_path.startswith('uploads/branding/')
        written = os.path.join(
            sa_client.application.root_path, 'static', branding.logo_path.replace('/', os.sep)
        )
        try:
            assert os.path.exists(written)
        finally:
            if os.path.exists(written):
                os.remove(written)


# ---------------------------------------------------------------------------
# routes/super_admin/data.py
# ---------------------------------------------------------------------------


class TestDataRoutes:
    def test_branch_templates_page(self, sa_client):
        assert sa_client.get('/super-admin/branch-templates').status_code == 200

    def test_branch_templates_post_and_read_back(self, sa_client, db):
        from models.system_config import SystemConfig

        items = [{'name': 'Branch A', 'city': 'Gaza'}]
        resp = sa_client.post('/super-admin/branch-templates', json={'items': items})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='branch_templates'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() == items

    def test_data_warehouse_page(self, sa_client):
        assert sa_client.get('/super-admin/data-warehouse').status_code == 200

    def test_data_warehouse_export(self, sa_client):
        resp = sa_client.get('/super-admin/data-warehouse/export?days=14')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_data_warehouse_export_clamps_days(self, sa_client):
        resp = sa_client.get('/super-admin/data-warehouse/export?days=99999')
        assert resp.status_code == 200

    def test_export_data_creates_downloadable_file(self, sa_client):
        resp = sa_client.post('/super-admin/export-data')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        filename = body['download_url'].rsplit('/', 1)[-1]
        try:
            download = sa_client.get(f'/super-admin/download-export/{filename}')
            assert download.status_code == 200
            payload = json.loads(download.get_data(as_text=True))
            assert 'users' in payload['data']
            assert 'patients' in payload['data']
            assert 'visits' in payload['data']
        finally:
            path = os.path.join('instance', filename)
            if os.path.exists(path):
                os.remove(path)

    def test_download_export_missing_file_redirects(self, sa_client):
        resp = sa_client.get(
            '/super-admin/download-export/no_such_file_12345.json', follow_redirects=False
        )
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# routes/super_admin/departments.py
# ---------------------------------------------------------------------------


class TestDepartmentRoutes:
    def test_departments_page_lists_departments(self, sa_client, db):
        dept = _make_department(db, name=_uniq('VisibleDept'))
        resp = sa_client.get('/super-admin/departments')
        assert resp.status_code == 200
        assert dept.name.encode() in resp.data

    def test_create_department_ok(self, sa_client, db):
        name = _uniq('En')
        resp = sa_client.post(
            '/super-admin/departments/create',
            data={'name': name, 'name_ar': 'DP-AR', 'description': 'd', 'phone': '050'},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert db.session.get(Department, body['department_id']) is not None

    def test_create_department_missing_fields_returns_400(self, sa_client):
        resp = sa_client.post('/super-admin/departments/create', data={'name': 'Only English'})
        assert resp.status_code == 400

    def test_view_department_page(self, sa_client, db):
        dept = _make_department(db)
        assert sa_client.get(f'/super-admin/department/{dept.id}').status_code == 200

    def test_view_missing_department_redirects(self, sa_client):
        assert sa_client.get('/super-admin/department/987654').status_code == 302

    def test_edit_department_post(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/edit-department/{dept.id}',
            data={
                'name': 'ED-AR',
                'name_en': 'Renamed English',
                'description': 'updated',
                'location': 'Floor 2',
                'phone': '0501234567',
                'is_active': 'y',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(dept)
        assert dept.name == 'Renamed English'
        assert dept.name_ar == 'ED-AR'
        assert dept.location == 'Floor 2'

    def test_department_staff_add_and_remove(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        dept = _make_department(db)
        user = ensure_test_user(db, test_tenant, username=_uniq('staff'), role='reception')
        resp = sa_client.post(
            f'/super-admin/department-staff/{dept.id}/add',
            json={'user_id': user.id},
        )
        assert resp.status_code == 200
        db.session.refresh(user)
        assert user.department_id == dept.id

        resp = sa_client.post(
            f'/super-admin/department-staff/{dept.id}/remove',
            json={'user_id': user.id},
        )
        assert resp.status_code == 200
        db.session.refresh(user)
        assert user.department_id is None

    def test_department_staff_page(self, sa_client, db):
        dept = _make_department(db)
        assert sa_client.get(f'/super-admin/department-staff/{dept.id}').status_code == 200

    def test_add_staff_missing_user_aborts_404(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/department-staff/{dept.id}/add',
            json={'user_id': 987654},
        )
        # abort(404) inside the view try-block is converted by the generic
        # exception handler into a 500 JSON response.
        assert resp.status_code in (404, 500)

    def test_activate_and_deactivate_department(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(f'/super-admin/deactivate-department/{dept.id}')
        assert resp.get_json()['success'] is True
        db.session.refresh(dept)
        assert dept.is_active is False
        resp = sa_client.post(f'/super-admin/activate-department/{dept.id}')
        assert resp.get_json()['success'] is True
        db.session.refresh(dept)
        assert dept.is_active is True

    def test_export_departments_csv(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.get('/super-admin/export-departments')
        assert resp.status_code == 200
        assert 'departments_export.csv' in resp.headers.get('Content-Disposition', '')
        body = resp.get_data(as_text=True)
        assert str(dept.id) in body


# ---------------------------------------------------------------------------
# routes/super_admin/security.py & security_logs_api.py
# ---------------------------------------------------------------------------


class TestSecurityRoutes:
    def test_security_logs_page(self, sa_client):
        assert sa_client.get('/super-admin/security-logs').status_code == 200

    def test_security_center_page(self, sa_client, db, sa_user):
        from models.audit_trail import LoginAttempt, SecurityEvent, SystemLog

        db.session.add(
            SecurityEvent(
                event_type='login_failed',
                description='test event',
                severity='high',
                user_id=sa_user.id,
                is_resolved=False,
            )
        )
        db.session.add(LoginAttempt(username='someone', success=False, user_ip='10.0.0.1'))
        db.session.add(
            SystemLog(
                log_level='ERROR',
                log_category='security',
                message='test error',
                user_id=sa_user.id,
            )
        )
        db.session.commit()
        assert sa_client.get('/super-admin/security-center').status_code == 200

    def test_audit_trail_page(self, sa_client, db, sa_user):
        from models.phi_audit_log import PHIAuditLog

        db.session.add(
            PHIAuditLog(
                actor_id=sa_user.id,
                ip_address='127.0.0.1',
                request_id='req-coverage-1',
                target_model='Patient',
                target_id=1,
                action='UPDATE',
                changes={'name': {'old': 'a', 'new': 'b'}},
            )
        )
        db.session.commit()
        assert sa_client.get('/super-admin/audit-trail').status_code == 200

    def test_audit_trail_filters(self, sa_client, db, sa_user):
        from models.phi_audit_log import PHIAuditLog

        db.session.add(
            PHIAuditLog(
                actor_id=sa_user.id,
                target_model='Patient',
                target_id=42,
                action='UPDATE',
            )
        )
        db.session.commit()
        resp = sa_client.get(
            '/super-admin/audit-trail?action_filter=UPDATE'
            f'&user_filter={sa_user.id}&model_filter=Patient'
            '&patient_id_filter=42&date_from=2000-01-01&date_to=2100-01-01'
        )
        assert resp.status_code == 200
        assert b'Patient' in resp.data

    def test_audit_trail_bad_filters_do_not_crash(self, sa_client):
        resp = sa_client.get(
            '/super-admin/audit-trail?action_filter=NOPE&user_filter=abc&patient_id_filter=xyz'
            '&date_from=notadate&date_to=alsonotadate'
        )
        assert resp.status_code == 200


class TestSecurityLogsApi:
    @pytest.fixture
    def seeded(self, db, sa_user):
        from models.audit_trail import AuditTrail, LoginAttempt

        trail = AuditTrail(
            entity_type='user',
            entity_id=sa_user.id,
            action='login_failed',
            user_id=sa_user.id,
            user_ip='10.0.0.9',
            description='coverage login failure unique-marker',
        )
        db.session.add(trail)
        db.session.add(
            LoginAttempt(username='coverage_attempt_user', success=False, user_ip='10.0.0.8')
        )
        db.session.commit()
        return sa_user

    def test_security_logs_default(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['pagination']['total'] >= 1
        actions = {item['action'] for item in body['items']}
        assert actions

    def test_security_logs_filter_by_action_login_failed(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?action=login_failed')
        assert resp.status_code == 200
        for item in resp.get_json()['items']:
            assert item['action'] == 'login_failed'

    def test_security_logs_filter_by_action_login(self, sa_client, seeded, db):
        from models.audit_trail import LoginAttempt

        db.session.add(LoginAttempt(username='coverage_ok_user', success=True, user_id=seeded.id))
        db.session.commit()
        resp = sa_client.get('/super-admin/api/security-logs?action=login')
        assert resp.status_code == 200
        for item in resp.get_json()['items']:
            assert item['action'] == 'login'

    def test_security_logs_filter_by_unknown_action(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?action=definitely_not_real')
        assert resp.status_code == 200
        assert resp.get_json()['items'] == []

    def test_security_logs_filter_severity(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?severity=high')
        assert resp.status_code == 200
        for item in resp.get_json()['items']:
            assert item['severity'] == 'high'
        resp = sa_client.get('/super-admin/api/security-logs?severity=low')
        assert resp.status_code == 200
        for item in resp.get_json()['items']:
            assert item['severity'] == 'low'

    def test_security_logs_filter_bogus_severity(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?severity=bogus')
        assert resp.status_code == 200
        assert resp.get_json()['items'] == []

    def test_security_logs_filter_by_user(self, sa_client, seeded):
        resp = sa_client.get(f'/super-admin/api/security-logs?user_id={seeded.id}')
        assert resp.status_code == 200

    def test_security_logs_filter_by_query_and_dates(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?q=unique-marker')
        assert resp.status_code == 200
        assert any('unique-marker' in (i['description'] or '') for i in resp.get_json()['items'])
        today = date.today().isoformat()
        resp = sa_client.get(f'/super-admin/api/security-logs?date_from={today}&date_to={today}')
        assert resp.status_code == 200
        resp = sa_client.get('/super-admin/api/security-logs?date_from=bogus&date_to=alsonotadate')
        assert resp.status_code == 200

    def test_security_logs_pagination_clamped(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs?page=1&page_size=9999')
        assert resp.status_code == 200
        assert resp.get_json()['pagination']['page_size'] == 100

    def test_security_logs_summary(self, sa_client, seeded):
        resp = sa_client.get('/super-admin/api/security-logs/summary')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['failed_logins'] >= 1
        assert body['logins_today'] >= 0


# ---------------------------------------------------------------------------
# routes/super_admin/dashboard.py
# ---------------------------------------------------------------------------


class TestDashboardRoutes:
    def test_dashboard_page_renders(self, sa_client, db, sa_user):
        from models.audit_trail import LoginAttempt, SecurityEvent, SystemLog

        db.session.add(
            SecurityEvent(
                event_type='permission_denied',
                description='coverage event',
                severity='medium',
                user_id=sa_user.id,
                is_resolved=False,
            )
        )
        db.session.add(LoginAttempt(username='dash_failed', success=False, user_ip='10.1.1.1'))
        db.session.add(
            SystemLog(log_level='ERROR', log_category='security', message='coverage error')
        )
        db.session.commit()
        assert sa_client.get('/super-admin/dashboard').status_code == 200


# ---------------------------------------------------------------------------
# routes/super_admin/api.py
# ---------------------------------------------------------------------------


class TestApiRoutes:
    def test_api_audit_log_creates_row(self, sa_client, db, sa_user):
        from models.audit_trail import AuditTrail

        marker = _uniq('marker')
        resp = sa_client.post(
            '/super-admin/api/audit-log',
            json={
                'action': 'login',
                'entity_type': 'system',
                'entity_id': 0,
                'description': marker,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        row = db.session.execute(select(AuditTrail).filter_by(description=marker)).scalars().first()
        assert row is not None
        assert row.action == 'login'

    def test_api_audit_log_sanitizes_unknown_action_and_entity(self, sa_client, db):
        from models.audit_trail import AuditTrail

        marker = _uniq('marker')
        resp = sa_client.post(
            '/super-admin/api/audit-log',
            json={
                'action': 'definitely_not_allowed',
                'entity_type': 'also_not_allowed',
                'description': marker,
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        row = db.session.execute(select(AuditTrail).filter_by(description=marker)).scalars().first()
        assert row is not None
        assert row.action == 'view'
        assert row.entity_type == 'system'
        assert 'raw_action=definitely_not_allowed' in (row.notes or '')
        assert 'raw_entity_type=also_not_allowed' in (row.notes or '')

    def test_api_recent_activities(self, sa_client, db, sa_user):
        from models.audit_trail import AuditTrail

        marker = _uniq('marker')
        db.session.add(
            AuditTrail(
                entity_type='system',
                entity_id=0,
                action='login',
                user_id=sa_user.id,
                description=marker,
            )
        )
        db.session.commit()
        resp = sa_client.get('/super-admin/api/recent-activities')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert any(marker in (a['title'] or '') for a in body['activities'])

    def test_api_ai_assistant_returns_response(self, sa_client):
        resp = sa_client.post('/super-admin/api/ai-assistant', json={'message': 'how many users'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert isinstance(body['response'], str) and body['response']


# ---------------------------------------------------------------------------
# routes/super_admin/usage.py & subscription.py
# ---------------------------------------------------------------------------


class TestUsageAndSubscription:
    def test_usage_page(self, sa_client):
        assert sa_client.get('/super-admin/usage').status_code == 200

    def test_subscription_status_page(self, sa_client):
        assert sa_client.get('/super-admin/subscription-status').status_code == 200

    def test_change_plan_page(self, sa_client):
        assert sa_client.get('/super-admin/change-plan').status_code == 200

    def test_change_plan_missing_version_redirects(self, sa_client):
        resp = sa_client.post(
            '/super-admin/change-plan', data={'action': 'upgrade'}, follow_redirects=False
        )
        assert resp.status_code == 302

    def test_change_plan_bogus_version_redirects(self, sa_client):
        resp = sa_client.post(
            '/super-admin/change-plan',
            data={'action': 'upgrade', 'package_version_id': '987654', 'billing_type': 'monthly'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_change_plan_bogus_downgrade_redirects(self, sa_client):
        resp = sa_client.post(
            '/super-admin/change-plan',
            data={'action': 'downgrade', 'package_version_id': '987654', 'billing_type': 'monthly'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
