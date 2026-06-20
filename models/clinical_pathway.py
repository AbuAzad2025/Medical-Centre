"""
Clinical Pathways / Care Plans
Structured treatment protocols and care plans
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class ClinicalPathway(TenantMixin, db.Model):
    """Master clinical pathway template"""
    __tablename__ = 'clinical_pathways'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    name_ar = db.Column(db.String(300), nullable=True)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id', ondelete='SET NULL'), nullable=True, index=True)
    description = db.Column(db.Text, nullable=True)
    specialty = db.Column(db.String(100), nullable=True)
    expected_duration_days = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    icd10 = db.relationship('ICD10Code')
    steps = db.relationship('ClinicalPathwayStep', back_populates='pathway', lazy='dynamic', cascade='all, delete-orphan')
    patient_plans = db.relationship('PatientCarePlan', back_populates='pathway', lazy='dynamic')

    def __repr__(self):
        return f"<ClinicalPathway {self.name}>"


class ClinicalPathwayStep(TenantMixin, db.Model):
    """Individual step in a clinical pathway"""
    __tablename__ = 'clinical_pathway_steps'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    pathway_id = db.Column(db.Integer, db.ForeignKey('clinical_pathways.id', ondelete='CASCADE'), nullable=False, index=True)
    step_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(300), nullable=False)
    title_ar = db.Column(db.String(300), nullable=True)
    description = db.Column(db.Text, nullable=True)
    step_type = db.Column(db.String(50), default='TASK')  # TASK, INVESTIGATION, MEDICATION, SURGERY, CONSULTATION, EDUCATION
    expected_day = db.Column(db.Integer, nullable=True)  # Day from start
    responsible_role = db.Column(db.String(100), nullable=True)  # doctor, nurse, pharmacist, etc.
    is_mandatory = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    pathway = db.relationship('ClinicalPathway', back_populates='steps')


    def __repr__(self):
        return f"<ClinicalPathwayStep {self.step_number}>"


class PatientCarePlan(TenantMixin, db.Model):
    """Care plan assigned to a specific patient"""
    __tablename__ = 'patient_care_plans'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='CASCADE'), nullable=True, index=True)
    pathway_id = db.Column(db.Integer, db.ForeignKey('clinical_pathways.id', ondelete='SET NULL'), nullable=True, index=True)
    plan_name = db.Column(db.String(300), nullable=False)
    plan_name_ar = db.Column(db.String(300), nullable=True)

    # Timeline
    start_date = db.Column(db.Date, nullable=False)
    target_end_date = db.Column(db.Date, nullable=True)
    actual_end_date = db.Column(db.Date, nullable=True)

    # Status
    status = db.Column(db.String(30), default='ACTIVE')  # ACTIVE, COMPLETED, CANCELLED, ON_HOLD
    progress_percentage = db.Column(db.Integer, default=0)

    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='care_plans')
    visit = db.relationship('Visit', back_populates='care_plans')
    admission = db.relationship('Admission', back_populates='care_plans')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
    tasks = db.relationship('CarePlanTask', back_populates='care_plan', lazy='dynamic', cascade='all, delete-orphan')
    pathway = db.relationship('ClinicalPathway', back_populates='patient_plans')


    def __repr__(self):
        return f"<PatientCarePlan {self.status}>"


class CarePlanTask(TenantMixin, db.Model):
    """Individual task within a patient care plan"""
    __tablename__ = 'care_plan_tasks'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    care_plan_id = db.Column(db.Integer, db.ForeignKey('patient_care_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    task_title = db.Column(db.String(300), nullable=False)
    task_description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), default='PENDING')  # PENDING, IN_PROGRESS, COMPLETED, OVERDUE, CANCELLED
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    completed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])
    completed_by = db.relationship('User', foreign_keys=[completed_by_id])
    care_plan = db.relationship('PatientCarePlan', back_populates='tasks')


