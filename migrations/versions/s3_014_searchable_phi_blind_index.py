"""S3-014: make PHI searchable and identity enforceable.

Fixes the defect recorded in docs/DEEP_AUDIT_REPORT_2026-09-27.md section 3:
``FieldEncryptionService.encrypt`` uses a random 12-byte nonce, so the same
plaintext yields different ciphertext on every write. Consequences on a
correctly configured database (FIELD_ENCRYPTION_KEY present):

  * ``select(Patient).filter_by(national_id=...)`` could never match, so
    duplicate-national-id rejection was dead code -- unlimited patients could
    share one national id.
  * ``unique=True`` on the ciphertext never fired, because the stored values
    were never equal. It gave a false guarantee rather than a real one.
  * ``ILIKE`` on the name/phone columns matched nothing, so patient search
    returned nothing (57 lookup sites across 17 files).
  * Every index on an encrypted column indexed random bytes: write cost with
    no selectivity.

The fix uses the two standard primitives, each with its own HKDF-derived key:

  * names and address move to deterministic AES-SIV (RFC 5297) so ``=``,
    ``ILIKE``, ``ORDER BY`` and B-tree indexes work again while the value stays
    encrypted at rest. Equal values become visible as equal to a key holder,
    which is the accepted trade-off for a searchable PHI store; rows stay
    tenant-scoped by RLS.
  * national id and phone keep non-deterministic AES-GCM (maximum
    confidentiality) and gain a keyed HMAC-SHA256 blind index for exact match
    and grouping. The stored digest reveals nothing about the value.
  * uniqueness moves from the ciphertext to a partial unique index on
    (tenant_id, national_id_hash).

Data migration, idempotent by ciphertext prefix:
  * searchable columns: $gcm$/$enc$/plaintext -> $siv$
  * blind-index columns: backfilled from the decrypted plaintext
  * the bogus UNIQUE on patients.national_id is dropped

Revision: s3_014_searchable_phi_blind_index
Revises: s3_013_missing_schema_objects
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, index_exists, table_exists  # noqa: E402

revision = 's3_014_searchable_phi_blind_index'
down_revision = 's3_013_missing_schema_objects'
branch_labels = None
depends_on = None

SEARCHABLE_COLUMNS = (
    'first_name',
    'last_name',
    'first_name_ar',
    'last_name_ar',
    'address',
)
BLIND_INDEX_COLUMNS = (
    ('national_id', 'national_id_hash'),
    ('phone', 'phone_hash'),
    ('first_name', 'first_name_hash'),
    ('last_name', 'last_name_hash'),
    ('first_name_ar', 'first_name_ar_hash'),
    ('last_name_ar', 'last_name_ar_hash'),
)
BATCH = 500


def _service():
    """Return the encryption service, or None when the key is not configured.

    A missing key is not an error here: without it the columns hold plaintext
    and the blind index is NULL, which is exactly the pre-migration behaviour.
    The application already refuses to start in production without the key.
    """
    try:
        sys.path.insert(
            0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        from services.field_encryption_service import FieldEncryptionService

        return FieldEncryptionService.get_service()
    except Exception:
        return None


def _add_columns() -> None:
    if not table_exists('patients'):
        return
    for _source, digest in BLIND_INDEX_COLUMNS:
        if not column_exists('patients', digest):
            op.add_column('patients', sa.Column(digest, sa.String(64), nullable=True))
        # Index every digest, not just the first two: without one the lookup is
        # a sequential scan of the tenant's patients.
        index_name = f'ix_patients_{digest}'
        if not index_exists('patients', index_name):
            op.create_index(index_name, 'patients', [digest])


def _drop_bogus_unique() -> None:
    """Drop UNIQUE on patients.national_id.

    It constrains the ciphertext, which is different on every row, so it never
    fired and only created the illusion of protection. Uniqueness now comes from
    the blind index below. NOT VALID is not accepted for UNIQUE, so the
    constraint is dropped outright; the replacement is created after the backfill
    has deduplicated nothing (it must not silently delete rows).
    """
    if not table_exists('patients'):
        return
    op.execute('ALTER TABLE patients DROP CONSTRAINT IF EXISTS patients_national_id_key')
    # A unique index created by create_all() in some environments.
    op.execute('DROP INDEX IF EXISTS ix_patients_national_id')


def _backfill() -> None:
    """Re-encrypt searchable columns and populate the blind indexes.

    Runs once per tenant, with ``app.tenant_id`` bound for that tenant.

    This is not optional. ``patients`` carries an enforced, FORCEd RLS policy, so
    on a connection with no tenant bound the SELECT below matches nothing and the
    migration would "succeed" while leaving every digest NULL -- i.e. duplicate
    detection stays broken and nothing reports an error. CI hides this because
    it migrates as a superuser. Iterating tenants and binding each one keeps the
    isolation guarantee intact instead of disabling RLS for the migration.
    """
    svc = _service()
    if svc is None:
        # No key configured: columns are plaintext, so there is nothing to
        # re-encrypt and the blind index stays NULL (the application treats NULL
        # as "not indexable" and falls back to a direct comparison).
        return
    if not table_exists('patients'):
        return
    if not table_exists('tenants'):
        return

    conn = op.get_bind()
    searchable = [c for c in SEARCHABLE_COLUMNS if column_exists('patients', c)]
    blind = [(s, d) for s, d in BLIND_INDEX_COLUMNS if column_exists('patients', d)]
    if not searchable and not blind:
        return

    from app.shared.encrypted_type import blind_index_value

    # `tenants` itself carries no RLS policy, so it is readable before any
    # tenant is bound.
    tenant_ids = [r[0] for r in conn.execute(sa.text('SELECT id FROM tenants ORDER BY id'))]
    total = 0
    for tid in tenant_ids:
        conn.execute(sa.text("SELECT set_config('app.tenant_id', :t, false)"), {'t': str(tid)})
        last_id = 0
        while True:
            rows = (
                conn.execute(
                    sa.text(
                        'SELECT id, '
                        + ', '.join(searchable + [s for s, _ in blind])
                        + ' FROM patients WHERE tenant_id = :tid AND id > :last '
                        'ORDER BY id LIMIT :lim'
                    ),
                    {'tid': tid, 'last': last_id, 'lim': BATCH},
                )
                .mappings()
                .all()
            )
            if not rows:
                break
            for row in rows:
                updates = {}
                for col in searchable:
                    value = row.get(col)
                    if value and not svc.is_searchable_encrypted(value):
                        # encrypt_searchable transparently upgrades $gcm$/plaintext.
                        # Refuse to touch a row whose legacy ciphertext cannot be
                        # decrypted: encrypt_searchable would happily nest the old
                        # ciphertext inside a new one and destroy the only copy.
                        if not svc.can_decrypt(value):
                            raise RuntimeError(
                                f's3_014: patients.id={row["id"]} column {col!r} holds a '
                                'ciphertext that cannot be decrypted with the current '
                                'FIELD_ENCRYPTION_KEY. Re-run with the key that wrote it, '
                                'or restore the value from backup, before migrating.'
                            )
                        updates[col] = svc.encrypt_searchable(value)
                for source, digest in blind:
                    if row.get(digest) is None:
                        value = row.get(source)
                        if value:
                            updates[digest] = blind_index_value(value)
                if updates:
                    assignments = ', '.join(f'{c} = :{c}' for c in updates)
                    conn.execute(
                        sa.text(f'UPDATE patients SET {assignments} WHERE id = :id'),
                        {**updates, 'id': row['id']},
                    )
                    total += 1
                last_id = row['id']
    conn.execute(sa.text("SELECT set_config('app.tenant_id', '', false)"))

    if total:
        sys.stderr.write(f'  s3_014: backfilled {total} patient row(s)\n')
    else:
        remaining = conn.execute(sa.text('SELECT count(*) FROM patients')).scalar()
        if remaining:
            # Refuse to let a silently-empty backfill pass as success.
            sys.stderr.write(
                '  s3_014: WARNING - patients exist but nothing was backfilled. '
                'Check that FIELD_ENCRYPTION_KEY is set for the migration role '
                'and that the role is not blocked by RLS.\n'
            )


def _preflight_duplicates() -> None:
    """Abort before the unique index if legacy data already has duplicate ids.

    The index is what finally enforces one patient per national id, and the old
    UNIQUE on the ciphertext never fired. Real deployments can therefore already
    contain the duplicates this index rejects. Failing here with the actual
    offenders is far more useful than the bare UniqueViolation from
    CREATE UNIQUE INDEX, and it is done as an explicit check rather than a
    silent delete: dropping or merging patient records is not this migration's
    decision to make.
    """
    if not table_exists('patients') or not column_exists('patients', 'national_id_hash'):
        return
    conn = op.get_bind()
    rows = (
        conn.execute(
            sa.text(
                'SELECT tenant_id, national_id_hash, count(*) AS n, min(id) AS first_id '
                'FROM patients WHERE national_id_hash IS NOT NULL '
                'GROUP BY tenant_id, national_id_hash HAVING count(*) > 1 '
                'ORDER BY n DESC, tenant_id LIMIT 5'
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        return
    detail = '; '.join(
        f'tenant {r["tenant_id"]} has {r["n"]} patients sharing one national id '
        f'(earliest id {r["first_id"]})'
        for r in rows
    )
    raise RuntimeError(
        's3_014: cannot enforce unique national ids because existing rows collide '
        f'on the blind index: {detail}. The previous UNIQUE constraint was on the '
        'ciphertext and never actually fired. Resolve the duplicates in the '
        'application first (merge, correct, or archive the records), then re-run '
        'this migration.'
    )


def _create_unique_index() -> None:
    """Partial unique index on (tenant_id, national_id_hash).

    Partial so that rows without a national id remain allowed, and tenant-scoped
    because a national id is only unique within one organisation.
    """
    if not table_exists('patients') or not column_exists('patients', 'national_id_hash'):
        return
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_patients_tenant_national_id_hash '
        'ON patients (tenant_id, national_id_hash) '
        'WHERE national_id_hash IS NOT NULL'
    )


def upgrade() -> None:
    _add_columns()
    _drop_bogus_unique()
    _backfill()
    _preflight_duplicates()
    _create_unique_index()


def downgrade() -> None:
    if not table_exists('patients'):
        return
    op.execute('DROP INDEX IF EXISTS uq_patients_tenant_national_id_hash')
    for _source, digest in BLIND_INDEX_COLUMNS:
        if index_exists('patients', f'ix_patients_{digest}'):
            op.execute(f'DROP INDEX IF EXISTS ix_patients_{digest}')
        if column_exists('patients', digest):
            op.drop_column('patients', digest)
    # Restoring UNIQUE on the ciphertext would re-create the false guarantee, so
    # the downgrade deliberately does not bring it back.
