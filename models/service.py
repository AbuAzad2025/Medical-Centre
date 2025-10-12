"""
مرجع الخدمات الطبية - ServiceMaster
"""
from datetime import datetime
from sqlalchemy import Index
from app_factory import db


class ServiceMaster(db.Model):
    __tablename__ = 'service_master'

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
    
    is_active = db.Column(db.Boolean, default=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    department = db.relationship('Department', lazy='select')

    def __repr__(self) -> str:
        return f"<ServiceMaster {self.code}>"