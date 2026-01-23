"""
نموذج إدارة التسعير - Pricing Management Model
Medical System Pricing Management Model
"""

from datetime import datetime, timezone
from app_factory import db
from decimal import Decimal, ROUND_HALF_UP
import json

class PricingManagement(db.Model):
    """نموذج إدارة التسعير"""
    
    __tablename__ = 'pricing_management'
    
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service_master.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # التسعير الأساسي
    base_price = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default='ILS')
    
    # التسعير المتخصص
    emergency_price = db.Column(db.Numeric(12, 2), nullable=True)
    insurance_price = db.Column(db.Numeric(12, 2), nullable=True)
    private_price = db.Column(db.Numeric(12, 2), nullable=True)
    
    # الخصومات
    discount_percentage = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Numeric(12, 2), default=0.0)
    
    # الضرائب
    tax_percentage = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Numeric(12, 2), default=0.0)
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    effective_from = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    effective_to = db.Column(db.DateTime, nullable=True)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # العلاقات
    service = db.relationship('ServiceMaster', backref='pricing_management')
    department = db.relationship('Department', backref='pricing_management')
    creator = db.relationship('User', backref='created_pricing')
    
    def __repr__(self):
        return f'<PricingManagement {self.service.name if self.service else "Unknown"} - {self.base_price} {self.currency}>'
    
    def get_final_price(self, price_type='base'):
        """حساب السعر النهائي"""
        if price_type == 'emergency' and self.emergency_price:
            price = self.emergency_price
        elif price_type == 'insurance' and self.insurance_price:
            price = self.insurance_price
        elif price_type == 'private' and self.private_price:
            price = self.private_price
        else:
            price = self.base_price
        
        # تطبيق الخصم
        price = Decimal(price)
        if self.discount_percentage and self.discount_percentage > 0:
            price = price * (Decimal(1) - (Decimal(str(self.discount_percentage)) / Decimal(100)))
        elif self.discount_amount and self.discount_amount > 0:
            price = price - Decimal(self.discount_amount)
        
        # تطبيق الضريبة
        if self.tax_percentage and self.tax_percentage > 0:
            price = price * (Decimal(1) + (Decimal(str(self.tax_percentage)) / Decimal(100)))
        elif self.tax_amount and self.tax_amount > 0:
            price = price + Decimal(self.tax_amount)
        
        return price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'service_id': self.service_id,
            'department_id': self.department_id,
            'base_price': self.base_price,
            'currency': self.currency,
            'emergency_price': self.emergency_price,
            'insurance_price': self.insurance_price,
            'private_price': self.private_price,
            'discount_percentage': self.discount_percentage,
            'discount_amount': self.discount_amount,
            'tax_percentage': self.tax_percentage,
            'tax_amount': self.tax_amount,
            'is_active': self.is_active,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }

class PricingRule(db.Model):
    """نموذج قواعد التسعير"""
    
    __tablename__ = 'pricing_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # شروط القاعدة
    condition_type = db.Column(db.String(50), nullable=False)  # patient_age, patient_type, visit_type, etc.
    condition_value = db.Column(db.String(100), nullable=False)
    condition_operator = db.Column(db.String(20), default='equals')  # equals, greater_than, less_than, contains
    
    # تأثير القاعدة
    price_adjustment_type = db.Column(db.String(20), default='percentage')  # percentage, fixed_amount
    price_adjustment_value = db.Column(db.Numeric(12, 2), nullable=False)
    
    # الأولوية
    priority = db.Column(db.Integer, default=1)
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # العلاقات
    creator = db.relationship('User', backref='created_pricing_rules')
    
    def __repr__(self):
        return f'<PricingRule {self.name}>'
    
    def applies_to(self, **kwargs):
        """التحقق من تطبيق القاعدة"""
        if self.condition_type in kwargs:
            value = kwargs[self.condition_type]
            condition_value = self.condition_value
            
            if self.condition_operator == 'equals':
                return str(value) == str(condition_value)
            elif self.condition_operator == 'greater_than':
                return float(value) > float(condition_value)
            elif self.condition_operator == 'less_than':
                return float(value) < float(condition_value)
            elif self.condition_operator == 'contains':
                return str(condition_value).lower() in str(value).lower()
        
        return False
    
    def apply_to_price(self, base_price):
        """تطبيق القاعدة على السعر"""
        if self.price_adjustment_type == 'percentage':
            return Decimal(base_price) * (Decimal(1) + (Decimal(self.price_adjustment_value) / Decimal(100)))
        else:
            return Decimal(base_price) + Decimal(self.price_adjustment_value)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'condition_type': self.condition_type,
            'condition_value': self.condition_value,
            'condition_operator': self.condition_operator,
            'price_adjustment_type': self.price_adjustment_type,
            'price_adjustment_value': self.price_adjustment_value,
            'priority': self.priority,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }
