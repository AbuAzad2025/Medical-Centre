"""IoT Device Monitoring Service — real-time device monitoring."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.extensions import db
from models.iot_device import IoTDevice, IoTReading

logger = logging.getLogger(__name__)

# Critical thresholds for IoT readings
CRITICAL_THRESHOLDS = {
    'heart_rate': {'low': 40, 'high': 150},
    'spo2': {'low': 90, 'high': 100},
    'bp_systolic': {'low': 80, 'high': 180},
    'bp_diastolic': {'low': 50, 'high': 120},
    'temperature': {'low': 35.0, 'high': 39.0},
    'infusion_rate': {'low': 0, 'high': 500},
}


class IoTMonitoringService:
    """Real-time IoT device monitoring service."""

    @staticmethod
    def register_device(
        device_id: str,
        device_type: str,
        tenant_id: int,
        device_name: str | None = None,
        patient_id: int | None = None,
        visit_id: int | None = None,
        location: str | None = None,
    ) -> IoTDevice:
        """Register a new IoT device."""
        device = IoTDevice(
            tenant_id=tenant_id,
            device_id=device_id,
            device_type=device_type,
            device_name=device_name,
            patient_id=patient_id,
            visit_id=visit_id,
            location=location,
            status='online',
            last_seen=datetime.now(UTC),
        )
        db.session.add(device)
        db.session.commit()
        logger.info('Registered IoT device: %s (%s)', device_id, device_type)
        return device

    @staticmethod
    def record_reading(
        device_id: str,
        reading_type: str,
        value: float,
        unit: str | None = None,
        tenant_id: int | None = None,
    ) -> IoTReading | None:
        """Record a reading from an IoT device."""
        device = (
            db.session.execute(select(IoTDevice).filter_by(device_id=device_id)).scalars().first()
        )
        if not device:
            logger.warning('Unknown device: %s', device_id)
            return None

        # Check critical thresholds
        thresholds = CRITICAL_THRESHOLDS.get(reading_type)
        is_critical = False
        if thresholds:
            if value < thresholds['low'] or value > thresholds['high']:
                is_critical = True

        reading = IoTReading(
            tenant_id=tenant_id or device.tenant_id,
            device_id=device.id,
            patient_id=device.patient_id,
            visit_id=device.visit_id,
            reading_type=reading_type,
            value=value,
            unit=unit,
            is_critical=is_critical,
        )
        db.session.add(reading)

        # Update device status
        device.last_seen = datetime.now(UTC)
        device.status = 'online'

        db.session.commit()

        if is_critical:
            logger.warning('Critical reading: %s=%s on device %s', reading_type, value, device_id)

        return reading

    @staticmethod
    def get_device_status(device_id: str) -> dict[str, Any] | None:
        """Get current status and latest readings for a device."""
        device = (
            db.session.execute(select(IoTDevice).filter_by(device_id=device_id)).scalars().first()
        )
        if not device:
            return None

        # Check if device is stale (no reading in last 5 minutes)
        if device.last_seen:
            stale_threshold = datetime.now(UTC) - timedelta(minutes=5)
            if device.last_seen < stale_threshold:
                device.status = 'offline'

        latest_readings = (
            db.session.execute(
                select(IoTReading)
                .filter_by(device_id=device.id)
                .order_by(IoTReading.recorded_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        return {
            'device': device.to_dict(),
            'latest_readings': [r.to_dict() for r in latest_readings],
        }

    @staticmethod
    def get_critical_alerts(tenant_id: int, since_minutes: int = 60) -> list[dict[str, Any]]:
        """Get all critical IoT readings in the last N minutes."""
        since = datetime.now(UTC) - timedelta(minutes=since_minutes)
        readings = (
            db.session.execute(
                select(IoTReading)
                .filter(
                    IoTReading.tenant_id == tenant_id,
                    IoTReading.is_critical,
                    IoTReading.recorded_at >= since,
                )
                .order_by(IoTReading.recorded_at.desc())
            )
            .scalars()
            .all()
        )
        return [r.to_dict() for r in readings]

    @staticmethod
    def assign_device_to_patient(device_id: str, patient_id: int, visit_id: int | None = None):
        """Assign a device to a patient/visit."""
        device = (
            db.session.execute(select(IoTDevice).filter_by(device_id=device_id)).scalars().first()
        )
        if device:
            device.patient_id = patient_id
            device.visit_id = visit_id
            db.session.commit()
            logger.info('Assigned device %s to patient %d', device_id, patient_id)
