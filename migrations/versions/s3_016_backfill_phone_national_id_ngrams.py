"""S3-016: index phone and national_id in the trigram side table.

s3_015 indexed the name columns only, so a partial-number search -- what
reception actually types, "050222" for "0502222222" -- could not be answered: the
exact blind index needs the whole value. The table already carries a `source`
column, so this is a backfill of two extra sources and no schema change.

Revision: s3_016_backfill_phone_national_id_ngrams
Revises: s3_015_patient_search_ngrams
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, table_exists  # noqa: E402

revision = 's3_016_backfill_phone_national_id_ngrams'
down_revision = 's3_015_patient_search_ngrams'
branch_labels = None
depends_on = None

TABLE = 'patient_search_ngrams'
SOURCES = ('phone', 'national_id')
BATCH = 200


def _service():
    try:
        sys.path.insert(
            0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        from services.field_encryption_service import FieldEncryptionService

        return FieldEncryptionService.get_service()
    except Exception:
        return None


def upgrade() -> None:
    if _service() is None:
        # No key: the columns are plaintext and search falls back to ILIKE.
        return
    if not table_exists(TABLE) or not table_exists('patients') or not table_exists('tenants'):
        return
    cols = [c for c in SOURCES if column_exists('patients', c)]
    if not cols:
        return

    from app.shared import search_index
    from app.shared.encrypted_type import normalize_for_index

    conn = op.get_bind()
    tenant_ids = [r[0] for r in conn.execute(sa.text('SELECT id FROM tenants ORDER BY id'))]
    total = 0
    for tid in tenant_ids:
        conn.execute(sa.text("SELECT set_config('app.tenant_id', :t, false)"), {'t': str(tid)})
        last_id = 0
        while True:
            rows = (
                conn.execute(
                    sa.text(
                        'SELECT id, ' + ', '.join(cols) + ' FROM patients '
                        'WHERE tenant_id = :tid AND id > :last ORDER BY id LIMIT :lim'
                    ),
                    {'tid': tid, 'last': last_id, 'lim': BATCH},
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            for row in rows:
                payload = []
                for col in cols:
                    for digest in search_index.digests_for(normalize_for_index(row.get(col))):
                        payload.append(
                            {'patient_id': row['id'], 'source': col, 'digest': digest, 'tid': tid}
                        )
                if payload:
                    conn.execute(
                        sa.text(
                            f'INSERT INTO {TABLE} (patient_id, source, digest, tenant_id) '
                            'VALUES (:patient_id, :source, :digest, :tid) '
                            'ON CONFLICT ON CONSTRAINT uq_patient_ngram DO NOTHING'
                        ),
                        payload,
                    )
                    total += len(payload)
                last_id = row['id']
    conn.execute(sa.text("SELECT set_config('app.tenant_id', '', false)"))
    if total:
        sys.stderr.write(f'  s3_016: indexed {total} phone/national_id trigram row(s)\n')


def downgrade() -> None:
    if not table_exists(TABLE):
        return
    op.execute(f"DELETE FROM {TABLE} WHERE source IN ('phone', 'national_id')")
