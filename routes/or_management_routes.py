"""
Operating Room Management Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.or_management import SurgerySchedule, SurgeryChecklist
from models.patient import Patient
from models.user import User
from models.icd_coding import CPTCode, ICD10Code
from app_factory import db

or_bp = Blueprint('or', __name__)


@or_bp.route('/schedule')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def schedule():
    date = request.args.get('date')
    status = request.args.get('status', 'SCHEDULED')
    query = SurgerySchedule.query
    if status:
        query = query.filter_by(status=status)
    if date:
        from datetime import datetime
        try:
            d = datetime.strptime(date, '%Y-%m-%d').date()
            query = query.filter(SurgerySchedule.scheduled_date == d)
        except ValueError:
            pass
    surgeries = query.order_by(SurgerySchedule.scheduled_date, SurgerySchedule.scheduled_start_time).limit(100).all()
    return render_template('or/schedule.html', surgeries=surgeries, status=status)

@or_bp.route('/surgery/<int:surgery_id>')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def surgery_detail(surgery_id):
    surgery = SurgerySchedule.query.get_or_404(surgery_id)
    checklist = SurgeryChecklist.query.filter_by(surgery_schedule_id=surgery_id).first()
    return render_template('or/surgery_detail.html', surgery=surgery, checklist=checklist)
