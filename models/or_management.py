"""
Operating Room (OR) Management
Surgery scheduling, team assignment, instrument tracking
"""
from datetime import datetime, timezone
from app_factory import db

class SurgerySchedule(db.Model):
    """Scheduled surgery/procedure"""
    __tablename__ = 'surgery_schedules'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='CASCADE'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)

    # Procedure info
    procedure_name = db.Column(db.String(500), nullable=False)
    procedure_name_ar = db.Column(db.String(500), nullable=True)
    cpt_code_id = db.Column(db.Integer, db.ForeignKey('cpt_codes.id', ondelete='SET NULL'), nullable=True, index=True)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id', ondelete='SET NULL'), nullable=True, index=True)
    surgery_type = db.Column(db.String(50), default='ELECTIVE')  # ELECTIVE, EMERGENCY, URGENT
    priority = db.Column(db.String(20), default='NORMAL')  # NORMAL, URGENT, STAT

    # OR details
    or_room = db.Column(db.String(100), nullable=True)
    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_start_time = db.Column(db.Time, nullable=True)
    estimated_duration_minutes = db.Column(db.Integer, nullable=True)

    # Team
    surgeon_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    assistant_surgeon_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    anesthesiologist_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    circulating_nurse_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    scrub_nurse_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Status
    status = db.Column(db.String(30), default='SCHEDULED')  # SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, DELAYED
    actual_start_time = db.Column(db.DateTime, nullable=True)
    actual_end_time = db.Column(db.DateTime, nullable=True)

    # Outcome
    outcome = db.Column(db.String(200), nullable=True)
    complications = db.Column(db.Text, nullable=True)
    specimens_sent = db.Column(db.Text, nullable=True)
    estimated_blood_loss = db.Column(db.String(50), nullable=True)

    # Consent
    consent_signed = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='surgeries')
    admission = db.relationship('Admission', back_populates='surgeries')
    visit = db.relationship('Visit', back_populates='surgeries')
    surgeon = db.relationship('User', foreign_keys=[surgeon_id])
    cpt_code = db.relationship('CPTCode')
    checklist = db.relationship('SurgeryChecklist', back_populates='surgery')


    def __repr__(self):
        return f"<SurgerySchedule {self.status}>"


class SurgeryChecklist(db.Model):
    """WHO Surgical Safety Checklist"""
    __tablename__ = 'surgery_checklists'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    surgery_schedule_id = db.Column(db.Integer, db.ForeignKey('surgery_schedules.id', ondelete='CASCADE'), nullable=False, index=True)

    # Sign In (before anesthesia)
    sign_in_patient_identity = db.Column(db.Boolean, default=False)
    sign_in_site_marked = db.Column(db.Boolean, default=False)
    sign_in_anesthesia_check = db.Column(db.Boolean, default=False)
    sign_in_pulse_oximeter = db.Column(db.Boolean, default=False)
    sign_in_allergies_checked = db.Column(db.Boolean, default=False)
    sign_in_airway_risk = db.Column(db.Boolean, default=False)
    sign_in_blood_loss_risk = db.Column(db.Boolean, default=False)

    # Time Out (before incision)
    time_out_team_introduced = db.Column(db.Boolean, default=False)
    time_out_patient_identity = db.Column(db.Boolean, default=False)
    time_out_procedure = db.Column(db.Boolean, default=False)
    time_out_site = db.Column(db.Boolean, default=False)
    time_out_antibiotics_given = db.Column(db.Boolean, default=False)
    time_out_equipment_ready = db.Column(db.Boolean, default=False)
    time_out_imaging_displayed = db.Column(db.Boolean, default=False)

    # Sign Out (before leaving OR)
    sign_out_procedure_recorded = db.Column(db.Boolean, default=False)
    sign_out_specimen_labeled = db.Column(db.Boolean, default=False)
    sign_out_equipment_count = db.Column(db.Boolean, default=False)
    sign_out_equipment_issues = db.Column(db.Text, nullable=True)

    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    surgery = db.relationship('SurgerySchedule', back_populates='checklist')
    completed_by = db.relationship('User', foreign_keys=[completed_by_id])
