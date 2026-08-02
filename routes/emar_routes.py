"""
eMAR — Electronic Medication Administration Record Routes
"""

from datetime import UTC, date, datetime

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import eMARAdministrationStatus
from models.emar import eMARAdministration
from models.patient import Patient
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

emar_bp = Blueprint('emar', __name__)


@emar_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def dashboard():
    today = date.today()
    administrations = (
        db.session.execute(
            select(eMARAdministration)
            .filter(db.func.date(eMARAdministration.scheduled_time) == today)
            .order_by(eMARAdministration.scheduled_time)
        )
        .scalars()
        .all()
    )
    pending = [a for a in administrations if a.status == eMARAdministrationStatus.SCHEDULED]
    given = [a for a in administrations if a.status == 'GIVEN']
    return render_template(
        'emar/dashboard.html',
        administrations=administrations,
        pending=pending,
        given=given,
        today=today,
    )


@emar_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin')
@handle_route_errors
def patient_mar(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    administrations = (
        db.session.execute(
            select(eMARAdministration)
            .filter_by(patient_id=patient_id)
            .order_by(eMARAdministration.scheduled_time.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return render_template(
        'emar/patient_mar.html', patient=patient, administrations=administrations
    )


@emar_bp.route('/administer/<int:admin_id>', methods=['POST'])
@login_required
@role_required('nurse', 'admin')
@handle_route_errors
def administer(admin_id):
    admin = db.get_or_404(eMARAdministration, admin_id)
    admin.status = 'GIVEN'
    admin.administered_time = datetime.now(UTC)
    admin.nurse_id = current_user.id
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    flash('تم تسجيل إعطاء الدواء بنجاح', 'success')
    return redirect(url_for('emar.dashboard'))
