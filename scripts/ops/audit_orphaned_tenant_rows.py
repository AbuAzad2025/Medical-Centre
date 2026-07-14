#!/usr/bin/env python3
"""Audit script to detect orphaned tenant_id=0 rows in tenant-scoped tables.

Scans all tenant-scoped models for rows with tenant_id=0 (invalid)
and reports them. Returns non-zero exit code if orphans found.
"""

import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')

from app_factory import create_app

def main():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return 1

    app = create_app('testing')
    with app.app_context():
        from sqlalchemy import text, inspect
        from app.extensions import db
        from app.shared.tenant_filter import _skip_table

        total_orphans = 0
        results = []

        # Get all mapped models from SQLAlchemy registry
        from app.extensions import db
        mapper_registry = db.Model.registry.mappers

        for mapper in mapper_registry:
            model = mapper.class_
            if hasattr(model, '__tablename__'):
                if _skip_table(model):
                    continue  # Skip global tables
                table = model.__tablename__
                try:
                    # Check for tenant_id=0 rows
                    count = db.session.execute(
                        text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id = 0")
                    ).scalar() or 0
                    if count > 0:
                        results.append(f"  {table}: {count} orphaned rows (tenant_id=0)")
                        total_orphans += count
                except Exception as e:
                    results.append(f"  {table}: ERROR - {e}")

        if results:
            print("ORPHANED ROWS DETECTED:")
            for r in results:
                print(r)
            print(f"TOTAL ORPHANS: {total_orphans}")
            return 1

        print("OK: No orphaned tenant_id=0 rows found.")
        return 0

if __name__ == '__main__':
    sys.exit(main())