"""
Clinical Pathways / Care Plans
Structured treatment protocols and care plans
"""
from datetime import datetime, timezone
from app_factory import db

class ClinicalPathway(db.Model):
    """Master clinical pathway template"""
    __tablename__ = 'clinical_pathways'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    name_ar = db.Column(db.String(300), nullable=True)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    specialty = db.Column(db.String(100), nullable=True)
    expected_duration_days = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    icd10 = db.relationship('ICD10Code')
    steps = db.relationship('ClinicalPathwayStep', backref='pathway', lazy='dynamic', cascade='all, delete-orphan')
    patient_plans = db.relationship('PatientCarePlan', backref='pathway', lazy='dynamic')

    def __repr__(self):
        return f"<ClinicalPathway {self.name}>"


class ClinicalPathwayStep(db.Model):
    """Individual step in a clinical pathway"""
    __tablename__ = 'clinical_pathway_steps'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    pathway_id = db.Column(db.Integer, db.ForeignKey('clinical_pathways.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    title_ar = db.Column(db.String(300), nullable=True)
    description = db.Column(db.Text, nullable=True)
    step_type = db.Column(db.String(50), default='TASK')  # TASK, INVESTIGATION, MEDICATION, SURGERY, CONSULTATION, EDUCATION
    expected_day = db.Column(db.Integer, nullable=True)  # Day from start
    responsible_role = db.Column(db.String(100), nullable=True)  # doctor, nurse, pharmacist, etc.
    is_mandatory = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<ClinicalPathwayStep {self.step_number}>"


class PatientCarePlan(db.Model):
    """Care plan assigned to a specific patient"""
    __tablename__ = 'patient_care_plans'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id'), nullable=True)
    pathway_id = db.Column(db.Integer, db.ForeignKey('clinical_pathways.id'), nullable=True)
    plan_name = db.Column(db.String(300), nullable=False)
    plan_name_ar = db.Column(db.String(300), nullable=True)

    # Timeline
    start_date = db.Column(db.Date, nullable=False)
    target_end_date = db.Column(db.Date, nullable=True)
    actual_end_date = db.Column(db.Date, nullable=True)

    # Status
    status = db.Column(db.String(30), default='ACTIVE')  # ACTIVE, COMPLETED, CANCELLED, ON_HOLD
    progress_percentage = db.Column(db.Integer, default=0)

    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='care_plans')
    visit = db.relationship('Visit', backref='care_plans')
    admission = db.relationship('Admission', backref='care_plans')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
    tasks = db.relationship('CarePlanTask', backref='care_plan', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<PatientCarePlan {self.status}>"


class CarePlanTask(db.Model):
    """Individual task within a patient care plan"""
    __tablename__ = 'care_plan_tasks'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    care_plan_id = db.Column(db.Integer, db.ForeignKey('patient_care_plans.id'), nullable=False)
    task_title = db.Column(db.String(300), nullable=False)
    task_description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default='PENDING')  # PENDING, IN_PROGRESS, COMPLETED, OVERDUE, CANCELLED
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])
    completed_by = db.relationship('User', foreign_keys=[completed_by_id])
