"""reports routes - extracted from monolithic emergency.py"""

import logging

# Imports
from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app.shared.print_context import generate_qr_data_uri
from routes.emergency import emergency_bp
from services.emergency_service import emergency_service
from utils.decorators import role_required

# =============================================
# REPORTS ROUTES
# =============================================


@emergency_bp.route('/emergency-report/<int:emergency_id>')
@login_required
@role_required('emergency', 'manager')
def emergency_report(emergency_id):
    """تقرير الطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        return render_template('emergency/emergency_report.html', emergency=emergency)
    except Exception:
        logging.exception('Error generating emergency report: %s')
        flash('حدث خطأ في إنشاء تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/print-emergency-report/<int:emergency_id>')
@login_required
@role_required('emergency', 'manager')
def print_emergency_report(emergency_id):
    """طباعة تقرير الطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        qr_data_uri = generate_qr_data_uri(
            f'ER|{emergency.id}|{emergency.patient_id}|{emergency.created_at.isoformat() if emergency.created_at else ""}'
        )
        return render_template(
            'print/emergency_report.html', emergency=emergency, qr_data_uri=qr_data_uri
        )
    except Exception:
        logging.exception('Error printing emergency report: %s')
        flash('حدث خطأ في طباعة تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))


# ==================== الميزات الذكية للطوارئ ====================
