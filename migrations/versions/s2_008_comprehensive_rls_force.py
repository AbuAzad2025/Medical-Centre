"""Enable RLS FORCE on all tenant-scoped tables (comprehensive)

Revision ID: s2_008_comprehensive_rls_force
Revises: s2_007_phi_audit_rls
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists, column_exists


revision = 's2_008_comprehensive_rls_force'
down_revision = 's2_007_phi_audit_rls'
branch_labels = None
depends_on = None


# Tables that should have tenant isolation (from s1_011)
TABLES_WITH_POLICIES = [
    'admissions', 'ai_imaging_analyses', 'ai_recommendations',
    'allergy_intolerances', 'appointments', 'audit_logs', 'audit_trails',
    'backup_logs', 'backup_restore_logs', 'backups', 'barcode_registry',
    'barcode_scan_logs', 'bed_transfers', 'beds', 'biometric_auth_challenges',
    'biometric_credentials', 'budgets', 'care_plan_tasks', 'cash_registers',
    'cds_alert_rules', 'cds_fired_alerts', 'clinical_pathway_steps',
    'clinical_pathways', 'coded_diagnoses', 'coded_procedures',
    'data_warehouse_syncs', 'dental_charts', 'dental_teeth',
    'department_workflows', 'departments', 'dicom_instances', 'dicom_series',
    'dicom_studies', 'digital_signatures', 'disease_patterns',
    'disease_registries', 'doctor_pricing', 'dw_daily_visit_summary',
    'dw_monthly_finance_summary', 'email_messages', 'emar_administrations',
    'emergency_cases', 'emergency_status_history', 'encrypted_fields',
    'enterprise_contracts', 'entitlement_grants', 'exchange_rates',
    'expenses', 'fhir_audit_logs', 'fhir_document_references',
    'fhir_encounters', 'fhir_observations', 'fhir_patients',
    'file_categories', 'file_permissions', 'file_uploads',
    'follow_up_requests', 'immunizations', 'insurance_claims',
    'insurance_companies', 'insurance_providers', 'invoice_services',
    'invoices', 'lab_quality_control_entries', 'lab_reagents',
    'lab_requests', 'lab_results', 'lab_test_catalog', 'lab_test_panels',
    'login_attempts', 'medical_records', 'medical_reports',
    'medication_administration_logs', 'medication_purchases',
    'medication_reconciliations', 'medication_schedules',
    'medication_supply_request_items', 'medication_supply_requests',
    'medications', 'mfa_login_attempts', 'model_predictions',
    'notification_queue', 'notification_templates', 'notifications',
    'nurses', 'nursing_assessments', 'online_booking_payment_transactions',
    'online_bookings', 'pacs_configurations', 'password_policies',
    'patient_accounts', 'patient_allergies', 'patient_care_plans',
    'patient_education_assignments', 'patient_education_materials',
    'patient_insights', 'patient_problems', 'patient_satisfaction_surveys',
    'patient_visit_counters', 'patient_workflows', 'patients', 'payments',
    'performance_analytics', 'pharmacy_returns', 'pharmacy_sale_items',
    'pharmacy_sales', 'population_health_indicators',
    'prescription_dispense_logs', 'prescription_items', 'prescriptions',
    'pricing_catalog', 'pricing_management', 'pricing_rules',
    'project_members', 'project_tasks', 'projects', 'quality_measures',
    'queue_management', 'queue_settings', 'radiology_requests',
    'radiology_results', 'receipts', 'referrals', 'refund_requests',
    'report_executions', 'report_templates', 'reports', 'request_workflows',
    'resource_usage', 'rooms', 'security_events', 'service_master',
    'service_prices', 'session_logs', 'slow_query_entries',
    'slow_query_reports', 'specialty_form_fields', 'specialty_form_submissions',
    'specialty_form_versions', 'specialty_forms', 'sso_configurations',
    'sso_user_mappings', 'staff_absences', 'staff_work_schedules',
    'stock_movements', 'subscription_lines', 'suppliers', 'support_tickets',
    'surgery_checklists', 'surgery_schedules', 'system_logs',
    'task_attachments', 'task_comments', 'tasks', 'telemedicine_appointments',
    'temporary_services', 'tenant_entitlements', 'tenant_feature_flags',
    'tenant_module_settings', 'tenant_modules', 'tenant_overrides',
    'tenant_subscription_history', 'treatments', 'user_department_access',
    'user_mfa_settings', 'users', 'vaccination_schedules', 'vaccines',
    'visit_transfer_logs', 'visit_workflow_events', 'visits', 'vital_signs',
    'wards', 'what_if_scenarios', 'whatsapp_config',
    'whatsapp_integration_messages', 'whatsapp_messages', 'whatsapp_templates',
    'workflow_queues', 'workflow_steps', 'workflow_transfers',
]

# Tables that have tenant_id but no RLS policies yet
TENANT_TABLES_NO_POLICY = [
    'branding_settings',
    'department_permissions',
    'module_permissions',
    'permissions',
    'platform_audit_logs',
    'role_permissions',
    'roles',
    'system_configs',
    'system_themes',
    'user_permissions',
]


def upgrade() -> None:
    # 1. Ensure all tables with policies have RLS FORCED and WITH CHECK
    for table in TABLES_WITH_POLICIES:
        if not table_exists(table):
            continue
        if not column_exists(table, 'tenant_id'):
            continue
        policy_name = f'tenant_isolation_{table}'
        # Enable RLS and FORCE
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        # Recreate policy with WITH CHECK
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int)"
        )

    # 2. Enable RLS + FORCE + policies for tables without policies
    for table in TENANT_TABLES_NO_POLICY:
        if not table_exists(table):
            continue
        if not column_exists(table, 'tenant_id'):
            continue
        policy_name = f'tenant_isolation_{table}'
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int)"
        )

    # 3. For any other tables with tenant_id that don't have RLS yet
    # Find all tables with tenant_id column that don't have policies yet
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT c.table_name
        FROM information_schema.columns c
        WHERE c.column_name = 'tenant_id'
        AND c.table_schema = 'public'
        AND c.table_name NOT IN (
            SELECT table_name FROM information_schema.columns
            WHERE column_name = 'tenant_id' AND table_schema = 'public'
        )
        ORDER BY c.table_name
    """))
    all_tenant_tables = [row[0] for row in result]

    # Also check for tables that have RLS enabled but not forced
    result = conn.execute(sa.text("""
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
        AND n.nspname = 'public'
        AND c.relrowsecurity = true
        AND c.relforcerowsecurity = false
        AND EXISTS (
            SELECT 1 FROM information_schema.columns c2
            WHERE c2.table_name = c.relname
            AND c2.column_name = 'tenant_id'
            AND c2.table_schema = 'public'
        )
    """))
    not_forced_tables = [row[0] for row in result]

    # Force RLS on tables that have RLS enabled but not forced
    for table in not_forced_tables:
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')

    # Ensure all tenant tables have RLS enabled and forced
    # (combining all lists and deduplicating)
    all_tenant_tables = set(TABLES_WITH_POLICIES + TENANT_TABLES_NO_POLICY + not_forced_tables)
    for table in all_tenant_tables:
        if not table_exists(table):
            continue
        if not column_exists(table, 'tenant_id'):
            continue
        # Ensure RLS is enabled and forced
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        
        # Ensure policy exists with USING and WITH CHECK
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int)"
        )


def downgrade() -> None:
    # Remove WITH CHECK from policies (revert to USING-only)
    for table in TABLES_WITH_POLICIES:
        if not table_exists(table):
            continue
        policy_name = f'tenant_isolation_{table}'
        op.execute(
            f"ALTER POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int)"
        )

    # Remove policies + disable RLS for the 10 uncovered tables
    for table in TENANT_TABLES_NO_POLICY:
        if not table_exists(table):
            continue
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')