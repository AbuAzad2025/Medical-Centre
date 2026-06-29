"""S1-007: RLS phase 4 — remaining ORM tenant tables missed by per-file AST bleed.

Revision: s1_007_rls_phase4
Revises: s1_006_rls_phase3
"""
from migrations.migration_utils import disable_tenant_rls, enable_tenant_rls

revision = 's1_007_rls_phase4'
down_revision = 's1_006_rls_phase3'
branch_labels = None
depends_on = None

RLS_TABLES = [
    'admissions',
    'ai_recommendations',
    'beds',
    'cds_alert_rules',
    'clinical_pathway_steps',
    'clinical_pathways',
    'coded_diagnoses',
    'data_warehouse_syncs',
    'dental_charts',
    'digital_signatures',
    'disease_patterns',
    'disease_registries',
    'doctor_pricing',
    'dw_daily_visit_summary',
    'emar_administrations',
    'enterprise_contracts',
    'entitlement_grants',
    'file_categories',
    'file_uploads',
    'immunizations',
    'insurance_providers',
    'lab_test_panels',
    'notification_templates',
    'nurses',
    'password_policies',
    'patient_care_plans',
    'patient_education_materials',
    'patient_insights',
    'patient_problems',
    'performance_analytics',
    'pharmacy_returns',
    'pharmacy_sale_items',
    'population_health_indicators',
    'prescription_dispense_logs',
    'prescription_items',
    'project_tasks',
    'projects',
    'report_executions',
    'reports',
    'request_workflows',
    'resource_usage',
    'rooms',
    'security_events',
    'service_prices',
    'session_logs',
    'slow_query_entries',
    'slow_query_reports',
    'specialty_form_fields',
    'specialty_form_versions',
    'specialty_forms',
    'staff_work_schedules',
    'subscription_lines',
    'suppliers',
    'support_tickets',
    'surgery_schedules',
    'system_logs',
    'task_attachments',
    'task_comments',
    'tenant_feature_flags',
    'tenant_module_settings',
    'tenant_overrides',
    'tenant_subscription_history',
    'user_mfa_settings',
    'vaccines',
    'vital_signs',
    'whatsapp_integration_messages',
    'whatsapp_messages',
    'whatsapp_templates',
]


def upgrade() -> None:
    enable_tenant_rls(RLS_TABLES)


def downgrade() -> None:
    disable_tenant_rls(RLS_TABLES)
