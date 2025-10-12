"""
الفواتير - Invoice & InvoiceService (نسخة نهائية 1:* من الزيارة إلى الفواتير)
"""
from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    status = db.Column(db.String(20), default='DRAFT', index=True)  # DRAFT|ISSUED|PAID|VOID
    currency = db.Column(db.String(8), default='ILS', nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    paid_amount = db.Column(db.Numeric(12, 2), default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name='chk_invoice_total_non_negative'),
        CheckConstraint("paid_amount >= 0", name='chk_invoice_paid_non_negative'),
        Index('idx_invoice_status', 'status'),
    )

    visit = db.relationship('Visit', back_populates='invoices', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

    lines = db.relationship(
        'InvoiceService',
        back_populates='invoice',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Invoice #{self.invoice_number or self.id}>"


class InvoiceService(db.Model):
    __tablename__ = 'invoice_services'

    id = db.Column(db.Integer, primary_key=True)
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
    department = db.relationship('Department', lazy='select')
    visit = db.relationship('Visit', lazy='select')

    def __repr__(self) -> str:
        return f"<InvoiceService {self.service_code} x{self.quantity}>"