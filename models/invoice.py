"""
الفواتير - Invoice & InvoiceService (نسخة نهائية 1:* من الزيارة إلى الفواتير)
"""
from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    status = db.Column(db.String(20), default='DRAFT', index=True)  # DRAFT|ISSUED|PAID|VOID
    currency = db.Column(db.String(8), default='ILS', nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    paid_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    posted_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name='chk_invoice_total_non_negative'),
        CheckConstraint("paid_amount >= 0", name='chk_invoice_paid_non_negative'),
        Index('idx_invoice_status', 'status'),
        Index('idx_invoice_status_created', 'status', 'created_at'),
        Index('idx_invoice_visit_created', 'visit_id', 'created_at'),
        Index('idx_invoice_tenant_status', 'tenant_id', 'status'),
    )

    visit = db.relationship('Visit', back_populates='invoices', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    lines = db.relationship(
        'InvoiceService',
        back_populates='invoice',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Invoice #{self.invoice_number or self.id}>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "invoice_number": self.invoice_number,
            "visit_id": self.visit_id,
            "created_by": self.created_by,
            "status": self.status,
            "currency": self.currency,
            "total_amount": float(self.total_amount or 0),
            "paid_amount": float(self.paid_amount or 0),
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class InvoiceService(db.Model):
    __tablename__ = 'invoice_services'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)

    service_code = db.Column(db.String(50), nullable=False, index=True)
    service_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    total_price = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name='chk_line_qty_positive'),
        CheckConstraint("unit_price >= 0", name='chk_line_unit_price_non_negative'),
        CheckConstraint("total_price >= 0", name='chk_line_total_price_non_negative'),
    )

    invoice = db.relationship('Invoice', back_populates='lines', lazy='selectin')
    department = db.relationship('Department', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')

    def __repr__(self) -> str:
        return f"<InvoiceService {self.service_code} x{self.quantity}>"
