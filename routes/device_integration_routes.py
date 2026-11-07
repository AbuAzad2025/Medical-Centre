"""Device Integration Routes — IoT, MDI, DICOM Store, HL7 ORU."""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.extensions import db
from models.iot_device import IoTDevice
from models.medical_device import MedicalDevice
from services.hl7_oru_service import HL7ORUService
from services.iot_monitoring_service import IoTMonitoringService
from services.mdi_service import MDIService
from utils.decorators import handle_route_errors, role_required

device_bp = Blueprint('device_integration', __name__)


# === IoT Device Routes ===


@device_bp.route('/iot/devices', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def iot_list_devices():
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    devices = (
        db.session.execute(
            __import__('sqlalchemy', fromlist=['select'])
            .select(IoTDevice)
            .filter_by(tenant_id=tenant_id)
        )
        .scalars()
        .all()
    )
    return jsonify({'devices': [d.to_dict() for d in devices]})


@device_bp.route('/iot/devices', methods=['POST'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def iot_register_device():
    data = request.get_json() or {}
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    device = IoTMonitoringService.register_device(
        device_id=data.get('device_id', ''),
        device_type=data.get('device_type', ''),
        tenant_id=tenant_id,
        device_name=data.get('device_name'),
        patient_id=data.get('patient_id'),
        visit_id=data.get('visit_id'),
        location=data.get('location'),
    )
    return jsonify(device.to_dict()), 201


@device_bp.route('/iot/readings', methods=['POST'])
@login_required
@handle_route_errors
def iot_record_reading():
    data = request.get_json() or {}
    reading = IoTMonitoringService.record_reading(
        device_id=data.get('device_id', ''),
        reading_type=data.get('reading_type', ''),
        value=float(data.get('value', 0)),
        unit=data.get('unit'),
    )
    if reading:
        return jsonify(reading.to_dict()), 201
    return jsonify({'error': 'Device not found'}), 404


@device_bp.route('/iot/devices/<device_id>/status', methods=['GET'])
@login_required
@handle_route_errors
def iot_device_status(device_id):
    status = IoTMonitoringService.get_device_status(device_id)
    if status:
        return jsonify(status)
    return jsonify({'error': 'Device not found'}), 404


@device_bp.route('/iot/alerts', methods=['GET'])
@login_required
@handle_route_errors
def iot_alerts():
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    minutes = request.args.get('minutes', 60, type=int)
    alerts = IoTMonitoringService.get_critical_alerts(tenant_id, minutes)
    return jsonify({'alerts': alerts})


# === Medical Device (MDI) Routes ===


@device_bp.route('/mdi/devices', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def mdi_list_devices():
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    devices = (
        db.session.execute(
            __import__('sqlalchemy', fromlist=['select'])
            .select(MedicalDevice)
            .filter_by(tenant_id=tenant_id)
        )
        .scalars()
        .all()
    )
    return jsonify({'devices': [d.to_dict() for d in devices]})


@device_bp.route('/mdi/devices', methods=['POST'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def mdi_register_device():
    data = request.get_json() or {}
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    device = MDIService.register_device(
        device_id=data.get('device_id', ''),
        device_type=data.get('device_type', ''),
        tenant_id=tenant_id,
        device_name=data.get('device_name'),
        patient_id=data.get('patient_id'),
        visit_id=data.get('visit_id'),
        location=data.get('location'),
    )
    return jsonify(device.to_dict()), 201


@device_bp.route('/mdi/parameters', methods=['POST'])
@login_required
@handle_route_errors
def mdi_record_parameter():
    data = request.get_json() or {}
    param = MDIService.record_parameter(
        device_id=data.get('device_id', ''),
        parameter_name=data.get('parameter_name', ''),
        value=float(data.get('value', 0)),
        unit=data.get('unit'),
    )
    if param:
        return jsonify(param.to_dict()), 201
    return jsonify({'error': 'Device not found'}), 404


@device_bp.route('/mdi/alarms', methods=['GET'])
@login_required
@handle_route_errors
def mdi_alarms():
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    alarms = MDIService.get_active_alarms(tenant_id)
    return jsonify({'alarms': alarms})


@device_bp.route('/mdi/dashboard', methods=['GET'])
@login_required
@handle_route_errors
def mdi_dashboard():
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    dashboard = MDIService.get_device_dashboard(tenant_id)
    return jsonify(dashboard)


# === HL7 ORU Routes ===


@device_bp.route('/hl7/oru/parse', methods=['POST'])
@login_required
@handle_route_errors
def hl7_oru_parse():
    data = request.get_json() or {}
    raw = data.get('message', '')
    result = HL7ORUService.parse_oru_message(raw)
    return jsonify(result)


@device_bp.route('/hl7/oru/create', methods=['POST'])
@login_required
@handle_route_errors
def hl7_oru_create():
    data = request.get_json() or {}
    raw = data.get('message', '')
    tenant_id = getattr(__import__('flask').g, 'tenant_id', None)
    result = HL7ORUService.create_results_from_oru(raw, tenant_id)
    return jsonify(result)
