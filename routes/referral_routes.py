"""
Referral Management Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.referral import Referral
from models.patient import Patient
from app_factory import db

referral_bp = Blueprint('referral', __name__)

@referral_bp.route('/list')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager', 'receptionist')
def list_referrals():
    status = request.args.get('status', 'PENDING')
    items = Referral.query.filter_by(status=status).order_by(
        Referral.created_at.desc()
    ).limit(200).all()
    return render_template('referral/list.html', referrals=items, status=status)

@referral_bp.route('/detail/<int:referral_id>')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
def detail(referral_id):
    ref = Referral.query.get_or_404(referral_id)
    return render_template('referral/detail.html', referral=ref)
