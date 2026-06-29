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


def test_ensure_helpers_return_counts(app, monkeypatch):
    monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
    with app.app_context():
        assert ensure_module_definitions() >= 0
        assert ensure_product_bundles() >= 0
        assert ensure_saas_packages() >= 0
