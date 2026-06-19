"""
نموذج الحجز عن بعد - Online Booking Models
Medical System Online Booking Models
"""

from datetime import datetime, date, timedelta, timezone
from app_factory import db
import secrets
import string

class OnlineBooking(db.Model):
    """نموذج الحجز عن بعد"""
    
    __tablename__ = 'online_bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    booking_reference = db.Column(db.String(20), unique=True, nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # معلومات المريض (للحجوزات الجديدة)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    national_id = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    
    # معلومات الحجز
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    visit_type = db.Column(db.String(20), default='first')  # first, follow_up, emergency
    symptoms = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # معلومات الدفع
    payment_amount = db.Column(db.Numeric(12, 2), nullable=False, default=10.0)
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, failed, refunded
    payment_reference = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.String(50), nullable=True)  # card, bank_transfer, etc.
    
    # حالة الحجز
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, completed, no_show
    confirmation_code = db.Column(db.String(10), nullable=True)
    
    # معلومات إضافية
    is_new_patient = db.Column(db.Boolean, default=True)
    insurance_company = db.Column(db.String(100), nullable=True)
    insurance_number = db.Column(db.String(50), nullable=True)
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    no_show_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='online_bookings')
    department = db.relationship('Department', back_populates='online_bookings')
    doctor = db.relationship('User', back_populates='online_bookings')
    payment_transactions = db.relationship('PaymentTransaction', back_populates='booking')

    
    def __repr__(self):
        return f'<OnlineBooking {self.booking_reference}>'
    
    @staticmethod
    def generate_booking_reference():
        """توليد رقم مرجع الحجز"""
        while True:
            alphabet = string.ascii_uppercase + string.digits
            ref = ''.join(secrets.choice(alphabet) for _ in range(8))
            if not OnlineBooking.query.filter_by(booking_reference=ref).first():
                return ref
    
    @staticmethod
    def generate_confirmation_code():
        """توليد رمز التأكيد"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    def get_status_display(self):
        """حالة الحجز للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'confirmed': 'مؤكد',
            'cancelled': 'ملغي',
            'completed': 'مكتمل',
            'no_show': 'لم يحضر'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'pending': 'warning',
            'confirmed': 'success',
            'cancelled': 'danger',
            'completed': 'info',
            'no_show': 'secondary'
        }
        return color_map.get(self.status, 'secondary')
    
    def get_payment_status_display(self):
        """حالة الدفع للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'paid': 'مدفوع',
            'failed': 'فشل',
            'refunded': 'مسترد'
        }
        return status_map.get(self.payment_status, 'غير محدد')
    
    def is_payment_required(self):
        """هل يتطلب الدفع"""
        return self.payment_status == 'pending'
    
    def is_payment_valid(self):
        """هل الدفع صالح"""
        return self.payment_status == 'paid'
    
    def can_be_cancelled(self):
        """هل يمكن إلغاؤه"""
        return self.status in ['pending', 'confirmed']
    
    def is_no_show_eligible(self):
        """هل مؤهل لعدم الحضور"""
        if self.status != 'confirmed':
            return False
        
        # إذا تجاوز 30 دقيقة من وقت الموعد
        appointment_datetime = datetime.combine(self.appointment_date, self.appointment_time)
        now = datetime.now()
        return now > appointment_datetime + timedelta(minutes=30)
    
    def get_full_name(self):
        """الاسم الكامل"""
        return f"{self.first_name} {self.last_name}"
    
    def get_appointment_datetime(self):
        """تاريخ ووقت الموعد"""
        return datetime.combine(self.appointment_date, self.appointment_time)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'booking_reference': self.booking_reference,
            'patient_id': self.patient_id,
            'patient_name': self.get_full_name(),
            'national_id': self.national_id,
            'phone': self.phone,
            'email': self.email,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'gender': self.gender,
            'department_id': self.department_id,
            'department_name': self.department.name_ar if self.department else None,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'appointment_date': self.appointment_date.isoformat(),
            'appointment_time': self.appointment_time.isoformat(),
            'appointment_datetime': self.get_appointment_datetime().isoformat(),
            'visit_type': self.visit_type,
            'symptoms': self.symptoms,
            'notes': self.notes,
            'payment_amount': self.payment_amount,
            'payment_status': self.payment_status,
            'payment_status_display': self.get_payment_status_display(),
            'payment_reference': self.payment_reference,
            'payment_method': self.payment_method,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'confirmation_code': self.confirmation_code,
            'is_new_patient': self.is_new_patient,
            'insurance_company': self.insurance_company,
            'insurance_number': self.insurance_number,
            'is_payment_required': self.is_payment_required(),
            'is_payment_valid': self.is_payment_valid(),
            'can_be_cancelled': self.can_be_cancelled(),
            'is_no_show_eligible': self.is_no_show_eligible(),
            'created_at': self.created_at.isoformat(),
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'no_show_at': self.no_show_at.isoformat() if self.no_show_at else None
        }

class PaymentTransaction(db.Model):
    """نموذج معاملة الدفع"""
    
    __tablename__ = 'online_booking_payment_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('online_bookings.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_reference = db.Column(db.String(100), unique=True, nullable=False)
    
    # معلومات الدفع
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), default='ILS')  # شيقل إسرائيلي
    payment_method = db.Column(db.String(50), nullable=False)
    payment_gateway = db.Column(db.String(50), nullable=True)
    
    # حالة المعاملة
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed, cancelled
    gateway_response = db.Column(db.Text, nullable=True)
    gateway_transaction_id = db.Column(db.String(100), nullable=True)
    
    # معلومات إضافية
    card_last_four = db.Column(db.String(4), nullable=True)
    card_type = db.Column(db.String(20), nullable=True)
    
    # تواريخ
    initiated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    booking = db.relationship('OnlineBooking', back_populates='payment_transactions')
    
    def __repr__(self):
        return f'<PaymentTransaction {self.transaction_reference}>'
    
    @staticmethod
    def generate_transaction_reference():
        """توليد رقم مرجع المعاملة"""
        while True:
            ref = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
            if not PaymentTransaction.query.filter_by(transaction_reference=ref).first():
                return ref
    
    def get_status_display(self):
        """حالة المعاملة للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'completed': 'مكتملة',
            'failed': 'فشلت',
            'cancelled': 'ملغية'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'pending': 'warning',
            'completed': 'success',
            'failed': 'danger',
            'cancelled': 'secondary'
        }
        return color_map.get(self.status, 'secondary')
    
    def is_successful(self):
        """هل نجحت المعاملة"""
        return self.status == 'completed'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'transaction_reference': self.transaction_reference,
            'amount': self.amount,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_gateway': self.payment_gateway,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'gateway_response': self.gateway_response,
            'gateway_transaction_id': self.gateway_transaction_id,
            'card_last_four': self.card_last_four,
            'card_type': self.card_type,
            'is_successful': self.is_successful(),
            'initiated_at': self.initiated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None
        }
