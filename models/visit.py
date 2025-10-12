"""
نموذج الزيارة - Visit (نسخة نهائية موحّدة)
"""
from datetime import datetime
from sqlalchemy import Index
from app_factory import db


class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
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
    payment_method = db.Column(db.String(20), default='cash')  # cash|visa|insurance|force
    insurance_provider = db.Column(db.String(100), nullable=True)
    is_emergency = db.Column(db.Boolean, default=False)
    is_force_payment = db.Column(db.Boolean, default=False)
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

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    archived_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        Index('idx_visit_doctor_status', 'doctor_id', 'status'),
        Index('idx_visit_department_status', 'department_id', 'status'),
        Index('idx_visit_patient_created', 'patient_id', 'created_at'),
    )

    patient = db.relationship('Patient', back_populates='visits', lazy='selectin')
    department = db.relationship('Department', back_populates='visits', lazy='selectin')
    doctor = db.relationship('User', back_populates='doctor_visits', foreign_keys=[doctor_id], lazy='selectin')

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

    @property
    def remaining_amount(self):
        """حساب المبلغ المتبقي"""
        return float(self.total_amount or 0) - float(self.paid_amount or 0)
    
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
        if self.payment_method == 'insurance' and self.insurance_coverage_percentage:
            coverage = float(self.insurance_coverage_percentage) / 100
            self.insurance_amount = float(self.total_amount or 0) * coverage
            self.patient_share = float(self.total_amount or 0) * (1 - coverage)
    
    def __repr__(self) -> str:
        return f"<Visit #{self.visit_number or self.id} patient={self.patient_id}>"