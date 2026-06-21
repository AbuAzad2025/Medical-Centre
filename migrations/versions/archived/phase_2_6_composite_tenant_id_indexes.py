"""
Phase 2.6: Add composite (tenant_id, created_at) and (tenant_id, status)
indexes on major tenant-scoped tables for query performance.

Revision ID: phase_2_6_composite_tenant_id_indexes
Revises: phase_2_5_tenant_id_all_remaining
Create Date: 2026-06-20
"""
from alembic import op

revision = 'phase_2_6_composite_tenant_id_indexes'
down_revision = 'phase_2_5_tenant_id_all_remaining'
branch_labels = None
depends_on = None


# (table, index_name, columns)
TENANT_CREATED_AT = [
    ('patients', 'idx_patients_tenant_created', ('tenant_id', 'created_at')),
    ('visits', 'idx_visits_tenant_created', ('tenant_id', 'created_at')),
    ('users', 'idx_users_tenant_created', ('tenant_id', 'created_at')),
    ('appointments', 'idx_appointments_tenant_created', ('tenant_id', 'created_at')),
    ('invoices', 'idx_invoices_tenant_created', ('tenant_id', 'created_at')),
    ('lab_results', 'idx_lab_results_tenant_created', ('tenant_id', 'created_at')),
    ('radiology_results', 'idx_radiology_results_tenant_created', ('tenant_id', 'created_at')),
    ('prescriptions', 'idx_prescriptions_tenant_created', ('tenant_id', 'created_at')),
    ('medications', 'idx_medications_tenant_created', ('tenant_id', 'created_at')),
    ('notifications', 'idx_notifications_tenant_created', ('tenant_id', 'created_at')),
    ('receipts', 'idx_receipts_tenant_created', ('tenant_id', 'created_at')),
    ('treatments', 'idx_treatments_tenant_created', ('tenant_id', 'created_at')),
    ('medical_records', 'idx_medical_records_tenant_created', ('tenant_id', 'created_at')),
    ('medical_reports', 'idx_medical_reports_tenant_created', ('tenant_id', 'created_at')),
    ('emergency_cases', 'idx_emergency_cases_tenant_created', ('tenant_id', 'created_at')),
    ('queue_management', 'idx_queue_management_tenant_created', ('tenant_id', 'created_at')),
    ('lab_requests', 'idx_lab_requests_tenant_created', ('tenant_id', 'created_at')),
    ('radiology_requests', 'idx_radiology_requests_tenant_created', ('tenant_id', 'created_at')),
]

TENANT_STATUS = [
    ('patients', 'idx_patients_tenant_status', ('tenant_id', 'status')),
    ('visits', 'idx_visits_tenant_status', ('tenant_id', 'status')),
    ('users', 'idx_users_tenant_status', ('tenant_id', 'is_active')),
    ('appointments', 'idx_appointments_tenant_status', ('tenant_id', 'status')),
    ('invoices', 'idx_invoices_tenant_status', ('tenant_id', 'status')),  # already exists, idempotent
    ('lab_requests', 'idx_lab_requests_tenant_status', ('tenant_id', 'status')),
    ('radiology_requests', 'idx_radiology_requests_tenant_status', ('tenant_id', 'status')),
    ('prescriptions', 'idx_prescriptions_tenant_status', ('tenant_id', 'status')),
    ('treatments', 'idx_treatments_tenant_status', ('tenant_id', 'status')),
    ('admissions', 'idx_admissions_tenant_status', ('tenant_id', 'status')),
    ('beds', 'idx_beds_tenant_status', ('tenant_id', 'status')),
    ('queue_management', 'idx_queue_management_tenant_status', ('tenant_id', 'status')),
    ('notifications', 'idx_notifications_tenant_status', ('tenant_id', 'is_read')),
]


def upgrade():
    for table, idx, cols in TENANT_CREATED_AT:
        cols_sql = ', '.join(f'"{c}"' for c in cols)
        op.execute(f'CREATE INDEX IF NOT EXISTS "{idx}" ON "{table}" ({cols_sql})')
    for table, idx, cols in TENANT_STATUS:
        cols_sql = ', '.join(f'"{c}"' for c in cols)
        op.execute(f'CREATE INDEX IF NOT EXISTS "{idx}" ON "{table}" ({cols_sql})')


def downgrade():
    for table, idx, cols in TENANT_CREATED_AT + TENANT_STATUS:
        op.execute(f'DROP INDEX IF EXISTS "{idx}"')
