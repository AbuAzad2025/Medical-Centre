"""
Clinical Decision Support (CDS) Alerts
Smart alerts for drug interactions, allergies, contraindications
"""
from datetime import datetime, timezone
from app_factory import db

class CDSAlertRule(db.Model):
    """Rules for generating clinical alerts"""
    __tablename__ = 'cds_alert_rules'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    rule_name = db.Column(db.String(300), nullable=False)
    rule_type = db.Column(db.String(50), nullable=False)
    # DRUG_INTERACTION, ALLERGY, CONTRAINDICATION, DUPLICATE_THERAPY,
    # DOSAGE_RANGE, LAB_MONITORING, VITAL_SIGN_ALERT, AGE_RESTRICTION,
    # PREGNANCY_WARNING, RENAL_DOSE_ADJUST, HEPATIC_DOSE_ADJUST

    trigger_entity_type = db.Column(db.String(50), nullable=False)  # MEDICATION, DIAGNOSIS, LAB, VITAL
    trigger_entity_code = db.Column(db.String(100), nullable=True)  # specific drug code or null for all
    trigger_entity_code_2 = db.Column(db.String(100), nullable=True)  # second entity for interactions

    # Conditions
    condition_logic = db.Column(db.Text, nullable=True)  # JSON conditions
    min_severity = db.Column(db.String(20), default='MODERATE')  # INFO, LOW, MODERATE, HIGH, CRITICAL

    # Alert content
    alert_title = db.Column(db.String(500), nullable=False)
    alert_message = db.Column(db.Text, nullable=False)
    alert_message_ar = db.Column(db.Text, nullable=True)
    suggested_action = db.Column(db.Text, nullable=True)

    # Behavior
    is_blocking = db.Column(db.Boolean, default=False)  # Hard stop vs soft alert
    requires_acknowledgment = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    fired_alerts = db.relationship('CDSFiredAlert', backref='rule', lazy='dynamic')

    def __repr__(self):
        return f"<CDSAlertRule {self.rule_type}>"


class CDSFiredAlert(db.Model):
    """Individual fired alert instance"""
    __tablename__ = 'cds_fired_alerts'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('cds_alert_rules.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=True)

    severity = db.Column(db.String(20), nullable=False)
    alert_title = db.Column(db.String(500), nullable=False)
    alert_message = db.Column(db.Text, nullable=False)
    suggested_action = db.Column(db.Text, nullable=True)

    # User response
    fired_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    acknowledged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    overridden = db.Column(db.Boolean, default=False)
    override_reason = db.Column(db.Text, nullable=True)
    override_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Outcome tracking
    action_taken = db.Column(db.Text, nullable=True)
    patient_outcome = db.Column(db.String(200), nullable=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', backref='cds_alerts')
    visit = db.relationship('Visit', backref='cds_alerts')
    prescription = db.relationship('Prescription', backref='cds_alerts')
    acknowledged_by = db.relationship('User', foreign_keys=[acknowledged_by_id])
    override_by = db.relationship('User', foreign_keys=[override_by_id])

    def __repr__(self):
        return f"<CDSFiredAlert {self.severity}>"
