"""
مرجع الخدمات الطبية - ServiceMaster
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db
from app.shared.mixins import TenantMixin


class ServiceMaster(TenantMixin, db.Model):
    __tablename__ = 'service_master'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    name_ar = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False, default='general')  # doctor, lab, radiology, general
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # الأسعار
    base_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    emergency_price = db.Column(db.Numeric(12, 2), nullable=True)
    insurance_price = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(10), default='شيكل', nullable=False)
    duration = db.Column(db.Integer, nullable=True)
    max_daily = db.Column(db.Integer, nullable=True)
    is_required = db.Column(db.Boolean, default=False, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    department = db.relationship('Department', lazy='selectin')
    pricing_management = db.relationship('PricingManagement', back_populates='service')


    def __repr__(self) -> str:
        return f"<ServiceMaster {self.code}>"
