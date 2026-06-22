"""
المدفوعات - Payment (مرتبطة بالفواتير/الزيارات)
نسخة محسّنة مع دعم كامل لسيناريوهات الدفع
"""
from datetime import datetime
from sqlalchemy import CheckConstraint, Index
from app_factory import db
from app.shared.mixins import TenantMixin
from datetime import datetime, timezone


class PaymentMethod:
    """طرق الدفع المتاحة"""
    CASH = "CASH"
    CARD = "CARD"
    WIRE = "WIRE"
    INSURANCE = "INSURANCE"
    FORCE = "FORCE"


class PaymentStatus:
    """حالات الدفع"""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PAID = "PAID"
    PARTIAL = "PARTIAL"
    DEBT = "DEBT"
    EMERGENCY_DEBT = "EMERGENCY_DEBT"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class Payment(TenantMixin, db.Model):
    """نموذج المدفوعات - يسجل كل عملية دفع"""
    __tablename__ = 'payments'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    
    # الارتباطات
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # معلومات الدفع الأساسية
    method = db.Column(db.String(16), default=PaymentMethod.CASH, nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    currency = db.Column(db.String(8), default='ILS', nullable=False)
    status = db.Column(db.String(16), default=PaymentStatus.CONFIRMED, nullable=False, index=True)

    # P3-001: Idempotency support. `operation_type` scopes the key (e.g. 'payment',
    # 'refund'). Partial unique index below only enforces uniqueness when the key
    # is not NULL, allowing older rows without keys to coexist.
    idempotency_key = db.Column(db.String(64), nullable=True, index=True)
    operation_type = db.Column(db.String(32), nullable=True, index=True)

    # مرجع خارجي (رقم قسيمة/تحويل/معاملة بطاقة)
    reference = db.Column(db.String(64), nullable=True, index=True)
    
    # رقم الإيصال
    receipt_number = db.Column(db.String(50), nullable=True, unique=True)
    is_provisional = db.Column(db.Boolean, default=False, index=True)
    provisional_reason = db.Column(db.Text, nullable=True)
    
    # ملاحظات
    notes = db.Column(db.Text, nullable=True)
    
    # من استلم الدفع
    received_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # للإلغاء/الاسترجاع
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)
    
    # التواريخ
    payment_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("amount >= 0", name='chk_payment_amount_non_negative'),
        Index('idx_payment_patient_date', 'patient_id', 'payment_date'),
        Index('idx_payment_visit_date', 'visit_id', 'payment_date'),
        Index('idx_payment_invoice_created', 'invoice_id', 'created_at'),
        Index('idx_payment_status', 'status'),
        Index('idx_payment_method', 'method'),
        Index('idx_payment_idempotency', 'tenant_id', 'operation_type', 'idempotency_key', unique=True, postgresql_where=db.text("idempotency_key IS NOT NULL")),
    )

    # العلاقات
    patient = db.relationship('Patient', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    invoice = db.relationship('Invoice', lazy='selectin')
    receiver = db.relationship('User', foreign_keys=[received_by], lazy='selectin')
    canceller = db.relationship('User', foreign_keys=[cancelled_by], lazy='selectin')

    @property
    def is_cancelled(self):
        """هل تم إلغاء الدفع"""
        return self.status == PaymentStatus.CANCELLED
    
    @property
    def is_confirmed(self):
        """هل تم تأكيد الدفع"""
        return self.status == PaymentStatus.CONFIRMED
    
    @property
    def method_display(self):
        """عرض طريقة الدفع بالعربية"""
        method_map = {
            'CASH': 'نقدي',
            'CARD': 'بطاقة',
            'WIRE': 'تحويل',
            'INSURANCE': 'تأمين',
            'FORCE': 'قسري'
        }
        return method_map.get(self.method, self.method)
    
    @property
    def status_display(self):
        """عرض حالة الدفع بالعربية"""
        status_map = {
            'PENDING': 'معلق',
            'CONFIRMED': 'مؤكد',
            'CANCELLED': 'ملغي',
            'REFUNDED': 'مسترجع'
        }
        return status_map.get(self.status, self.status)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "visit_id": self.visit_id,
            "invoice_id": self.invoice_id,
            "method": self.method,
            "amount": float(self.amount or 0),
            "currency": self.currency,
            "status": self.status,
            "reference": self.reference,
            "receipt_number": self.receipt_number,
            "is_provisional": self.is_provisional,
            "provisional_reason": self.provisional_reason,
            "notes": self.notes,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def can_be_cancelled(self):
        """هل يمكن إلغاء الدفع"""
        if self.status == PaymentStatus.CANCELLED:
            return False, "الدفع ملغي مسبقاً"
        
        if self.status == PaymentStatus.REFUNDED:
            return False, "الدفع مسترجع"
        
        # يمكن إلغاء الدفع خلال 24 ساعة
        from datetime import timedelta, timezone
        now = datetime.now(timezone.utc)
        created = self.created_at if self.created_at else now
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created) > timedelta(hours=24):
            return False, "تجاوز وقت الإلغاء (24 ساعة)"
        
        return True, "يمكن الإلغاء"
    
    def cancel(self, user_id, reason):
        """إلغاء الدفع"""
        can_cancel, message = self.can_be_cancelled()
        if not can_cancel:
            return False, message
        
        self.status = PaymentStatus.CANCELLED
        self.cancelled_by = user_id
        from datetime import timezone
        self.cancelled_at = datetime.now(timezone.utc)
        self.cancellation_reason = reason
        
        return True, "تم الإلغاء بنجاح"

    def __repr__(self) -> str:
        return f"<Payment #{self.id} {self.method} {self.amount} {self.currency}>"
