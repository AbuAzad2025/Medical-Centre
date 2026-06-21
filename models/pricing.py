"""
نماذج الأسعار والخدمات - Pricing Models
Medical System Pricing Models
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from decimal import Decimal, ROUND_HALF_UP
from app_factory import db
from app.shared.mixins import TenantMixin

class ServicePrice(TenantMixin, db.Model):
    """نموذج أسعار الخدمات"""
    
    __tablename__ = 'service_prices'
    
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(200), nullable=False)
    service_type = db.Column(db.String(100), nullable=False)  # consultation, lab_test, radiology_scan, medication, procedure
    service_code = db.Column(db.String(50), nullable=True)  # كود الخدمة
    
    # الأسعار
    base_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    insurance_price = db.Column(db.Numeric(12, 2), nullable=True)
    cash_price = db.Column(db.Numeric(12, 2), nullable=True)
    vip_price = db.Column(db.Numeric(12, 2), nullable=True)
    
    # معلومات إضافية
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    requires_doctor = db.Column(db.Boolean, default=False)
    requires_department = db.Column(db.Boolean, default=False)
    
    # التواريخ
    effective_from = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    effective_to = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("base_price >= 0", name='chk_service_base_price'),
        CheckConstraint("insurance_price >= 0", name='chk_service_insurance_price'),
        CheckConstraint("cash_price >= 0", name='chk_service_cash_price'),
        CheckConstraint("vip_price >= 0", name='chk_service_vip_price'),
        CheckConstraint("service_type IN ('consultation', 'lab_test', 'radiology_scan', 'medication', 'procedure', 'emergency', 'other')", name='chk_service_type'),
        Index('idx_service_name', 'service_name'),
        Index('idx_service_type', 'service_type'),
        Index('idx_service_code', 'service_code'),
        Index('idx_service_active', 'is_active'),
        Index('idx_service_effective', 'effective_from', 'effective_to'),
    )
    
    def __repr__(self):
        return f'<ServicePrice {self.service_name}>'
    
    def get_price(self, payment_method='cash'):
        """الحصول على السعر حسب طريقة الدفع"""
        if payment_method == 'insurance' and self.insurance_price:
            return self.insurance_price
        elif payment_method == 'cash' and self.cash_price:
            return self.cash_price
        elif payment_method == 'vip' and self.vip_price:
            return self.vip_price
        else:
            return self.base_price
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'service_name': self.service_name,
            'service_type': self.service_type,
            'service_code': self.service_code,
            'base_price': self.base_price,
            'insurance_price': self.insurance_price,
            'cash_price': self.cash_price,
            'vip_price': self.vip_price,
            'description': self.description,
            'is_active': self.is_active,
            'requires_doctor': self.requires_doctor,
            'requires_department': self.requires_department,
            'effective_from': self.effective_from.isoformat(),
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class DoctorPricing(TenantMixin, db.Model):
    """نموذج أسعار الأطباء"""
    
    __tablename__ = 'doctor_pricing'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # الأسعار
    consultation_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    follow_up_price = db.Column(db.Numeric(12, 2), nullable=True)
    emergency_price = db.Column(db.Numeric(12, 2), nullable=True)
    vip_price = db.Column(db.Numeric(12, 2), nullable=True)
    
    # معلومات إضافية
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    
    # التواريخ
    effective_from = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    effective_to = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("consultation_price >= 0", name='chk_doctor_consultation_price'),
        CheckConstraint("follow_up_price >= 0", name='chk_doctor_follow_up_price'),
        CheckConstraint("emergency_price >= 0", name='chk_doctor_emergency_price'),
        CheckConstraint("vip_price >= 0", name='chk_doctor_vip_price'),
        Index('idx_doctor_pricing_doctor', 'doctor_id'),
        Index('idx_doctor_pricing_department', 'department_id'),
        Index('idx_doctor_pricing_active', 'is_active'),
        Index('idx_doctor_pricing_effective', 'effective_from', 'effective_to'),
    )
    
    # العلاقات
    doctor = db.relationship('User', foreign_keys=[doctor_id], back_populates='pricing', lazy='selectin')
    department = db.relationship('Department', back_populates='doctor_pricing', lazy='selectin')
    
    def __repr__(self):
        return f'<DoctorPricing {self.doctor.full_name if self.doctor else "Unknown"}>'
    
    def get_price(self, visit_type='consultation', payment_method='cash'):
        """الحصول على السعر حسب نوع الزيارة وطريقة الدفع"""
        visit_type = (visit_type or 'consultation').lower()
        if visit_type == 'consultation':
            base_price = self.consultation_price
        elif visit_type == 'follow_up':
            base_price = self.follow_up_price or self.consultation_price
        elif visit_type == 'emergency':
            base_price = self.emergency_price or self.consultation_price
        else:
            base_price = self.consultation_price
        
        if payment_method == 'vip' and self.vip_price:
            return self.vip_price
        else:
            return base_price
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'department_id': self.department_id,
            'department_name': self.department.name_ar if self.department else None,
            'consultation_price': self.consultation_price,
            'follow_up_price': self.follow_up_price,
            'emergency_price': self.emergency_price,
            'vip_price': self.vip_price,
            'is_active': self.is_active,
            'notes': self.notes,
            'effective_from': self.effective_from.isoformat(),
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class InsuranceProvider(TenantMixin, db.Model):
    """نموذج شركات التأمين"""
    
    __tablename__ = 'insurance_providers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=True)
    
    # معلومات الشركة
    contact_person = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.Text, nullable=True)
    
    # معلومات التأمين
    coverage_percentage = db.Column(db.Float, default=100.0)
    max_coverage_amount = db.Column(db.Numeric(12, 2), nullable=True)
    requires_authorization = db.Column(db.Boolean, default=False)  # يتطلب ترخيص مسبق
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("coverage_percentage >= 0 AND coverage_percentage <= 100", name='chk_coverage_percentage'),
        CheckConstraint("max_coverage_amount >= 0", name='chk_max_coverage_amount'),
        Index('idx_insurance_name', 'name'),
        Index('idx_insurance_name_ar', 'name_ar'),
        Index('idx_insurance_code', 'code'),
        Index('idx_insurance_active', 'is_active'),
    )
    
    def __repr__(self):
        return f'<InsuranceProvider {self.name_ar}>'
    
    def calculate_coverage(self, amount):
        """حساب مبلغ التغطية"""
        amount_dec = Decimal(str(amount))
        coverage = amount_dec * (Decimal(str(self.coverage_percentage)) / Decimal(100))
        if self.max_coverage_amount and coverage > Decimal(self.max_coverage_amount):
            coverage = Decimal(self.max_coverage_amount)
        return coverage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'code': self.code,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'coverage_percentage': self.coverage_percentage,
            'max_coverage_amount': self.max_coverage_amount,
            'requires_authorization': self.requires_authorization,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class PricingCatalog(TenantMixin, db.Model):
    """نموذج كتالوج التسعير المركزي"""
    
    __tablename__ = 'pricing_catalog'
    
    id = db.Column(db.Integer, primary_key=True)
    service_type = db.Column(db.String(100), nullable=False)  # consultation, lab, radiology, medication
    service_name = db.Column(db.String(200), nullable=False)  # اسم الخدمة
    service_name_ar = db.Column(db.String(200), nullable=False)  # اسم الخدمة بالعربية
    base_price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    insurance_coverage = db.Column(db.Float, default=0.0)
    patient_share = db.Column(db.Numeric(12, 2), default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    is_temporary = db.Column(db.Boolean, default=False)  # خدمة مؤقتة من "أخرى"
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("base_price >= 0", name='chk_pricing_base_price'),
        CheckConstraint("insurance_coverage >= 0 AND insurance_coverage <= 100", name='chk_pricing_insurance_coverage'),
        CheckConstraint("patient_share >= 0", name='chk_pricing_patient_share'),
        CheckConstraint("service_type IN ('consultation', 'lab', 'radiology', 'medication', 'other')", name='chk_pricing_service_type'),
        Index('idx_pricing_service_type', 'service_type'),
        Index('idx_pricing_active', 'is_active'),
        Index('idx_pricing_temporary', 'is_temporary'),
    )
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<PricingCatalog {self.service_name_ar}>'
    
    def get_final_price(self, insurance_type=None):
        """الحصول على السعر النهائي حسب نوع التأمين"""
        if insurance_type == 'insurance' and self.insurance_coverage > 0:
            return self.patient_share
        return self.base_price
    
    def get_insurance_coverage_amount(self):
        """مبلغ التغطية التأمينية"""
        return (Decimal(self.base_price) * (Decimal(str(self.insurance_coverage)) / Decimal(100))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'service_type': self.service_type,
            'service_name': self.service_name,
            'service_name_ar': self.service_name_ar,
            'base_price': self.base_price,
            'insurance_coverage': self.insurance_coverage,
            'patient_share': self.patient_share,
            'is_active': self.is_active,
            'is_temporary': self.is_temporary,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class TemporaryService(TenantMixin, db.Model):
    """نموذج الخدمات المؤقتة"""
    
    __tablename__ = 'temporary_services'
    
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(200), nullable=False)
    service_name_ar = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("price >= 0", name='chk_temporary_service_price'),
        Index('idx_temporary_service_name', 'service_name'),
        Index('idx_temporary_service_active', 'is_active'),
    )
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<TemporaryService {self.service_name_ar}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'service_name': self.service_name,
            'service_name_ar': self.service_name_ar,
            'price': self.price,
            'description': self.description,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
