"""api routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from services.manager_service import manager_service
from app_factory import db
from app.shared.enums import VisitState
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# API ROUTES
# =============================================

@manager_bp.route('/api/what-if', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def api_what_if():
    try:
        data = request.get_json(silent=True) or {}
        add_staff = int(data.get('add_staff') or 0)
        add_rooms = int(data.get('add_rooms') or 0)
        base_visits = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])).count()
        capacity_gain = (add_staff * 6) + (add_rooms * 8)
        predicted_throughput = int(base_visits + capacity_gain)
        predicted_wait = max(5, int(30 - (capacity_gain / 2)))
        predicted_revenue = float(db.session.query(func.sum(Payment.amount)).scalar() or 0) * (1 + (capacity_gain / 100))
        return jsonify({
            'success': True,
            'predicted_throughput': predicted_throughput,
            'predicted_wait_minutes': predicted_wait,
            'predicted_revenue': round(predicted_revenue, 2)
        }), 200
    except Exception as e:
        logging.error(f"Error computing what-if: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر احتساب السيناريو'}), 500
