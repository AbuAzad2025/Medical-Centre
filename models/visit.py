"""
نموذج الزيارة - Visit (نسخة نهائية موحّدة)
"""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Index
from app_factory import db


class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    visit_number = db.Column(db.String(40), nullable=True, unique=True)
    status = db.Column(db.String(20), default='OPEN', index=True)  # OPEN|IN_PROGRESS|COMPLETED|ARCHIVED

    payment_status = db.Column(db.String(16), default='PENDING', nullable=False, index=True)  # PENDING|PAID|DEBT
    total_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    paid_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    currency = db.Column(db.String(8), default='ILS', nullable=False)
    receipt_number = db.Column(db.String(40), nullable=True)
    receipt_printed = db.Column(db.Boolean, default=False)
    
    # حقول جديدة للسيناريو المطور
    visit_type = db.Column(db.String(20), default='REGULAR')  # REGULAR|FOLLOW_UP|CONSULTATION|EMERGENCY
    visit_date = db.Column(db.Date, default=db.func.date(db.func.now()), index=True)
    visit_time = db.Column(db.DateTime, default=db.func.now())
    payment_method = db.Column(db.String(20), default='CASH')
    insurance_provider = db.Column(db.String(100), nullable=True)
    insurance_company_id = db.Column(db.Integer, db.ForeignKey('insurance_companies.id', ondelete='SET NULL'), nullable=True, index=True)
    is_emergency = db.Column(db.Boolean, default=False)
    is_force_payment = db.Column(db.Boolean, default=False)
    is_strong_pay = db.Column(db.Boolean, default=False)
    symptoms = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # حقول إضافية للطباعة والتوثيق
    diagnosis = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.Date, nullable=True)
    prescription_issued = db.Column(db.Boolean, default=False)
    lab_tests_ordered = db.Column(db.Boolean, default=False)
    radiology_ordered = db.Column(db.Boolean, default=False)

    triage_level = db.Column(db.String(10), nullable=True, index=True)
    
    # حقول الضرائب
    tax_percent = db.Column(db.Numeric(5, 2), default=0.0)  # نسبة الضريبة
    tax_amount = db.Column(db.Numeric(12, 2), default=0.0)  # قيمة الضريبة
    is_tax_inclusive = db.Column(db.Boolean, default=False)  # هل السعر شامل الضريبة
    
    # حقول الدفع المتقدمة
    card_number_last_digits = db.Column(db.String(4), nullable=True)
    card_holder_name = db.Column(db.String(100), nullable=True)
    
    # حقول التأمين المتقدمة
    insurance_policy_number = db.Column(db.String(100), nullable=True)
    insurance_coverage_percentage = db.Column(db.Numeric(5, 2), nullable=True)  # نسبة التغطية (0-100)
    insurance_amount = db.Column(db.Numeric(12, 2), default=0, nullable=True)  # مبلغ التأمين
    patient_share = db.Column(db.Numeric(12, 2), default=0, nullable=True)  # حصة المريض
    
    # حقول الدفع القسري
    force_payment_reason = db.Column(db.Text, nullable=True)
    force_payment_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    force_payment_approved_at = db.Column(db.DateTime, nullable=True)
    
    # حقول الإيصال المتقدمة
    receipt_printed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receipt_printed_at = db.Column(db.DateTime, nullable=True)

    # حقول مالية إضافية لدعم GatekeeperService
    financial_locked = db.Column(db.Boolean, default=False)
    liability_acknowledged_at = db.Column(db.DateTime, nullable=True)
    financial_completed_at = db.Column(db.DateTime, nullable=True)
    gl_posted_at = db.Column(db.DateTime, nullable=True)
    archive_status = db.Column(db.String(20), default='ACTIVE')

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        Index('idx_visit_doctor_status', 'doctor_id', 'status'),
        Index('idx_visit_department_status', 'department_id', 'status'),
        Index('idx_visit_patient_created', 'patient_id', 'created_at'),
        Index('idx_visit_payment_method', 'payment_method'),
    )

    patient = db.relationship('Patient', back_populates='visits', lazy='selectin')
    department = db.relationship('Department', back_populates='visits', lazy='selectin')
    doctor = db.relationship('User', back_populates='doctor_visits', foreign_keys=[doctor_id], lazy='selectin')
    insurance_company = db.relationship('InsuranceCompany', foreign_keys=[insurance_company_id], lazy='select')

    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    completer = db.relationship('User', foreign_keys=[completed_by], lazy='select')
    archiver = db.relationship('User', foreign_keys=[archived_by], lazy='select')
    force_payment_approver = db.relationship('User', foreign_keys=[force_payment_approved_by], lazy='select')
    receipt_printer = db.relationship('User', foreign_keys=[receipt_printed_by], lazy='select')

    invoices = db.relationship(
        'Invoice',
        back_populates='visit',
        lazy='selectin',
        passive_deletes=True
    )
    lab_requests = db.relationship(
        'LabRequest',
        back_populates='visit',
        lazy='selectin',
        passive_deletes=True
    )
    radiology_requests = db.relationship(
        'RadiologyRequest',
        back_populates='visit',
        lazy='selectin',
        passive_deletes=True
    )


    @property
    def remaining_amount(self):
        from decimal import Decimal
        """حساب المبلغ المتبقي"""
        return Decimal(str(self.total_amount or 0)) - Decimal(str(self.paid_amount or 0))
    
    @property
    def is_fully_paid(self):
        """هل تم الدفع بالكامل"""
        return self.remaining_amount <= 0
    
    @property
    def payment_status_display(self):
        """عرض حالة الدفع بالعربية"""
        status_map = {
            'PENDING': 'معلق',
            'PAID': 'مدفوع',
            'PARTIAL': 'جزئي',
            'DEBT': 'دين'
        }
        return status_map.get(self.payment_status, self.payment_status)
    
    @property
    def visit_type_display(self):
        """عرض نوع الزيارة بالعربية"""
        type_map = {
            'REGULAR': 'عادية',
            'FOLLOW_UP': 'متابعة',
            'CONSULTATION': 'استشارة',
            'EMERGENCY': 'طوارئ'
        }
        return type_map.get(self.visit_type, self.visit_type)

    @property
    def visit_id_number(self):
        return self.visit_number or self.id

    def get_status_display(self):
        status_map = {
            'OPEN': 'مفتوحة',
            'IN_PROGRESS': 'قيد التنفيذ',
            'COMPLETED': 'مكتملة',
            'ARCHIVED': 'مؤرشفة',
            'READY': 'جاهز',
            'PENDING': 'في الانتظار'
        }
        return status_map.get(self.status, self.status)
    
    def can_be_archived(self):
        """هل يمكن أرشفة الزيارة"""
        if self.status != 'COMPLETED':
            return False, "الزيارة غير مكتملة"
        
        if self.payment_status == 'PENDING' and not self.is_force_payment:
            return False, "الدفع غير مكتمل"
        
        if self.is_force_payment and not self.force_payment_approved_by:
            return False, "الدفع القسري يحتاج موافقة"
        
        return True, "جاهز للأرشفة"
    
    def calculate_insurance_amounts(self):
        """حساب مبالغ التأمين تلقائياً"""
        if str(self.payment_method or '').lower() == 'insurance' and self.insurance_coverage_percentage:
            coverage = Decimal(str(self.insurance_coverage_percentage)) / Decimal('100')
            total = Decimal(str(self.total_amount or 0))
            self.insurance_amount = total * coverage
            self.patient_share = total * (Decimal('1') - coverage)
    
    def __repr__(self) -> str:
        return f"<Visit #{self.visit_number or self.id} patient={self.patient_id}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "department_id": self.department_id,
            "doctor_id": self.doctor_id,
            "visit_number": self.visit_number,
            "status": self.status,
            "payment_status": self.payment_status,
            "total_amount": str(Decimal(str(self.total_amount or 0)).quantize(Decimal('0.01'))),
            "paid_amount": str(Decimal(str(self.paid_amount or 0)).quantize(Decimal('0.01'))),
            "currency": self.currency,
            "visit_type": self.visit_type,
            "visit_date": self.visit_date.isoformat() if self.visit_date else None,
            "visit_time": self.visit_time.isoformat() if self.visit_time else None,
            "payment_method": self.payment_method,
            "insurance_provider": self.insurance_provider,
            "insurance_company_id": self.insurance_company_id,
            "is_emergency": self.is_emergency,
            "is_force_payment": self.is_force_payment,
            "insurance_amount": str(Decimal(str(self.insurance_amount or 0)).quantize(Decimal('0.01'))) if self.insurance_amount is not None else None,
            "patient_share": str(Decimal(str(self.patient_share or 0)).quantize(Decimal('0.01'))) if self.patient_share is not None else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }
