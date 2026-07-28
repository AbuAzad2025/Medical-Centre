"""
Advanced Security Routes
Digital signatures, password policy, session management, encryption
"""
from sqlalchemy import select
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from utils.decorators import handle_route_errors, role_required
from flask_login import login_required, current_user
from models.digital_signature import DigitalSignature, PasswordPolicy, SessionLog, EncryptedField
from models.user import User
from app.extensions import db

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
    items = db.session.execute(select(SessionLog).order_by(SessionLog.login_at.desc()).limit(200)).scalars().all()
    return render_template('security/sessions.html', sessions=items)


@security_bp.route('/sessions/terminate-others', methods=['POST'])
@login_required
@handle_route_errors
def terminate_other_sessions():
    """Terminate all active sessions for the current user except the current one."""
    try:
        current_sid = session.get('_id') or request.headers.get('X-Session-Id', '')
        rows = db.session.execute(
            select(SessionLog).filter_by(
                user_id=current_user.id,
                is_active=True,
                tenant_id=getattr(current_user, 'tenant_id', None),
            )
        ).scalars().all()
        terminated = 0
        for s in rows:
            if s.session_id and s.session_id != str(current_sid):
                s.is_active = False
                s.terminated_by = 'USER'
                s.logout_at = datetime.now(timezone.utc)
                terminated += 1
        db.session.commit()
        return jsonify({'success': True, 'terminated': terminated})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@security_bp.route('/password-policy')
@login_required
@role_required('admin')
@handle_route_errors
def password_policy():
    policy = db.session.execute(select(PasswordPolicy).filter_by(is_active=True)).scalars().first()
    return render_template('security/password_policy.html', policy=policy)
