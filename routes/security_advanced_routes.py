"""
Advanced Security Routes
Digital signatures, password policy, session management, encryption
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from utils.decorators import handle_route_errors, role_required
from flask_login import login_required, current_user
from models.digital_signature import DigitalSignature, PasswordPolicy, SessionLog, EncryptedField
from models.user import User
from app_factory import db

security_bp = Blueprint('security', __name__)

@security_bp.route('/signatures')
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def signatures():
    user_id = request.args.get('user_id', type=int)
    query = DigitalSignature.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    items = query.order_by(DigitalSignature.signed_at.desc()).limit(200).all()
    return render_template('security/signatures.html', signatures=items)

@security_bp.route('/sessions')
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def sessions():
    items = SessionLog.query.order_by(SessionLog.login_at.desc()).limit(200).all()
    return render_template('security/sessions.html', sessions=items)

@security_bp.route('/password-policy')
@login_required
@role_required('admin')
@handle_route_errors
def password_policy():
    policy = PasswordPolicy.query.filter_by(is_active=True).first()
    return render_template('security/password_policy.html', policy=policy)
