"""
نموذج سند القبض - Receipt Model
Medical System Receipt Model
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db
import qrcode
import io
import base64

class Receipt(db.Model):
    """نموذج سند القبض"""
    
    __tablename__ = 'receipts'
    
    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False)  # رقم سند القبض
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    
    # تفاصيل الدفع
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)  # المبلغ الإجمالي
    paid_amount = db.Column(db.Numeric(12, 2), nullable=False)  # المبلغ المدفوع
    remaining_amount = db.Column(db.Numeric(12, 2), default=0.0)  # المبلغ المتبقي
    payment_method = db.Column(db.String(50), nullable=False)  # طريقة الدفع
    payment_status = db.Column(db.String(50), default='PAID')  # حالة الدفع
    
    # تفاصيل التأمين
    insurance_type = db.Column(db.String(100), nullable=True)  # نوع التأمين
    insurance_coverage = db.Column(db.Numeric(5, 2), default=0.0)  # نسبة التغطية
    insurance_amount = db.Column(db.Numeric(12, 2), default=0.0)  # مبلغ التأمين
    patient_share = db.Column(db.Numeric(12, 2), default=0.0)  # حصة المريض
    
    # تفاصيل الدين (إن وجد)
    is_debt = db.Column(db.Boolean, default=False)  # هل هو دين
    debt_reason = db.Column(db.Text, nullable=True)  # سبب الدين

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name='chk_receipt_total_non_negative'),
        CheckConstraint("paid_amount >= 0", name='chk_receipt_paid_non_negative'),
        CheckConstraint("remaining_amount >= 0", name='chk_receipt_remaining_non_negative'),
        CheckConstraint("insurance_coverage >= 0 AND insurance_coverage <= 100", name='chk_receipt_coverage_percent'),
    )
    debt_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من وافق على الدين
    debt_approved_at = db.Column(db.DateTime, nullable=True)  # وقت الموافقة
    
    # تفاصيل الطباعة
    is_printed = db.Column(db.Boolean, default=False)  # هل تم طباعته
    printed_at = db.Column(db.DateTime, nullable=True)  # وقت الطباعة
    printed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # من طبع السند
    
    # QR Code
    qr_code = db.Column(db.Text, nullable=True)  # QR Code كـ base64
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name='chk_receipt_total_amount'),
        CheckConstraint("paid_amount >= 0", name='chk_receipt_paid_amount'),
        CheckConstraint("remaining_amount >= 0", name='chk_receipt_remaining_amount'),
        CheckConstraint("payment_method IN ('cash', 'card', 'visa', 'mada', 'debt')", name='chk_receipt_payment_method'),
        CheckConstraint("payment_status IN ('PAID', 'PARTIAL', 'DEBT', 'EMERGENCY_DEBT')", name='chk_receipt_payment_status'),
        CheckConstraint("insurance_coverage >= 0 AND insurance_coverage <= 100", name='chk_receipt_insurance_coverage'),
        CheckConstraint("insurance_amount >= 0", name='chk_receipt_insurance_amount'),
        CheckConstraint("patient_share >= 0", name='chk_receipt_patient_share'),
        Index('idx_receipt_number', 'receipt_number'),
        Index('idx_receipt_visit', 'visit_id'),
        Index('idx_receipt_patient', 'patient_id'),
        Index('idx_receipt_created', 'created_at'),
        Index('idx_receipt_printed', 'is_printed'),
    )
    
    # العلاقات
    visit = db.relationship('Visit', foreign_keys=[visit_id])
    patient = db.relationship('Patient', foreign_keys=[patient_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    debt_approver = db.relationship('User', foreign_keys=[debt_approved_by])
    printer = db.relationship('User', foreign_keys=[printed_by])
    
    def __repr__(self):
        return f'<Receipt {self.receipt_number}>'
    
    def generate_receipt_number(self):
        """توليد رقم سند القبض"""
        if not self.receipt_number:
            # تنسيق: RCP-YYYYMMDD-XXXX
            date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
            # البحث عن آخر رقم لهذا اليوم
            last_receipt = Receipt.query.filter(
                Receipt.receipt_number.like(f'RCP-{date_str}-%')
            ).order_by(Receipt.id.desc()).first()
            
            if last_receipt:
                last_number = int(last_receipt.receipt_number.split('-')[-1])
                new_number = last_number + 1
            else:
                new_number = 1
            
            self.receipt_number = f'RCP-{date_str}-{new_number:04d}'
    
    def generate_qr_code(self):
        """توليد QR Code للسند"""
        if not self.qr_code:
            # بيانات QR Code
            qr_data = {
                'receipt_number': self.receipt_number,
                'visit_id': self.visit_id,
                'patient_id': self.patient_id,
                'total_amount': self.total_amount,
                'paid_amount': self.paid_amount,
                'payment_method': self.payment_method,
                'created_at': self.created_at.isoformat()
            }
            
            # إنشاء QR Code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(str(qr_data))
            qr.make(fit=True)
            
            # تحويل إلى base64
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            self.qr_code = img_str
    
    def calculate_insurance_details(self, insurance_type=None, insurance_coverage=0):
        """حساب تفاصيل التأمين"""
        if insurance_type and insurance_coverage > 0:
            self.insurance_type = insurance_type
            self.insurance_coverage = insurance_coverage
            self.insurance_amount = self.total_amount * (insurance_coverage / 100)
            self.patient_share = self.total_amount - self.insurance_amount
        else:
            self.insurance_type = None
            self.insurance_coverage = 0
            self.insurance_amount = 0
            self.patient_share = self.total_amount
    
    def mark_as_printed(self, user_id):
        """تسجيل الطباعة"""
        self.is_printed = True
        self.printed_at = datetime.now(timezone.utc)
        self.printed_by = user_id
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'receipt_number': self.receipt_number,
            'visit_id': self.visit_id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'total_amount': self.total_amount,
            'paid_amount': self.paid_amount,
            'remaining_amount': self.remaining_amount,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'insurance_type': self.insurance_type,
            'insurance_coverage': self.insurance_coverage,
            'insurance_amount': self.insurance_amount,
            'patient_share': self.patient_share,
            'is_debt': self.is_debt,
            'debt_reason': self.debt_reason,
            'debt_approved_by': self.debt_approved_by,
            'debt_approver_name': self.debt_approver.full_name if self.debt_approver else None,
            'debt_approved_at': self.debt_approved_at.isoformat() if self.debt_approved_at else None,
            'is_printed': self.is_printed,
            'printed_at': self.printed_at.isoformat() if self.printed_at else None,
            'printed_by': self.printed_by,
            'printer_name': self.printer.full_name if self.printer else None,
            'qr_code': self.qr_code,
            'created_at': self.created_at.isoformat(),
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None
        }
    
    def get_print_data(self):
        """بيانات الطباعة"""
        return {
            'receipt_number': self.receipt_number,
            'patient_name': self.patient.full_name if self.patient else 'غير محدد',
            'visit_date': self.visit.visit_date.strftime('%Y-%m-%d') if self.visit else 'غير محدد',
            'total_amount': f"{self.total_amount:.2f}",
            'paid_amount': f"{self.paid_amount:.2f}",
            'payment_method': self.get_payment_method_display(),
            'insurance_info': self.get_insurance_display(),
            'debt_info': self.get_debt_display(),
            'qr_code': self.qr_code,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'creator_name': self.creator.full_name if self.creator else 'غير محدد'
        }
    
    def get_payment_method_display(self):
        """عرض طريقة الدفع"""
        method_names = {
            'cash': 'نقد',
            'card': 'بطاقة',
            'visa': 'فيزا',
            'mada': 'مدى',
            'debt': 'دين',
            'wire': 'تحويل',
            'insurance': 'تأمين',
            'force': 'قسري'
        }
        key = (self.payment_method or '').lower()
        return method_names.get(key, self.payment_method)
    
    def get_insurance_display(self):
        """عرض معلومات التأمين"""
        if self.insurance_type and self.insurance_coverage > 0:
            return f"{self.insurance_type} - {self.insurance_coverage}%"
        return "لا يوجد تأمين"
    
    def get_debt_display(self):
        """عرض معلومات الدين"""
        if self.is_debt:
            return f"دين - {self.debt_reason or 'بدون سبب محدد'}"
        return "مدفوع بالكامل"
