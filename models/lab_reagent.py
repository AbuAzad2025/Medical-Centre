from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db


class LabReagent(db.Model):
    __tablename__ = 'lab_reagents'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False, index=True)
    supplier = db.Column(db.String(120), nullable=True)
    lot_number = db.Column(db.String(80), nullable=True, index=True)
    unit = db.Column(db.String(40), nullable=True)

    stock_quantity = db.Column(db.Integer, nullable=False, default=0, index=True)
    minimum_stock = db.Column(db.Integer, nullable=False, default=0, index=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_lab_reagents_stock', 'is_active', 'stock_quantity'),
        Index('idx_lab_reagents_expiry', 'is_active', 'expiry_date'),
    )

