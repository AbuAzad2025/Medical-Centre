"""
HL7v2 MLLP routes — status + test ingest (HTTP wrapper for MLLP).
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from services.hl7_mllp_service import hl7_mllp_service
from utils.api_security import limit_payload_size
from utils.decorators import role_required

hl7_bp = Blueprint('hl7', __name__)


@hl7_bp.route('/status', methods=['GET'])
@login_required
@role_required('super_admin', 'admin', 'manager', 'lab')
def hl7_status():
    alive = hl7_mllp_service._thread.is_alive() if hl7_mllp_service._thread else False
    return jsonify(
        {
            "mllp_host": hl7_mllp_service.host,
            "mllp_port": hl7_mllp_service.port,
            "running": alive,
            "handlers": list(hl7_mllp_service._handlers.keys()),
        }
    )


@hl7_bp.route('/ingest', methods=['POST'])
@login_required
@role_required('super_admin', 'admin', 'lab')
@limit_payload_size(512 * 1024)
def hl7_ingest():
    """HTTP test ingest — POST raw ER7 body, returns ACK (useful without TCP MLLP client)."""
    raw = request.get_data(as_text=True)
    if not raw or "MSH" not in raw:
        return jsonify(success=False, error='Missing HL7 MSH segment'), 400
    ack = hl7_mllp_service.handle_raw(raw)
    return jsonify(success=True, ack=ack)


@hl7_bp.route('/control/<action>', methods=['POST'])
@login_required
@role_required('super_admin')
@limit_payload_size(16 * 1024)
def hl7_control(action):
    if action == "start":
        hl7_mllp_service.start()
        return jsonify(success=True, running=True)
    if action == "stop":
        hl7_mllp_service.stop()
        return jsonify(success=True, running=False)
    return jsonify(success=False, error='unknown action'), 400
