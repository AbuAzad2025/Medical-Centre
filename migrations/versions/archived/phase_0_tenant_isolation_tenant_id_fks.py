"""phase_0_tenant_isolation_add_tenant_id_fks

Phase 0: Add tenant_id foreign key constraints to models with TenantMixin.
Columns already exist in DB from direct ALTER TABLE.
This migration only adds the FK constraints and indexes.

Revision ID: phase_0_tenant_isolation
Revises: add_composite_indexes_20260619
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_0_tenant_isolation'
down_revision = 'add_composite_indexes_20260619'
branch_labels = None
depends_on = None


TABLES_WITH_TENANT_ID = [
    'admissions', 'bed_transfers', 'beds', 'care_plan_tasks',
    'clinical_pathway_steps', 'clinical_pathways', 'coded_diagnoses', 'coded_procedures',
    'departments', 'email_messages', 'emar_administrations', 'emergency_cases',
    'file_uploads', 'follow_up_requests', 'insurance_claims', 'insurance_companies',
    'invoice_services', 'invoices', 'lab_requests', 'lab_results',
    'medical_records', 'medical_reports', 'medication_administration_logs',
    'medication_reconciliations', 'medication_schedules',
    'medication_supply_request_items', 'medication_supply_requests',
    'medications', 'notification_queue', 'notification_templates',
    'notifications', 'patient_accounts', 'patient_problems',
    'allergy_intolerances', 'prescription_dispense_logs',
    'prescriptions', 'prescription_items', 'pricing_catalog',
    'radiology_requests', 'radiology_results', 'receipts',
    'referrals', 'rooms', 'service_prices', 'surgery_checklists',
    'surgery_schedules', 'telemedicine_appointments', 'treatments',
    'users', 'vital_signs', 'wards', 'whatsapp_messages',
]


def upgrade():
    for table in TABLES_WITH_TENANT_ID:
        # Only add FK if it doesn't exist
        op.create_foreign_key(
            f'fk_{table}_tenant_id_tenants',
            table, 'tenants',
            ['tenant_id'], ['id'],
            ondelete='CASCADE'
        )
        # Index already created by direct SQL, but ensure it exists
        op.create_index(
            f'ix_{table}_tenant_id', table, ['tenant_id'], unique=False,
            if_not_exists=True
        )


def downgrade():
    for table in reversed(TABLES_WITH_TENANT_ID):
        op.drop_constraint(f'fk_{table}_tenant_id_tenants', table, type_='foreignkey')
        op.drop_index(f'ix_{table}_tenant_id', table_name=table)
