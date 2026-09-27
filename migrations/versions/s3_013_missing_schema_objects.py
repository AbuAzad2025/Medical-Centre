"""S3-013: Create the 7 ORM tables and 5 ORM columns that no migration ever made.

The ORM declares these objects but the migration chain never created them, so
on any database built with ``flask db upgrade`` (i.e. every real deployment,
including production) the following code paths raise at request time:

  * ``app/modules/owner/routes.py::owner_cards_vault``
        -> ``relation "payment_cards" does not exist``
  * ``routes/insurance_routes.py::list_claims``
        -> ``column insurance_claims.claim_date does not exist``
  * ``services/insurance_claim_service.py`` (``InsurancePayout``, ``EOB``)
        -> ``relation "insurance_payouts" / "eobs" does not exist``
  * the whole patient-consent feature (``PatientConsent``,
    ``ConsentTemplate``, ``ConsentAuditLog``) — and ``PatientConsent`` is in
    ``TRACKED_MODELS``, so it is a PHI-audited model with no table.

This was invisible to ``scripts/ops/pre_pilot_verification.py`` because that
gate inspects ``Model.__table__.columns`` (ORM metadata) rather than the
migrated schema, so it reported "86 assertions, 0 failures" against a database
that was missing all of them.

All new tables follow the deployed convention for tenant-scoped clinical data:
``tenant_id NOT NULL`` + ``ENABLE`` + ``FORCE`` ROW LEVEL SECURITY + a
``tenant_isolation_*`` policy using the NULLIF-guarded expression (see
s3_012_rls_nullif_reassert). EncryptedString columns are created as TEXT,
matching s2_009.

Idempotent: every object is guarded by an existence check.

Revision: s3_013_missing_schema_objects
Revises: s3_012_rls_nullif_reassert
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migration_utils import column_exists, table_exists  # noqa: E402

revision = 's3_013_missing_schema_objects'
down_revision = 's3_012_rls_nullif_reassert'
branch_labels = None
depends_on = None

TENANT_RLS_TABLES = [
    'patient_consents',
    'consent_templates',
    'consent_audit_logs',
    'insurance_claim_lines',
    'insurance_payouts',
    'eobs',
    'payment_cards',
]

_SAFE = "tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer"


def _create_consent_tables() -> None:
    if not table_exists('patient_consents'):
        op.create_table(
            'patient_consents',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('patient_id', sa.Integer, nullable=False),
            sa.Column('consent_type', sa.String(50), nullable=False),
            sa.Column('scope_description', sa.Text, nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='granted'),
            sa.Column('version', sa.Integer, nullable=False, server_default='1'),
            sa.Column('previous_version_id', sa.Integer, nullable=True),
            sa.Column('granted_at', sa.DateTime, nullable=False),
            sa.Column('expires_at', sa.DateTime, nullable=True),
            sa.Column('withdrawn_at', sa.DateTime, nullable=True),
            sa.Column('withdrawal_reason', sa.Text, nullable=True),
            sa.Column('granted_by_patient', sa.Boolean, nullable=False, server_default=sa.true()),
            # EncryptedString -> TEXT (ciphertext overflows narrow varchars)
            sa.Column('guardian_name', sa.Text, nullable=True),
            sa.Column('guardian_relationship', sa.String(50), nullable=True),
            sa.Column('guardian_id_number', sa.Text, nullable=True),
            sa.Column('capture_method', sa.String(50), nullable=False, server_default='written'),
            sa.Column('capture_document_id', sa.Integer, nullable=True),
            sa.Column('recorded_by_user_id', sa.Integer, nullable=False),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.Column('updated_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['previous_version_id'], ['patient_consents.id']),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
            sa.UniqueConstraint(
                'patient_id', 'consent_type', 'version', name='uq_patient_consent_version'
            ),
        )
        op.create_index('ix_patient_consents_patient_id', 'patient_consents', ['patient_id'])
        op.create_index('ix_patient_consents_consent_type', 'patient_consents', ['consent_type'])
        op.create_index('ix_patient_consents_status', 'patient_consents', ['status'])
        op.create_index(
            'ix_patient_consents_recorded_by_user_id', 'patient_consents', ['recorded_by_user_id']
        )
        op.create_index('idx_consent_status_type', 'patient_consents', ['status', 'consent_type'])
        op.create_index('idx_consent_patient_active', 'patient_consents', ['patient_id', 'status'])

    if not table_exists('consent_templates'):
        op.create_table(
            'consent_templates',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('consent_type', sa.String(50), nullable=False),
            sa.Column('scope_description', sa.Text, nullable=False),
            sa.Column('default_expiry_days', sa.Integer, nullable=True),
            sa.Column('requires_guardian', sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.Column('updated_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_consent_templates_consent_type', 'consent_templates', ['consent_type'])

    if not table_exists('consent_audit_logs'):
        op.create_table(
            'consent_audit_logs',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('consent_id', sa.Integer, nullable=False),
            sa.Column('action', sa.String(50), nullable=False),
            sa.Column('performed_by_user_id', sa.Integer, nullable=True),
            sa.Column('patient_id', sa.Integer, nullable=False),
            sa.Column('details', sa.Text, nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text, nullable=True),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['consent_id'], ['patient_consents.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_consent_audit_logs_consent_id', 'consent_audit_logs', ['consent_id'])
        op.create_index('ix_consent_audit_logs_action', 'consent_audit_logs', ['action'])
        op.create_index('ix_consent_audit_logs_patient_id', 'consent_audit_logs', ['patient_id'])
        op.create_index(
            'idx_consent_audit_patient', 'consent_audit_logs', ['patient_id', 'created_at']
        )


def _create_insurance_tables() -> None:
    if not table_exists('insurance_claim_lines'):
        op.create_table(
            'insurance_claim_lines',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('claim_id', sa.Integer, nullable=False),
            sa.Column('service_name', sa.String(200), nullable=False),
            sa.Column('service_code', sa.String(50), nullable=True),
            sa.Column('quantity', sa.Integer, nullable=False, server_default='1'),
            sa.Column('unit_price', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('total_price', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['claim_id'], ['insurance_claims.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_insurance_claim_lines_claim_id', 'insurance_claim_lines', ['claim_id'])

    if not table_exists('insurance_payouts'):
        op.create_table(
            'insurance_payouts',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('claim_id', sa.Integer, nullable=False),
            sa.Column('payout_number', sa.String(40), nullable=True, unique=True),
            sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
            sa.Column('payout_date', sa.Date, nullable=True),
            sa.Column('method', sa.String(20), nullable=True, server_default='WIRE'),
            sa.Column('reference', sa.String(100), nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['claim_id'], ['insurance_claims.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_insurance_payouts_claim_id', 'insurance_payouts', ['claim_id'])

    if not table_exists('eobs'):
        op.create_table(
            'eobs',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('claim_id', sa.Integer, nullable=False),
            sa.Column('eob_number', sa.String(40), nullable=True, unique=True),
            sa.Column(
                'adjudication_status', sa.String(20), nullable=True, server_default='PENDING'
            ),
            sa.Column('adjudication_date', sa.DateTime, nullable=True),
            sa.Column('total_billed', sa.Numeric(12, 2), nullable=True, server_default='0'),
            sa.Column('total_allowed', sa.Numeric(12, 2), nullable=True, server_default='0'),
            sa.Column(
                'patient_responsibility', sa.Numeric(12, 2), nullable=True, server_default='0'
            ),
            sa.Column('denial_reason', sa.Text, nullable=True),
            sa.Column('raw_payload', sa.Text, nullable=True),
            sa.Column('tenant_id', sa.Integer, nullable=False),
            sa.Column('created_at', sa.DateTime, nullable=False),
            sa.ForeignKeyConstraint(['claim_id'], ['insurance_claims.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        )
        op.create_index('ix_eobs_claim_id', 'eobs', ['claim_id'])

    # columns the ORM selects but the chain never added
    if table_exists('insurance_claims'):
        if not column_exists('insurance_claims', 'claim_date'):
            op.add_column('insurance_claims', sa.Column('claim_date', sa.DateTime, nullable=True))
            op.create_index('ix_insurance_claims_claim_date', 'insurance_claims', ['claim_date'])
        if not column_exists('insurance_claims', 'patient_share_amount'):
            op.add_column(
                'insurance_claims',
                sa.Column(
                    'patient_share_amount', sa.Numeric(12, 2), nullable=True, server_default='0'
                ),
            )
        if not column_exists('insurance_claims', 'insurance_share_amount'):
            op.add_column(
                'insurance_claims',
                sa.Column(
                    'insurance_share_amount', sa.Numeric(12, 2), nullable=True, server_default='0'
                ),
            )
        if not column_exists('insurance_claims', 'adjudication_notes'):
            op.add_column(
                'insurance_claims', sa.Column('adjudication_notes', sa.Text, nullable=True)
            )


def _create_payment_cards() -> None:
    if table_exists('payment_cards'):
        return
    op.create_table(
        'payment_cards',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('owner_name', sa.Text, nullable=False),  # EncryptedString
        sa.Column('owner_email', sa.Text, nullable=True),  # EncryptedString
        sa.Column('bank_name', sa.String(100), nullable=True),
        sa.Column('card_type', sa.String(20), nullable=False),
        sa.Column('last_four', sa.String(4), nullable=False),
        sa.Column('expiry_month', sa.Integer, nullable=False),
        sa.Column('expiry_year', sa.Integer, nullable=False),
        sa.Column('cardholder_name', sa.Text, nullable=True),  # EncryptedString
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('tenant_id', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_payment_cards_created_at', 'payment_cards', ['created_at'])


def _add_pharmacy_return_disposition() -> None:
    if not table_exists('pharmacy_returns'):
        return
    if column_exists('pharmacy_returns', 'disposition'):
        return
    op.add_column(
        'pharmacy_returns',
        sa.Column('disposition', sa.String(20), nullable=False, server_default='RESTOCK'),
    )


def _apply_rls() -> None:
    for t in TENANT_RLS_TABLES:
        if not table_exists(t) or not column_exists(t, 'tenant_id'):
            continue
        pol = f'tenant_isolation_{t}'
        op.execute(f'ALTER TABLE {t} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {t} FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS {pol} ON {t}')
        op.execute(f'CREATE POLICY {pol} ON {t} USING ({_SAFE}) WITH CHECK ({_SAFE})')
        op.execute(f'CREATE INDEX IF NOT EXISTS ix_{t}_tenant_id ON {t} (tenant_id)')


def upgrade() -> None:
    _create_consent_tables()
    _create_insurance_tables()
    _create_payment_cards()
    _add_pharmacy_return_disposition()
    _apply_rls()


def downgrade() -> None:
    for t in reversed(TENANT_RLS_TABLES):
        if table_exists(t):
            op.execute(f'DROP TABLE IF EXISTS {t}')
    if table_exists('pharmacy_returns') and column_exists('pharmacy_returns', 'disposition'):
        op.drop_column('pharmacy_returns', 'disposition')
    if table_exists('insurance_claims'):
        for col in (
            'adjudication_notes',
            'insurance_share_amount',
            'patient_share_amount',
            'claim_date',
        ):
            if column_exists('insurance_claims', col):
                op.drop_column('insurance_claims', col)
