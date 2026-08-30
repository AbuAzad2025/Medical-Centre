"""care routes - extracted from monolithic nurse_routes.py"""

import logging

# Imports
from flask import flash, redirect, render_template, url_for
from flask_login import login_required
from sqlalchemy import desc, select

from app.extensions import db
from models.patient import Patient
from routes.nurse_routes import nurse_bp
from utils.decorators import role_required

# =============================================
# CARE ROUTES
# =============================================


@nurse_bp.route('/patient-care')
@login_required
@role_required('nurse', 'manager')
def patient_care():
    """رعاية المرضى"""

    try:
        from flask_login import current_user

        patients = (
            db.session.execute(
                select(Patient)
                .filter(
                    Patient.tenant_id == current_user.tenant_id
                    if hasattr(Patient, 'tenant_id') and current_user.tenant_id
                    else True
                )
                .order_by(desc(Patient.created_at))
                .limit(20)
            )
            .scalars()
            .all()
        )

        return render_template('nurse/patient_care.html', patients=patients)
    except Exception:
        logging.exception('Error loading patient care: %s')
        flash('حدث خطأ في تحميل رعاية المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))


@nurse_bp.route('/patient-monitoring')
@login_required
@role_required('nurse', 'manager')
def patient_monitoring():
    """مراقبة المرضى"""

    try:
        from flask_login import current_user

        patients = (
            db.session.execute(
                select(Patient)
                .filter(
                    Patient.tenant_id == current_user.tenant_id
                    if hasattr(Patient, 'tenant_id') and current_user.tenant_id
                    else True
                )
                .order_by(desc(Patient.created_at))
                .limit(20)
            )
            .scalars()
            .all()
        )

        return render_template('nurse/patient_monitoring.html', patients=patients)
    except Exception:
        logging.exception('Error loading patient monitoring: %s')
        flash('حدث خطأ في تحميل مراقبة المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))
