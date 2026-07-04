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


def test_ensure_helpers_return_counts(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        assert ensure_module_definitions() >= 0
        assert ensure_product_bundles() >= 0
        assert ensure_saas_packages() >= 0
