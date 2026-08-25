"""ShiftHandover — operational shift lifecycle with frozen snapshots.

A shift is materialized as: open (optionally targeted to a successor) →
close/transfer (requires cash reconciliation or an explicit note) →
acknowledge (successor confirms).  Cash summary and pending-work snapshots
are captured at close time and are IMMUTABLE afterwards.
"""

from datetime import UTC, datetime

from sqlalchemy import Index

from app.shared.mixins import TenantMixin
from app_factory import db


class ShiftHandover(TenantMixin, db.Model):
    __tablename__ = 'shift_handovers'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)

    opened_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    closed_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    to_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    role = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='OPEN', nullable=False, index=True)

    opened_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    cash_summary = db.Column(db.JSON, nullable=True)

    pending_items = db.Column(db.JSON, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    close_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('OPEN','CLOSED','ACKNOWLEDGED')", name='chk_handover_status'
        ),
        Index('idx_handover_tenant_status', 'tenant_id', 'status'),
        Index('idx_handover_role_opened', 'role', 'opened_at'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'role': self.role,
            'status': self.status,
            'opened_by': self.opened_by_id,
            'to_user': self.to_user_id,
            'closed_by': self.closed_by_id,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'cash_summary': self.cash_summary,
            'pending_items': self.pending_items,
            'notes': self.notes,
            'close_note': self.close_note,
        }
