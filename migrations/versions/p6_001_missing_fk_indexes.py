"""add missing FK indexes

Revision ID: p6_001_missing_fk_indexes
Revises: c713f656048c, 8b9457bfc4d7
Create Date: 2026-08-21

Adds indexes for 21 FK columns found missing a leading-column index by
scripts/audit_indexes.py (21/606 FK columns). Indexes use IF NOT EXISTS
semantics via op.create_index(checkfirst=True) so re-runs are safe.
"""

from alembic import op

revision = 'p6_001_missing_fk_indexes'
down_revision = ('c713f656048c', '8b9457bfc4d7')
branch_labels = None
depends_on = None

# (index_name, table_name, column_name)
MISSING_FK_INDEXES = [
    ('idx_audit_fk_entitlement_grants_granted_by_user_id', 'entitlement_grants', 'granted_by_user_id'),
    ('idx_audit_fk_entitlement_grants_revoked_by_user_id', 'entitlement_grants', 'revoked_by_user_id'),
    ('idx_audit_fk_expenses_approved_by', 'expenses', 'approved_by'),
    ('idx_audit_fk_patient_consents_capture_document_id', 'patient_consents', 'capture_document_id'),
    ('idx_audit_fk_patient_consents_previous_version_id', 'patient_consents', 'previous_version_id'),
    ('idx_audit_fk_platform_audit_logs_user_id', 'platform_audit_logs', 'user_id'),
    ('idx_audit_fk_platform_tenant_assumptions_assumed_by', 'platform_tenant_assumptions', 'assumed_by'),
    ('idx_audit_fk_platform_tenant_assumptions_revoked_by', 'platform_tenant_assumptions', 'revoked_by'),
    ('idx_audit_fk_specialty_form_submissions_patient_id', 'specialty_form_submissions', 'patient_id'),
    ('idx_audit_fk_specialty_form_submissions_submitted_by', 'specialty_form_submissions', 'submitted_by'),
    ('idx_audit_fk_specialty_form_submissions_version_id', 'specialty_form_submissions', 'version_id'),
    ('idx_audit_fk_specialty_form_submissions_visit_id', 'specialty_form_submissions', 'visit_id'),
    ('idx_audit_fk_specialty_form_versions_published_by', 'specialty_form_versions', 'published_by'),
    ('idx_audit_fk_specialty_forms_created_by', 'specialty_forms', 'created_by'),
    ('idx_audit_fk_specialty_forms_latest_published_version_id', 'specialty_forms', 'latest_published_version_id'),
    ('idx_audit_fk_stock_movements_performed_by', 'stock_movements', 'performed_by'),
    ('idx_audit_fk_support_tickets_assigned_to', 'support_tickets', 'assigned_to'),
    ('idx_audit_fk_support_tickets_created_by', 'support_tickets', 'created_by'),
    ('idx_audit_fk_tenant_modules_activated_by', 'tenant_modules', 'activated_by'),
    ('idx_audit_fk_tenant_subscription_history_performed_by', 'tenant_subscription_history', 'performed_by'),
    ('idx_audit_fk_tenants_plan_id', 'tenants', 'plan_id'),
]


def upgrade():
    for idx_name, table, column in MISSING_FK_INDEXES:
        op.create_index(idx_name, table, [column], if_not_exists=True)


def downgrade():
    for idx_name, table, _column in MISSING_FK_INDEXES:
        op.drop_index(idx_name, table_name=table, if_exists=True)
