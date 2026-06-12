"""
Vaccination / Immunization Registry
Track patient vaccinations with schedules and boosters
"""
from datetime import datetime, timezone, date
from app_factory import db

class Vaccine(db.Model):
    """Vaccine master data"""
    __tablename__ = 'vaccines'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200), nullable=True)
    code = db.Column(db.String(50), nullable=False, unique=True)  # CVX code
    manufacturer = db.Column(db.String(200), nullable=True)
    lot_number = db.Column(db.String(100), nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    doses_required = db.Column(db.Integer, default=1)
    dose_interval_days = db.Column(db.Integer, nullable=True)
    target_age_months = db.Column(db.String(200), nullable=True)  # JSON: [2, 4, 6]
    contraindications = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    immunizations = db.relationship('Immunization', backref='vaccine', lazy='dynamic')

    def __repr__(self):
        return f"<Vaccine {self.name}>"


class Immunization(db.Model):
    """Patient immunization record"""
    __tablename__ = 'immunizations'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)
    dose_number = db.Column(db.Integer, default=1)
    administration_date = db.Column(db.Date, nullable=False)
    administration_site = db.Column(db.String(100), nullable=True)  # Left Arm, Right Arm, Left Thigh, etc.
    route = db.Column(db.String(50), default='IM')  # IM, SC, PO, ID, INTRANASAL
    dosage = db.Column(db.String(100), nullable=True)  # 0.5 mL, etc.
    lot_number = db.Column(db.String(100), nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)
    manufacturer = db.Column(db.String(200), nullable=True)

    # Provider
    administered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    facility = db.Column(db.String(200), nullable=True)

    # Status
    status = db.Column(db.String(30), default='COMPLETED')  # COMPLETED, REFUSED, DEFERRED, PARTIAL
    refusal_reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Next dose tracking
    next_due_date = db.Column(db.Date, nullable=True)
    is_overdue = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='immunizations')
    administered_by = db.relationship('User', foreign_keys=[administered_by_id])

    def __repr__(self):
        return f"<Immunization {self.dose_number}>"


class VaccinationSchedule(db.Model):
    """Recommended vaccination schedule (e.g., WHO Expanded Programme)"""
    __tablename__ = 'vaccination_schedules'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    vaccine_id = db.Column(db.Integer, db.ForeignKey('vaccines.id'), nullable=False)
    schedule_name = db.Column(db.String(100), default='STANDARD')  # STANDARD, CATCH_UP, TRAVEL
    dose_number = db.Column(db.Integer, nullable=False)
    recommended_age_months = db.Column(db.Integer, nullable=False)
    min_age_months = db.Column(db.Integer, nullable=True)
    max_age_months = db.Column(db.Integer, nullable=True)
    interval_from_previous_days = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    vaccine = db.relationship('Vaccine', backref='schedules')
