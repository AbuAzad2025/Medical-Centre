"""
Referral Management Routes
"""

from flask import Blueprint, render_template, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.referral import Referral
from utils.decorators import handle_route_errors, role_required

referral_bp = Blueprint('referral', __name__)


@referral_bp.route('/list')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager', 'receptionist')
@handle_route_errors
def list_referrals():
    status = request.args.get('status', 'PENDING')
    items = (
        db.session.execute(
            select(Referral)
            .filter_by(status=status)
            .order_by(Referral.created_at.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return render_template('referral/list.html', referrals=items, status=status)


@referral_bp.route('/detail/<int:referral_id>')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def detail(referral_id):
    ref = db.get_or_404(Referral, referral_id)
    return render_template('referral/detail.html', referral=ref)
