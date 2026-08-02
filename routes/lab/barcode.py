"""Lab barcode scan and print routes."""

from datetime import UTC, datetime

from flask import g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.barcode_tracking import BarcodeRegistry, BarcodeScanLog
from models.lab_request import LabRequest
from routes.lab import lab_bp
from services.barcode_service import generate_lab_barcode, register_in_barcode_registry
from utils.db_safety import safe_commit
from utils.decorators import role_required


@lab_bp.route('/barcode/scan/<barcode>', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'technician', 'nurse', 'admin')
def barcode_scan(barcode):
    """Scan a barcode — lookup LabRequest, log scan, optionally update status."""
    lab_request = (
        db.session.execute(select(LabRequest).filter_by(barcode=barcode)).scalars().first()
    )

    if request.method == 'GET':
        if lab_request:
            return redirect(url_for('lab.worklist_request', request_id=lab_request.id))
        return jsonify({'success': False, 'message': 'الباركود غير مرتبط بطلب مختبر'}), 404

    # POST: process scan
    data = request.get_json(force=True, silent=True) or {}
    action = data.get('action', 'COLLECT').upper()

    if not lab_request:
        return jsonify({'success': False, 'message': 'لم يتم العثور على طلب'}), 404

    registry = (
        db.session.execute(
            select(BarcodeRegistry).filter_by(
                barcode_value=barcode, entity_type='SPECIMEN', is_active=True
            )
        )
        .scalars()
        .first()
    )

    scan_log = BarcodeScanLog(
        barcode_registry_id=registry.id if registry else None,
        scan_action=action,
        scanned_by_id=current_user.id,
        location=data.get('location'),
        verification_result='SUCCESS',
        ip_address=request.remote_addr,
    )
    db.session.add(scan_log)

    if action == 'COLLECT' and lab_request.status == 'REQUESTED':
        lab_request.status = 'COLLECTED'
        lab_request.collection_time = datetime.now(UTC)
    elif action == 'RECEIVE' and lab_request.status == 'COLLECTED':
        lab_request.status = 'RECEIVED'
        lab_request.received_time = datetime.now(UTC)

    lab_request.updated_at = datetime.now(UTC)
    safe_commit(db.session, error_message='database commit failed', reraise=True)

    return jsonify(
        {
            'success': True,
            'request_id': lab_request.id,
            'status': lab_request.status,
        }
    )


@lab_bp.route('/barcode/print/<int:request_id>')
@login_required
@role_required('lab', 'technician', 'nurse', 'admin')
def barcode_print(request_id):
    """Show a print page with the barcode QR image."""
    lab_request = (
        db.session.execute(
            select(LabRequest).filter(
                LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
            )
        )
        .scalars()
        .first()
    )
    if not lab_request:
        return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404

    if not lab_request.barcode_image:
        barcode_val, b64_img = generate_lab_barcode(lab_request.id, lab_request.patient_id)
        lab_request.barcode = barcode_val
        lab_request.barcode_image = b64_img
        register_in_barcode_registry(
            barcode_value=barcode_val,
            lab_request_id=lab_request.id,
            generated_by_id=current_user.id,
            tenant_id=getattr(current_user, 'tenant_id', None),
        )
        safe_commit(db.session, error_message='database commit failed', reraise=True)

    return render_template('lab/barcode_print.html', lab_request=lab_request)
