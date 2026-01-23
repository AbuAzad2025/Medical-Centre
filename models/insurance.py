"""
التأمين - شركة ومطالبات (نسخة نهائية مبسطة)
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db


class InsuranceCompany(db.Model):
    __tablename__ = 'insurance_companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    name_ar = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    claims = db.relationship('InsuranceClaim', back_populates='company', lazy='selectin', passive_deletes=True)

    def __repr__(self) -> str:
        return f"<InsuranceCompany {self.name}>"


class InsuranceClaim(db.Model):
    __tablename__ = 'insurance_claims'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('insurance_companies.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True, index=True)

    claim_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    status = db.Column(db.String(20), default='DRAFT', index=True)  # DRAFT|SUBMITTED|APPROVED|REJECTED|PAID
    total_claim = db.Column(db.Numeric(12, 2), default=0)
    approved_amount = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_insurance_claim_company_status', 'company_id', 'status'),
        Index('idx_insurance_claim_status', 'status'),
        Index('idx_insurance_claim_created', 'created_at'),
    )

    company = db.relationship('InsuranceCompany', back_populates='claims', lazy='select')
    visit = db.relationship('Visit', lazy='select')
    invoice = db.relationship('Invoice', lazy='select')

    def __repr__(self) -> str:
        return f"<InsuranceClaim #{self.claim_number or self.id}>"
