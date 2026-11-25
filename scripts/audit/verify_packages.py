"""Verify each package tenant's modules/entitlements against its bundle."""

import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:testpass@127.0.0.1:5433/Medical2026')
os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('SKIP_PLATFORM_BOOTSTRAP', '1')
os.environ.setdefault('RLS_BYPASS_ALLOWED', '1')

from app_factory import create_app  # noqa: E402
from app.core.tenant.models import ProductBundle, Tenant  # noqa: E402
from app.extensions import db  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

app = create_app('development')
problems = []
rows = []
with app.app_context():
    tenants = (
        db.session.execute(select(Tenant).where(Tenant.slug.like('pkg-%')).order_by(Tenant.id))
        .scalars()
        .all()
    )
    for tenant in tenants:
        slug = tenant.slug[4:].replace('-', '_')
        bundle = db.session.execute(select(ProductBundle).filter_by(slug=slug)).scalars().first()
        expected = set(bundle.get_modules()) if bundle else set()
        actual = {
            r[0]
            for r in db.session.execute(
                text(
                    'SELECT module_name FROM tenant_modules WHERE tenant_id=:tid AND is_active=true'
                ),
                {'tid': tenant.id},
            )
        }
        version_id = db.session.execute(
            text('SELECT package_version_id FROM subscription_lines WHERE tenant_id=:tid LIMIT 1'),
            {'tid': tenant.id},
        ).scalar()
        caps = {
            r[0]
            for r in db.session.execute(
                text(
                    'SELECT capability_key FROM tenant_entitlements WHERE tenant_id=:tid AND is_effective=true'
                ),
                {'tid': tenant.id},
            )
        }
        ok = actual == expected and bool(caps) and bool(version_id)
        rows.append(
            {
                'slug': slug,
                'tenant_id': tenant.id,
                'version_id': version_id,
                'expected': sorted(expected),
                'actual': sorted(actual),
                'capabilities': len(caps),
                'ok': ok,
            }
        )
        if not ok:
            problems.append(
                f'{slug}: expected={sorted(expected)} actual={sorted(actual)} '
                f'caps={len(caps)} version={version_id}'
            )

print(f'tenants checked: {len(rows)}, problems: {len(problems)}')
for line in problems:
    print('  ', line)

import json

out = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'package_verification.json')
with open(out, 'w', encoding='utf-8') as fh:
    json.dump({'checked': len(rows), 'problems': problems, 'rows': rows}, fh, indent=2)
    fh.write('\n')
print('wrote', out)
