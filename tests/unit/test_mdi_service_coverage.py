"""Coverage tests for services.mdi_service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from models.user import User
from services.mdi_service import MDIService

pytest_plugins = ['tests._isolated_tenant']


def _make_user(db, tenant_id, username, role='doctor', is_active=True, department_id=None):
    u = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=is_active,
        tenant_id=tenant_id,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.flush()
    return u


def _make_patient(db, tenant_id, first_name='Patient', last_name='Test'):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_tenant_device(db, tenant_id, device_id='DEV-001', device_type='ventilator',
                         patient_id=None, visit_id=None, status='online'):
    from models.medical_device import MedicalDevice

    d = MedicalDevice(
        tenant_id=tenant_id,
        device_id=device_id,
        device_type=device_type,
        device_name=f'Test {device_type}',
        patient_id=patient_id,
        visit_id=visit_id,
        location='ICU',
        status=status,
        last_seen=datetime.now(UTC),
    )
    db.session.add(d)
    db.session.flush()
    return d


class TestMDIService:
    def test_register_device(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = MDIService.register_device(
            device_id='VENT-001',
            device_type='ventilator',
            tenant_id=test_tenant.id,
            device_name='Ventilator 1',
            location='ICU Room 1',
        )
        assert device is not None
        assert device.device_id == 'VENT-001'
        assert device.device_type == 'ventilator'
        assert device.status == 'online'

    def test_record_parameter_unknown_device(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = MDIService.record_parameter(
            device_id='UNKNOWN-DEV',
            parameter_name='peak_pressure',
            value=45.0,
            tenant_id=test_tenant.id,
        )
        assert result is None

    def test_record_parameter_no_alarm(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-002',
                                     device_type='ventilator')
        result = MDIService.record_parameter(
            device_id='VENT-002',
            parameter_name='peep',
            value=5.0,
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is False

    def test_record_parameter_high_alarm(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-003',
                                     device_type='ventilator')
        result = MDIService.record_parameter(
            device_id='VENT-003',
            parameter_name='peak_pressure',
            value=50.0,  # above threshold of 40
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is True

    def test_record_parameter_low_alarm(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-004',
                                     device_type='ventilator')
        result = MDIService.record_parameter(
            device_id='VENT-004',
            parameter_name='tidal_volume',
            value=100.0,  # below threshold of 200
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is True

    def test_acknowledge_alarm(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-005')
        from models.medical_device import DeviceAlarm

        alarm = DeviceAlarm(
            tenant_id=test_tenant.id,
            device_id=device.id,
            alarm_type='peak_pressure',
            severity='critical',
            message='peak_pressure: 50.0',
        )
        db.session.add(alarm)
        db.session.flush()

        user = _make_user(db, test_tenant.id, 'mdi_user')
        result = MDIService.acknowledge_alarm(alarm.id, user.id)
        assert result is True

    def test_acknowledge_alarm_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = MDIService.acknowledge_alarm(alarm_id=99999, user_id=1)
        assert result is False

    def test_resolve_alarm(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-006')
        from models.medical_device import DeviceAlarm

        alarm = DeviceAlarm(
            tenant_id=test_tenant.id,
            device_id=device.id,
            alarm_type='peep',
            severity='high',
            message='peep: 25.0',
            is_active=True,
        )
        db.session.add(alarm)
        db.session.flush()

        result = MDIService.resolve_alarm(alarm.id)
        assert result is True

    def test_resolve_alarm_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = MDIService.resolve_alarm(alarm_id=99999)
        assert result is False

    def test_get_active_alarms(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-007')
        from models.medical_device import DeviceAlarm

        alarm = DeviceAlarm(
            tenant_id=test_tenant.id,
            device_id=device.id,
            alarm_type='fio2',
            severity='high',
            message='fio2: 105',
            is_active=True,
        )
        db.session.add(alarm)
        db.session.flush()

        result = MDIService.get_active_alarms(test_tenant.id)
        assert isinstance(result, list)

    def test_get_device_dashboard(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-008')

        result = MDIService.get_device_dashboard(test_tenant.id)
        assert 'total_devices' in result
        assert 'online_devices' in result
        assert 'in_use_devices' in result
        assert 'offline_devices' in result
        assert 'active_alarms' in result
        assert 'alarms' in result
        assert 'devices' in result

    def test_assign_device(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='VENT-009',
                                     patient_id=None)

        patient = _make_patient(db, test_tenant.id, first_name='Device', last_name='Patient')
        MDIService.assign_device('VENT-009', patient.id)
        db.session.refresh(device)
        assert device.patient_id == patient.id
        assert device.status == 'in_use'

    def test_assign_device_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = MDIService.assign_device('NONEXISTENT', 1)
        assert result is None
