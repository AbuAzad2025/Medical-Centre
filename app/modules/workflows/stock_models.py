"""
StockMovement model — ledger for all inventory changes
"""
from datetime import datetime, timezone
from app.extensions import db

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False, index=True)
    movement_type = db.Column(db.String(20), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)  # negative for outflow
    before_quantity = db.Column(db.Integer, nullable=False)
    after_quantity = db.Column(db.Integer, nullable=False)

    reference_type = db.Column(db.String(50), nullable=True)  # PrescriptionItem, PurchaseOrder, Adjustment
    reference_id = db.Column(db.Integer, nullable=True)

    batch_number = db.Column(db.String(100), nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        db.Index('idx_stock_movement_ref', 'reference_type', 'reference_id'),
    )
