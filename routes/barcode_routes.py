"""
Barcode / QR Code Tracking Routes
"""

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.barcode_tracking import BarcodeRegistry, BarcodeScanLog
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

barcode_bp = Blueprint('barcode', __name__)


@barcode_bp.route('/scan')
@login_required
@role_required('nurse', 'pharmacist', 'lab_tech', 'admin')
@handle_route_errors
def scan_page():
    return render_template('barcode/scan.html')


@barcode_bp.route('/api/scan', methods=['POST'])
@login_required
@role_required('nurse', 'reception', 'doctor', 'admin', 'manager')
@handle_route_errors
def api_scan():
    data = request.get_json()
    barcode_value = data.get('barcode') if data else request.form.get('barcode')
    action = data.get('action') if data else request.form.get('action', 'VERIFY')

    if not barcode_value:
        return jsonify({'success': False, 'message': 'Barcode required'})

    registry = (
        db.session.execute(
            select(BarcodeRegistry).filter_by(barcode_value=barcode_value, is_active=True)
        )
        .scalars()
        .first()
    )
    if not registry:
        # Log failed scan
        log = BarcodeScanLog(
            barcode_registry_id=None,
            scan_action=action,
            scanned_by_id=current_user.id,
            verification_result='NOT_FOUND',
            verification_message='Barcode not found in registry',
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': False, 'message': 'Barcode not found'})

    # Log successful scan
    log = BarcodeScanLog(
        barcode_registry_id=registry.id,
        scan_action=action,
        scanned_by_id=current_user.id,
        verification_result='SUCCESS',
        ip_address=request.remote_addr,
    )
    db.session.add(log)
    registry.print_count += 1
    safe_commit(db.session, error_message='database commit failed', reraise=True)

    return jsonify(
        {
            'success': True,
            'entity_type': registry.entity_type,
            'entity_id': registry.entity_id,
            'barcode': registry.barcode_value,
        }
    )


@barcode_bp.route('/registry')
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def registry():
    entity_type = request.args.get('entity_type')
    query = BarcodeRegistry.query
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    items = query.order_by(BarcodeRegistry.created_at.desc()).limit(200).all()
    return render_template('barcode/registry.html', items=items)
