"""S1-006: RLS phase 3 — remaining tenant-scoped tables.

Revision: s1_006_rls_phase3
Revises: s1_005_rls_phase2
"""
from migrations.migration_utils import disable_tenant_rls, enable_tenant_rls

revision = 's1_006_rls_phase3'
down_revision = 's1_005_rls_phase2'
branch_labels = None
depends_on = None

RLS_TABLES = [
    'ai_imaging_analyses',
    'allergy_intolerances',
    'audit_logs',
    'backup_logs',
    'backup_restore_logs',
    'bed_transfers',
    'care_plan_tasks',
    'cds_fired_alerts',
    'coded_procedures',
    'dental_teeth',
    'department_workflows',
    'dw_monthly_finance_summary',
    'email_messages',
    'emergency_status_history',
    'encrypted_fields',
    'exchange_rates',
    'file_permissions',
    'follow_up_requests',
    'invoice_services',
    'lab_quality_control_entries',
    'lab_reagents',
    'lab_results',
    'login_attempts',
    'medication_administration_logs',
    'medication_purchases',
    'medication_reconciliations',
    'medication_schedules',
    'mfa_login_attempts',
    'model_predictions',
    'nursing_assessments',
    'online_booking_payment_transactions',
    'pacs_configurations',
    'patient_allergies',
    'patient_education_assignments',
    'patient_satisfaction_surveys',
    'patient_visit_counters',
    'project_members',
    'quality_measures',
    'queue_settings',
    'radiology_requests',
    'radiology_results',
    'report_templates',
    'service_master',
    'specialty_form_submissions',
    'staff_absences',
    'stock_movements',
    'surgery_checklists',
    'temporary_services',
    'tenant_entitlements',
    'tenant_modules',
    'user_department_access',
    'vaccination_schedules',
    'visit_transfer_logs',
    'what_if_scenarios',
    'whatsapp_config',
]


def upgrade() -> None:
    enable_tenant_rls(RLS_TABLES)


def downgrade() -> None:
    disable_tenant_rls(RLS_TABLES)
