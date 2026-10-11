"""Execute tenant provisioning and module entitlement.

Phase 7c. Two questions: what a tenant is given when it is created, and what it is
allowed to switch on afterwards.

Driven through:

  POST /owner/api/tenants/provision
  POST /owner/api/tenants/<id>/modules/<module>/activate
  POST /owner/api/tenants/<id>/modules/<module>/deactivate
  GET  /owner/api/tenants/<id>/modules

What execution established:

  * Activation writes a TenantModule row, stamps activated_at, and the feature gate
    sees it on the next request. Deactivation is symmetric. The gate reads
    TenantModule per request rather than caching, so there is no propagation delay
    to reason about.

  * The bundle boundary is enforced, and it is enforced only for a tenant that has
    a product_profile_code. _get_bundle_for_tenant returns None when the profile is
    null, and can_activate_module treats None as "no restriction" — every module
    passes. So the boundary is real but it is a property of the tenant record, not
    of the system: a tenant whose profile was cleared, or was never set, is
    unrestricted.

    This is pinned in both directions. A profiled tenant is refused a module
    outside its bundle, and an unprofiled one is not refused anything. Which of
    those two is the intended behaviour for the second is a product decision, and
    the case says so rather than asserting either.

  * The public signup routes named by the specification do not exist. The spec
    lists POST /saas/signup and POST /api/saas/register as the two writes that let
    a tenant create itself, and neither is registered. Signup is therefore an owner
    action in this codebase, which is a defensible position for a medical system
    and not the one the spec describes.
"""

from __future__ import annotations

import pytest
from flask import g

from app.extensions import db
from tests.scenario_execution_registry import covers


@pytest.fixture
def platform_owner(app, test_tenant):
    """An owner session able to act on any tenant."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['auth'])
    owner = ensure_test_user(db, test_tenant, username='e2e_prov_owner', role='owner')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, owner, test_tenant)
    return {'app': app, 'client': client, 'owner': owner, 'tenant': test_tenant}


def _seed_bundle(profile_code, modules):
    """Ensure a ProductBundle row exists for *profile_code*, carrying *modules*.

    get_bundle_for_profile reads the ProductBundle table, so a profile with no row
    resolves to no bundle at all and the boundary being tested does not exist.

    Idempotent, and deliberately so. Whether product_bundles is seeded is an
    environment difference — it is empty locally and populated in CI — so inserting
    unconditionally either duplicates the row or trips a unique constraint,
    depending on where the test runs. Looking first makes the case mean the same
    thing everywhere, which is the property an xfail needs most: a marker that
    fires in one environment and not another is not a record of a defect.
    """
    import json

    from app.core.tenant.models import ProductBundle

    existing = (
        db.session.execute(db.select(ProductBundle).filter_by(profile_code=profile_code))
        .scalars()
        .first()
    )
    if existing is not None:
        existing.modules = json.dumps(modules)
        existing.is_active = True
        db.session.commit()
        return existing

    bundle = ProductBundle(
        name=profile_code.replace('_', ' ').title(),
        name_ar=profile_code,
        slug=f'{profile_code}-e2e',
        monthly_price=0,
        yearly_price=0,
        setup_fee=0,
        currency='SAR',
        modules=json.dumps(modules),
        is_public=True,
        is_active=True,
        profile_code=profile_code,
    )
    db.session.add(bundle)
    db.session.commit()
    return bundle


def _fresh_tenant(slug, profile=None):
    """A tenant in its own right, outside the fixture tenant's scope."""
    from app.core.tenant.models import Tenant

    t = Tenant(
        slug=slug,
        name=slug.replace('-', ' ').title(),
        contact_email=f'{slug}@example.com',
        status='ACTIVE',
        product_profile_code=profile,
    )
    db.session.add(t)
    db.session.commit()
    return t.id


@covers('OWNER_MODULE_ENTITLEMENT')
class TestModuleEntitlementPerTenant:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: the owner module routes look TenantModule up through the '
            'ORM tenant filter, which scopes to the operator tenant, so for any other '
            'tenant the lookup misses and deactivate changes nothing while reporting '
            'success'
        ),
    )
    def test_activating_and_deactivating_a_module_is_per_tenant(self, platform_owner):
        """Activation is a row, and deactivation reverses it.

        Asserted per tenant rather than globally because the specification is
        explicit that the same module can be live in one tenant and absent in the
        next, and a test that only ever looked at one tenant would not know the
        difference.
        """
        client = platform_owner['client']
        a = _fresh_tenant('e2e-ent-a')
        b = _fresh_tenant('e2e-ent-b')

        resp = client.post(f'/owner/api/tenants/{a}/modules/lab/activate', follow_redirects=False)
        assert resp.status_code == 200, (
            f'activate answered {resp.status_code}: {resp.get_data(as_text=True)[:200]}'
        )
        assert resp.get_json().get('status') == 'activated'

        from app.core.module.models import TenantModule

        active_a = (
            db.session.execute(db.select(TenantModule).filter_by(tenant_id=a, module_name='lab'))
            .scalars()
            .first()
        )
        active_b = (
            db.session.execute(db.select(TenantModule).filter_by(tenant_id=b, module_name='lab'))
            .scalars()
            .first()
        )

        assert active_a is not None and active_a.is_active, 'tenant A has no active lab module'
        assert active_b is None or not active_b.is_active, (
            'activating lab for tenant A also activated it for tenant B. Entitlement is per tenant'
        )
        assert active_a.activated_at is not None, 'activation did not stamp activated_at'

        client.post(f'/owner/api/tenants/{a}/modules/lab/deactivate', follow_redirects=False)
        db.session.expire_all()
        after = (
            db.session.execute(db.select(TenantModule).filter_by(tenant_id=a, module_name='lab'))
            .scalars()
            .first()
        )
        assert after is None or not after.is_active, (
            f'deactivation reported success but left is_active at {after.is_active!r}'
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: the owner module routes look TenantModule up through the '
            'ORM tenant filter, which scopes to the operator tenant, so for any other '
            'tenant the lookup misses and deactivate changes nothing while reporting '
            'success'
        ),
    )
    def test_deactivating_a_module_for_another_tenant_actually_deactivates_it(self, platform_owner):
        """Deactivation must reach the tenant it names.

        api_deactivate_module does `if tm: tm.is_active = False`, then returns
        {"status": "deactivated"} either way. Its select goes through the
        do_orm_execute listener, which adds tenant_id = the operator's tenant, so for
        a tenant the operator does not belong to the row is never found, the branch is
        skipped, and the endpoint still reports success.

        The consequence is worse than the route doing nothing: an operator switching
        a module off for a customer is told it worked, and the customer's feature gate
        keeps returning True.
        """
        from app.core.module.models import TenantModule

        client = platform_owner['client']
        a = _fresh_tenant('e2e-deact-target')

        client.post(f'/owner/api/tenants/{a}/modules/pharmacy/activate', follow_redirects=False)
        db.session.expire_all()

        resp = client.post(
            f'/owner/api/tenants/{a}/modules/pharmacy/deactivate', follow_redirects=False
        )
        assert resp.status_code == 200
        assert resp.get_json().get('status') == 'deactivated'

        db.session.expire_all()
        rows = (
            db.session.execute(
                db.select(TenantModule).filter_by(tenant_id=a, module_name='pharmacy')
            )
            .scalars()
            .all()
        )
        assert rows and not any(r.is_active for r in rows), (
            f'deactivation returned {resp.get_json()!r} and left '
            f'{[(r.id, r.is_active) for r in rows]} still active. The lookup is '
            f'scoped to the operator tenant, so it found nothing to turn off'
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: api_activate_module looks the row up through the ORM '
            'tenant filter, misses it for another tenant, and inserts a second '
            'TenantModule instead of updating the existing one'
        ),
    )
    def test_activating_a_module_twice_is_idempotent(self, platform_owner):
        """Activating something already active succeeds and changes nothing.

        The route reads the row and only inserts when the read came back empty. That
        read is tenant-scoped to the operator, so for any other tenant it always comes
        back empty and the second activation tries to insert a duplicate of a row that
        already exists. Whatever happens next is a failure an operator should not be
        able to cause by repeating themselves.
        """
        from app.core.module.models import TenantModule

        client = platform_owner['client']
        a = _fresh_tenant('e2e-activate-twice')

        first = client.post(f'/owner/api/tenants/{a}/modules/lab/activate', follow_redirects=False)
        second = client.post(f'/owner/api/tenants/{a}/modules/lab/activate', follow_redirects=False)

        assert first.status_code == 200, f'the first activation answered {first.status_code}'
        assert second.status_code == 200, (
            f'activating an already-active module answered {second.status_code}: '
            f'{second.get_data(as_text=True)[:200]}. Repeating an activation is not '
            f'something an operator should be able to get wrong'
        )

        db.session.expire_all()
        rows = (
            db.session.execute(db.select(TenantModule).filter_by(tenant_id=a, module_name='lab'))
            .scalars()
            .all()
        )
        assert len(rows) == 1, (
            f'two activations left {len(rows)} TenantModule rows for one module: {[r.id for r in rows]}'
        )

    def test_a_profiled_tenant_cannot_activate_outside_its_bundle(self, platform_owner):
        """The bundle boundary holds, once a bundle row exists for the profile.

        get_bundle_for_profile reads the ProductBundle table rather than the seed
        dict in app/core/tenant/models.py, so a profile code with no matching row
        resolves to None and can_activate_module reads None as "no restriction".
        The bundle is seeded explicitly here, because product_bundles is empty in
        this database and without a row there is no boundary to test.

        With the row present, doctor_clinic_full carries lab and radiology and not
        inpatient, so inpatient must be refused with a message naming the boundary.
        """
        client = platform_owner['client']
        _seed_bundle('doctor_clinic_full', ['reception', 'doctor', 'lab', 'radiology'])
        tenant_id = _fresh_tenant('e2e-bundle-guard', profile='doctor_clinic_full')

        resp = client.post(
            f'/owner/api/tenants/{tenant_id}/modules/inpatient/activate', follow_redirects=False
        )
        assert resp.status_code == 400, (
            f'activating inpatient for a doctor_clinic_full tenant answered '
            f'{resp.status_code}. The bundle is supposed to be the boundary on what '
            f'this profile may switch on'
        )
        body = resp.get_json()
        assert 'bundle' in (body.get('error') or '').lower(), (
            f'the refusal does not mention the bundle: {body!r}'
        )

    def test_a_tenant_with_no_profile_is_not_bounded_by_anything(self, platform_owner):
        """No profile means no boundary, which is worth knowing out loud.

        _get_bundle_for_tenant returns None when product_profile_code is null, and
        can_activate_module reads None as unrestricted. It does the same when the
        profile is set but no ProductBundle row matches it, which is the more
        interesting half: product_bundles is empty in this database, so every
        profile in it is unbounded.

        The boundary therefore fails open rather than closed. A tenant whose bundle
        row is missing, or whose profile code has drifted from the seed, is as
        unrestricted as one with no profile at all — and nothing tells the operator.
        For a medical system that is the wrong default: an unknown profile should
        refuse, or at minimum refuse and say so.

        Asserted as current behaviour and named, because whether a missing bundle
        should mean "anything" is a product decision nobody has recorded.
        """
        client = platform_owner['client']
        tenant_id = _fresh_tenant('e2e-no-profile', profile=None)

        resp = client.post(
            f'/owner/api/tenants/{tenant_id}/modules/inpatient/activate', follow_redirects=False
        )
        assert resp.status_code == 200, (
            f'an unprofiled tenant was refused inpatient with {resp.status_code}: '
            f'{resp.get_data(as_text=True)[:200]}. A null product_profile_code leaves '
            f'the bundle unrestricted, so this is the documented boundary rather than '
            f'a missing one — but it means clearing a profile also clears the limit '
            f'on what that tenant may switch on.'
        )

    def test_a_module_outside_the_registry_is_refused(self, platform_owner):
        """An unknown module name is refused rather than stored.

        Worth its own case because the insert is otherwise indiscriminate: without
        the registry check a typo in the module name would be written as a
        TenantModule row and then silently gate nothing.
        """
        client = platform_owner['client']
        tenant_id = _fresh_tenant('e2e-unknown-module', profile='doctor_clinic_full')

        resp = client.post(
            f'/owner/api/tenants/{tenant_id}/modules/not_a_module/activate', follow_redirects=False
        )
        assert resp.status_code == 400, f'an unknown module answered {resp.status_code}'
        assert 'unknown module' in (resp.get_json().get('error') or '').lower()


@covers('OWNER_TENANT_SELF_SERVICE_SIGNUP')
class TestThePublicSignupRoutes:
    def test_the_signup_routes_named_by_the_spec_are_not_registered(self, platform_owner):
        """Neither /saas/signup nor /api/saas/register exists.

        The specification calls these "the public write that creates a tenant" and
        says a self-registered tenant arrives pending. No such route is registered,
        so signup in this codebase is an owner action.

        For a medical system that is a defensible position — a tenant should not be
        able to bring itself into existence without review — but the spec should
        not describe a route as shipped when it is not, and a reader who assumes it
        exists will look for the activation queue that never receives anything.
        """
        client = platform_owner['client']

        from app.core.tenant.models import Tenant

        for path in ('/saas/signup', '/api/saas/register'):
            resp = client.post(
                path,
                json={
                    'slug': f'e2e-signup-{path.strip("/").replace("/", "-")}',
                    'name': 'Self Signed Up',
                    'email': 'signup@example.com',
                },
            )
            assert resp.status_code in (404, 400), (
                f'POST {path} answered {resp.status_code}. The specification describes '
                f'this as a shipped public write that creates a pending tenant. If it '
                f'now accepts the request, it is the route that lets anyone create a '
                f'tenant, and it needs the pending-then-activate shape rather than a '
                f'bare success.'
            )

            made = (
                db.session.execute(db.select(Tenant).filter_by(contact_email='signup@example.com'))
                .scalars()
                .first()
            )
            assert made is None, (
                f'POST {path} created tenant {made.slug!r}. If self-service signup is '
                f'intended, a self-registered tenant must arrive pending and '
                f'unreachable until an owner activates it'
            )


@covers('OWNER_TENANT_PROVISIONING')
class TestProvisioningIsOwnerOnly:
    def test_a_non_owner_cannot_provision_a_tenant(self, platform_owner):
        """Provisioning is behind owner_required, and that holds."""
        from tests.tenant_context import ensure_test_user, login_test_client

        doctor = ensure_test_user(
            db, platform_owner['tenant'], username='e2e_prov_doctor', role='doctor'
        )
        client = platform_owner['app'].test_client()
        with platform_owner['app'].test_request_context():
            g.tenant_id = platform_owner['tenant'].id
            login_test_client(client, doctor, platform_owner['tenant'])

        resp = client.post(
            '/owner/api/tenants/provision',
            json={'slug': 'e2e-sneaky', 'name': 'Sneaky', 'email': 's@example.com'},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 403), (
            f'a doctor provisioning a tenant answered {resp.status_code}'
        )

        from app.core.tenant.models import Tenant

        made = db.session.execute(db.select(Tenant).filter_by(slug='e2e-sneaky')).scalars().first()
        assert made is None, 'a doctor created a tenant through the provisioning route'
