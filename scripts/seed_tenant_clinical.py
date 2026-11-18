"""Seed clinical demo data for any tenant id already in the DB (idempotent).

Reuses the exact same seeders as seed_23_tenants.py so the data shape is
identical. Used to fill the platform tenant (id 1), which the package seeder
intentionally skips because it is the platform/admin tenant.

Usage:
    SEED_TARGET_TENANT=1 python scripts/seed_tenant_clinical.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2

from scripts import seed_23_tenants as s

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
LOG = logging.getLogger('seed_tenant_clinical')


def main() -> int:
    tenant_id = int(os.environ.get('SEED_TARGET_TENANT', '1'))
    seed_key = int(os.environ.get('SEED_TARGET_KEY', '0'))
    conn = psycopg2.connect(**s.DB_CONFIG)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SET app.bypass_rls='on'")
            cur.execute('SELECT id, slug FROM tenants WHERE id=%s', (tenant_id,))
            row = cur.fetchone()
            if row is None:
                LOG.error('Tenant %s does not exist', tenant_id)
                return 1
            slug = row[1]
            s.bind_tenant(cur, tenant_id)
            stamp = s.now_naive()
            today = date.today()
            LOG.info('Seeding clinical data for tenant %s (%s)', tenant_id, slug)
            dept_ids = s.seed_departments(cur, tenant_id, seed_key, slug, stamp)
            admin_id = s.seed_admin(cur, tenant_id, seed_key, dept_ids[0], stamp)
            patient_ids = s.seed_patients(cur, tenant_id, seed_key, today, stamp)
            per_patient = s.seed_visits(
                cur, tenant_id, seed_key, patient_ids, dept_ids, admin_id, today, stamp
            )
            s.seed_appointments(
                cur, tenant_id, seed_key, patient_ids, dept_ids, admin_id, stamp, stamp
            )
            s.seed_lab_and_radiology(
                cur, tenant_id, seed_key, patient_ids, per_patient, admin_id, stamp
            )
            s.verify_tenant(cur, tenant_id, slug)
        LOG.info('Done; committed')
        return 0
    except Exception:
        LOG.exception('Seed failed; rolled back')
        return 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
