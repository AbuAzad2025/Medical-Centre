"""Add composite indexes for query performance

Revision ID: add_composite_indexes_20260619
Revises: add_fk_index_20260619
Create Date: 2026-06-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_composite_indexes_20260619'
down_revision = 'add_fk_index_20260619'
branch_labels = None
depends_on = None


def upgrade():
    # ==================== Patient ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_patient_name_birthdate" ON "patients" ("first_name", "last_name", "birth_date")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_patient_insurance_created" ON "patients" ("insurance_company_id", "created_at")')

    # ==================== Visit ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_patient_status" ON "visits" ("patient_id", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_status_created" ON "visits" ("status", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_doctor_created" ON "visits" ("doctor_id", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_department_created" ON "visits" ("department_id", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_type_status" ON "visits" ("visit_type", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_type_created" ON "visits" ("visit_type", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_visit_payment_status_created" ON "visits" ("payment_status", "created_at")')

    # ==================== VitalSigns ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_vitals_patient_recorded" ON "vital_signs" ("patient_id", "recorded_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_vitals_nurse_recorded" ON "vital_signs" ("nurse_id", "recorded_at")')

    # ==================== MedicalRecord ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_med_record_patient_created" ON "medical_records" ("patient_id", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_med_record_visit_created" ON "medical_records" ("visit_id", "created_at")')

    # ==================== MedicalReport ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_med_report_visit_created" ON "medical_reports" ("visit_id", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_med_report_signer_created" ON "medical_reports" ("signed_by", "created_at")')

    # ==================== User ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_user_department_role" ON "users" ("department_id", "role")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_user_active_role" ON "users" ("is_active", "role")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_user_department_active" ON "users" ("department_id", "is_active")')

    # ==================== QueueManagement ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_queue_dept_status" ON "queue_management" ("department_id", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_queue_dept_priority_status" ON "queue_management" ("department_id", "priority_level", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_queue_dept_queued" ON "queue_management" ("department_id", "queued_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_queue_patient_status" ON "queue_management" ("patient_id", "status")')

    # ==================== Appointment ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_appt_dept_status" ON "appointments" ("department_id", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_appt_patient_status" ON "appointments" ("patient_id", "status")')

    # ==================== EmergencyCase ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_emergency_severity_created" ON "emergency_cases" ("severity", "created_at")')

    # ==================== Invoice ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_invoice_visit_created" ON "invoices" ("visit_id", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_invoice_tenant_status" ON "invoices" ("tenant_id", "status")')

    # ==================== Treatment ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_treatment_visit_status" ON "treatments" ("visit_id", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_treatment_doctor_status" ON "treatments" ("doctor_id", "status")')

    # ==================== Bed (via migration only — can't inline extend_existing) ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bed_room_status" ON "beds" ("room_id", "status")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bed_room_active" ON "beds" ("room_id", "is_active")')

    # ==================== Admission ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_admission_patient_active" ON "admissions" ("patient_id", "is_active")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_admission_bed_active" ON "admissions" ("bed_id", "is_active")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_admission_status_datetime" ON "admissions" ("status", "admission_datetime")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_admission_doctor_status" ON "admissions" ("admitting_doctor_id", "status")')

    # ==================== BedTransfer ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bed_transfer_admission_date" ON "bed_transfers" ("admission_id", "transfer_datetime")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_bed_transfer_patient_date" ON "bed_transfers" ("patient_id", "transfer_datetime")')

    # ==================== Notification ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_notif_recipient_unread_sent" ON "notifications" ("recipient_id", "is_read", "sent_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_notif_recipient_sent" ON "notifications" ("recipient_id", "sent_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_notif_dept_unread" ON "notifications" ("recipient_department_id", "is_read")')

    # ==================== NotificationQueue ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_notif_queue_status_scheduled" ON "notification_queue" ("status", "scheduled_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_notif_queue_type_status_priority" ON "notification_queue" ("notification_type", "status", "priority")')

    # ==================== Receipt ====================
    op.execute('CREATE INDEX IF NOT EXISTS "idx_receipt_payment_status_created" ON "receipts" ("payment_status", "created_at")')
    op.execute('CREATE INDEX IF NOT EXISTS "idx_receipt_visit_payment" ON "receipts" ("visit_id", "payment_status")')


def downgrade():
    # Patient
    op.execute('DROP INDEX IF EXISTS "idx_patient_name_birthdate"')
    op.execute('DROP INDEX IF EXISTS "idx_patient_insurance_created"')

    # Visit
    op.execute('DROP INDEX IF EXISTS "idx_visit_patient_status"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_status_created"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_doctor_created"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_department_created"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_type_status"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_type_created"')
    op.execute('DROP INDEX IF EXISTS "idx_visit_payment_status_created"')

    # VitalSigns
    op.execute('DROP INDEX IF EXISTS "idx_vitals_patient_recorded"')
    op.execute('DROP INDEX IF EXISTS "idx_vitals_nurse_recorded"')

    # MedicalRecord
    op.execute('DROP INDEX IF EXISTS "idx_med_record_patient_created"')
    op.execute('DROP INDEX IF EXISTS "idx_med_record_visit_created"')

    # MedicalReport
    op.execute('DROP INDEX IF EXISTS "idx_med_report_visit_created"')
    op.execute('DROP INDEX IF EXISTS "idx_med_report_signer_created"')

    # User
    op.execute('DROP INDEX IF EXISTS "idx_user_department_role"')
    op.execute('DROP INDEX IF EXISTS "idx_user_active_role"')
    op.execute('DROP INDEX IF EXISTS "idx_user_department_active"')

    # QueueManagement
    op.execute('DROP INDEX IF EXISTS "idx_queue_dept_status"')
    op.execute('DROP INDEX IF EXISTS "idx_queue_dept_priority_status"')
    op.execute('DROP INDEX IF EXISTS "idx_queue_dept_queued"')
    op.execute('DROP INDEX IF EXISTS "idx_queue_patient_status"')

    # Appointment
    op.execute('DROP INDEX IF EXISTS "idx_appt_dept_status"')
    op.execute('DROP INDEX IF EXISTS "idx_appt_patient_status"')

    # EmergencyCase
    op.execute('DROP INDEX IF EXISTS "idx_emergency_severity_created"')

    # Invoice
    op.execute('DROP INDEX IF EXISTS "idx_invoice_visit_created"')
    op.execute('DROP INDEX IF EXISTS "idx_invoice_tenant_status"')

    # Treatment
    op.execute('DROP INDEX IF EXISTS "idx_treatment_visit_status"')
    op.execute('DROP INDEX IF EXISTS "idx_treatment_doctor_status"')

    # Bed
    op.execute('DROP INDEX IF EXISTS "idx_bed_room_status"')
    op.execute('DROP INDEX IF EXISTS "idx_bed_room_active"')

    # Admission
    op.execute('DROP INDEX IF EXISTS "idx_admission_patient_active"')
    op.execute('DROP INDEX IF EXISTS "idx_admission_bed_active"')
    op.execute('DROP INDEX IF EXISTS "idx_admission_status_datetime"')
    op.execute('DROP INDEX IF EXISTS "idx_admission_doctor_status"')

    # BedTransfer
    op.execute('DROP INDEX IF EXISTS "idx_bed_transfer_admission_date"')
    op.execute('DROP INDEX IF EXISTS "idx_bed_transfer_patient_date"')

    # Notification
    op.execute('DROP INDEX IF EXISTS "idx_notif_recipient_unread_sent"')
    op.execute('DROP INDEX IF EXISTS "idx_notif_recipient_sent"')
    op.execute('DROP INDEX IF EXISTS "idx_notif_dept_unread"')

    # NotificationQueue
    op.execute('DROP INDEX IF EXISTS "idx_notif_queue_status_scheduled"')
    op.execute('DROP INDEX IF EXISTS "idx_notif_queue_type_status_priority"')

    # Receipt
    op.execute('DROP INDEX IF EXISTS "idx_receipt_payment_status_created"')
    op.execute('DROP INDEX IF EXISTS "idx_receipt_visit_payment"')
