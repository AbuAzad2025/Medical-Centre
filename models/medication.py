"""
نموذج الدواء - Medication Model
Medical System Medication Model
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint, UniqueConstraint
from app_factory import db
from app.shared.mixins import TenantMixin

class Medication(TenantMixin, db.Model):
    """نموذج الدواء"""
    
    __tablename__ = 'medications'
    __tenant_migration__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    scientific_name = db.Column(db.String(200), nullable=False)
    trade_name = db.Column(db.String(200), nullable=False)
    generic_name = db.Column(db.String(200), nullable=True)
    dosage_form = db.Column(db.String(100), nullable=False)  # tablet, syrup, injection, etc.
    strength = db.Column(db.String(100), nullable=False)  # 500mg, 10ml, etc.
    manufacturer = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=0.0)
    category = db.Column(db.String(100), nullable=True)  # antibiotic, painkiller, etc.
    description = db.Column(db.Text, nullable=True)
    standard_instructions = db.Column(db.Text, nullable=True)
    side_effects = db.Column(db.Text, nullable=True)
    contraindications = db.Column(db.Text, nullable=True)
    drug_interactions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='active')  # active, inactive, discontinued
    stock_quantity = db.Column(db.Integer, default=0)
    minimum_stock = db.Column(db.Integer, default=10)
    expiry_date = db.Column(db.Date, nullable=True)
    batch_number = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("price >= 0", name='chk_medication_price'),
        CheckConstraint("stock_quantity >= 0", name='chk_medication_stock'),
        Index('idx_medication_trade_name', 'trade_name'),
        Index('idx_medication_generic_name', 'generic_name'),
        Index('idx_medication_active', 'is_active'),
        Index('idx_medication_name_search', 'generic_name', 'trade_name'),
    )
    
    # العلاقات
    prescription_items = db.relationship('PrescriptionItem', back_populates='medication', lazy='dynamic')
    emar_administrations = db.relationship('eMARAdministration', back_populates='medication')

    
    def __repr__(self):
        return f'<Medication {self.trade_name}>'
    
    def get_full_name(self):
        """الاسم الكامل للدواء"""
        return f"{self.trade_name} ({self.scientific_name})"
    
    def get_price_display(self):
        """سعر الدواء للعرض"""
        return f"{self.price:,.2f} ريال"
    
    def get_dosage_display(self):
        """جرعة الدواء للعرض"""
        return f"{self.strength} {self.dosage_form}"
    
    def is_low_stock(self):
        """التحقق من انخفاض المخزون"""
        return self.stock_quantity <= self.minimum_stock
    
    def is_out_of_stock(self):
        """التحقق من نفاد المخزون"""
        return self.stock_quantity <= 0
    
    def get_stock_status(self):
        """حالة المخزون"""
        if self.is_out_of_stock():
            return 'out_of_stock'
        elif self.is_low_stock():
            return 'low_stock'
        else:
            return 'in_stock'
    
    def get_stock_status_display(self):
        """حالة المخزون للعرض"""
        status_map = {
            'out_of_stock': 'نفد المخزون',
            'low_stock': 'مخزون منخفض',
            'in_stock': 'متوفر'
        }
        return status_map.get(self.get_stock_status(), 'غير محدد')
    
    def is_expired(self):
        """التحقق من انتهاء الصلاحية"""
        if not self.expiry_date:
            return False
        from datetime import date
        return self.expiry_date <= date.today()
    
    def is_expiring_soon(self, days=30):
        """التحقق من انتهاء الصلاحية قريباً"""
        if not self.expiry_date:
            return False
        from datetime import date, timedelta
        return self.expiry_date <= date.today() + timedelta(days=days)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'scientific_name': self.scientific_name,
            'trade_name': self.trade_name,
            'generic_name': self.generic_name,
            'full_name': self.get_full_name(),
            'dosage_form': self.dosage_form,
            'strength': self.strength,
            'dosage_display': self.get_dosage_display(),
            'manufacturer': self.manufacturer,
            'price': self.price,
            'price_display': self.get_price_display(),
            'category': self.category,
            'description': self.description,
            'standard_instructions': self.standard_instructions,
            'side_effects': self.side_effects,
            'contraindications': self.contraindications,
            'drug_interactions': self.drug_interactions,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @property
    def min_stock_level(self):
        return self.minimum_stock

    @min_stock_level.setter
    def min_stock_level(self, value):
        self.minimum_stock = int(value) if value is not None else self.minimum_stock

    @db.validates('stock_quantity')
    def validate_stock(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"الكمية لا يمكن أن تكون سالبة: {value}")
        return value

    @db.validates('price')
    def validate_price(self, key, value):
        if value is not None:
            from decimal import Decimal
            val = Decimal(str(value)) if not isinstance(value, Decimal) else value
            if val < 0:
                raise ValueError(f"السعر لا يمكن أن يكون سالباً: {value}")
        return value

class Prescription(TenantMixin, db.Model):
    """نموذج الروشيتا"""
    
    __tablename__ = 'prescriptions'
    __tenant_migration__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    prescription_number = db.Column(db.String(50), unique=True, nullable=False)
    diagnosis = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    total_cost = db.Column(db.Numeric(12, 2), default=0.0)
    status = db.Column(db.String(50), default='active')  # active, dispensed, cancelled
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("status IN ('active', 'dispensed', 'cancelled')", name='chk_prescription_status'),
        CheckConstraint("total_cost >= 0", name='chk_prescription_total_cost'),
        Index('idx_prescription_patient', 'patient_id'),
        Index('idx_prescription_doctor', 'doctor_id'),
        Index('idx_prescription_visit', 'visit_id'),
        Index('idx_prescription_status', 'status'),
        Index('idx_prescription_number', 'prescription_number'),
        Index('idx_prescription_patient_status', 'patient_id', 'status'),
    )
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='prescriptions')
    doctor = db.relationship('User', foreign_keys=[doctor_id], back_populates='prescriptions')
    visit = db.relationship('Visit', foreign_keys=[visit_id])
    items = db.relationship('PrescriptionItem', back_populates='prescription', lazy='dynamic', cascade='all, delete-orphan')
    dispense_logs = db.relationship('PrescriptionDispenseLog', back_populates='prescription', lazy='dynamic', cascade='all, delete-orphan')
    cds_alerts = db.relationship('CDSFiredAlert', back_populates='prescription')
    emar_administrations = db.relationship('eMARAdministration', back_populates='prescription')
    pharmacy_sales = db.relationship('PharmacySale', back_populates='prescription')



    
    def __repr__(self):
        return f'<Prescription {self.prescription_number}>'
    
    def get_status_display(self):
        """حالة الروشيتا للعرض"""
        status_map = {
            'active': 'نشط',
            'dispensed': 'تم الصرف',
            'cancelled': 'ملغي'
        }
        return status_map.get(self.status, self.status)
    
    def get_total_cost_display(self):
        """التكلفة الإجمالية للعرض"""
        return f"{self.total_cost:,.2f} ريال"
    
    def calculate_total_cost(self):
        """حساب التكلفة الإجمالية"""
        total = sum(item.total_price for item in self.items)
        self.total_cost = total
        return total
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'visit_id': self.visit_id,
            'prescription_number': self.prescription_number,
            'diagnosis': self.diagnosis,
            'notes': self.notes,
            'total_cost': self.total_cost,
            'total_cost_display': self.get_total_cost_display(),
            'status': self.status,
            'status_display': self.get_status_display(),
            'items_count': self.items.count(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class PrescriptionItem(TenantMixin, db.Model):
    """نموذج عنصر الروشيتا"""
    
    __tablename__ = 'prescription_items'
    __tenant_migration__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='RESTRICT'), nullable=False, index=True)
    dosage = db.Column(db.String(100), nullable=False)  # 1 tablet, 2 times daily
    quantity = db.Column(db.Integer, nullable=False, default=1)
    duration_days = db.Column(db.Integer, nullable=False, default=7)
    instructions = db.Column(db.Text, nullable=True)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("quantity > 0", name='chk_prescription_item_quantity'),
        CheckConstraint("unit_price >= 0", name='chk_prescription_item_unit_price'),
        CheckConstraint("total_price >= 0", name='chk_prescription_item_total_price'),
        Index('idx_prescription_item_prescription', 'prescription_id'),
        Index('idx_prescription_item_medication', 'medication_id'),
    )
    
    # العلاقات
    prescription = db.relationship('Prescription', back_populates='items')
    medication = db.relationship('Medication', back_populates='prescription_items')
    schedules = db.relationship('MedicationSchedule', back_populates='prescription_item')

    
    def __repr__(self):
        return f'<PrescriptionItem {self.medication.trade_name if self.medication else "Unknown"}>'
    
    def calculate_total_price(self):
        """حساب السعر الإجمالي"""
        self.total_price = self.unit_price * self.quantity
        return self.total_price
    
    def get_dosage_display(self):
        """جرعة الدواء للعرض"""
        return f"{self.dosage} لمدة {self.duration_days} أيام"
    
    def get_total_price_display(self):
        """السعر الإجمالي للعرض"""
        return f"{self.total_price:,.2f} ريال"
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'prescription_id': self.prescription_id,
            'medication_id': self.medication_id,
            'medication_name': self.medication.get_full_name() if self.medication else None,
            'dosage': self.dosage,
            'quantity': self.quantity,
            'duration_days': self.duration_days,
            'dosage_display': self.get_dosage_display(),
            'instructions': self.instructions,
            'unit_price': self.unit_price,
            'total_price': self.total_price,
            'total_price_display': self.get_total_price_display(),
            'created_at': self.created_at.isoformat()
        }

class PrescriptionDispenseLog(TenantMixin, db.Model):
    __tablename__ = 'prescription_dispense_logs'

    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    dispensed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    dispensed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)

    prescription = db.relationship('Prescription', back_populates='dispense_logs', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    dispenser = db.relationship('User', foreign_keys=[dispensed_by], lazy='selectin')

    def to_dict(self):
        return {
            'id': self.id,
            'prescription_id': self.prescription_id,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'dispensed_by': self.dispensed_by,
            'dispensed_at': self.dispensed_at.isoformat() if self.dispensed_at else None,
            'notes': self.notes
        }


class PharmacySale(TenantMixin, db.Model):
    """Standalone pharmacy sale (no visit required)."""
    __tablename__ = 'pharmacy_sales'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    sale_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='SET NULL'), nullable=True, index=True)
    doctor_name = db.Column(db.String(200), nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    total_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    payment_method = db.Column(db.String(20), default='cash', nullable=False, index=True)
    card_last_digits = db.Column(db.String(4), nullable=True)
    transaction_id = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(20), default='completed', index=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = db.relationship('Patient', back_populates='pharmacy_sales', lazy='selectin')
    prescription = db.relationship('Prescription', back_populates='pharmacy_sales', lazy='selectin')
    items = db.relationship('PharmacySaleItem', back_populates='sale', cascade='all, delete-orphan', lazy='selectin')


class PharmacySaleItem(TenantMixin, db.Model):
    """Item in a pharmacy sale."""
    __tablename__ = 'pharmacy_sale_items'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('pharmacy_sales.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='RESTRICT'), nullable=False, index=True)
    medication_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    batch_number = db.Column(db.String(50), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    sale = db.relationship('PharmacySale', back_populates='items', lazy='selectin')
    medication = db.relationship('Medication', lazy='selectin')


class PharmacyReturn(TenantMixin, db.Model):
    """Pharmacy return/refund."""
    __tablename__ = 'pharmacy_returns'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('pharmacy_sale_items.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='RESTRICT'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(200), nullable=False)
    refund_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    returned_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Supplier(TenantMixin, db.Model):
    """مورد الأدوية - Supplier"""
    __tablename__ = 'suppliers'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    address = db.Column(db.Text, nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    purchases = db.relationship('MedicationPurchase', back_populates='supplier', lazy='dynamic')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class MedicationPurchase(TenantMixin, db.Model):
    """شراء أدوية من مورد - Purchase with batch tracking"""
    __tablename__ = 'medication_purchases'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)
    batch_number = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    remaining_quantity = db.Column(db.Integer, nullable=False, default=0)
    purchase_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    selling_price = db.Column(db.Numeric(12, 2), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    invoice_number = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    supplier = db.relationship('Supplier', back_populates='purchases', lazy='selectin')
    medication = db.relationship('Medication', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    def __repr__(self):
        return f'<MedicationPurchase {self.batch_number} - {self.medication.trade_name if self.medication else "?"}>'
