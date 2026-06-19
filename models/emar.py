"""
eMAR — Electronic Medication Administration Record
Nurse medication administration tracking with barcode/QR support
"""
from datetime import datetime, timezone
from app_factory import db

class eMARAdministration(db.Model):
    """Record of nurse administering medication to patient"""
    __tablename__ = 'emar_administrations'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id', ondelete='RESTRICT'), nullable=False, index=True)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='CASCADE'), nullable=True, index=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id', ondelete='RESTRICT'), nullable=False, index=True)

    # Administration details
    scheduled_time = db.Column(db.DateTime, nullable=False)
    administered_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), default='SCHEDULED')
    # SCHEDULED, GIVEN, NOT_GIVEN, HELD, REFUSED, PARTIAL, MISSED, LATE

    # Dose given
    dose_given = db.Column(db.String(100), nullable=True)
    route = db.Column(db.String(50), nullable=True)  # Oral, IV, IM, SC, etc.
    site = db.Column(db.String(100), nullable=True)  # Injection site

    # Barcode / QR scanning
    barcode_scanned = db.Column(db.Boolean, default=False)
    patient_barcode = db.Column(db.String(100), nullable=True)
    medication_barcode = db.Column(db.String(100), nullable=True)

    # Nurse documentation
    nurse_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    witnessed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    refusal_reason = db.Column(db.String(200), nullable=True)
    hold_reason = db.Column(db.String(200), nullable=True)

    # Vitals at time of administration (if required)
    bp_systolic = db.Column(db.Integer, nullable=True)
    bp_diastolic = db.Column(db.Integer, nullable=True)
    heart_rate = db.Column(db.Integer, nullable=True)
    temperature = db.Column(db.Numeric(4, 1), nullable=True)
    pain_score = db.Column(db.Integer, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    patient = db.relationship('Patient', back_populates='emar_administrations')
    visit = db.relationship('Visit', back_populates='emar_administrations')
    prescription = db.relationship('Prescription', back_populates='emar_administrations')
    medication = db.relationship('Medication', back_populates='emar_administrations')
    nurse = db.relationship('User', foreign_keys=[nurse_id])
    witnessed_by = db.relationship('User', foreign_keys=[witnessed_by_id])

    def __repr__(self):
        return f"<eMARAdministration {self.status}>"


class MedicationSchedule(db.Model):
    """Scheduled medication times for a prescription item"""
    __tablename__ = 'medication_schedules'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id', ondelete='CASCADE'), nullable=False, index=True)
    scheduled_time = db.Column(db.Time, nullable=False)
    dose = db.Column(db.String(100), nullable=True)
    frequency = db.Column(db.String(50), nullable=True)  # Q4H, BID, TID, QD, etc.
    window_before = db.Column(db.Integer, default=30)  # minutes
    window_after = db.Column(db.Integer, default=60)  # minutes
    is_prn = db.Column(db.Boolean, default=False)  # As needed
    prn_reason = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    prescription_item = db.relationship('PrescriptionItem', back_populates='schedules')
