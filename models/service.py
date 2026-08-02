"""
مرجع الخدمات الطبية - ServiceMaster
"""

from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db


class ServiceMaster(TenantMixin, db.Model):
    __tablename__ = 'service_master'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    name_ar = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(
        db.String(50), nullable=False, default='general'
    )  # doctor, lab, radiology, general
    department_id = db.Column(
        db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True
    )

    # الأسعار
    base_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    emergency_price = db.Column(db.Numeric(12, 2), nullable=True)
    insurance_price = db.Column(db.Numeric(12, 2), nullable=True)
    currency = db.Column(db.String(10), default='شيكل', nullable=False)
    duration = db.Column(db.Integer, nullable=True)
    max_daily = db.Column(db.Integer, nullable=True)
    is_required = db.Column(db.Boolean, default=False, nullable=True)

    is_active = db.Column(db.Boolean, default=True, index=True)

    # Ticket 6: custom service lifecycle fields
    is_custom = db.Column(db.Boolean, default=False, nullable=True, index=True)
    approved_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    approved_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    department = db.relationship('Department', lazy='selectin')
    pricing_management = db.relationship('PricingManagement', back_populates='service')
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    def __repr__(self) -> str:
        return f'<ServiceMaster {self.code}>'
