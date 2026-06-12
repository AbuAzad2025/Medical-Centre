"""
Population Health & Disease Registry
Analytics for community health, epidemiology, disease surveillance
"""
from datetime import datetime, timezone, date
from app_factory import db

class DiseaseRegistry(db.Model):
    """Registry of notifiable diseases for public health reporting"""
    __tablename__ = 'disease_registries'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id'), nullable=True)
    disease_name = db.Column(db.String(300), nullable=False)
    disease_name_ar = db.Column(db.String(300), nullable=True)
    is_notifiable = db.Column(db.Boolean, default=False)
    notification_sent = db.Column(db.Boolean, default=False)
    notification_date = db.Column(db.Date, nullable=True)
    onset_date = db.Column(db.Date, nullable=False)
    diagnosis_date = db.Column(db.Date, nullable=False)
    resolution_date = db.Column(db.Date, nullable=True)
    outcome = db.Column(db.String(50), nullable=True)  # RECOVERED, DECEASED, CHRONIC, UNKNOWN
    district = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(200), nullable=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='disease_registries')
    icd10 = db.relationship('ICD10Code')
    reported_by = db.relationship('User', foreign_keys=[reported_by_id])

    def __repr__(self):
        return f"<DiseaseRegistry {self.disease_name}>"


class PopulationHealthIndicator(db.Model):
    """Pre-calculated population health KPIs"""
    __tablename__ = 'population_health_indicators'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    indicator_name = db.Column(db.String(200), nullable=False)
    indicator_type = db.Column(db.String(50), nullable=False)  # MORTALITY, MORBIDITY, VACCINATION_COVERAGE, etc.
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    value = db.Column(db.Numeric(15, 4), nullable=True)
    unit = db.Column(db.String(50), nullable=True)  # PERCENT, RATE_PER_1000, COUNT, AVERAGE
    numerator = db.Column(db.Integer, nullable=True)
    denominator = db.Column(db.Integer, nullable=True)
    district = db.Column(db.String(200), nullable=True)
    gender_breakdown = db.Column(db.Text, nullable=True)  # JSON
    age_breakdown = db.Column(db.Text, nullable=True)  # JSON
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<PopulationHealthIndicator {self.indicator_name}>"


class QualityMeasure(db.Model):
    """Healthcare quality measures (HEDIS-style)"""
    __tablename__ = 'quality_measures'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    measure_code = db.Column(db.String(50), nullable=False, unique=True)
    measure_name = db.Column(db.String(300), nullable=False)
    measure_name_ar = db.Column(db.String(300), nullable=True)
    description = db.Column(db.Text, nullable=True)
    measure_type = db.Column(db.String(50), nullable=False)  # PROCESS, OUTCOME, STRUCTURE, PATIENT_EXPERIENCE
    target_value = db.Column(db.Numeric(10, 4), nullable=True)
    current_value = db.Column(db.Numeric(10, 4), nullable=True)
    period_start = db.Column(db.Date, nullable=True)
    period_end = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<QualityMeasure {self.measure_code}>"
