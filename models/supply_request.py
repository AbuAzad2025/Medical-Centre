from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class MedicationSupplyRequest(db.Model):
    __tablename__ = 'medication_supply_requests'

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(40), nullable=False, unique=True, index=True)

    status = db.Column(db.String(16), nullable=False, default='DRAFT', index=True)
    notes = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    fulfilled_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    approved_at = db.Column(db.DateTime, nullable=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('DRAFT','APPROVED','FULFILLED','CANCELLED')", name='chk_med_supply_requests_status'),
        Index('idx_med_supply_requests_status_created', 'status', 'created_at'),
    )

    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='select')
    fulfiller = db.relationship('User', foreign_keys=[fulfilled_by], lazy='select')

    items = db.relationship('MedicationSupplyRequestItem', back_populates='request', lazy='selectin', cascade='all, delete-orphan')


class MedicationSupplyRequestItem(db.Model):
    __tablename__ = 'medication_supply_request_items'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('medication_supply_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)

    current_stock = db.Column(db.Integer, nullable=False, default=0)
    minimum_stock = db.Column(db.Integer, nullable=False, default=0)
    requested_qty = db.Column(db.Integer, nullable=False, default=1)
    approved_qty = db.Column(db.Integer, nullable=True)
    fulfilled_qty = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("requested_qty > 0", name='chk_med_supply_request_items_requested_qty'),
        Index('idx_med_supply_request_items_request_med', 'request_id', 'medication_id'),
    )

    request = db.relationship('MedicationSupplyRequest', back_populates='items', lazy='select')
    medication = db.relationship('Medication', lazy='select')

