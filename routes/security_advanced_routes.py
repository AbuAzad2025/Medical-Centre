"""
Advanced Security Routes
Digital signatures, password policy, session management, encryption
"""

import logging
from datetime import UTC, datetime

from flask import Blueprint, abort, jsonify, render_template, request, session
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.digital_signature import DigitalSignature, PasswordPolicy, SessionLog
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import TenantContextError, get_tenant_record

security_bp = Blueprint('security', __name__)


@security_bp.route('/signatures')
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def signatures():
    user_id = request.args.get('user_id', type=int)
    if user_id and user_id != current_user.id:
        if current_user.role not in ['admin', 'manager']:
            abort(404)
        try:
            from models.user import User

            get_tenant_record(User, user_id)
        except TenantContextError:
            abort(404)
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
    items = (
        db.session.execute(select(SessionLog).order_by(SessionLog.login_at.desc()).limit(200))
        .scalars()
        .all()
    )
    return render_template('security/sessions.html', sessions=items)


@security_bp.route('/sessions/terminate-others', methods=['POST'])
@login_required
@handle_route_errors
def terminate_other_sessions():
    """Terminate all active sessions for the current user except the current one."""
    try:
        current_sid = session.get('_id') or request.headers.get('X-Session-Id', '')
        rows = (
            db.session.execute(
                select(SessionLog).filter_by(
                    user_id=current_user.id,
                    is_active=True,
                    tenant_id=getattr(current_user, 'tenant_id', None),
                )
            )
            .scalars()
            .all()
        )
        terminated = 0
        for s in rows:
            if s.session_id and s.session_id != str(current_sid):
                s.is_active = False
                s.terminated_by = 'USER'
                s.logout_at = datetime.now(UTC)
                terminated += 1
        safe_commit(db.session)

        # The SessionLog rows record that each session ended, but nothing
        # recorded that the user ended it. A revocation and an expiry then look
        # identical, which is exactly the distinction an investigator is
        # looking for after a suspected compromise.
        try:
            from models.audit_trail import AuditTrail

            db.session.add(
                AuditTrail(
                    entity_type='user_session',
                    entity_id=current_user.id,
                    tenant_id=getattr(current_user, 'tenant_id', None),
                    action='TERMINATE_OTHER_SESSIONS',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description=f'إنهاء {terminated} جلسة نشطة',
                    new_values=str(terminated),
                )
            )
            safe_commit(db.session, error_message='audit commit failed', reraise=True)
        except Exception:
            # The sessions are already terminated and committed. Report that
            # failure to the log rather than to the caller, who would otherwise
            # retry a lock-out that already happened.
            logging.exception('Terminate-sessions audit write failed')

        return jsonify({'success': True, 'terminated': terminated})
    except Exception as e:
        safe_rollback(db.session)
        return jsonify({'success': False, 'message': str(e)}), 500


@security_bp.route('/password-policy')
@login_required
@role_required('admin')
@handle_route_errors
def password_policy():
    policy = db.session.execute(select(PasswordPolicy).filter_by(is_active=True)).scalars().first()
    return render_template('security/password_policy.html', policy=policy)
