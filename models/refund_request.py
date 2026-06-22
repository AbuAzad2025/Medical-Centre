"""
Refund Request - P3-006
Tracks the full refund lifecycle: Request → Approval → Execution.
"""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Index
from app_factory import db
from app.shared.mixins import TenantMixin


class RefundStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class RefundRequest(TenantMixin, db.Model):
    __tablename__ = 'refund_requests'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reason = db.Column(db.Text, nullable=False)

    requested_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    executed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    status = db.Column(db.String(20), default=RefundStatus.PENDING, nullable=False, index=True)

    requested_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    executed_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        CheckConstraint("amount > 0", name='chk_refund_amount_positive'),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED')",
            name='chk_refund_status'
        ),
        Index('idx_refund_request_payment', 'payment_id'),
        Index('idx_refund_request_status', 'status'),
    )

    payment = db.relationship('Payment', lazy='selectin')
    requester = db.relationship('User', foreign_keys=[requested_by], lazy='selectin')
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='selectin')
    executor = db.relationship('User', foreign_keys=[executed_by], lazy='selectin')

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "payment_id": self.payment_id,
            "amount": float(self.amount or 0),
            "reason": self.reason,
            "status": self.status,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "executed_by": self.executed_by,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "notes": self.notes,
        }
