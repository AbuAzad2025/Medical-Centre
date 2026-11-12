"""Coverage tests for services.iot_monitoring_service.py."""

from __future__ import annotations

from datetime import UTC, datetime

from models.user import User
from services.iot_monitoring_service import IoTMonitoringService

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


def _make_tenant_device(
    db,
    tenant_id,
    device_id='IOT-001',
    device_type='heart_monitor',
    patient_id=None,
    visit_id=None,
    status='online',
):
    from models.iot_device import IoTDevice

    d = IoTDevice(
        tenant_id=tenant_id,
        device_id=device_id,
        device_type=device_type,
        device_name=f'Test {device_type}',
        patient_id=patient_id,
        visit_id=visit_id,
        location='Ward A',
        status=status,
        last_seen=datetime.now(UTC),
    )
    db.session.add(d)
    db.session.flush()
    return d


class TestIoTMonitoringService:
    def test_register_device(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = IoTMonitoringService.register_device(
            device_id='HR-001',
            device_type='heart_monitor',
            tenant_id=test_tenant.id,
            device_name='Heart Monitor 1',
            location='Room 101',
        )
        assert device is not None
        assert device.device_id == 'HR-001'
        assert device.status == 'online'

    def test_record_reading_unknown_device(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = IoTMonitoringService.record_reading(
            device_id='UNKNOWN',
            reading_type='heart_rate',
            value=75.0,
            tenant_id=test_tenant.id,
        )
        assert result is None

    def test_record_reading_normal(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _device = _make_tenant_device(
            db, test_tenant.id, device_id='HR-002', device_type='heart_monitor'
        )
        result = IoTMonitoringService.record_reading(
            device_id='HR-002',
            reading_type='heart_rate',
            value=75.0,
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is False

    def test_record_reading_critical_high(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _device = _make_tenant_device(
            db, test_tenant.id, device_id='HR-003', device_type='heart_monitor'
        )
        result = IoTMonitoringService.record_reading(
            device_id='HR-003',
            reading_type='heart_rate',
            value=200.0,  # above threshold of 150
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is True

    def test_record_reading_critical_low(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _device = _make_tenant_device(
            db, test_tenant.id, device_id='HR-004', device_type='heart_monitor'
        )
        result = IoTMonitoringService.record_reading(
            device_id='HR-004',
            reading_type='heart_rate',
            value=30.0,  # below threshold of 40
            tenant_id=test_tenant.id,
        )
        assert result is not None
        assert result.is_critical is True

    def test_get_device_status(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        _device = _make_tenant_device(db, test_tenant.id, device_id='HR-005')

        result = IoTMonitoringService.get_device_status('HR-005')
        assert result is not None
        assert 'device' in result
        assert 'latest_readings' in result

    def test_get_device_status_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = IoTMonitoringService.get_device_status('NONEXISTENT')
        assert result is None

    def test_get_critical_alerts(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='HR-006')
        from models.iot_device import IoTReading

        reading = IoTReading(
            tenant_id=test_tenant.id,
            device_id=device.id,
            patient_id=None,
            visit_id=None,
            reading_type='heart_rate',
            value=200.0,
            unit='bpm',
            is_critical=True,
            recorded_at=datetime.now(UTC),
        )
        db.session.add(reading)
        db.session.flush()

        result = IoTMonitoringService.get_critical_alerts(test_tenant.id)
        assert isinstance(result, list)

    def test_get_critical_alerts_empty(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = IoTMonitoringService.get_critical_alerts(test_tenant.id)
        assert result == []

    def test_assign_device_to_patient(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        device = _make_tenant_device(db, test_tenant.id, device_id='HR-007', patient_id=None)
        patient = _make_patient(db, test_tenant.id, first_name='IoT', last_name='Patient')

        IoTMonitoringService.assign_device_to_patient('HR-007', patient.id)
        db.session.refresh(device)
        assert device.patient_id == patient.id

    def test_assign_device_to_patient_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        # Should not raise
        IoTMonitoringService.assign_device_to_patient('NONEXISTENT', 1)
