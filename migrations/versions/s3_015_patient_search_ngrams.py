"""S3-015: blind trigram index, so substring search works on encrypted PHI.

Completes the fix started in s3_014. AES-SIV made ``=`` and B-tree indexes work
on the name columns, and the blind indexes made exact identity lookups work, but
neither can answer ``LIKE '%term%'``: a plaintext substring has no relationship
to a ciphertext. Every substring search against an encrypted column therefore
returned nothing, which is how 57 lookup sites across 17 files came to be dead
code on a correctly configured database.

The standard remedy is an n-gram side index. For each name column this stores
one row per distinct trigram, with the trigram replaced by an HMAC-SHA256 digest
under a search-specific label. A query digests its own trigrams, keeps the
patients that have all of them, and then re-checks the substring on the
decrypted value -- that second phase is what keeps the results exact, because
trigram overlap on its own yields false positives.

Trade-offs, stated rather than hidden:
  * the digests are not reversible, but their *set* is stable, so frequency
    analysis is possible by anyone holding the table. RLS bounds the blast
    radius to rows the attacker can already read.
  * storage grows with name length (about len(name) rows per column).
  * a term shorter than three characters has no trigram, so it can only be
    matched exactly; that limitation is handled, not hidden.

Revision: s3_015_patient_search_ngrams
Revises: s3_014_searchable_phi_blind_index
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import (  # noqa: E402
    column_exists,
    enable_tenant_rls,
    index_exists,
    table_exists,
)

revision = 's3_015_patient_search_ngrams'
down_revision = 's3_014_searchable_phi_blind_index'
branch_labels = None
depends_on = None

TABLE = 'patient_search_ngrams'
#: Must match Patient._NGRAM_FIELDS.
SOURCES = ('first_name', 'last_name', 'first_name_ar', 'last_name_ar')
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


def _create_table() -> None:
    if table_exists(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('digest', sa.String(64), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'patient_id', 'source', 'digest', name='uq_patient_ngram'),
    )
    if not index_exists(TABLE, 'ix_patient_search_ngrams_patient_id'):
        op.create_index('ix_patient_search_ngrams_patient_id', TABLE, ['patient_id'])
    # The lookup predicate is (tenant_id, digest), so that column order matters.
    if not index_exists(TABLE, 'ix_patient_ngram_lookup'):
        op.create_index('ix_patient_ngram_lookup', TABLE, ['tenant_id', 'digest'])
    enable_tenant_rls([TABLE])


def _backfill() -> None:
    """Populate trigram rows for patients that already exist.

    Runs once per tenant with app.tenant_id bound, for the same reason s3_014
    does: the table carries enforced RLS, so an unbound connection sees no rows
    and the migration would report success having indexed nothing.
    """
    svc = _service()
    if svc is None:
        # No key: the columns hold plaintext and the application uses ILIKE, so
        # there is nothing to index.
        return
    if not table_exists(TABLE) or not table_exists('patients') or not table_exists('tenants'):
        return

    conn = op.get_bind()
    cols = [c for c in SOURCES if column_exists('patients', c)]
    if not cols:
        return

    from app.shared import search_index
    from app.shared.encrypted_type import normalize_for_index

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
                    normalised = normalize_for_index(row.get(col))
                    for digest in search_index.digests_for(normalised):
                        payload.append({'patient_id': row['id'], 'source': col, 'digest': digest})
                if payload:
                    # ON CONFLICT DO NOTHING makes a re-run a no-op rather than
                    # an error, which keeps the migration restartable.
                    conn.execute(
                        sa.text(
                            f'INSERT INTO {TABLE} (patient_id, source, digest, tenant_id) '
                            'VALUES (:patient_id, :source, :digest, :tid) '
                            'ON CONFLICT ON CONSTRAINT uq_patient_ngram DO NOTHING'
                        ),
                        [{**p, 'tid': tid} for p in payload],
                    )
                    total += len(payload)
                last_id = row['id']
    conn.execute(sa.text("SELECT set_config('app.tenant_id', '', false)"))
    if total:
        sys.stderr.write(f'  s3_015: indexed {total} trigram row(s)\n')


def upgrade() -> None:
    _create_table()
    _backfill()


def downgrade() -> None:
    if table_exists(TABLE):
        op.execute(f'DROP TABLE IF EXISTS {TABLE}')
