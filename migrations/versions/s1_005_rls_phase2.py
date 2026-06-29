"""S1-005: RLS phase 2 — high-priority clinical, workflow, and integration tables.

Revision: s1_005_rls_phase2
Revises: s1_004_expenses_rls_uniques
"""
from migrations.migration_utils import disable_tenant_rls, enable_tenant_rls

revision = 's1_005_rls_phase2'
down_revision = 's1_004_expenses_rls_uniques'
branch_labels = None
depends_on = None

RLS_TABLES = [
    'tasks',
    'patient_workflows',
    'workflow_steps',
    'workflow_queues',
    'workflow_transfers',
    'visit_workflow_events',
    'pricing_catalog',
    'pricing_management',
    'pricing_rules',
    'medication_supply_requests',
    'medication_supply_request_items',
    'referrals',
    'dicom_studies',
    'dicom_series',
    'dicom_instances',
    'fhir_patients',
    'fhir_observations',
    'fhir_encounters',
    'fhir_document_references',
    'fhir_audit_logs',
    'sso_configurations',
    'sso_user_mappings',
    'telemedicine_appointments',
    'online_bookings',
    'patient_accounts',
    'lab_test_catalog',
    'notification_queue',
    'backups',
]


def upgrade() -> None:
    enable_tenant_rls(RLS_TABLES)


def downgrade() -> None:
    disable_tenant_rls(RLS_TABLES)
