"""
Phase 2.5: Add tenant_id to remaining tenant-scoped models
(dental, vaccination, AI, SSO, FHIR, CDS, DICOM/PACS,
biometric, barcode, data warehouse, population health,
digital signature, online booking, nurse, file, user,
patient, nursing assessment, session, encrypted field)

Revision ID: phase_2_5_tenant_id_all_remaining
Revises: phase_2_3_product_bundles
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_2_5_tenant_id_all_remaining'
down_revision = 'phase_2_3_product_bundles'
branch_labels = None
depends_on = None

# Tables that need column + FK + index (new tables without tenant_id)
NEED_COLUMN = [
    'dental_charts', 'dental_teeth',
    'vaccines', 'immunizations', 'vaccination_schedules',
    'ai_imaging_analyses',
    'ai_recommendations', 'disease_patterns', 'performance_analytics',
    'patient_insights', 'model_predictions',
    'sso_configurations', 'sso_user_mappings',
    'fhir_patients', 'fhir_observations', 'fhir_encounters',
    'fhir_document_references', 'fhir_audit_logs',
    'cds_alert_rules', 'cds_fired_alerts',
    'dicom_studies', 'dicom_series', 'dicom_instances',
    'pacs_configurations',
    'biometric_credentials', 'biometric_auth_challenges',
    'barcode_registry', 'barcode_scan_logs',
    'data_warehouse_syncs', 'dw_daily_visit_summary', 'dw_monthly_finance_summary',
    'disease_registries', 'population_health_indicators', 'quality_measures',
    'session_logs', 'encrypted_fields', 'file_permissions',
]

# Tables that already have tenant_id column but need FK + index added
NEED_FK_ONLY = [
    'digital_signatures', 'password_policies',
    'online_bookings', 'online_booking_payment_transactions',
    'nurses', 'file_categories',
    'staff_work_schedules', 'staff_absences',
    'patients', 'patient_allergies', 'nursing_assessments',
]

ALL_TABLES = NEED_COLUMN + NEED_FK_ONLY


def _add_tenant_fk(table):
    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_foreign_key(
                f'fk_{table}_tenant_id',
                'tenants', ['tenant_id'], ['id'],
                ondelete='CASCADE'
            )
    except Exception:
        pass


def _add_tenant_index(table):
    try:
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_index(f'ix_{table}_tenant_id', ['tenant_id'])
    except Exception:
        pass


def upgrade():
    # Tables that need column + FK + index
    for table in NEED_COLUMN:
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(sa.Column('tenant_id', sa.Integer(), nullable=True))
        except Exception:
            pass
        _add_tenant_fk(table)
        _add_tenant_index(table)

    # Tables that need only FK + index (column already exists)
    for table in NEED_FK_ONLY:
        _add_tenant_fk(table)
        _add_tenant_index(table)


def downgrade():
    for table in reversed(ALL_TABLES):
        try:
            with op.batch_alter_table(table) as batch_op:
                batch_op.drop_constraint(f'fk_{table}_tenant_id', type_='foreignkey')
                batch_op.drop_index(f'ix_{table}_tenant_id')
                if table in NEED_COLUMN:
                    batch_op.drop_column('tenant_id')
        except Exception:
            pass
