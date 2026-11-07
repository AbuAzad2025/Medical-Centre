"""IoT Device Integration models — heart monitors, infusion pumps, etc."""

from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db


class IoTDevice(TenantMixin, db.Model):
    """An IoT medical device registered to a tenant."""

    __tablename__ = 'iot_devices'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    device_type = db.Column(
        db.String(50), nullable=False
    )  # heart_monitor, infusion_pump, pulse_oximeter, bp_monitor
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
    status = db.Column(db.String(20), default='offline')  # online, offline, error, maintenance
    last_seen = db.Column(db.DateTime, nullable=True)
    battery_level = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    registered_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )

    readings = db.relationship(
        'IoTReading', backref='device', lazy='dynamic', cascade='all, delete-orphan'
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
            'battery_level': self.battery_level,
            'is_active': self.is_active,
        }


class IoTReading(TenantMixin, db.Model):
    """A single reading from an IoT device."""

    __tablename__ = 'iot_readings'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(
        db.Integer, db.ForeignKey('iot_devices.id', ondelete='CASCADE'), nullable=False, index=True
    )
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True
    )
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True)
    reading_type = db.Column(
        db.String(50), nullable=False
    )  # heart_rate, spo2, bp_systolic, bp_diastolic, temperature, infusion_rate
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=True)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), index=True)
    is_critical = db.Column(db.Boolean, default=False)
    alert_sent = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'reading_type': self.reading_type,
            'value': self.value,
            'unit': self.unit,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'is_critical': self.is_critical,
        }
