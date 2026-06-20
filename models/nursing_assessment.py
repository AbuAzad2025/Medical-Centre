"""
Nursing Assessment Scales: Braden, Glasgow Coma, Fall Risk, Pain Scale
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class NursingAssessment(TenantMixin, db.Model):
    __tablename__ = 'nursing_assessments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=True, index=True)
    nurse_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Assessment type
    assessment_type = db.Column(db.String(30), nullable=False, index=True)
    # Types: 'braden', 'glasgow', 'fall_risk', 'pain_scale', 'norton', 'morse'

    # Generic score fields (used based on assessment_type)
    total_score = db.Column(db.Integer, nullable=True)
    risk_level = db.Column(db.String(20), nullable=True)  # low | moderate | high | severe

    # Braden Scale (6 subscales, total 6-23)
    braden_sensory_perception = db.Column(db.Integer, nullable=True)  # 1-4
    braden_moisture = db.Column(db.Integer, nullable=True)  # 1-4
    braden_activity = db.Column(db.Integer, nullable=True)  # 1-4
    braden_mobility = db.Column(db.Integer, nullable=True)  # 1-4
    braden_nutrition = db.Column(db.Integer, nullable=True)  # 1-4
    braden_friction_shear = db.Column(db.Integer, nullable=True)  # 1-3

    # Glasgow Coma Scale (3 components, total 3-15)
    glasgow_eye = db.Column(db.Integer, nullable=True)  # 1-4
    glasgow_verbal = db.Column(db.Integer, nullable=True)  # 1-5
    glasgow_motor = db.Column(db.Integer, nullable=True)  # 1-6

    # Fall Risk (Morse: 6 items, total 0-125)
    fall_history = db.Column(db.Integer, nullable=True)
    fall_secondary_diagnosis = db.Column(db.Integer, nullable=True)
    fall_ambulatory_aid = db.Column(db.Integer, nullable=True)
    fall_iv_saline = db.Column(db.Integer, nullable=True)
    fall_gait = db.Column(db.Integer, nullable=True)
    fall_mental_status = db.Column(db.Integer, nullable=True)

    # Pain Scale (0-10)
    pain_score = db.Column(db.Integer, nullable=True)
    pain_location = db.Column(db.String(100), nullable=True)
    pain_character = db.Column(db.String(50), nullable=True)

    # Norton Scale (5 items, total 5-20)
    norton_physical_condition = db.Column(db.Integer, nullable=True)
    norton_mental_condition = db.Column(db.Integer, nullable=True)
    norton_activity = db.Column(db.Integer, nullable=True)
    norton_mobility = db.Column(db.Integer, nullable=True)
    norton_incontinence = db.Column(db.Integer, nullable=True)

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    patient = db.relationship('Patient', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    nurse = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<NursingAssessment {self.assessment_type} patient={self.patient_id} score={self.total_score}>"

    @property
    def braden_total(self):
        if self.assessment_type != 'braden':
            return None
        vals = [self.braden_sensory_perception, self.braden_moisture,
                self.braden_activity, self.braden_mobility,
                self.braden_nutrition, self.braden_friction_shear]
        if None in vals:
            return None
        return sum(vals)

    @property
    def glasgow_total(self):
        if self.assessment_type != 'glasgow':
            return None
        vals = [self.glasgow_eye, self.glasgow_verbal, self.glasgow_motor]
        if None in vals:
            return None
        return sum(vals)

    @property
    def morse_total(self):
        if self.assessment_type != 'fall_risk':
            return None
        vals = [self.fall_history, self.fall_secondary_diagnosis,
                self.fall_ambulatory_aid, self.fall_iv_saline,
                self.fall_gait, self.fall_mental_status]
        if None in vals:
            return None
        return sum(vals)

    @property
    def norton_total(self):
        if self.assessment_type != 'norton':
            return None
        vals = [self.norton_physical_condition, self.norton_mental_condition,
                self.norton_activity, self.norton_mobility, self.norton_incontinence]
        if None in vals:
            return None
        return sum(vals)
