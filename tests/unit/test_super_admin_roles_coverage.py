"""Real HTTP coverage for routes/super_admin/roles.py.

Complements test_super_admin_coverage.py and test_super_admin_wave2.py. Every
endpoint and helper branch in roles.py is exercised here so this module can be
run in isolation with --cov=routes.
"""

from __future__ import annotations

import re
import uuid

import pytest
from sqlalchemy import select

from models.department import Department


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


@pytest.fixture
def sa_client(app, client, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, test_tenant, username='super_admin_roles_cov', role='super_admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def sa_user(app, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, test_tenant, username='super_admin_roles_cov', role='super_admin')


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


def _make_role(db, name: str | None = None, is_system_role: bool = False):
    from app.core.tenant.models import Tenant
    from models.permissions import Role
    from tests.tenant_context import DEFAULT_TEST_TENANT_SLUG

    tenant = (
        db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
        .scalars()
        .first()
    )
    role = Role(
        name=name or _uniq('role'),
        name_ar='QD',
        description='test role',
        is_system_role=is_system_role,
        is_active=True,
        tenant_id=tenant.id if tenant is not None else None,
    )
    db.session.add(role)
    db.session.commit()
    return role


def _permission_ids(db, limit: int = 2):
    from models.permissions import Permission

    return [p.id for p in db.session.execute(select(Permission).limit(limit)).scalars().all()]


def _role_permission_ids(db, role_id: int) -> set[int]:
    from models.permissions import RolePermission

    return {
        rp.permission_id
        for rp in db.session.execute(select(RolePermission).filter_by(role_id=role_id))
        .scalars()
        .all()
    }


def _raise(*args, **kwargs):
    raise RuntimeError('boom')


def _no_tables(_engine=None):
    class _Insp:
        def has_table(self, name):
            return False

    return _Insp()


class TestRolesPage:
    def test_roles_page_renders(self, sa_client):
        assert sa_client.get('/super-admin/roles').status_code == 200

    def test_roles_page_exception_renders_empty(self, sa_client, monkeypatch):
        import routes.super_admin.roles as _m

        original = _m.db.session.execute

        def patched(*args, **kwargs):
            if 'roles' in str(args[0] if args else '').lower():
                raise RuntimeError('boom')
            return original(*args, **kwargs)

        monkeypatch.setattr('routes.super_admin.roles.db.session.execute', patched)
        resp = sa_client.get('/super-admin/roles')
        assert resp.status_code == 200


class TestCreateRole:
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
                'description': 'desc',
                'is_system_role': 'on',
                'is_active': 'on',
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
        assert resp.status_code == 200
        assert db.session.execute(select(Role).filter_by(name=name)).scalars().first() is None

    def test_create_role_commit_failure_redirects(self, sa_client, db, monkeypatch):
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        name = _uniq('commitfail')
        resp = sa_client.post(
            '/super-admin/roles/create',
            data={'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 200


class TestEditRole:
    def test_edit_role_get(self, sa_client, db):
        role = _make_role(db)
        assert sa_client.get(f'/super-admin/roles/{role.id}/edit').status_code == 200

    def test_edit_role_missing_redirects(self, sa_client):
        assert sa_client.get('/super-admin/roles/987654/edit').status_code == 302

    def test_edit_role_missing_post_redirects(self, sa_client):
        assert sa_client.post('/super-admin/roles/987654/edit', data={}).status_code == 302

    def test_edit_role_replaces_permissions_scoped_to_role(self, sa_client, db):
        role_a = _make_role(db)
        role_b = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(
            RolePermission(role_id=role_b.id, permission_id=perm_b, tenant_id=role_b.tenant_id)
        )
        db.session.commit()

        resp = sa_client.post(
            f'/super-admin/roles/{role_a.id}/edit',
            data={
                'name': role_a.name,
                'name_ar': 'R2-AR',
                'description': 'updated',
                'is_system_role': 'on',
                'is_active': 'on',
                'permissions': [str(perm_a)],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role_a.id) == {perm_a}
        assert _role_permission_ids(db, role_b.id) == {perm_b}

    def test_edit_role_bad_permission_id_rolls_back(self, sa_client, db):
        from models.permissions import RolePermission

        role = _make_role(db)
        perm = _permission_ids(db, 1)[0]
        db.session.add(
            RolePermission(role_id=role.id, permission_id=perm, tenant_id=role.tenant_id)
        )
        db.session.commit()
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/edit',
            data={'name': role.name, 'permissions': ['not-an-int']},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = db.session.execute(select(RolePermission).filter_by(role_id=role.id)).scalars().all()
        assert [r.permission_id for r in rows] == [perm]

    def test_edit_role_commit_failure_redirects(self, sa_client, db, monkeypatch):
        role = _make_role(db)
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/edit',
            data={'name': role.name},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestManageRolePermissions:
    def test_manage_permissions_get_renders(self, sa_client, db):
        role = _make_role(db)
        assert sa_client.get(f'/super-admin/roles/{role.id}/permissions').status_code == 200

    def test_manage_permissions_missing_role_get_redirects(self, sa_client):
        assert sa_client.get('/super-admin/roles/987654/permissions').status_code == 302

    def test_manage_permissions_missing_role_post_redirects(self, sa_client):
        assert sa_client.post('/super-admin/roles/987654/permissions').status_code == 302

    def test_manage_role_permissions_post_replaces_set(self, sa_client, db):
        role = _make_role(db)
        role_other = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(
            RolePermission(
                role_id=role_other.id, permission_id=perm_b, tenant_id=role_other.tenant_id
            )
        )
        db.session.commit()

        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/permissions',
            data={'permissions': [str(perm_a)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role.id) == {perm_a}
        assert _role_permission_ids(db, role_other.id) == {perm_b}

    def test_manage_role_permissions_commit_failure_redirects(self, sa_client, db, monkeypatch):
        role = _make_role(db)
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/permissions',
            data={},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestManageRoleDepartmentPermissions:
    def test_department_permissions_get_renders(self, sa_client, db):
        role = _make_role(db)
        assert (
            sa_client.get(f'/super-admin/roles/{role.id}/department-permissions').status_code == 200
        )

    def test_department_permissions_get_with_existing_rows(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        dept = _make_department(db)
        db.session.add(
            DepartmentPermission(
                role_id=role.id,
                department_id=dept.id,
                can_access=True,
                tenant_id=role.tenant_id,
            )
        )
        db.session.commit()
        assert (
            sa_client.get(f'/super-admin/roles/{role.id}/department-permissions').status_code == 200
        )

    def test_department_permissions_missing_role_get_redirects(self, sa_client, db):
        # tables exist; role missing -> abort -> except -> redirect
        assert sa_client.get('/super-admin/roles/987654/department-permissions').status_code == 302

    def test_department_permissions_missing_role_post_redirects(self, sa_client):
        assert (
            sa_client.post('/super-admin/roles/987654/department-permissions', data={}).status_code
            == 302
        )

    def test_department_permissions_tables_missing_get_redirects(self, sa_client, monkeypatch):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', _no_tables)
        resp = sa_client.get('/super-admin/roles/1/department-permissions', follow_redirects=False)
        assert resp.status_code == 302

    def test_department_permissions_tables_missing_post_redirects(self, sa_client, monkeypatch):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', _no_tables)
        resp = sa_client.post(
            '/super-admin/roles/1/department-permissions', data={}, follow_redirects=False
        )
        assert resp.status_code == 302

    def test_department_permissions_post_manage_flag_implies_can_access(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={f'dept_{dept.id}_can_manage_visits': 'on'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(
                select(DepartmentPermission).filter_by(role_id=role.id, department_id=dept.id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].can_access is True
        assert rows[0].can_manage_visits is True

    def test_department_permissions_post_all_manage_flag_implies_can_access(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={'dept_all_can_manage_staff': 'on'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        )
        all_rows = [r for r in rows if r.department_id is None]
        assert len(all_rows) == 1
        assert all_rows[0].can_access is True
        assert all_rows[0].can_manage_staff is True

    def test_department_permissions_post_no_flags_inserts_nothing(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={f'dept_{dept.id}_can_access': '', f'dept_{dept.id}_can_manage_visits': ''},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        )
        assert rows == []

    def test_department_permissions_post_full_matrix(self, sa_client, db):
        from models.advanced_permissions import DepartmentPermission

        role = _make_role(db)
        dept = _make_department(db)
        role_other = _make_role(db)
        db.session.add(
            DepartmentPermission(
                role_id=role_other.id,
                department_id=dept.id,
                can_access=True,
                tenant_id=role_other.tenant_id,
            )
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
        other = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role_other.id))
            .scalars()
            .all()
        )
        assert len(other) == 1

    def test_department_permissions_commit_failure_redirects(self, sa_client, db, monkeypatch):
        role = _make_role(db)
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestPermissionsMatrix:
    def test_permissions_matrix_page(self, sa_client):
        assert sa_client.get('/super-admin/permissions-matrix').status_code == 200

    def test_permissions_matrix_tables_missing_get_redirects(self, sa_client, monkeypatch):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', _no_tables)
        resp = sa_client.get('/super-admin/permissions-matrix', follow_redirects=False)
        assert resp.status_code == 302

    def test_permissions_matrix_tables_missing_post_redirects(self, sa_client, monkeypatch):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', _no_tables)
        resp = sa_client.post('/super-admin/permissions-matrix', data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_permissions_matrix_create_default_exception_still_renders(
        self, sa_client, monkeypatch
    ):
        monkeypatch.setattr(
            'models.permissions.create_default_permissions',
            _raise,
        )
        resp = sa_client.get('/super-admin/permissions-matrix')
        assert resp.status_code == 200

    def test_permissions_matrix_post_replaces_submitted_and_clears_others(self, sa_client, db):
        role_a = _make_role(db)
        role_b = _make_role(db)
        perm_a, perm_b = _permission_ids(db, 2)

        from models.permissions import RolePermission

        db.session.add(
            RolePermission(role_id=role_b.id, permission_id=perm_b, tenant_id=role_b.tenant_id)
        )
        db.session.commit()

        resp = sa_client.post(
            '/super-admin/permissions-matrix',
            data={f'role_{role_a.id}_permissions': [str(perm_a)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _role_permission_ids(db, role_a.id) == {perm_a}
        assert _role_permission_ids(db, role_b.id) == set()

    def test_permissions_matrix_post_skips_invalid_permission_ids(self, sa_client, db):
        from models.permissions import RolePermission

        role = _make_role(db)
        perm = _permission_ids(db, 1)[0]
        resp = sa_client.post(
            '/super-admin/permissions-matrix',
            data={f'role_{role.id}_permissions': ['not-an-int', str(perm)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = db.session.execute(select(RolePermission).filter_by(role_id=role.id)).scalars().all()
        assert [r.permission_id for r in rows] == [perm]

    def test_permissions_matrix_commit_failure_redirects(self, sa_client, db, monkeypatch):
        _make_role(db)
        _permission_ids(db, 1)
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(
            '/super-admin/permissions-matrix',
            data={},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestDeleteRole:
    def test_delete_role_removes_role_and_permissions(self, sa_client, db):
        role = _make_role(db)
        perm_a = _permission_ids(db, 1)[0]

        from models.permissions import Role, RolePermission

        db.session.add(
            RolePermission(role_id=role.id, permission_id=perm_a, tenant_id=role.tenant_id)
        )
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

    def test_delete_role_commit_failure_redirects(self, sa_client, db, monkeypatch):
        role = _make_role(db)
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(f'/super-admin/roles/{role.id}/delete', follow_redirects=False)
        assert resp.status_code == 302


class TestPermissionsPage:
    def test_permissions_page(self, sa_client):
        assert sa_client.get('/super-admin/permissions').status_code == 200

    def test_permissions_page_exception_renders_empty(self, sa_client, monkeypatch):
        import routes.super_admin.roles as _m

        original = _m.db.session.execute

        def patched(*args, **kwargs):
            if 'permissions' in str(args[0] if args else '').lower():
                raise RuntimeError('boom')
            return original(*args, **kwargs)

        monkeypatch.setattr('routes.super_admin.roles.db.session.execute', patched)
        resp = sa_client.get('/super-admin/permissions')
        assert resp.status_code == 200


class TestCreatePermission:
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

    def test_create_permission_commit_failure_redirects(self, sa_client, db, monkeypatch):
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        name = _uniq('permcf')
        resp = sa_client.post(
            '/super-admin/permissions/create',
            data={'name': name, 'description': 'x', 'category': 'AUDIT', 'level': 'READ'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestEditPermission:
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

    def test_edit_permission_missing_redirects(self, sa_client):
        assert sa_client.post('/super-admin/permissions/987654/edit', data={}).status_code == 302

    def test_edit_permission_commit_failure_redirects(self, sa_client, db, monkeypatch):
        from models.permissions import Permission

        name = _uniq('permcf2')
        sa_client.post(
            '/super-admin/permissions/create',
            data={'name': name, 'description': 'x', 'category': 'AUDIT', 'level': 'READ'},
            follow_redirects=False,
        )
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(
            f'/super-admin/permissions/{row.id}/edit',
            data={'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestDeletePermission:
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

    def test_delete_permission_commit_failure_redirects(self, sa_client, db, monkeypatch):
        from models.permissions import Permission

        name = _uniq('permcf3')
        sa_client.post(
            '/super-admin/permissions/create',
            data={'name': name, 'description': 'x', 'category': 'AUDIT', 'level': 'READ'},
            follow_redirects=False,
        )
        row = db.session.execute(select(Permission).filter_by(name=name)).scalars().first()
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        resp = sa_client.post(f'/super-admin/permissions/{row.id}/delete', follow_redirects=False)
        assert resp.status_code == 302


class TestCreateRoleSimple:
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

    def test_create_role_simple_commit_failure_redirects(self, sa_client, db, monkeypatch):
        token = _csrf_from(sa_client, '/super-admin/users')
        assert token
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        name = _uniq('simplecf')
        resp = sa_client.post(
            '/super-admin/create-role-simple',
            data={'csrf_token': token, 'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestCreatePermissionSimple:
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

    def test_create_permission_simple_commit_failure_redirects(self, sa_client, db, monkeypatch):
        token = _csrf_from(sa_client, '/super-admin/users')
        assert token
        monkeypatch.setattr(
            'routes.super_admin.roles.safe_commit',
            _raise,
        )
        name = _uniq('simplepermc')
        resp = sa_client.post(
            '/super-admin/create-permission-simple',
            data={'csrf_token': token, 'name': name},
            follow_redirects=False,
        )
        assert resp.status_code == 302


class TestCreateRoleValidation:
    def test_missing_name_persists_no_role(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.permissions import Role

        marker = _uniq('missingname')
        resp = sa_client.post(
            '/super-admin/roles/create',
            data={'name_ar': marker, 'description': 'no name submitted'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)
        count = db.session.execute(
            select(sfunc.count()).select_from(Role).filter_by(name_ar=marker)
        ).scalar()
        assert count == 0


class TestEditRoleRollback:
    def test_bad_permission_id_rolls_back_delete(self, sa_client, db):
        from models.permissions import RolePermission

        role = _make_role(db, name=None)
        # ensure tenant? _make_role doesn't set tenant; ok
        perm = _permission_ids(db, 1)[0]
        db.session.add(
            RolePermission(role_id=role.id, permission_id=perm, tenant_id=role.tenant_id)
        )
        db.session.commit()
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/edit',
            data={'name': role.name, 'permissions': ['not-an-int']},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = db.session.execute(select(RolePermission).filter_by(role_id=role.id)).scalars().all()
        assert [r.permission_id for r in rows] == [perm]
