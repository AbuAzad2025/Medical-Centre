"""Medical Device Integration (MDI) models — ventilators, infusion pumps, etc."""

from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db


class MedicalDevice(TenantMixin, db.Model):
    """A medical device integrated with the system."""

    __tablename__ = 'medical_devices'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    device_type = db.Column(
        db.String(50), nullable=False
    )  # ventilator, infusion_pump, monitor, anesthesia_machine
    device_name = db.Column(db.String(200), nullable=True)
    manufacturer = db.Column(db.String(200), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    serial_number = db.Column(db.String(100), nullable=True)
    firmware_version = db.Column(db.String(50), nullable=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True
    )
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    status = db.Column(
        db.String(20), default='offline'
    )  # online, offline, error, maintenance, in_use
    last_seen = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    registered_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    parameters = db.relationship(
        'DeviceParameter', backref='device', lazy='dynamic', cascade='all, delete-orphan'
    )
    alarms = db.relationship(
        'DeviceAlarm', backref='device', lazy='dynamic', cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'device_type': self.device_type,
            'device_name': self.device_name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'location': self.location,
            'status': self.status,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_active': self.is_active,
        }


class DeviceParameter(TenantMixin, db.Model):
    """A parameter reading from a medical device."""

    __tablename__ = 'device_parameters'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey('medical_devices.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    parameter_name = db.Column(
        db.String(100), nullable=False
    )  # tidal_volume, respiratory_rate, peep, fio2, etc.
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=True)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), index=True)
    is_critical = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'parameter_name': self.parameter_name,
            'value': self.value,
            'unit': self.unit,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'is_critical': self.is_critical,
        }


class DeviceAlarm(TenantMixin, db.Model):
    """An alarm from a medical device."""

    __tablename__ = 'device_alarms'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey('medical_devices.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    alarm_type = db.Column(
        db.String(50), nullable=False
    )  # high_pressure, low_oxygen, disconnection, etc.
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    message = db.Column(db.Text, nullable=True)
    triggered_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    acknowledged_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'alarm_type': self.alarm_type,
            'severity': self.severity,
            'message': self.message,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'is_active': self.is_active,
        }
