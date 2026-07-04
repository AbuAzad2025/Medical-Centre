"""Platform bootstrap smoke tests."""
from app.core.platform_bootstrap import (
    ensure_module_definitions,
    ensure_product_bundles,
    ensure_saas_packages,
    run_platform_bootstrap,
)


def test_run_platform_bootstrap_idempotent(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        first = run_platform_bootstrap(quiet=True)
        second = run_platform_bootstrap(quiet=True)
        assert not second.get('skipped')
        assert second['module_definitions_added'] == 0
        assert first['product_bundles'] >= 0


def test_create_app_does_not_seed_developer_configs(app):
    """Regression test for startup read-only contract.

    Previously, create_app() unconditionally INSERTed developer_company,
    developer_name, etc. into system_configs during startup. This violated the
    read-only startup contract and caused InsufficientPrivilege errors under the
    med_app_runtime role when RLS was enabled. Developer seeding now lives
    exclusively in the privileged bootstrap path
    (platform_bootstrap.ensure_developer_config()).
    """
    from models.system_config import SystemConfig

    keys = [
        'developer_company', 'developer_name', 'developer_logo_url',
        'developer_mobile', 'developer_location',
    ]
    found = (
        SystemConfig.query
        .filter(SystemConfig.config_key.in_(keys))
        .count()
    )
    assert found == 0, (
        f'Found {found} developer_* rows in system_configs — '
        'startup should be read-only.'
    )


def test_auto_assign_tenant_works_after_prior_commit(app, db, monkeypatch):
    """Regression: after a commit, the before_flush hook must still assign
    tenant_id to new objects and re-assert SET LOCAL for RLS compliance.

    Background worker threads call send_notification() once per relevant
    item.  The first commit clears the transaction-scoped SET LOCAL
    app.tenant_id session variable.  The before_flush hook must re-assert
    it on every flush so the next INSERT passes the RLS WITH CHECK.
    """
    from datetime import datetime, timezone
    from flask import g
    from models.notification import Notification
    from app.core.tenant.models import Tenant
    from sqlalchemy import text

    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )

    with app.app_context():
        tenant = Tenant.query.first()
        assert tenant is not None, 'Need a tenant in the test database'

        g.tenant_id = tenant.id
        db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))

        # First insert — verify tenant_id assigned by hook
        n1 = Notification(
            title='First', message='First', notification_type='info',
            recipient_role='admin', sent_at=datetime.now(timezone.utc),
        )
        db.session.add(n1)
        db.session.flush()
        assert n1.tenant_id == tenant.id, 'auto_assign_tenant did not assign tenant_id'
        db.session.commit()

        # Second insert after prior commit — would fail RLS without re-assert
        n2 = Notification(
            title='Second', message='Second', notification_type='info',
            recipient_role='admin', sent_at=datetime.now(timezone.utc),
        )
        db.session.add(n2)
        db.session.flush()
        assert n2.tenant_id == tenant.id, 'tenant_id missing on second insert'
        db.session.commit()

        # Re-assert SET LOCAL so the SELECT queries below are visible through RLS
        db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))
        assert Notification.query.get(n1.id) is not None
        assert Notification.query.get(n2.id) is not None

        g.pop('tenant_id', None)


def test_ensure_helpers_return_counts(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        assert ensure_module_definitions() >= 0
        assert ensure_product_bundles() >= 0
        assert ensure_saas_packages() >= 0
