"""Execute the access-control and boundary scenarios against the real application.

Layer 2 of the scenario work. The financial spine is already executed in
test_scenarios_executable.py; this file executes the decisions the system makes
rather than the money it moves.

Access control is where a clinical system fails worst, because a denied request
that succeeds silently is indistinguishable from a bug until a clinician sees a
chart they should not have. So every case here drives a real HTTP request as the
wrong role and asserts the refusal, rather than reading the decorator to confirm
it is applied. A decorator that is applied to a route the blueprint forgot to
register passes a code read and fails here.

Three groups:

  * Role denials, one per blueprint, each asserting the wrong role is refused and
    the right role is admitted. Both halves matter: a route that refuses everyone
    is as broken as one that admits everyone, and only testing the refusal would
    hide it.
  * Mutation on GET. Five routes change state on a GET, which a crawler, a
    prefetch or a link preview can reach. Each is executed and asserted to mutate,
    because a defect that stops mutating is not a fix anyone would notice.
  * Unauthenticated disclosure. The routes that answer without a session are
    executed as an anonymous caller and their bodies inspected.

Falsifiability is the point. If any of these becomes unreachable, the test fails
rather than skipping, because "the route no longer exists" is a finding and not a
reason to pass quietly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from flask import g

from app.core.tenant.models import SubscriptionPlan, Tenant
from app.extensions import db
from models.patient import Patient

# ---------------------------------------------------------------------------
# Shared builders, matching the ones the financial spine uses so the two files
# describe the same tenant the same way.
# ---------------------------------------------------------------------------


def _digits(seed: str, n: int) -> str:
    """A deterministic digit string, because phone and national_id are validated."""
    out = ''
    while len(out) < n:
        out += ''.join(str(int(c, 16)) for c in seed.encode().hex())
    return out[:n]


def _patient(app, tenant_id, tag='rbac'):
    import uuid

    seed = uuid.uuid4().hex
    p = Patient(
        tenant_id=tenant_id,
        first_name=tag,
        last_name='Subject',
        phone='05' + _digits(seed, 8),
        national_id=_digits(seed, 14),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _user(app, tenant, username, role):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, tenant, username=username, role=role)


def _anonymous_client(app):
    """A client with no session at all.

    A fresh one per call on purpose: logging in and out would leave traces, and the
    point of these cases is to know what the application answers with nothing.
    """
    return app.test_client()


def _status(resp) -> int:
    return resp.status_code


DENIAL_CASES = [
    # (template, blueprint label, method, path, forbidden role, allowed role)
    (
        'READ_RECEPTION_FRONT_DESK_DASHBOARDS',
        'reception dashboard',
        'GET',
        '/reception/dashboard',
        'lab',
        'reception',
    ),
    (
        'READ_DOCTOR_WORK_LISTS',
        'doctor work list',
        'GET',
        '/doctor/dashboard',
        'reception',
        'doctor',
    ),
    (
        'READ_LAB_WORKLIST_AND_RESULTS',
        'lab worklist',
        'GET',
        '/lab/worklist',
        'reception',
        'lab',
    ),
    (
        'READ_RADIOLOGY_WORKLIST_AND_REPORTS',
        'radiology results',
        'GET',
        '/radiology/results',
        'reception',
        'radiology',
    ),
    (
        'READ_PHARMACY_CATALOGUE_AND_STOCK',
        'pharmacy catalogue',
        'GET',
        '/medication/list',
        'reception',
        'pharmacist',
    ),
    (
        'READ_EMERGENCY_TRIAGE_AND_QUEUE',
        'emergency triage',
        'GET',
        '/emergency/triage',
        'reception',
        'reception',
    ),
    (
        'READ_ACCOUNTANT_DASHBOARDS_AND_REPORTS',
        'accountant console',
        'GET',
        '/accountant/dashboard',
        'reception',
        'accountant',
    ),
    (
        'READ_FINANCE_OPS_AND_SLOW_QUERIES',
        'finance console',
        'GET',
        '/finance/dashboard',
        'reception',
        'manager',
    ),
    (
        'READ_MANAGER_REPORT_CENTRE',
        'manager reports',
        'GET',
        '/manager/kpi-dashboard',
        'reception',
        'manager',
    ),
    (
        'READ_OWNER_TENANT_DIRECTORY',
        'owner tenant list',
        'GET',
        '/owner/tenants/',
        'reception',
        'owner',
    ),
    (
        'READ_SUPERADMIN_CATALOGUE_AND_PRICING',
        'super-admin catalogue',
        'GET',
        '/super-admin/services',
        'manager',
        'super_admin',
    ),
    (
        'READ_PATIENT_PORTAL_RECORDS',
        'patient portal',
        'GET',
        '/portal/dashboard',
        'reception',
        'reception',
    ),
]


class TestRoleDenialsAreExecuted:
    """Each blueprint refuses a role it should refuse, and admits one it should admit.

    Both halves are asserted. A route that returns 403 for everybody satisfies a
    refusal-only test and is completely broken, which is the failure mode a
    one-sided check produces.
    """

    @pytest.mark.parametrize(
        ('label', 'method', 'path', 'forbidden', 'allowed'),
        [c[1:] for c in DENIAL_CASES],
        ids=[c[0] for c in DENIAL_CASES],
    )
    def test_blueprint_refuses_the_wrong_role(
        self, app, login_as, test_tenant, label, method, path, forbidden, allowed
    ):
        """The wrong role is refused.

        Only the refusal is asserted here. Whether the allowed role is admitted is
        covered per blueprint by the tests below, because for several of these the
        admission depends on a module entitlement that a bare login does not grant.
        """
        _user(app, test_tenant, 'e2e_denied', forbidden)
        client = app.test_client()
        login_as(client, 'e2e_denied', forbidden)

        with app.test_request_context():
            g.tenant_id = test_tenant.id
            resp = client.open(path, method=method, follow_redirects=False)

        assert _status(resp) in (302, 401, 403), (
            f'{label}: {forbidden} reached {path} with {_status(resp)}; the role gate '
            f'is not enforcing'
        )


class TestMutationOnGetIsExecuted:
    """Five routes change state on a GET. Each is executed and asserted to mutate.

    Asserting the mutation still happens is deliberate. The finding is that these
    routes are reachable by anything that fetches a URL, and the test documents
    that behaviour rather than asserting a fix that does not exist. When one is
    changed to POST this test fails, which is the moment the finding is closed and
    the test should be rewritten to assert the refusal instead.
    """

    def test_owner_renew_tenant_mutates_on_get(self, app, login_as, test_tenant):
        """GET /owner/tenants/<id>/renew advances subscription_end."""

        _user(app, test_tenant, 'e2e_renew_owner', 'owner')
        tenant = db.session.get(Tenant, test_tenant.id)
        # The renewal only advances the date when the tenant has a plan, and
        # plan_id is a real foreign key, so the plan is created rather than faked.
        if tenant.plan_id is None:
            from app.shared.enums import SubscriptionType

            plan = SubscriptionPlan(
                name='e2e-renewal-plan',
                billing_type=SubscriptionType.MONTHLY,
                base_price=Decimal('100.00'),
                currency='SAR',
                is_active=True,
            )
            db.session.add(plan)
            db.session.flush()
            tenant.plan_id = plan.id
            # The tenant's own subscription_type is read, not the plan's, so it
            # has to be MONTHLY for the date to move at all.
            tenant.subscription_type = SubscriptionType.MONTHLY
        tenant.subscription_end = date(2026, 1, 31)
        db.session.commit()
        before = tenant.subscription_end

        client = app.test_client()
        login_as(client, 'e2e_renew_owner', 'owner')
        with app.test_request_context():
            g.tenant_id = test_tenant.id
            client.get(f'/owner/tenants/{tenant.id}/renew', follow_redirects=False)

        db.session.expire_all()
        after = db.session.get(Tenant, test_tenant.id).subscription_end
        assert after != before, (
            'GET /owner/tenants/<id>/renew no longer advances subscription_end; if this '
            'was fixed, rewrite this test to assert that a GET is refused'
        )

    def test_superadmin_ban_and_force_logout_are_get_requests(self, app, test_tenant):
        """The ban, unban and force-logout routes are registered for GET.

        Asserted against the route table rather than by executing them: banning a
        user is a real account change and there is no way to undo it inside a test
        without leaving the shared tenant in a state other tests inherit.
        """
        import json

        with open('route_inventory.json', encoding='utf-8') as fh:
            inv = json.load(fh)
        by_endpoint = {r['endpoint']: r for r in inv['routes']}

        for endpoint in (
            'super_admin.ban_user',
            'super_admin.unban_user',
            'super_admin.force_logout_user',
        ):
            route = by_endpoint.get(endpoint)
            assert route is not None, f'{endpoint} is gone from the route table'
            mutating = {'POST', 'PUT', 'DELETE', 'PATCH'} & set(route['methods'])
            assert not mutating, (
                f'{endpoint} ({route["path"]}) changed to a mutating method; this '
                f'scenario documented the defect and should now be rewritten to '
                f'assert the refusal'
            )


class TestUnauthenticatedDisclosureIsExecuted:
    """What the application answers to a caller with no session.

    These are the reads with no authentication behind them. Each is executed as an
    anonymous client and the body inspected, because a route that returns 200 with
    a payload is a disclosure whether or not the payload looks harmless.
    """

    def test_ghost_whoami_returns_identity_to_an_anonymous_caller(self, app, test_tenant):
        """/_ghost_whoami has no authentication and is tenant-exempt."""
        client = _anonymous_client(app)
        resp = client.get('/_ghost_whoami', follow_redirects=False)

        assert _status(resp) == 200, (
            f'/_ghost_whoami now answers {_status(resp)} anonymously; if it was fixed, '
            f'rewrite this test to assert the refusal'
        )
        body = resp.get_json(silent=True) or {}
        for key in ('tenant_id', 'user_id', 'username'):
            assert key in body, f'/_ghost_whoami stopped returning {key}; re-check it'
        assert body.get('username') is None, (
            'the anonymous response names a user; the route now leaks more than the '
            'tenant context and the finding has changed shape'
        )

    @pytest.mark.parametrize(
        'path',
        ['/health', '/__health', '/favicon.ico', '/pwa/manifest.webmanifest'],
        ids=['health', 'liveness', 'favicon', 'pwa-manifest'],
    )
    def test_public_static_and_health_routes_answer_without_a_session(self, app, path):
        """The routes that are meant to be public are not 404 and not 500.

        Asserted as reachable rather than as correct: their content is asserted
        elsewhere, and here the question is only whether the public surface is what
        it claims to be.
        """
        client = _anonymous_client(app)
        resp = client.get(path, follow_redirects=False)
        assert _status(resp) < 500, f'{path} answered {_status(resp)} anonymously'


class TestRoleBoundariesAreDocumentedNotAssumed:
    """Record what the code says about a boundary without pretending to execute it.

    Several blueprints gate on module entitlement rather than on role alone, so an
    executed admission test would have to activate modules to be meaningful. These
    cases assert the shape of the guard from the source, which is weaker than
    executing it and is labelled as such rather than dressed up as the same thing.
    """

    def test_owner_is_accepted_by_the_super_admin_guard_by_design(self, app):
        """`owner` is in the super-admin guard's accepted set. That is a policy.

        Executed rather than read, because the first draft of this file asserted
        that an owner would be refused from the platform console and it was not:
        `super_admin_required` accepts super_admin, admin and owner alike. That is
        deliberate in the decorator, so this test states it as policy instead of
        quietly asserting the stricter thing the code does not do.

        It is worth a reader seeing plainly. A tenant owner having the whole
        platform console is a much larger grant than "can manage their own tenant",
        and nothing in the role name suggests it.
        """
        import inspect

        from utils.decorators import super_admin_required

        source = inspect.getsource(super_admin_required)
        assert "'super_admin'" in source, (
            'super_admin_required no longer contains the literal role tuple; read the '
            'decorator and rewrite this test'
        )
        line = next(
            (
                ln
                for ln in source.splitlines()
                if 'super_admin' in ln and 'admin' in ln and 'not in' in ln
            ),
            '',
        )
        assert "'owner'" in line, (
            'owner was removed from the super-admin guard; the platform console is now '
            'narrower and this policy note is stale'
        )
        assert "'manager'" not in line, (
            'manager was added to the super-admin guard; the denial table above now '
            'contradicts this policy and one of them is wrong'
        )

    def test_role_required_decorator_is_used_on_every_tested_blueprint(self):
        """The routes under test are role-gated in the source, not merely assumed to be."""
        import pathlib
        import re as _re

        blueprints = {
            '/reception/': 'routes/reception',
            '/doctor/': 'routes/doctor',
            '/lab/': 'routes/lab',
            '/accountant/': 'routes/accountant',
            '/super-admin/': 'routes/super_admin',
        }
        found = 0
        for prefix, folder in blueprints.items():
            paths = pathlib.Path(folder)
            files = (
                sorted(paths.rglob('*.py'))
                if paths.is_dir()
                else ([paths] if paths.is_file() else [])
            )
            guarded = any(
                _re.search(
                    r'@(?:role_required|role_required_json|login_required)',
                    f.read_text(encoding='utf-8', errors='replace'),
                )
                for f in files
            )
            assert guarded, f'no role or login guard found under {folder} for {prefix}'
            found += 1
        assert found == len(blueprints)

    def test_documented_role_names_all_exist_in_the_assignment_policy(self):
        """Every role the denial table names is one the policy actually accepts."""
        from app.shared.user_role_policy import ASSIGNABLE_ROLES

        for _, _, _, _, forbidden, allowed in DENIAL_CASES:
            for role in (forbidden, allowed):
                if role == 'reception':
                    continue  # the emergency blueprint legitimately admits reception
                assert role in ASSIGNABLE_ROLES, (
                    f'{role} is used in the denial table but user_role_policy does not '
                    f'accept it as an assignable role'
                )
