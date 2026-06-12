"""
Problem List — Active patient health problems / diagnoses
"""
from datetime import datetime, timezone
from app_factory import db

class PatientProblem(db.Model):
    """Active/chronic problems for a patient"""
    __tablename__ = 'patient_problems'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id'), nullable=True)
    problem_description = db.Column(db.Text, nullable=False)
    problem_description_ar = db.Column(db.Text, nullable=True)

    # Classification
    problem_type = db.Column(db.String(50), default='DIAGNOSIS')  # DIAGNOSIS, SYMPTOM, COMPLAINT, FUNCTIONAL_LIMITATION
    severity = db.Column(db.String(20), default='MODERATE')  # MILD, MODERATE, SEVERE, LIFE_THREATENING
    priority = db.Column(db.Integer, default=0)  # Display order

    # Status lifecycle
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, CHRONIC, RESOLVED, RELAPSE, IN_REMISSION, RULED_OUT
    onset_date = db.Column(db.Date, nullable=True)
    resolution_date = db.Column(db.Date, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # Attribution
    recorded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recorded_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Clinical details
    clinical_notes = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)

    # Alerts
    is_critical = db.Column(db.Boolean, default=False)
    alert_message = db.Column(db.String(500), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='problems')
    icd10_code = db.relationship('ICD10Code')
    recorded_by = db.relationship('User', foreign_keys=[recorded_by_id])

    def __repr__(self):
        return f"<PatientProblem {self.status}>"


class AllergyIntolerance(db.Model):
    """Patient allergies and intolerances for CDS alerts"""
    __tablename__ = 'allergy_intolerances'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    substance = db.Column(db.String(200), nullable=False)  # Penicillin, Latex, Peanuts, etc.
    substance_ar = db.Column(db.String(200), nullable=True)
    category = db.Column(db.String(50), default='MEDICATION')  # MEDICATION, FOOD, ENVIRONMENTAL, BIOLOGIC
    criticality = db.Column(db.String(20), default='HIGH')  # LOW, HIGH, UNABLE_TO_ASSESS

    # Reaction details
    reaction_description = db.Column(db.Text, nullable=True)
    reaction_severity = db.Column(db.String(20), default='MODERATE')  # MILD, MODERATE, SEVERE
    onset_date = db.Column(db.Date, nullable=True)
    verification_status = db.Column(db.String(20), default='CONFIRMED')  # UNCONFIRMED, CONFIRMED, REFUTED, ENTERED_IN_ERROR

    # Source
    reported_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reported_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='allergy_intolerances')
    reported_by = db.relationship('User', foreign_keys=[reported_by_id])

    def __repr__(self):
        return f"<AllergyIntolerance {self.substance}>"
