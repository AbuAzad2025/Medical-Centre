"""
Medication Reconciliation
Compare medications across care transitions (admission, transfer, discharge)
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class MedicationReconciliation(TenantMixin, db.Model):
    """Medication reconciliation at care transition"""
    __tablename__ = 'medication_reconciliations'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='CASCADE'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)

    # Transition type
    transition_type = db.Column(db.String(50), nullable=False)
    # ADMISSION, TRANSFER_IN, TRANSFER_OUT, DISCHARGE, EMERGENCY_VISIT, OUTPATIENT_FOLLOWUP

    # Source medications (before transition)
    source_medication_list = db.Column(db.Text, nullable=True)  # JSON: list of meds before
    source_date = db.Column(db.Date, nullable=True)
    source_provider = db.Column(db.String(200), nullable=True)

    # Current/Destination medications (after transition)
    destination_medication_list = db.Column(db.Text, nullable=True)  # JSON: list of meds after
    destination_date = db.Column(db.Date, nullable=True)
    destination_provider = db.Column(db.String(200), nullable=True)

    # Reconciliation results
    status = db.Column(db.String(30), default='PENDING')  # PENDING, COMPLETED, PARTIAL, NOT_DONE
    reconciled_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reconciled_at = db.Column(db.DateTime, nullable=True)

    # Discrepancies found
    discrepancies = db.Column(db.Text, nullable=True)  # JSON: omissions, commissions, duplications
    omission_count = db.Column(db.Integer, default=0)
    commission_count = db.Column(db.Integer, default=0)
    duplication_count = db.Column(db.Integer, default=0)
    dose_discrepancy_count = db.Column(db.Integer, default=0)

    # Patient/caregiver education
    education_provided = db.Column(db.Boolean, default=False)
    education_notes = db.Column(db.Text, nullable=True)
    patient_understanding_confirmed = db.Column(db.Boolean, default=False)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='medication_reconciliations')
    admission = db.relationship('Admission', back_populates='medication_reconciliations')
    visit = db.relationship('Visit', back_populates='medication_reconciliations')
    reconciled_by = db.relationship('User', foreign_keys=[reconciled_by_id])

    def __repr__(self):
        return f"<MedicationReconciliation {self.status}>"
