"""Idempotent platform bootstrap — single entry for production catalog setup."""
from __future__ import annotations

import logging
import os
from typing import Any

from app.extensions import db

logger = logging.getLogger(__name__)


def _table_count(table: str) -> int:
    from sqlalchemy import inspect, text

    if table not in inspect(db.engine).get_table_names():
        return -1
    return int(db.session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar() or 0)


def ensure_module_definitions() -> int:
    """Register all MODULE_REGISTRY entries in module_definitions."""
    from app.core.module.models import ModuleDefinition
    from app.core.module.registry import MODULE_REGISTRY

    added = 0
    for name, meta in MODULE_REGISTRY.items():
        if ModuleDefinition.query.filter_by(name=name).first():
            continue
        db.session.add(
            ModuleDefinition(
                name=name,
                name_ar=meta.name_ar,
                category=meta.category,
                description=meta.description_ar,
                is_active=True,
            )
        )
        added += 1
    if added:
        db.session.commit()
    return added


def ensure_product_bundles() -> int:
    """Seed default ProductBundles when the catalog table is empty."""
    from app.core.tenant.models import seed_default_bundles

    before = _table_count('product_bundles')
    if before == 0:
        seed_default_bundles()
    return _table_count('product_bundles')


def ensure_saas_packages() -> int:
    """Mirror ProductBundle rows into packages / package_versions (idempotent)."""
    from app.core.saas.seed import seed_packages_from_product_bundles

    before = _table_count('packages')
    created = seed_packages_from_product_bundles()
    after = _table_count('packages')
    if created:
        logger.info('SaaS packages created: %s', len(created))
    return max(after - before, 0) if before >= 0 else len(created)


def run_platform_bootstrap(*, quiet: bool = False) -> dict[str, Any]:
    """Run full platform bootstrap. Safe to call on every deploy."""
    if os.environ.get('SKIP_PLATFORM_BOOTSTRAP', '').lower() in ('1', 'true', 'yes'):
        return {'skipped': True}

    log = logger.info if quiet else print

    modules_added = ensure_module_definitions()
    bundle_count = ensure_product_bundles()
    packages_added = ensure_saas_packages()

    summary = {
        'module_definitions_added': modules_added,
        'product_bundles': bundle_count,
        'saas_packages_added': packages_added,
    }
    log('Platform bootstrap: %s', summary)
    return summary
