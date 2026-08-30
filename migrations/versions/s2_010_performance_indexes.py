"""add performance indexes for N+1 and filter optimization

Revision ID: s2_010_performance_indexes
Revises: s2_009_schema_drift_sync
Create Date: 2026-08-30

Adds composite indexes for:
- Visit: tenant+status, tenant+date, tenant+payment_status
- Payment: tenant+status+date, tenant+method+date
- Invoice: tenant+status+date
- LabRequest: tenant+status, patient+status
- RadiologyRequest: tenant+status, patient+status, modality
- QueueManagement: tenant+status, tenant+department
- Appointment: tenant+status, tenant+starts_at, doctor+status+starts_at
- Prescription: tenant+status, doctor+status
- EmergencyCase: tenant+status, tenant+severity

These indexes eliminate table scans on the most common filter patterns
discovered during N+1 audit of routes/services.
"""

from alembic import op
import sqlalchemy as sa

revision = 's2_010_performance_indexes'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None

PERFORMANCE_INDEXES = [
    ('idx_visit_tenant_status', 'visits', ['tenant_id', 'status']),
    ('idx_visit_tenant_visit_date', 'visits', ['tenant_id', 'visit_date']),
    ('idx_visit_tenant_payment_status', 'visits', ['tenant_id', 'payment_status']),
    ('idx_visit_department_visit_date', 'visits', ['department_id', 'visit_date']),
    ('idx_visit_doctor_visit_date', 'visits', ['doctor_id', 'visit_date']),
    ('idx_payment_tenant_status_created', 'payments', ['tenant_id', 'status', 'created_at']),
    ('idx_payment_tenant_method_created', 'payments', ['tenant_id', 'method', 'created_at']),
    ('idx_invoice_tenant_status_created', 'invoices', ['tenant_id', 'status', 'created_at']),
    ('idx_invoice_tenant_posted_at', 'invoices', ['tenant_id', 'posted_at']),
    ('idx_lab_request_tenant_status', 'lab_requests', ['tenant_id', 'status']),
    ('idx_lab_request_patient_status', 'lab_requests', ['patient_id', 'status']),
    ('idx_lab_request_tenant_created', 'lab_requests', ['tenant_id', 'created_at']),
    ('idx_radiology_request_tenant_status', 'radiology_requests', ['tenant_id', 'status']),
    ('idx_radiology_request_patient_status', 'radiology_requests', ['patient_id', 'status']),
    ('idx_radiology_request_tenant_created', 'radiology_requests', ['tenant_id', 'created_at']),
    ('idx_radiology_request_modality', 'radiology_requests', ['modality']),
    ('idx_queue_management_tenant_status', 'queue_management', ['tenant_id', 'status']),
    ('idx_queue_management_tenant_department', 'queue_management', ['tenant_id', 'department_id']),
    ('idx_queue_management_priority', 'queue_management', ['priority_level']),
    ('idx_queue_management_queued_at', 'queue_management', ['queued_at']),
    ('idx_appointment_tenant_status', 'appointments', ['tenant_id', 'status']),
    ('idx_appointment_tenant_starts_at', 'appointments', ['tenant_id', 'starts_at']),
    ('idx_appointment_doctor_status_starts', 'appointments', ['doctor_id', 'status', 'starts_at']),
    ('idx_appointment_department_starts_at', 'appointments', ['department_id', 'starts_at']),
    ('idx_prescription_tenant_status', 'prescriptions', ['tenant_id', 'status']),
    ('idx_prescription_doctor_status', 'prescriptions', ['doctor_id', 'status']),
    ('idx_prescription_tenant_created', 'prescriptions', ['tenant_id', 'created_at']),
    ('idx_medication_tenant_active', 'medications', ['tenant_id', 'is_active']),
    ('idx_medication_tenant_category', 'medications', ['tenant_id', 'category']),
    ('idx_pharmacy_sale_tenant_status_created', 'pharmacy_sales', ['tenant_id', 'status', 'created_at']),
    ('idx_receipt_tenant_status_created', 'receipts', ['tenant_id', 'status', 'created_at']),
    ('idx_receipt_patient_created', 'receipts', ['patient_id', 'created_at']),
    ('idx_refund_request_tenant_status', 'refund_requests', ['tenant_id', 'status']),
    ('idx_refund_request_tenant_requested', 'refund_requests', ['tenant_id', 'requested_at']),
    ('idx_emergency_case_tenant_status', 'emergency_cases', ['tenant_id', 'status']),
    ('idx_emergency_case_tenant_severity', 'emergency_cases', ['tenant_id', 'severity']),
    ('idx_emergency_case_tenant_created', 'emergency_cases', ['tenant_id', 'created_at']),
    ('idx_medical_record_tenant_patient', 'medical_records', ['tenant_id', 'patient_id']),
    ('idx_medical_record_tenant_created', 'medical_records', ['tenant_id', 'created_at']),
    ('idx_nursing_assessment_tenant_patient', 'nursing_assessments', ['tenant_id', 'patient_id']),
    ('idx_nursing_assessment_tenant_type', 'nursing_assessments', ['tenant_id', 'assessment_type']),
    ('idx_patient_allergy_tenant_created', 'patient_allergies', ['tenant_id', 'created_at']),
    ('idx_audit_trail_tenant_created', 'audit_trails', ['tenant_id', 'created_at']),
    ('idx_audit_trail_tenant_entity', 'audit_trails', ['tenant_id', 'entity_type']),
    ('idx_audit_trail_tenant_action', 'audit_trails', ['tenant_id', 'action']),
    ('idx_audit_trail_entity_id', 'audit_trails', ['entity_id']),
]


def upgrade():
    bind = op.get_bind()
    for idx_name, table, columns in PERFORMANCE_INDEXES:
        exists = bind.execute(
            sa.text("SELECT to_regclass(:rel) IS NOT NULL"),
            {'rel': f'public.{table}'},
        ).scalar()
        if exists:
            op.create_index(idx_name, table, columns, if_not_exists=True)


def downgrade():
    bind = op.get_bind()
    for idx_name, table, _columns in PERFORMANCE_INDEXES:
        exists = bind.execute(
            sa.text("SELECT to_regclass(:rel) IS NOT NULL"),
            {'rel': f'public.{table}'},
        ).scalar()
        if exists:
            op.drop_index(idx_name, table_name=table, if_exists=True)
