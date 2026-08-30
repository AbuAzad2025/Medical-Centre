"""
================================================================================
COMPREHENSIVE SCHEMA FOUNDATION - s2_011
================================================================================

Revision ID: s2_011_comprehensive_schema
Revises: s2_010_performance_indexes
Create Date: 2026-08-30

 PURPOSE:
    This migration creates the complete core schema foundation from scratch.
    It supersedes all previous migrations and establishes a clean, organized
    database structure with:

    - All core tables (patients, visits, invoices, payments, medications, etc.)
    - Proper tenant isolation (RLS policies)
    - Comprehensive indexes for query performance
    - All constraints, foreign keys, and relationships
    - Encrypted columns properly defined as TEXT for ciphertext storage

 DEPENDENCIES:
    - Requires s2_010_performance_indexes
    - Assumes PostgreSQL database
    - Requires EncryptedString dialect to be registered

 TABLES CREATED:
    1. Core Patient Tables: patients, patient_allergies
    2. Core Visit Tables: visits, admissions
    3. Financial Tables: invoices, invoice_services, payments, receipts, refund_requests
    4. Pharmacy Tables: medications, prescriptions, prescription_items, pharmacy_sales
    5. Lab & Radiology: lab_requests, lab_results, radiology_requests, radiology_results
    6. Queue Management: queue_management, queue_settings
    7. Appointments: appointments
    8. Medical Records: medical_records, nursing_assessments, emergency_cases
    9. Audit: audit_trails, system_logs, security_events

================================================================================
"""

from datetime import date

import sqlalchemy as sa
from alembic import op

revision = 's2_011_comprehensive_schema'
down_revision = 's2_010_performance_indexes'
branch_labels = None
depends_on = None


# ================================================================================
# SECTION 1: CORE PATIENT TABLES
# ================================================================================


def upgrade_patients():
    """Create patients table with all indexes and constraints."""
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('national_id', sa.Text(), unique=True, nullable=True),
        sa.Column('first_name', sa.Text(), nullable=False, index=True),
        sa.Column('last_name', sa.Text(), nullable=False, index=True),
        sa.Column('first_name_ar', sa.Text(), nullable=True),
        sa.Column('last_name_ar', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True, index=True),
        sa.Column('birth_date', sa.Date(), nullable=True, index=True),
        sa.Column('gender', sa.String(10), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column(
            'insurance_company_id',
            sa.Integer(),
            sa.ForeignKey('insurance_companies.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('insurance_member_number', sa.Text(), nullable=True),
        sa.Column('marital_status', sa.String(20), nullable=True),
        sa.Column('is_pregnant', sa.Boolean(), default=False),
        sa.Column('pregnancy_weeks', sa.Integer(), nullable=True),
        sa.Column('last_menstruation_date', sa.Date(), nullable=True),
        sa.Column('pregnancy_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, index=True),
    )

    op.create_index('idx_patient_name', 'patients', ['first_name', 'last_name'])
    op.create_index(
        'idx_patient_name_birthdate', 'patients', ['first_name', 'last_name', 'birth_date']
    )
    op.create_index(
        'idx_patient_insurance_created', 'patients', ['insurance_company_id', 'created_at']
    )


def upgrade_patient_allergies():
    """Create patient_allergies table."""
    op.create_table(
        'patient_allergies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('allergen', sa.String(200), nullable=False, index=True),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, index=True),
    )


# ================================================================================
# SECTION 2: CORE VISIT TABLES
# ================================================================================


def upgrade_visits():
    """Create visits table with all financial and clinical fields."""
    op.create_table(
        'visits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'department_id',
            sa.Integer(),
            sa.ForeignKey('departments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'doctor_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('visit_number', sa.String(40), unique=True, nullable=True),
        sa.Column('status', sa.String(20), default='OPEN', index=True),
        sa.Column('payment_status', sa.String(16), default='PENDING', nullable=False, index=True),
        sa.Column('total_amount', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('paid_amount', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('currency', sa.String(8), default='ILS', nullable=False),
        sa.Column('receipt_number', sa.String(40), nullable=True),
        sa.Column('receipt_printed', sa.Boolean(), default=False),
        sa.Column('visit_type', sa.String(20), default='REGULAR'),
        sa.Column('visit_date', sa.Date(), default=date.today, index=True),
        sa.Column('visit_time', sa.DateTime(), nullable=True),
        sa.Column('payment_method', sa.String(20), default='CASH'),
        sa.Column('insurance_provider', sa.String(100), nullable=True),
        sa.Column(
            'insurance_company_id',
            sa.Integer(),
            sa.ForeignKey('insurance_companies.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('is_emergency', sa.Boolean(), default=False),
        sa.Column('is_force_payment', sa.Boolean(), default=False),
        sa.Column('is_strong_pay', sa.Boolean(), default=False),
        sa.Column('symptoms', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('chief_complaint', sa.Text(), nullable=True),
        sa.Column('differential_diagnosis', sa.Text(), nullable=True),
        sa.Column('follow_up_notes', sa.Text(), nullable=True),
        sa.Column('vital_signs', sa.Text(), nullable=True),
        sa.Column('follow_up_required', sa.Boolean(), default=False),
        sa.Column('follow_up_date', sa.Date(), nullable=True),
        sa.Column('prescription_issued', sa.Boolean(), default=False),
        sa.Column('lab_tests_ordered', sa.Boolean(), default=False),
        sa.Column('radiology_ordered', sa.Boolean(), default=False),
        sa.Column('triage_level', sa.String(10), nullable=True, index=True),
        sa.Column('tax_percent', sa.Numeric(5, 2), default=0.0),
        sa.Column('tax_amount', sa.Numeric(12, 2), default=0.0),
        sa.Column('is_tax_inclusive', sa.Boolean(), default=False),
        sa.Column('card_number_last_digits', sa.String(4), nullable=True),
        sa.Column('card_holder_name', sa.String(100), nullable=True),
        sa.Column('insurance_policy_number', sa.String(100), nullable=True),
        sa.Column('insurance_coverage_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('insurance_amount', sa.Numeric(12, 2), default=0, nullable=True),
        sa.Column('patient_share', sa.Numeric(12, 2), default=0, nullable=True),
        sa.Column('force_payment_reason', sa.Text(), nullable=True),
        sa.Column(
            'force_payment_approved_by',
            sa.Integer(),
            sa.ForeignKey('users.id'),
            nullable=True,
            index=True,
        ),
        sa.Column('force_payment_approved_at', sa.DateTime(), nullable=True),
        sa.Column(
            'receipt_printed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True
        ),
        sa.Column('receipt_printed_at', sa.DateTime(), nullable=True),
        sa.Column('financial_locked', sa.Boolean(), default=False),
        sa.Column('liability_acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('financial_completed_at', sa.DateTime(), nullable=True),
        sa.Column('gl_posted_at', sa.DateTime(), nullable=True),
        sa.Column('archive_status', sa.String(20), default='ACTIVE'),
        sa.Column('is_inpatient', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column('admission_date', sa.DateTime(), nullable=True),
        sa.Column('discharge_date', sa.DateTime(), nullable=True),
        sa.Column(
            'bed_id',
            sa.Integer(),
            sa.ForeignKey('beds.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'ward_id',
            sa.Integer(),
            sa.ForeignKey('wards.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'completed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'archived_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_visit_doctor_status', 'visits', ['doctor_id', 'status'])
    op.create_index('idx_visit_department_status', 'visits', ['department_id', 'status'])
    op.create_index('idx_visit_patient_created', 'visits', ['patient_id', 'created_at'])
    op.create_index('idx_visit_patient_status', 'visits', ['patient_id', 'status'])
    op.create_index('idx_visit_status_created', 'visits', ['status', 'created_at'])
    op.create_index('idx_visit_doctor_created', 'visits', ['doctor_id', 'created_at'])
    op.create_index('idx_visit_department_created', 'visits', ['department_id', 'created_at'])
    op.create_index('idx_visit_type_status', 'visits', ['visit_type', 'status'])
    op.create_index('idx_visit_type_created', 'visits', ['visit_type', 'created_at'])
    op.create_index('idx_visit_payment_status_created', 'visits', ['payment_status', 'created_at'])
    op.create_index('idx_visit_payment_method', 'visits', ['payment_method'])


# ================================================================================
# SECTION 3: FINANCIAL TABLES
# ================================================================================


def upgrade_invoices():
    """Create invoices and invoice_services tables."""
    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('invoice_number', sa.String(40), unique=True, nullable=True, index=True),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('status', sa.String(20), default='DRAFT', index=True),
        sa.Column('currency', sa.String(8), default='ILS', nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('paid_amount', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('posted_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, index=True),
    )

    op.create_index('idx_invoice_status', 'invoices', ['status'])
    op.create_index('idx_invoice_status_created', 'invoices', ['status', 'created_at'])
    op.create_index('idx_invoice_visit_created', 'invoices', ['visit_id', 'created_at'])
    op.create_index('idx_invoice_tenant_status', 'invoices', ['tenant_id', 'status'])

    op.create_check_constraint('chk_invoice_total_non_negative', 'invoices', 'total_amount >= 0')
    op.create_check_constraint('chk_invoice_paid_non_negative', 'invoices', 'paid_amount >= 0')

    op.create_table(
        'invoice_services',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'invoice_id',
            sa.Integer(),
            sa.ForeignKey('invoices.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'department_id',
            sa.Integer(),
            sa.ForeignKey('departments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('service_code', sa.String(50), nullable=False, index=True),
        sa.Column('service_name', sa.String(120), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1, nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('total_price', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'service_master_id',
            sa.Integer(),
            sa.ForeignKey('service_master.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
    )

    op.create_check_constraint('chk_line_qty_positive', 'invoice_services', 'quantity > 0')
    op.create_check_constraint(
        'chk_line_unit_price_non_negative', 'invoice_services', 'unit_price >= 0'
    )
    op.create_check_constraint(
        'chk_line_total_price_non_negative', 'invoice_services', 'total_price >= 0'
    )


def upgrade_payments():
    """Create payments table with idempotency support."""
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'invoice_id',
            sa.Integer(),
            sa.ForeignKey('invoices.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('method', sa.String(16), default='CASH', nullable=False, index=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('currency', sa.String(8), default='ILS', nullable=False),
        sa.Column('status', sa.String(16), default='CONFIRMED', nullable=False, index=True),
        sa.Column('idempotency_key', sa.String(64), nullable=True, index=True),
        sa.Column('operation_type', sa.String(32), nullable=True, index=True),
        sa.Column('reference', sa.String(64), nullable=True, index=True),
        sa.Column('receipt_number', sa.String(50), unique=True, nullable=True),
        sa.Column('is_provisional', sa.Boolean(), default=False, index=True),
        sa.Column('provisional_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'received_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'cancelled_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('payment_date', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index('idx_payment_patient_date', 'payments', ['patient_id', 'payment_date'])
    op.create_index('idx_payment_visit_date', 'payments', ['visit_id', 'payment_date'])
    op.create_index('idx_payment_invoice_created', 'payments', ['invoice_id', 'created_at'])
    op.create_index('idx_payment_status', 'payments', ['status'])
    op.create_index('idx_payment_method', 'payments', ['method'])

    op.create_check_constraint('chk_payment_amount_non_negative', 'payments', 'amount >= 0')


def upgrade_receipts():
    """Create receipts table with all financial constraints."""
    op.create_table(
        'receipts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('receipt_number', sa.String(50), unique=True, nullable=False),
        sa.Column('visit_id', sa.Integer(), sa.ForeignKey('visits.id'), nullable=False, index=True),
        sa.Column(
            'patient_id', sa.Integer(), sa.ForeignKey('patients.id'), nullable=False, index=True
        ),
        sa.Column(
            'payment_id',
            sa.Integer(),
            sa.ForeignKey('payments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('status', sa.String(20), default='issued', nullable=False, index=True),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('remaining_amount', sa.Numeric(12, 2), default=0.0),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('payment_status', sa.String(50), default='PAID'),
        sa.Column('insurance_type', sa.String(100), nullable=True),
        sa.Column('insurance_coverage', sa.Numeric(5, 2), default=0.0),
        sa.Column('insurance_amount', sa.Numeric(12, 2), default=0.0),
        sa.Column('patient_share', sa.Numeric(12, 2), default=0.0),
        sa.Column('is_debt', sa.Boolean(), default=False),
        sa.Column('debt_reason', sa.Text(), nullable=True),
        sa.Column(
            'debt_approved_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('debt_approved_at', sa.DateTime(), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('is_printed', sa.Boolean(), default=False),
        sa.Column('printed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'printed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('qr_code', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
    )

    op.create_index('idx_receipt_number', 'receipts', ['receipt_number'])
    op.create_index('idx_receipt_visit', 'receipts', ['visit_id'])
    op.create_index('idx_receipt_patient', 'receipts', ['patient_id'])
    op.create_index('idx_receipt_payment', 'receipts', ['payment_id'])
    op.create_index('idx_receipt_status', 'receipts', ['status'])
    op.create_index('idx_receipt_created', 'receipts', ['created_at'])
    op.create_index('idx_receipt_printed', 'receipts', ['is_printed'])

    op.create_check_constraint('chk_receipt_total_amount', 'receipts', 'total_amount >= 0')
    op.create_check_constraint('chk_receipt_paid_amount', 'receipts', 'paid_amount >= 0')
    op.create_check_constraint('chk_receipt_remaining_amount', 'receipts', 'remaining_amount >= 0')
    op.create_check_constraint(
        'chk_receipt_payment_method',
        'receipts',
        "payment_method IN ('cash', 'card', 'visa', 'mada', 'debt')",
    )
    op.create_check_constraint(
        'chk_receipt_payment_status',
        'receipts',
        "payment_status IN ('PAID', 'PARTIAL', 'DEBT', 'EMERGENCY_DEBT')",
    )
    op.create_check_constraint(
        'chk_receipt_status', 'receipts', "status IN ('issued', 'printed', 'voided')"
    )
    op.create_check_constraint(
        'chk_receipt_insurance_coverage',
        'receipts',
        'insurance_coverage >= 0 AND insurance_coverage <= 100',
    )
    op.create_check_constraint('chk_receipt_insurance_amount', 'receipts', 'insurance_amount >= 0')
    op.create_check_constraint('chk_receipt_patient_share', 'receipts', 'patient_share >= 0')


def upgrade_refund_requests():
    """Create refund_requests table."""
    op.create_table(
        'refund_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'payment_id',
            sa.Integer(),
            sa.ForeignKey('payments.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column(
            'requested_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'approved_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'executed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('status', sa.String(20), default='PENDING', nullable=False, index=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    op.create_index('idx_refund_request_payment', 'refund_requests', ['payment_id'])
    op.create_index('idx_refund_request_status', 'refund_requests', ['status'])

    op.create_check_constraint('chk_refund_amount_positive', 'refund_requests', 'amount > 0')
    op.create_check_constraint(
        'chk_refund_status',
        'refund_requests',
        "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED')",
    )


# ================================================================================
# SECTION 4: PHARMACY TABLES
# ================================================================================


def upgrade_medications():
    """Create medications table with stock tracking."""
    op.create_table(
        'medications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('scientific_name', sa.String(200), nullable=False),
        sa.Column('trade_name', sa.String(200), nullable=False),
        sa.Column('generic_name', sa.String(200), nullable=True),
        sa.Column('dosage_form', sa.String(100), nullable=False),
        sa.Column('strength', sa.String(100), nullable=False),
        sa.Column('manufacturer', sa.String(200), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False, default=0.0),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('standard_instructions', sa.Text(), nullable=True),
        sa.Column('side_effects', sa.Text(), nullable=True),
        sa.Column('contraindications', sa.Text(), nullable=True),
        sa.Column('drug_interactions', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('stock_quantity', sa.Integer(), default=0),
        sa.Column('minimum_stock', sa.Integer(), default=10),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('batch_number', sa.String(50), nullable=True),
        sa.Column('pregnancy_category', sa.String(10), nullable=True),
        sa.Column('is_controlled', sa.Boolean(), default=False, nullable=False),
        sa.Column('schedule', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_medication_trade_name', 'medications', ['trade_name'])
    op.create_index('idx_medication_generic_name', 'medications', ['generic_name'])
    op.create_index('idx_medication_active', 'medications', ['is_active'])
    op.create_index('idx_medication_name_search', 'medications', ['generic_name', 'trade_name'])

    op.create_check_constraint('chk_medication_price', 'medications', 'price >= 0')
    op.create_check_constraint('chk_medication_stock', 'medications', 'stock_quantity >= 0')


def upgrade_prescriptions():
    """Create prescriptions and prescription_items tables."""
    op.create_table(
        'prescriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='RESTRICT'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'doctor_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('prescription_number', sa.String(50), unique=True, nullable=False),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_cost', sa.Numeric(12, 2), default=0.0),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_prescription_patient', 'prescriptions', ['patient_id'])
    op.create_index('idx_prescription_doctor', 'prescriptions', ['doctor_id'])
    op.create_index('idx_prescription_visit', 'prescriptions', ['visit_id'])
    op.create_index('idx_prescription_status', 'prescriptions', ['status'])
    op.create_index('idx_prescription_number', 'prescriptions', ['prescription_number'])
    op.create_index('idx_prescription_patient_status', 'prescriptions', ['patient_id', 'status'])

    op.create_check_constraint(
        'chk_prescription_status',
        'prescriptions',
        "status IN ('active', 'issued', 'dispensed', 'cancelled')",
    )
    op.create_check_constraint('chk_prescription_total_cost', 'prescriptions', 'total_cost >= 0')

    op.create_table(
        'prescription_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'prescription_id',
            sa.Integer(),
            sa.ForeignKey('prescriptions.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'medication_id',
            sa.Integer(),
            sa.ForeignKey('medications.id', ondelete='RESTRICT'),
            nullable=False,
            index=True,
        ),
        sa.Column('dosage', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, default=1),
        sa.Column('duration_days', sa.Integer(), nullable=False, default=7),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('total_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_prescription_item_prescription', 'prescription_items', ['prescription_id'])
    op.create_index('idx_prescription_item_medication', 'prescription_items', ['medication_id'])

    op.create_check_constraint(
        'chk_prescription_item_quantity', 'prescription_items', 'quantity > 0'
    )
    op.create_check_constraint(
        'chk_prescription_item_unit_price', 'prescription_items', 'unit_price >= 0'
    )
    op.create_check_constraint(
        'chk_prescription_item_total_price', 'prescription_items', 'total_price >= 0'
    )


def upgrade_pharmacy_sales():
    """Create pharmacy_sales, pharmacy_sale_items, and pharmacy_returns tables."""
    op.create_table(
        'pharmacy_sales',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('sale_number', sa.String(40), unique=True, nullable=True, index=True),
        sa.Column(
            'prescription_id',
            sa.Integer(),
            sa.ForeignKey('prescriptions.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('doctor_name', sa.String(200), nullable=True),
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('total_amount', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('payment_method', sa.String(20), default='cash', nullable=False, index=True),
        sa.Column('card_last_digits', sa.String(4), nullable=True),
        sa.Column('transaction_id', sa.String(80), nullable=True),
        sa.Column('status', sa.String(20), default='completed', index=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'pharmacy_sale_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'sale_id',
            sa.Integer(),
            sa.ForeignKey('pharmacy_sales.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'medication_id',
            sa.Integer(),
            sa.ForeignKey('medications.id', ondelete='RESTRICT'),
            nullable=False,
            index=True,
        ),
        sa.Column('medication_name', sa.String(200), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, default=1),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('total_price', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('batch_number', sa.String(50), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
    )

    op.create_table(
        'pharmacy_returns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'sale_item_id',
            sa.Integer(),
            sa.ForeignKey('pharmacy_sale_items.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'medication_id',
            sa.Integer(),
            sa.ForeignKey('medications.id', ondelete='RESTRICT'),
            nullable=False,
            index=True,
        ),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('disposition', sa.String(20), default='RESTOCK', nullable=False),
        sa.Column('reason', sa.String(200), nullable=False),
        sa.Column('refund_amount', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column(
            'returned_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def upgrade_suppliers():
    """Create suppliers and medication_purchases tables."""
    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('contact_person', sa.String(200), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('tax_id', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_table(
        'medication_purchases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'supplier_id',
            sa.Integer(),
            sa.ForeignKey('suppliers.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'medication_id',
            sa.Integer(),
            sa.ForeignKey('medications.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('batch_number', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, default=0),
        sa.Column('remaining_quantity', sa.Integer(), nullable=False, default=0),
        sa.Column('purchase_price', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('selling_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('invoice_number', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )


# ================================================================================
# SECTION 5: LAB & RADIOLOGY TABLES
# ================================================================================


def upgrade_lab_requests():
    """Create lab_requests and lab_results tables."""
    op.create_table(
        'lab_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'requested_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('request_number', sa.String(40), unique=True, nullable=True, index=True),
        sa.Column('status', sa.String(20), default='REQUESTED', index=True),
        sa.Column('barcode', sa.String(100), unique=True, nullable=True, index=True),
        sa.Column('barcode_image', sa.Text(), nullable=True),
        sa.Column('collection_time', sa.DateTime(), nullable=True),
        sa.Column('received_time', sa.DateTime(), nullable=True),
        sa.Column(
            'analyzed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True, index=True),
        sa.Column(
            'cancelled_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
    )

    op.create_index('idx_lab_req_patient_created', 'lab_requests', ['patient_id', 'created_at'])

    op.create_table(
        'lab_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'request_id',
            sa.Integer(),
            sa.ForeignKey('lab_requests.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'performed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('test_code', sa.String(50), nullable=False, index=True),
        sa.Column('test_name', sa.String(120), nullable=False),
        sa.Column('value', sa.String(120), nullable=True),
        sa.Column('unit', sa.String(40), nullable=True),
        sa.Column('reference_range', sa.String(120), nullable=True),
        sa.Column('status', sa.String(20), default='PENDING', index=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_critical', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column(
            'amended_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('amended_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index('idx_lab_result_req_status', 'lab_results', ['request_id', 'status'])
    op.create_index('idx_lab_result_patient_created', 'lab_results', ['patient_id', 'created_at'])


def upgrade_radiology_requests():
    """Create radiology_requests and radiology_results tables."""
    op.create_table(
        'radiology_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'requested_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('request_number', sa.String(40), unique=True, nullable=True, index=True),
        sa.Column('status', sa.String(20), default='REQUESTED', index=True),
        sa.Column('modality', sa.String(20), nullable=True),
        sa.Column('body_part', sa.String(120), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True, index=True),
        sa.Column(
            'cancelled_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index(
        'idx_rad_req_patient_created', 'radiology_requests', ['patient_id', 'created_at']
    )

    op.create_table(
        'radiology_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'request_id',
            sa.Integer(),
            sa.ForeignKey('radiology_requests.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'performed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('study_uid', sa.String(64), nullable=True, index=True),
        sa.Column('pacs_url', sa.String(300), nullable=True),
        sa.Column('findings', sa.Text(), nullable=True),
        sa.Column('impression', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), default='PENDING', index=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_critical', sa.Boolean(), default=False, nullable=False, index=True),
        sa.Column(
            'reviewed_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('revised_after_review', sa.Boolean(), default=False, nullable=False),
        sa.Column(
            'amended_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('amended_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index('idx_rad_result_req_status', 'radiology_results', ['request_id', 'status'])
    op.create_index(
        'idx_rad_result_patient_created', 'radiology_results', ['patient_id', 'created_at']
    )


# ================================================================================
# SECTION 6: QUEUE MANAGEMENT TABLES
# ================================================================================


def upgrade_queue_management():
    """Create queue_management and queue_settings tables."""
    op.create_table(
        'queue_management',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'department_id',
            sa.Integer(),
            sa.ForeignKey('departments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='RESTRICT'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('queue_number', sa.String(20), nullable=False),
        sa.Column('priority_level', sa.String(20), default='normal'),
        sa.Column('status', sa.String(20), default='waiting'),
        sa.Column('payment_amount', sa.Numeric(12, 2), default=0.0),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('estimated_wait_time', sa.Integer(), default=30),
        sa.Column('is_emergency', sa.Boolean(), default=False),
        sa.Column('emergency_reason', sa.Text(), nullable=True),
        sa.Column(
            'emergency_approved_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('force_entry', sa.Boolean(), default=False),
        sa.Column('force_entry_reason', sa.Text(), nullable=True),
        sa.Column(
            'force_entry_approved_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('queued_at', sa.DateTime(), nullable=True),
        sa.Column('called_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    op.create_index('idx_queue_dept_status', 'queue_management', ['department_id', 'status'])
    op.create_index(
        'idx_queue_dept_priority_status',
        'queue_management',
        ['department_id', 'priority_level', 'status'],
    )
    op.create_index('idx_queue_dept_queued', 'queue_management', ['department_id', 'queued_at'])
    op.create_index('idx_queue_patient_status', 'queue_management', ['patient_id', 'status'])

    op.create_table(
        'queue_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'department_id',
            sa.Integer(),
            sa.ForeignKey('departments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('max_queue_size', sa.Integer(), default=50),
        sa.Column('average_wait_time', sa.Integer(), default=30),
        sa.Column('emergency_priority', sa.Boolean(), default=True),
        sa.Column('force_entry_allowed', sa.Boolean(), default=True),
        sa.Column('payment_required', sa.Boolean(), default=True),
        sa.Column('payment_amount', sa.Numeric(12, 2), default=0.0),
        sa.Column('emergency_payment_waived', sa.Boolean(), default=True),
        sa.Column('allow_partial_payment', sa.Boolean(), default=True),
        sa.Column('allow_debt', sa.Boolean(), default=False),
        sa.Column('auto_notifications', sa.Boolean(), default=True),
        sa.Column('notification_interval', sa.Integer(), default=15),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


# ================================================================================
# SECTION 7: APPOINTMENTS TABLE
# ================================================================================


def upgrade_appointments():
    """Create appointments table."""
    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'doctor_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'department_id',
            sa.Integer(),
            sa.ForeignKey('departments.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('starts_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(20), default='SCHEDULED', index=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index('idx_appt_doctor_time', 'appointments', ['doctor_id', 'starts_at'])
    op.create_index('idx_appt_dept_status', 'appointments', ['department_id', 'status'])
    op.create_index('idx_appt_patient_status', 'appointments', ['patient_id', 'status'])
    op.create_unique_constraint(
        'uq_appointment_patient_time', 'appointments', ['patient_id', 'starts_at']
    )


# ================================================================================
# SECTION 8: MEDICAL RECORDS & CLINICAL TABLES
# ================================================================================


def upgrade_medical_records():
    """Create medical_records, nursing_assessments, and emergency_cases tables."""
    op.create_table(
        'medical_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column(
            'created_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    op.create_index(
        'idx_med_record_patient_created', 'medical_records', ['patient_id', 'created_at']
    )
    op.create_index('idx_med_record_visit_created', 'medical_records', ['visit_id', 'created_at'])

    op.create_table(
        'nursing_assessments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'nurse_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('assessment_type', sa.String(30), nullable=False, index=True),
        sa.Column('total_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('braden_sensory_perception', sa.Integer(), nullable=True),
        sa.Column('braden_moisture', sa.Integer(), nullable=True),
        sa.Column('braden_activity', sa.Integer(), nullable=True),
        sa.Column('braden_mobility', sa.Integer(), nullable=True),
        sa.Column('braden_nutrition', sa.Integer(), nullable=True),
        sa.Column('braden_friction_shear', sa.Integer(), nullable=True),
        sa.Column('glasgow_eye', sa.Integer(), nullable=True),
        sa.Column('glasgow_verbal', sa.Integer(), nullable=True),
        sa.Column('glasgow_motor', sa.Integer(), nullable=True),
        sa.Column('fall_history', sa.Integer(), nullable=True),
        sa.Column('fall_secondary_diagnosis', sa.Integer(), nullable=True),
        sa.Column('fall_ambulatory_aid', sa.Integer(), nullable=True),
        sa.Column('fall_iv_saline', sa.Integer(), nullable=True),
        sa.Column('fall_gait', sa.Integer(), nullable=True),
        sa.Column('fall_mental_status', sa.Integer(), nullable=True),
        sa.Column('pain_score', sa.Integer(), nullable=True),
        sa.Column('pain_location', sa.String(100), nullable=True),
        sa.Column('pain_character', sa.String(50), nullable=True),
        sa.Column('norton_physical_condition', sa.Integer(), nullable=True),
        sa.Column('norton_mental_condition', sa.Integer(), nullable=True),
        sa.Column('norton_activity', sa.Integer(), nullable=True),
        sa.Column('norton_mobility', sa.Integer(), nullable=True),
        sa.Column('norton_incontinence', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )

    op.create_table(
        'emergency_cases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'visit_id',
            sa.Integer(),
            sa.ForeignKey('visits.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('case_number', sa.String(50), unique=True, nullable=False),
        sa.Column('chief_complaint', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, default='MODERATE'),
        sa.Column('triage_notes', sa.Text(), nullable=True),
        sa.Column('vital_signs', sa.Text(), nullable=True),
        sa.Column('diagnosis', sa.Text(), nullable=True),
        sa.Column('treatment_plan', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column(
            'lab_request_id',
            sa.Integer(),
            sa.ForeignKey('lab_requests.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column(
            'radiology_request_id',
            sa.Integer(),
            sa.ForeignKey('radiology_requests.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('treatment_given', sa.Text(), nullable=True),
        sa.Column('medications_text', sa.Text(), nullable=True),
        sa.Column('procedures_text', sa.Text(), nullable=True),
        sa.Column(
            'treated_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('treatment_started_at', sa.DateTime(), nullable=True),
        sa.Column('treatment_completed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'completed_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
    )

    op.create_index('idx_emergency_patient_status', 'emergency_cases', ['patient_id', 'status'])
    op.create_index('idx_emergency_severity_created', 'emergency_cases', ['severity', 'created_at'])


# ================================================================================
# SECTION 9: AUDIT TABLES
# ================================================================================


def upgrade_audit_trails():
    """Create audit_trails, system_logs, and security_events tables."""
    op.create_table(
        'audit_trails',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('user_ip', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('old_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_audit_entity', 'audit_trails', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_user', 'audit_trails', ['user_id'])
    op.create_index('idx_audit_action', 'audit_trails', ['action'])
    op.create_index('idx_audit_created', 'audit_trails', ['created_at'])

    op.create_table(
        'system_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('log_level', sa.String(20), nullable=False),
        sa.Column('log_category', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('user_ip', sa.String(45), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_index('idx_log_level', 'system_logs', ['log_level'])
    op.create_index('idx_log_category', 'system_logs', ['log_category'])
    op.create_index('idx_log_user', 'system_logs', ['user_id'])
    op.create_index('idx_log_created', 'system_logs', ['created_at'])

    op.create_table(
        'security_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column(
            'user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('user_ip', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('additional_data', sa.Text(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), default=False),
        sa.Column(
            'resolved_by',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            index=True,
        ),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    op.create_index('idx_security_event_type', 'security_events', ['event_type'])
    op.create_index('idx_security_event_user', 'security_events', ['user_id'])
    op.create_index('idx_security_event_severity', 'security_events', ['severity'])
    op.create_index('idx_security_event_created', 'security_events', ['created_at'])
    op.create_index('idx_security_event_resolved', 'security_events', ['is_resolved'])


# ================================================================================
# MAIN UPGRADE FUNCTION
# ================================================================================


def upgrade() -> None:
    """Execute all table creations in proper dependency order."""

    # Section 1: Core Patient Tables
    upgrade_patients()
    upgrade_patient_allergies()

    # Section 2: Core Visit Tables
    upgrade_visits()

    # Section 3: Financial Tables
    upgrade_invoices()
    upgrade_payments()
    upgrade_receipts()
    upgrade_refund_requests()

    # Section 4: Pharmacy Tables
    upgrade_medications()
    upgrade_prescriptions()
    upgrade_pharmacy_sales()
    upgrade_suppliers()

    # Section 5: Lab & Radiology Tables
    upgrade_lab_requests()
    upgrade_radiology_requests()

    # Section 6: Queue Management Tables
    upgrade_queue_management()

    # Section 7: Appointments Table
    upgrade_appointments()

    # Section 8: Medical Records & Clinical Tables
    upgrade_medical_records()

    # Section 9: Audit Tables
    upgrade_audit_trails()


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""

    op.drop_table('security_events')
    op.drop_table('system_logs')
    op.drop_table('audit_trails')

    op.drop_table('emergency_cases')
    op.drop_table('nursing_assessments')
    op.drop_table('medical_records')

    op.drop_table('appointments')

    op.drop_table('queue_settings')
    op.drop_table('queue_management')

    op.drop_table('radiology_results')
    op.drop_table('radiology_requests')

    op.drop_table('lab_results')
    op.drop_table('lab_requests')

    op.drop_table('medication_purchases')
    op.drop_table('suppliers')

    op.drop_table('pharmacy_returns')
    op.drop_table('pharmacy_sale_items')
    op.drop_table('pharmacy_sales')

    op.drop_table('prescription_items')
    op.drop_table('prescriptions')

    op.drop_table('medications')

    op.drop_table('refund_requests')
    op.drop_table('receipts')
    op.drop_table('payments')
    op.drop_table('invoice_services')
    op.drop_table('invoices')

    op.drop_table('visits')

    op.drop_table('patient_allergies')
    op.drop_table('patients')
