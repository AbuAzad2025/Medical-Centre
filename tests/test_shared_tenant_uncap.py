"""The shared test tenant must not inherit a user cap.

Every test in the suite logs into one tenant that is created once per session and
never cleaned, and several fixtures create Users with a plain commit, so its row
count only climbs. Part-way through a long shard the platform catalogue gets
bootstrapped and ``max_users`` starts resolving to the package default of 50 --
after which every later user creation fails with "package limit exceeded". That
is how one shard lost 17 setups and 12 tests at once, all of them unrelated to
packages.

The underlying leak is the real defect and is not fixed here; this pins the
mitigation so it cannot be dropped by accident. The cap is suppressed for this one
tenant id only, so the suites that assert on real caps keep asserting on them --
test_saas_limits.py and test_saas_data_contracts.py both cover that.
"""

from app.core.saas.resolver import EntitlementResolver


def test_shared_tenant_has_no_user_cap(app, rollback_db):
    from flask import g

    assert EntitlementResolver.get_limit(g.get('tenant_id'), 'max_users') is None


def test_other_tenants_are_not_exempt(app, rollback_db):
    """A tenant that is not the shared one goes through the resolver untouched."""
    from flask import g

    from app.core.saas import resolver as resolver_mod

    shared_id = g.get('tenant_id')
    calls = []

    def _record(tenant_id, at=None):
        calls.append(tenant_id)
        return {'max_users': 7}

    original = resolver_mod.EntitlementResolver.get_effective_limits
    resolver_mod.EntitlementResolver.get_effective_limits = staticmethod(_record)
    try:
        assert EntitlementResolver.get_limit(shared_id + 999, 'max_users') == 7
    finally:
        resolver_mod.EntitlementResolver.get_effective_limits = original

    assert calls == [shared_id + 999]
