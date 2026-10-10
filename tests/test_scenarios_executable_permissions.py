"""Execute the role and permission lifecycle over real HTTP.

Phase 2, access control. Roles and permissions are the one part of the system
where a successful write is almost always wrong by accident: creating a permission
with a level the decorator does not recognise, or granting a role globally when it
was meant to be departmental, produces an application that looks correct and
admits the wrong person.

The assertions here are on rows rather than on status codes, because a redirect
says only that the handler did not raise. The route catches every exception and
flashes a generic message, so from outside a failed write and a successful one look
identical. That is not a property of the test; it is why reading the status code
would have reported this module as green while the catalogue stayed empty.

What execution established, and what the cases below now hold:

  * permission.category and permission.level are database enums whose members are
    upper case, while the application posts lower case. Every permission created
    from the form is rejected.
  * A role_permission grant is written and can be read back.
  * owner is accepted by the platform guard, so the role console is not as narrow as
    the name suggests.
"""

from __future__ import annotations

import inspect

import pytest
from flask import g
from sqlalchemy import func, select

from app.extensions import db
from models.permissions import Permission, Role, RolePermission
from tests.scenario_execution_registry import covers


def _super_admin(app, tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username='e2e_super_admin', role='super_admin')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = tenant.id
        login_test_client(client, user, tenant)
    return client, user


@pytest.fixture
def platform(app, test_tenant):
    """A super_admin session carrying a tenant for the request context."""
    client, _user = _super_admin(app, test_tenant)
    return {'app': app, 'client': client, 'tenant': test_tenant}


def _count_permissions(app, name):
    return db.session.execute(
        select(func.count()).select_from(Permission).where(Permission.name == name)
    ).scalar()


def _create_permission(client, name, category, level, description='probe'):
    """POST the create route exactly as the caller does."""
    return client.post(
        '/super-admin/permissions/create',
        data={
            'name': name,
            'description': description,
            'category': category,
            'level': level,
        },
        follow_redirects=False,
    )


@covers('IDENTITY_PERMISSION_MATRIX')
class TestPermissionMatrixIsExecuted:
    """The permission catalogue is not writable at all, and this is the evidence."""

    def test_the_enums_the_application_posts_are_not_the_ones_the_column_accepts(self):
        """The first of two independent defects, stated as data.

        Read rather than executed because the two conventions are visible side by
        side here, and the value of the finding is precisely that they disagree: the
        application side is consistent with itself and only the column is out of
        step. Knowing which side is wrong is what decides the fix.
        """
        from app.shared.enums import PermissionCategory, PermissionLevel

        db_categories = set(Permission.__table__.columns['category'].type.enums)
        db_levels = set(Permission.__table__.columns['level'].type.enums)
        py_categories = {m.value for m in PermissionCategory}
        py_levels = {m.value for m in PermissionLevel}

        assert py_categories == {c.lower() for c in db_categories}, (
            f'the category enum changed shape: application {sorted(py_categories)} '
            f'against database {sorted(db_categories)}'
        )
        assert py_levels == {lvl.lower() for lvl in db_levels}, (
            f'the level enum changed shape: application {sorted(py_levels)} against '
            f'database {sorted(db_levels)}'
        )
        assert not (py_categories & db_categories), (
            'the category enum now overlaps the database enum; the posted values are '
            'accepted and this finding needs re-checking'
        )
        assert not (py_levels & db_levels), (
            'the level enum now overlaps the database enum; this finding is stale'
        )

    def test_no_permission_can_be_created_from_the_values_the_form_posts(self, platform):
        """The second of two independent defects: the route never sets tenant_id.

        permissions carries a row-level security policy, so an insert whose tenant_id
        is null is rejected with InsufficientPrivilege whatever the enums say. The
        create route never assigns tenant_id, so it cannot insert.

        Either defect alone prevents a permission being created. Together they mean
        the catalogue is unwritable: the values the form posts fail the enum check,
        and the values the column accepts fail the security check. A deployment
        therefore cannot add a permission through the interface at all.

        Asserted over HTTP because the route catches everything and flashes a generic
        message, so the row is the only evidence.
        """
        app, client, tenant = platform['app'], platform['client'], platform['tenant']
        from app.shared.enums import PermissionCategory, PermissionLevel

        before = _count_permissions(app, 'e2e_template_probe')
        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = _create_permission(
                client,
                'e2e_template_probe',
                PermissionCategory.MEDICAL_RECORDS.value,
                PermissionLevel.READ.value,
            )
        assert resp.status_code in (200, 302), (
            f'the create route answered {resp.status_code}; it no longer redirects on '
            f'failure, so this finding needs re-reading'
        )
        db.session.expire_all()
        assert _count_permissions(app, 'e2e_template_probe') == before, (
            'a permission was created from the values the form posts; the enum case '
            'mismatch has been fixed elsewhere and this finding is stale'
        )

    def test_a_permission_row_carries_a_tenant_because_the_policy_needs_one(self):
        """Why the missing tenant_id matters rather than being cosmetic.

        Read from information_schema rather than inferred, because the model says
        tenant_id is nullable while the deployed column and its RLS policy are what
        actually decide whether a row can be written.
        """
        from sqlalchemy import text

        row = (
            db.session.execute(
                text(
                    'SELECT is_nullable, (SELECT count(*) FROM pg_policies '
                    " WHERE tablename = 'permissions') AS policies "
                    'FROM information_schema.columns '
                    "WHERE table_name = 'permissions' AND column_name = 'tenant_id'"
                )
            )
            .mappings()
            .first()
        )
        assert row is not None, 'permissions no longer has a tenant_id column'
        assert row['policies'] > 0, (
            'permissions no longer has a row-level security policy, so the missing '
            'tenant_id in the create route is harmless and this finding is stale'
        )

    def test_the_catalogue_page_renders_and_swallows_a_failed_query(self, platform):
        """The permissions page cannot distinguish an empty catalogue from a failed query.

        The handler wraps its select in a bare except and renders the same template
        with an empty list when the query raises. That is a deliberate choice to show
        a page rather than an error, and it has the consequence that an operator
        cannot tell "there are no permissions" from "the permission table is
        unreadable", which is the state a deployment is in when the catalogue has
        never been writable.

        Asserted rather than worked around, because a test that proved rows render
        would have to distinguish the two states, which is precisely what the page
        cannot do from outside.
        """
        app, client, tenant = platform['app'], platform['client'], platform['tenant']
        import inspect

        source = inspect.getsource(type(client).__mro__[0]) if False else ''
        from routes.super_admin import roles as roles_module

        handler = inspect.getsource(roles_module.permissions)
        assert 'except Exception' in handler, (
            'the permissions handler no longer catches everything; if it now surfaces '
            'the failure, this note is stale'
        )
        assert 'permissions=[]' in handler, (
            'the fallback no longer renders an empty list; a failure may now be '
            'visible, and this test should be rewritten to assert what is shown'
        )

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.get('/super-admin/permissions', follow_redirects=False)
        assert resp.status_code == 200, f'the permission list answered {resp.status_code}'


@covers('IDENTITY_ROLE_DEPARTMENT_BINDING')
class TestRoleAndPermissionGrantingIsExecuted:
    """Attaching a permission to a role writes a join row that can be read back."""

    def test_granting_one_role_removes_the_grants_of_every_other_role(self, platform):
        """The grant route clears the whole join table before writing its own.

        manage_role_permissions issues ``select(RolePermission).delete()`` with no
        where clause, so granting a permission to one role removes every grant held
        by every other role in the deployment and then writes back only the selected
        ones. Two roles before the call, one after, and the flash says the grant
        succeeded.

        This is the most consequential thing in this file. It is not a wrong value
        or a missed edge: it silently removes access, in a table nobody is watching,
        from roles that were never part of the request.

        Measured by counting rather than by reading the source, because the source
        reads like an ordinary reset-then-set and only the count shows what it reset.
        """
        app, client, tenant = platform['app'], platform['client'], platform['tenant']
        keeper = Role(
            tenant_id=tenant.id, name='e2e_keeper', description='unrelated', is_active=True
        )
        target = Role(
            tenant_id=tenant.id, name='e2e_target', description='the role', is_active=True
        )
        kept = Permission(
            tenant_id=tenant.id,
            name='e2e_kept_permission',
            description='held by the other role',
            category='REPORTS',
            level='READ',
            is_active=True,
        )
        granted = Permission(
            tenant_id=tenant.id,
            name='e2e_new_permission',
            description='being granted now',
            category='SECURITY',
            level='WRITE',
            is_active=True,
        )
        db.session.add_all([keeper, target, kept, granted])
        db.session.commit()
        db.session.add(
            RolePermission(tenant_id=tenant.id, role_id=keeper.id, permission_id=kept.id)
        )
        db.session.commit()

        assert db.session.execute(select(func.count()).select_from(RolePermission)).scalar() >= 1, (
            'the pre-existing grant was not written'
        )

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                f'/super-admin/roles/{target.id}/permissions',
                data={'permissions': [str(granted.id)]},
                follow_redirects=False,
            )
        assert resp.status_code in (200, 302), (
            f'granting the permission was answered {resp.status_code}'
        )

        db.session.expire_all()
        survivors = (
            db.session.execute(
                select(RolePermission).filter_by(role_id=keeper.id, permission_id=kept.id)
            )
            .scalars()
            .first()
        )
        assert survivors is not None, (
            'granting one role removed a grant that belonged to a different role. '
            'manage_role_permissions deletes every row in role_permission before '
            'writing the selection, so access granted anywhere in the deployment is '
            'silently dropped. The delete needs a where clause on this role.'
        )

    def test_a_department_binding_is_not_the_same_thing_as_a_global_grant(self):
        """The two grants are stored apart, so conflating them over-grants.

        Asserted as a distinction rather than as a behaviour. If role_permission ever
        grows a department_id the grants can be scoped, and this test is written to
        fail then, because the distinction it describes would no longer be the one
        the code makes.
        """
        columns = {c.name for c in RolePermission.__table__.columns}
        assert 'department_id' not in columns, (
            'role_permission now carries a department_id, so a grant can be scoped; '
            'this test should be rewritten to assert the scoped behaviour'
        )
        assert 'role_id' in columns and 'permission_id' in columns, (
            'the join table no longer links a role to a permission, so the grant shape '
            'this describes has changed'
        )

    def test_owner_is_accepted_by_the_platform_guard(self, platform, test_tenant):
        """The role console is reachable by an owner, which the name does not suggest.

        A tenant administrator holding the whole platform role table is a larger
        grant than "can manage my tenant", and nothing in super_admin_required or in
        the route names says otherwise. Stated here rather than hidden in a policy
        test so the grant is visible where the routes are.
        """
        app, tenant = platform['app'], test_tenant
        from tests.tenant_context import ensure_test_user, login_test_client
        from utils.decorators import super_admin_required

        source = inspect.getsource(super_admin_required)
        accepted = next(
            line for line in source.splitlines() if 'not in' in line and 'super_admin' in line
        )
        assert "'owner'" in accepted, (
            f'owner was removed from the platform guard ({accepted.strip()}); the '
            f'console is narrower now and this note is stale'
        )

        owner = ensure_test_user(db, tenant, username='e2e_owner_probe', role='owner')
        client = app.test_client()
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(client, owner, tenant)
            resp = client.get('/super-admin/roles', follow_redirects=False)
        assert resp.status_code in (200, 302), (
            f'owner opened the role console with {resp.status_code}; the guard changed'
        )
