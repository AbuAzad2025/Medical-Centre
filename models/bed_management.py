"""
Bed Management — Ward, Room, Bed, Admission-Discharge-Transfer (ADT)
"""
from datetime import datetime, timezone
from app_factory import db

class Ward(db.Model):
    """Hospital ward / unit"""
    __tablename__ = 'wards'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    ward_type = db.Column(db.String(50), default='GENERAL')  # GENERAL, ICU, NICU, PICU, MATERNITY, SURGERY, ISOLATION
    capacity = db.Column(db.Integer, default=0)
    floor = db.Column(db.String(20), nullable=True)
    building = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    department = db.relationship('Department', back_populates='wards')
    rooms = db.relationship('Room', back_populates='ward', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def occupancy_rate(self):
        total = sum(r.capacity for r in self.rooms)
        occupied = sum(1 for r in self.rooms for b in r.beds if b.current_patient_id)
        return (occupied / total * 100) if total else 0

    def __repr__(self):
        return f"<Ward {self.name}>"


class Room(db.Model):
    """Room within a ward"""
    __tablename__ = 'rooms'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    ward_id = db.Column(db.Integer, db.ForeignKey('wards.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    room_type = db.Column(db.String(50), default='STANDARD')  # STANDARD, PRIVATE, SEMI_PRIVATE, ICU_BAY, ISOLATION
    capacity = db.Column(db.Integer, default=1)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    beds = db.relationship('Bed', back_populates='room', lazy='dynamic', cascade='all, delete-orphan')
    ward = db.relationship('Ward', back_populates='rooms')


    def __repr__(self):
        return f"<Room {self.name}>"


class Bed(db.Model):
    """Individual bed in a room"""
    __tablename__ = 'beds'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False, index=True)
    bed_number = db.Column(db.String(20), nullable=False)
    bed_type = db.Column(db.String(50), default='STANDARD')  # STANDARD, ELECTRIC, BARIATRIC, PEDIATRIC, ICU, INCUBATOR
    status = db.Column(db.String(20), default='AVAILABLE')  # AVAILABLE, OCCUPIED, RESERVED, CLEANING, OUT_OF_ORDER
    current_patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    current_patient = db.relationship('Patient', foreign_keys=[current_patient_id])
    admissions = db.relationship('Admission', back_populates='bed', lazy='dynamic')
    room = db.relationship('Room', back_populates='beds')


    def __repr__(self):
        return f"<Bed {self.bed_number}>"


class Admission(db.Model):
    """Patient admission record (ADT)"""
    __tablename__ = 'admissions'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    bed_id = db.Column(db.Integer, db.ForeignKey('beds.id', ondelete='SET NULL'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)

    # Admission details
    admission_type = db.Column(db.String(50), default='ELECTIVE')  # ELECTIVE, EMERGENCY, URGENT, TRANSFER, READMISSION
    admission_datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    discharge_datetime = db.Column(db.DateTime, nullable=True)
    discharge_type = db.Column(db.String(50), nullable=True)  # HOME, TRANSFER, DEATH, AGAINST_ADVICE

    # Clinical info
    admitting_diagnosis = db.Column(db.Text, nullable=True)
    discharge_diagnosis = db.Column(db.Text, nullable=True)
    drg_code_id = db.Column(db.Integer, db.ForeignKey('drg_codes.id', ondelete='SET NULL'), nullable=True, index=True)
    length_of_stay = db.Column(db.Integer, nullable=True)  # calculated days

    # Doctors
    admitting_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    attending_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Status
    status = db.Column(db.String(20), default='ADMITTED')  # ADMITTED, DISCHARGED, TRANSFERRED, DECEASED
    is_active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='admissions')
    visit = db.relationship('Visit', back_populates='admissions')
    drg = db.relationship('DRGCode', back_populates='admissions')
    admitting_doctor = db.relationship('User', foreign_keys=[admitting_doctor_id])
    attending_doctor = db.relationship('User', foreign_keys=[attending_doctor_id])
    bed = db.relationship('Bed', back_populates='admissions')
    transfers = db.relationship('BedTransfer', back_populates='admission')
    care_plans = db.relationship('PatientCarePlan', back_populates='admission')
    medication_reconciliations = db.relationship('MedicationReconciliation', back_populates='admission')
    surgeries = db.relationship('SurgerySchedule', back_populates='admission')






    def __repr__(self):
        return f"<Admission {self.admission_type}>"


class BedTransfer(db.Model):
    """Transfer patient between beds/wards"""
    __tablename__ = 'bed_transfers'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    admission_id = db.Column(db.Integer, db.ForeignKey('admissions.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    from_bed_id = db.Column(db.Integer, db.ForeignKey('beds.id', ondelete='SET NULL'), nullable=True, index=True)
    to_bed_id = db.Column(db.Integer, db.ForeignKey('beds.id', ondelete='CASCADE'), nullable=False, index=True)
    transfer_datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    transfer_type = db.Column(db.String(50), default='INTERNAL')  # INTERNAL, INTER_WARD, ICU, DISCHARGE
    reason = db.Column(db.Text, nullable=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    admission = db.relationship('Admission', back_populates='transfers')
    patient = db.relationship('Patient', back_populates='bed_transfers')
    from_bed = db.relationship('Bed', foreign_keys=[from_bed_id])
    to_bed = db.relationship('Bed', foreign_keys=[to_bed_id])
