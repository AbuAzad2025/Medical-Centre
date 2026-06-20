"""
Referral Management
Track referrals to/from external providers and facilities
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class Referral(TenantMixin, db.Model):
    """Patient referral to/from another provider/facility"""
    __tablename__ = 'referrals'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)

    # Direction
    referral_type = db.Column(db.String(20), default='OUTGOING')  # OUTGOING, INCOMING

    # Referring party
    referring_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    referring_facility = db.Column(db.String(300), nullable=True)
    referring_facility_phone = db.Column(db.String(50), nullable=True)
    referring_facility_email = db.Column(db.String(200), nullable=True)

    # Receiving party
    receiving_doctor_name = db.Column(db.String(200), nullable=True)
    receiving_specialty = db.Column(db.String(100), nullable=True)
    receiving_facility = db.Column(db.String(300), nullable=True)
    receiving_facility_address = db.Column(db.Text, nullable=True)
    receiving_facility_phone = db.Column(db.String(50), nullable=True)

    # Clinical info
    reason_for_referral = db.Column(db.Text, nullable=False)
    urgency = db.Column(db.String(20), default='ROUTINE')  # ROUTINE, URGENT, STAT
    clinical_summary = db.Column(db.Text, nullable=True)
    relevant_history = db.Column(db.Text, nullable=True)
    attached_files = db.Column(db.Text, nullable=True)  # JSON array of file IDs

    # Status
    status = db.Column(db.String(30), default='PENDING')  # PENDING, SENT, ACCEPTED, SCHEDULED, COMPLETED, CANCELLED, DECLINED
    sent_date = db.Column(db.DateTime, nullable=True)
    response_date = db.Column(db.DateTime, nullable=True)
    appointment_date = db.Column(db.DateTime, nullable=True)
    completion_date = db.Column(db.DateTime, nullable=True)

    # Counter-referral
    counter_referral_received = db.Column(db.Boolean, default=False)
    counter_referral_summary = db.Column(db.Text, nullable=True)
    counter_referral_file = db.Column(db.String(500), nullable=True)

    # Tracking
    tracking_number = db.Column(db.String(100), nullable=True, unique=True)
    notes = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='referrals')
    visit = db.relationship('Visit', back_populates='referrals')
    referring_doctor = db.relationship('User', foreign_keys=[referring_doctor_id])
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<Referral {self.status}>"
