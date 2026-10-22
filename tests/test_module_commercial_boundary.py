"""What a tenant may switch on is decided by what it paid for.

The module system has two halves that used to disagree. The tenant's
bundle decides what it bought, and ``tenant_modules`` records what is
switched on. The half that was supposed to enforce the first over the
second read only ``tenant.product_profile_code`` - and that field is NULL
for every tenant that signed itself up, because the signup form posts a
package version and no profile. So the boundary did not exist for exactly
the tenants that chose their own package, and a manager could switch on
anything in the registry.

These cases are about the boundary itself: a tenant that bought a small
package cannot switch on a module outside it, and a tenant with no
purchase at all is unrestricted - that is the single-install clinic that
never opted into the module system, and it is not the same thing as a
tenant that bought a small bundle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.module.models import TenantModule
from app.core.module.validators import (
    can_activate_module,
    get_purchased_modules_for_tenant,
)
from app.extensions import db


@pytest.fixture
def small_package_tenant(app, test_tenant):
    """A tenant that bought a package with two modules in it."""
    from app.core.saas.models import (
        Package,
        PackageVersion,
        PackageVersionEntitlement,
        SubscriptionLine,
        SubscriptionLineStatus,
        SubscriptionLineType,
    )

    pkg = Package(
        name='Boundary Test Package',
        slug=f'boundary-test-{test_tenant.id}',
        category='bundle',
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()
    version = PackageVersion(package_id=pkg.id, version='1.0.0', trial_days=0)
    db.session.add(version)
    db.session.flush()

    for module_name in ('reception', 'billing'):
        db.session.add(
            PackageVersionEntitlement(
                package_version_id=version.id,
                module_name=module_name,
                capability_key='dummy',
            )
        )
    db.session.add(
        SubscriptionLine(
            tenant_id=test_tenant.id,
            package_version_id=version.id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
            billing_type='monthly',
            quantity=1,
            unit_price=Decimal('0'),
            effective_from=datetime.now(UTC),
        )
    )
    db.session.commit()

    # The tenant's active modules have to match what it bought. The test
    # fixture activates every module in the registry, and a tenant whose
    # active set is the whole registry is not the case this is about: the
    # case is a tenant that bought a small package and has only that.
    for tm in (
        db.session.execute(select(TenantModule).filter_by(tenant_id=test_tenant.id)).scalars().all()
    ):
        tm.is_active = tm.module_name in ('reception', 'billing')
        if tm.is_active:
            tm.deactivated_at = None
        else:
            tm.deactivated_at = datetime.now(UTC)
    db.session.commit()

    # The tenant has to be bound: the ORM injects the tenant filter into
    # every query, so an unbound tenant cannot see its own subscription and
    # the purchase cannot be read.
    from tests.tenant_context import bind_tenant_on_g

    bind_tenant_on_g(test_tenant, db_session=db.session)
    return test_tenant


def test_the_purchase_is_read_from_the_package(app, small_package_tenant):
    """The tenant's subscription is what says what it bought."""
    purchased = get_purchased_modules_for_tenant(small_package_tenant.id)
    assert purchased == {'reception', 'billing'}


def test_a_module_outside_the_purchase_cannot_be_activated(app, small_package_tenant):
    """The hospital catalogue is not available to a tenant that did not buy it."""
    ok, err = can_activate_module(small_package_tenant.id, 'emergency')
    assert not ok, 'a module outside the purchased package was allowed'
    assert err and 'not included' in err

    ok, err = can_activate_module(small_package_tenant.id, 'ai_imaging')
    assert not ok, 'a module outside the purchased package was allowed'


def test_a_module_inside_the_purchase_can_be_activated(app, small_package_tenant):
    """The boundary refuses what was not bought and allows what was."""
    ok, err = can_activate_module(small_package_tenant.id, 'billing')
    assert ok, f'a module inside the purchased package was refused: {err}'


def test_the_self_service_switch_refuses_what_was_not_bought(app, small_package_tenant):
    """The tenant's own switch is inside the same boundary.

    This is the endpoint a manager uses, and it is where the gap was
    reachable: it checked the product profile, which is NULL for a
    self-signed tenant, so the check did not run.
    """
    from app.core.rate_limiter import _shared_store
    from tests.tenant_context import ensure_test_user, login_test_client

    _shared_store.clear()
    manager = ensure_test_user(
        db, small_package_tenant, username='boundary_manager', role='manager'
    )
    client = app.test_client()
    with app.test_request_context():
        from flask import g

        g.tenant_id = small_package_tenant.id
        login_test_client(client, manager, small_package_tenant)

    resp = client.post(
        '/manager/api/units/toggle',
        json={'module_name': 'emergency'},
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 403, (
        f'the switch answered {resp.status_code}; a manager was able to switch '
        'on a module the tenant had not bought'
    )
    still_off = db.session.execute(
        select(TenantModule).filter_by(tenant_id=small_package_tenant.id, module_name='emergency')
    ).scalar()
    assert still_off is None or not still_off.is_active, (
        'the module was switched on even though the boundary refused it'
    )


def test_a_tenant_with_no_purchase_is_unrestricted(app, test_tenant):
    """No subscription and no bundle means no boundary.

    This is the single-install clinic that never opted into the module
    system. It is a different thing from a tenant that bought a small
    bundle, and the two must not be confused - a boundary that failed
    closed here would lock a clinic out of the features it has always had.
    """
    purchased = get_purchased_modules_for_tenant(test_tenant.id)
    if purchased is None:
        ok, err = can_activate_module(test_tenant.id, 'emergency')
        assert ok, f'a tenant with no purchase was refused a module: {err}'
    else:
        ok, err = can_activate_module(test_tenant.id, 'emergency')
        assert ok == ('emergency' in purchased), (
            'the boundary and the purchase disagree about the same module'
        )


def test_a_switched_off_module_is_refused_outside_saas_mode(app, test_tenant):
    """The switch has to mean something in a single install.

    The guard used to be skipped unless SaaS mode was on, and SaaS mode is
    off by default - the project's own .env ships
    ``DEPLOYMENT_MODE=single_install``. So in the configuration a clinic
    actually runs, switching a module off changed nothing except that the
    menu item disappeared: the routes kept answering 200 and the data kept
    being readable.

    The guard is now enforced whenever the tenant has a module set at all.
    A tenant with no module rows is still unrestricted - that is a clinic
    that never opted into the module system.
    """
    from app.core.rate_limiter import _shared_store
    from tests.tenant_context import ensure_test_user, login_test_client

    _shared_store.clear()
    app.config['ENABLE_SAAS_MODE'] = False
    try:
        doctor = ensure_test_user(db, test_tenant, username='gate_doctor', role='doctor')
        client = app.test_client()
        with app.test_request_context():
            from flask import g

            g.tenant_id = test_tenant.id
            login_test_client(client, doctor, test_tenant)

        tm = db.session.execute(
            select(TenantModule).filter_by(tenant_id=test_tenant.id, module_name='lab')
        ).scalar()
        if tm is None:
            tm = TenantModule(tenant_id=test_tenant.id, module_name='lab', is_active=True)
            db.session.add(tm)
        tm.is_active = False
        db.session.commit()

        resp = client.get('/lab/worklist')
        assert resp.status_code == 403, (
            f'the route answered {resp.status_code} with the module switched off '
            'and SaaS mode off; the switch did nothing'
        )
    finally:
        app.config['ENABLE_SAAS_MODE'] = True


def test_a_downgrade_switches_off_what_it_no_longer_covers(app, small_package_tenant):
    """A downgrade has to take something away.

    The upgrade path activated the new package's modules and the downgrade
    path did nothing to the old ones, so a tenant that downgraded from the
    hospital package to a billing package kept the whole clinical platform -
    modules active, capabilities entitled - at the price of the small
    package. The rows stay, deactivated, so the history of what the tenant
    had is still there.
    """
    from app.core.saas.lifecycle import TenantProvisioningService

    # A package with a single module in it, and a line on it.
    from app.core.saas.models import (
        Package,
        PackageVersion,
        PackageVersionEntitlement,
    )

    pkg = Package(
        name='Boundary Small Package',
        slug=f'boundary-small-{small_package_tenant.id}',
        category='bundle',
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()
    small_version = PackageVersion(package_id=pkg.id, version='1.0.0', trial_days=0)
    db.session.add(small_version)
    db.session.flush()
    db.session.add(
        PackageVersionEntitlement(
            package_version_id=small_version.id,
            module_name='billing',
            capability_key='dummy',
        )
    )
    db.session.commit()

    # The tenant starts with the clinical modules active.
    for module_name in ('lab', 'emergency'):
        tm = db.session.execute(
            select(TenantModule).filter_by(
                tenant_id=small_package_tenant.id, module_name=module_name
            )
        ).scalar()
        if tm is None:
            tm = TenantModule(
                tenant_id=small_package_tenant.id,
                module_name=module_name,
                is_active=True,
            )
            db.session.add(tm)
        else:
            tm.is_active = True
    db.session.commit()

    TenantProvisioningService.downgrade_tenant(small_package_tenant.id, small_version.id, 'monthly')

    for module_name in ('lab', 'emergency'):
        tm = db.session.execute(
            select(TenantModule).filter_by(
                tenant_id=small_package_tenant.id, module_name=module_name
            )
        ).scalar()
        assert tm is not None, f'the row for {module_name} was removed instead of deactivated'
        assert tm.is_active is False, (
            f'{module_name} was still active after the downgrade; the tenant kept '
            'a module it no longer pays for'
        )
