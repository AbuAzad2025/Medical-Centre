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
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=False)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id'), nullable=True)
    medication_id = db.Column(db.Integer, db.ForeignKey('medications.id'), nullable=False)

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
    nurse_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    witnessed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
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
    patient = db.relationship('Patient', backref='emar_administrations')
    visit = db.relationship('Visit', backref='emar_administrations')
    prescription = db.relationship('Prescription', backref='emar_administrations')
    medication = db.relationship('Medication', backref='emar_administrations')
    nurse = db.relationship('User', foreign_keys=[nurse_id])
    witnessed_by = db.relationship('User', foreign_keys=[witnessed_by_id])

    def __repr__(self):
        return f"<eMARAdministration {self.status}>"


class MedicationSchedule(db.Model):
    """Scheduled medication times for a prescription item"""
    __tablename__ = 'medication_schedules'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    prescription_item_id = db.Column(db.Integer, db.ForeignKey('prescription_items.id'), nullable=False)
    scheduled_time = db.Column(db.Time, nullable=False)
    dose = db.Column(db.String(100), nullable=True)
    frequency = db.Column(db.String(50), nullable=True)  # Q4H, BID, TID, QD, etc.
    window_before = db.Column(db.Integer, default=30)  # minutes
    window_after = db.Column(db.Integer, default=60)  # minutes
    is_prn = db.Column(db.Boolean, default=False)  # As needed
    prn_reason = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    prescription_item = db.relationship('PrescriptionItem', backref='schedules')
