"""
التأمين - شركة ومطالبات (نسخة نهائية مبسطة)
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Index

from app.shared.mixins import TenantMixin
from app_factory import db


class InsuranceCompany(TenantMixin, db.Model):
    __tablename__ = 'insurance_companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    name_ar = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

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

    claims = db.relationship(
        'InsuranceClaim', back_populates='company', lazy='selectin', passive_deletes=True
    )

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_insurance_company_tenant_name'),
    )

    def __repr__(self) -> str:
        return f'<InsuranceCompany {self.name}>'


class InsuranceClaim(TenantMixin, db.Model):
    __tablename__ = 'insurance_claims'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(
        db.Integer,
        db.ForeignKey('insurance_companies.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    visit_id = db.Column(
        db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True
    )
    invoice_id = db.Column(
        db.Integer, db.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True, index=True
    )

    claim_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    status = db.Column(
        db.String(20), default='DRAFT', index=True
    )  # DRAFT|SUBMITTED|UNDER_REVIEW|APPROVED|PARTIALLY_APPROVED|REJECTED|SETTLED
    total_claim = db.Column(db.Numeric(12, 2), default=0)
    approved_amount = db.Column(db.Numeric(12, 2), default=0)
    claim_date = db.Column(db.DateTime, nullable=True, index=True)
    patient_share_amount = db.Column(db.Numeric(12, 2), default=0)
    insurance_share_amount = db.Column(db.Numeric(12, 2), default=0)
    adjudication_notes = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

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

    __table_args__ = (
        Index('idx_insurance_claim_company_status', 'company_id', 'status'),
        Index('idx_insurance_claim_status', 'status'),
        Index('idx_insurance_claim_created', 'created_at'),
    )

    company = db.relationship('InsuranceCompany', back_populates='claims', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    invoice = db.relationship('Invoice', lazy='selectin')

    def __repr__(self) -> str:
        return f'<InsuranceClaim #{self.claim_number or self.id}>'

    def submit(self) -> None:
        """Transition claim from DRAFT to SUBMITTED and record the claim date."""
        from app.shared.enums import InsuranceClaimStatus

        self.status = InsuranceClaimStatus.SUBMITTED
        self.claim_date = datetime.now(UTC)

    def adjudicate(
        self, approved_amount, status: str, notes: str | None = None
    ) -> None:
        """Adjudicate the claim with an approved amount and status."""
        from app.shared.enums import InsuranceClaimStatus

        approved_amount = Decimal(str(approved_amount)) if approved_amount is not None else Decimal(0)
        self.status = status
        self.approved_amount = approved_amount
        self.adjudication_notes = notes
        if status in (InsuranceClaimStatus.PARTIALLY_APPROVED, InsuranceClaimStatus.APPROVED):
            self.insurance_share_amount = approved_amount
            self.patient_share_amount = (
                self.total_claim - approved_amount if self.total_claim else Decimal(0)
            )
        elif status == InsuranceClaimStatus.REJECTED:
            self.insurance_share_amount = Decimal(0)
            self.patient_share_amount = self.total_claim

    def settle(self, settled_amount) -> None:
        """Mark the claim as SETTLED with the settled amount."""
        from app.shared.enums import InsuranceClaimStatus

        settled_amount = Decimal(str(settled_amount)) if settled_amount is not None else Decimal(0)
        self.status = InsuranceClaimStatus.SETTLED
        self.approved_amount = settled_amount
        self.insurance_share_amount = settled_amount
