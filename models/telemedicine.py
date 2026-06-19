"""
Telemedicine / Remote Consultation Appointments
"""
from datetime import datetime, timezone
from app_factory import db

class TelemedicineAppointment(db.Model):
    __tablename__ = 'telemedicine_appointments'

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='CASCADE'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Meeting details
    meeting_url = db.Column(db.String(500), nullable=True)  # Zoom, Teams, Jitsi, etc.
    meeting_provider = db.Column(db.String(50), nullable=True)  # jitsi | zoom | teams | custom
    meeting_id = db.Column(db.String(100), nullable=True)
    meeting_password = db.Column(db.String(100), nullable=True)

    # Status
    status = db.Column(db.String(20), default='scheduled', nullable=False, index=True)
    # scheduled | started | completed | cancelled | no_show

    scheduled_start = db.Column(db.DateTime, nullable=False)
    scheduled_end = db.Column(db.DateTime, nullable=True)
    actual_start = db.Column(db.DateTime, nullable=True)
    actual_end = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)

    # Clinical notes from telemedicine session
    chief_complaint = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    plan = db.Column(db.Text, nullable=True)

    # Recording (if enabled)
    recording_url = db.Column(db.String(500), nullable=True)
    recording_consent = db.Column(db.Boolean, default=False, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    appointment = db.relationship('Appointment', lazy='selectin')
    visit = db.relationship('Visit', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    doctor = db.relationship('User', foreign_keys=[doctor_id], lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    def __repr__(self):
        return f"<TelemedicineAppointment patient={self.patient_id} status={self.status}>"
