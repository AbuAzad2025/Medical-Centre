"""Medical Device Integration (MDI) Service — ventilators, infusion pumps, etc."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.extensions import db
from models.medical_device import DeviceAlarm, DeviceParameter, MedicalDevice

logger = logging.getLogger(__name__)

# Critical alarm thresholds
ALARM_THRESHOLDS = {
    'ventilator': {
        'peak_pressure': {'high': 40},
        'tidal_volume': {'low': 200, 'high': 800},
        'respiratory_rate': {'low': 8, 'high': 30},
        'peep': {'high': 20},
        'fio2': {'high': 100},
    },
    'infusion_pump': {
        'infusion_rate': {'high': 500},
        'pressure': {'high': 300},
    },
}


class MDIService:
    """Medical Device Integration service."""

    @staticmethod
    def register_device(
        device_id: str,
        device_type: str,
        tenant_id: int,
        device_name: str | None = None,
        patient_id: int | None = None,
        visit_id: int | None = None,
        location: str | None = None,
    ) -> MedicalDevice:
        """Register a new medical device."""
        device = MedicalDevice(
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
        logger.info('Registered medical device: %s (%s)', device_id, device_type)
        return device

    @staticmethod
    def record_parameter(
        device_id: str,
        parameter_name: str,
        value: float,
        unit: str | None = None,
        tenant_id: int | None = None,
    ) -> DeviceParameter | None:
        """Record a parameter reading from a medical device."""
        device = (
            db.session.execute(select(MedicalDevice).filter_by(device_id=device_id))
            .scalars()
            .first()
        )
        if not device:
            logger.warning('Unknown device: %s', device_id)
            return None

        # Check alarm thresholds
        thresholds = ALARM_THRESHOLDS.get(device.device_type, {}).get(parameter_name)
        is_critical = False
        if thresholds:
            if 'high' in thresholds and value > thresholds['high']:
                is_critical = True
            if 'low' in thresholds and value < thresholds['low']:
                is_critical = True

        param = DeviceParameter(
            tenant_id=tenant_id or device.tenant_id,
            device_id=device.id,
            parameter_name=parameter_name,
            value=value,
            unit=unit,
            is_critical=is_critical,
        )
        db.session.add(param)

        device.last_seen = datetime.now(UTC)
        device.status = 'in_use' if device.patient_id else 'online'

        db.session.commit()

        if is_critical:
            MDIService._trigger_alarm(device, parameter_name, value, 'critical')

        return param

    @staticmethod
    def _trigger_alarm(device: MedicalDevice, alarm_type: str, value: float, severity: str):
        """Trigger an alarm for a device."""
        alarm = DeviceAlarm(
            tenant_id=device.tenant_id,
            device_id=device.id,
            alarm_type=alarm_type,
            severity=severity,
            message=f'{alarm_type}: {value}',
        )
        db.session.add(alarm)
        db.session.commit()
        logger.warning('Device alarm: %s on %s — %s', alarm_type, device.device_id, value)

    @staticmethod
    def acknowledge_alarm(alarm_id: int, user_id: int) -> bool:
        """Acknowledge a device alarm."""
        alarm = db.session.get(DeviceAlarm, alarm_id)
        if alarm:
            alarm.acknowledged_at = datetime.now(UTC)
            alarm.acknowledged_by = user_id
            db.session.commit()
            return True
        return False

    @staticmethod
    def resolve_alarm(alarm_id: int) -> bool:
        """Resolve a device alarm."""
        alarm = db.session.get(DeviceAlarm, alarm_id)
        if alarm:
            alarm.resolved_at = datetime.now(UTC)
            alarm.is_active = False
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_active_alarms(tenant_id: int) -> list[dict[str, Any]]:
        """Get all active device alarms for a tenant."""
        alarms = (
            db.session.execute(
                select(DeviceAlarm)
                .filter(DeviceAlarm.tenant_id == tenant_id, DeviceAlarm.is_active)
                .order_by(DeviceAlarm.triggered_at.desc())
            )
            .scalars()
            .all()
        )
        return [a.to_dict() for a in alarms]

    @staticmethod
    def get_device_dashboard(tenant_id: int) -> dict[str, Any]:
        """Get device dashboard summary."""
        devices = (
            db.session.execute(select(MedicalDevice).filter(MedicalDevice.tenant_id == tenant_id))
            .scalars()
            .all()
        )
        active_alarms = MDIService.get_active_alarms(tenant_id)
        return {
            'total_devices': len(devices),
            'online_devices': sum(1 for d in devices if d.status == 'online'),
            'in_use_devices': sum(1 for d in devices if d.status == 'in_use'),
            'offline_devices': sum(1 for d in devices if d.status == 'offline'),
            'active_alarms': len(active_alarms),
            'alarms': active_alarms,
            'devices': [d.to_dict() for d in devices],
        }

    @staticmethod
    def assign_device(device_id: str, patient_id: int, visit_id: int | None = None):
        """Assign a device to a patient/visit."""
        device = (
            db.session.execute(select(MedicalDevice).filter_by(device_id=device_id))
            .scalars()
            .first()
        )
        if device:
            device.patient_id = patient_id
            device.visit_id = visit_id
            device.status = 'in_use'
            db.session.commit()
            logger.info('Assigned device %s to patient %d', device_id, patient_id)
