"""api routes - extracted from monolithic emergency.py"""

import logging
from datetime import datetime

# Imports
from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.emergency import EmergencyCase
from models.patient import Patient
from routes.emergency import emergency_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required_json

# =============================================
# API ROUTES
# =============================================


@emergency_bp.route('/api/ems/intake', methods=['POST'])
@login_required
@role_required_json('emergency', 'admin', 'manager')
def api_ems_intake():
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('patient_name') or '').strip()
        phone = (data.get('phone') or '').strip()
        complaint = (data.get('chief_complaint') or '').strip() or 'غير محدد'
        severity = (data.get('severity') or 'MODERATE').upper()
        if not name:
            return jsonify({'success': False, 'message': 'اسم المريض مطلوب'}), 400
        parts = [p for p in name.split(' ') if p]
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else '-'
        patient = None
        if phone:
            patient = db.session.execute(select(Patient).filter_by(phone=phone)).scalars().first()
        if not patient:
            patient = Patient(first_name=first_name, last_name=last_name, phone=phone or None)
            db.session.add(patient)
            db.session.flush()
        case = EmergencyCase(
            patient_id=patient.id,
            case_number=f'EMS-{int(datetime.now().timestamp())}',
            chief_complaint=complaint,
            severity=severity,
            status='WAITING',
        )
        db.session.add(case)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'case_id': case.id}), 201
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception("EMS intake error: %s")
        return jsonify({'success': False, 'message': 'تعذر تسجيل الحالة'}), 500
