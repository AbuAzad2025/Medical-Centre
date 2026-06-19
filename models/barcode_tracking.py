"""
Barcode / QR Code Tracking
Track medications, specimens, patients, and equipment via barcode/QR
"""
from datetime import datetime, timezone
from app_factory import db

class BarcodeRegistry(db.Model):
    """Registry of all barcodes/QR codes in the system"""
    __tablename__ = 'barcode_registry'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    barcode_value = db.Column(db.String(200), nullable=False, unique=True, index=True)
    barcode_type = db.Column(db.String(50), nullable=False)  # BARCODE, QR_CODE, DATAMATRIX
    entity_type = db.Column(db.String(50), nullable=False)
    # PATIENT, MEDICATION, SPECIMEN, EQUIPMENT, BED, STAFF, VISIT, PRESCRIPTION
    entity_id = db.Column(db.Integer, nullable=False)
    entity_sub_id = db.Column(db.Integer, nullable=True)  # e.g., prescription_item_id

    # Generation
    generated_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    generated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    print_count = db.Column(db.Integer, default=0)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    expired_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    scans = db.relationship('BarcodeScanLog', back_populates='barcode', lazy='dynamic')

    def __repr__(self):
        return f"<BarcodeRegistry {self.entity_type}>"


class BarcodeScanLog(db.Model):
    """Log of barcode/QR scans"""
    __tablename__ = 'barcode_scan_logs'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    barcode_registry_id = db.Column(db.Integer, db.ForeignKey('barcode_registry.id', ondelete='CASCADE'), nullable=False, index=True)
    scan_action = db.Column(db.String(50), nullable=False)
    # ADMINISTER, VERIFY, DISPENSE, COLLECT, TRANSFER, ADMIT, DISCHARGE, CHECK_IN

    scanned_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    scanned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    location = db.Column(db.String(200), nullable=True)  # Ward, Room, Pharmacy, Lab
    device_id = db.Column(db.String(100), nullable=True)  # Scanner device identifier
    verification_result = db.Column(db.String(20), default='SUCCESS')  # SUCCESS, MISMATCH, NOT_FOUND, EXPIRED
    verification_message = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    scanned_by = db.relationship('User', foreign_keys=[scanned_by_id])
    barcode = db.relationship('BarcodeRegistry', back_populates='scans')


    def __repr__(self):
        return f"<BarcodeScanLog {self.scan_action}>"
