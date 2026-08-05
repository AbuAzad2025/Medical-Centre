"""api routes - extracted from monolithic manager.py"""

import logging

# Imports
from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import VisitState
from models.payment import Payment
from models.visit import Visit
from routes.manager import manager_bp
from utils.decorators import (
    role_required,
)

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
        base_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
                Visit.tenant_id == current_user.tenant_id,
            )
        ).scalar()
        capacity_gain = (add_staff * 6) + (add_rooms * 8)
        predicted_throughput = int(base_visits + capacity_gain)
        predicted_wait = max(5, int(30 - (capacity_gain / 2)))
        predicted_revenue = float(
            db.session.execute(
                select(func.sum(Payment.amount)).filter(Payment.tenant_id == current_user.tenant_id)
            ).scalar()
            or 0
        ) * (1 + (capacity_gain / 100))
        return jsonify(
            {
                'success': True,
                'predicted_throughput': predicted_throughput,
                'predicted_wait_minutes': predicted_wait,
                'predicted_revenue': round(predicted_revenue, 2),
            }
        ), 200
    except Exception:
        logging.exception('Error computing what-if: %s')
        return jsonify({'success': False, 'message': 'تعذر احتساب السيناريو'}), 500
