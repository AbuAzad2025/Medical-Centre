"""
Biometric Authentication (WebAuthn/FIDO2) Routes
"""

import secrets
from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.core.rate_limiter import rate_limit
from app.extensions import db
from models import BiometricAuthChallenge, BiometricCredential
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

biometric_bp = Blueprint('biometric', __name__)


@biometric_bp.route('/')
@login_required
@role_required(
    'admin',
    'manager',
    'doctor',
    'nurse',
    'lab_tech',
    'radiology',
    'pharmacist',
    'reception',
    'accountant',
    'super_admin',
)
@handle_route_errors
def status():
    credentials = (
        db.session.execute(select(BiometricCredential).filter_by(user_id=current_user.id))
        .scalars()
        .all()
    )
    return render_template('biometric/status.html', credentials=credentials)


@biometric_bp.route('/register-challenge', methods=['POST'])
@login_required
@role_required(
    'admin',
    'manager',
    'doctor',
    'nurse',
    'lab_tech',
    'radiology',
    'pharmacist',
    'reception',
    'accountant',
    'super_admin',
)
@handle_route_errors
def register_challenge():
    challenge = secrets.token_urlsafe(32)
    ch = BiometricAuthChallenge(
        user_id=current_user.id,
        challenge=challenge,
        challenge_type='registration',
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.session.add(ch)
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    return jsonify(
        {
            'challenge': challenge,
            'rp_name': 'Azad Medical',
            'rp_id': request.host.split(':')[0],
            'user_id': str(current_user.id),
            'user_name': current_user.username,
        }
    )


@biometric_bp.route('/register-complete', methods=['POST'])
@login_required
@role_required(
    'admin',
    'manager',
    'doctor',
    'nurse',
    'lab_tech',
    'radiology',
    'pharmacist',
    'reception',
    'accountant',
    'super_admin',
)
@handle_route_errors
def register_complete():
    data = request.get_json() or {}
    cred = BiometricCredential(
        user_id=current_user.id,
        credential_id=data.get('credential_id', ''),
        public_key=data.get('public_key', ''),
        device_type=data.get('device_type', 'security_key'),
        device_name=data.get('device_name', 'Unknown Device'),
    )
    db.session.add(cred)
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    return jsonify({'success': True})


@biometric_bp.route('/authenticate-challenge', methods=['POST'])
# Intentionally public — used in initial biometric auth flow before user login
# Protected by rate limiting to prevent abuse
@rate_limit(max_requests=10, window_seconds=3600, namespace='biometric_auth')
@handle_route_errors
def authenticate_challenge():
    challenge = secrets.token_urlsafe(32)
    ch = BiometricAuthChallenge(
        challenge=challenge,
        challenge_type='authentication',
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.session.add(ch)
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    return jsonify({'challenge': challenge})


@biometric_bp.route('/remove/<int:cred_id>', methods=['POST'])
@login_required
@role_required(
    'admin',
    'manager',
    'doctor',
    'nurse',
    'lab_tech',
    'radiology',
    'pharmacist',
    'reception',
    'accountant',
    'super_admin',
)
@handle_route_errors
def remove_credential(cred_id):
    cred = select(BiometricCredential).filter_by(id=cred_id, user_id=current_user.id)
    db.session.delete(cred)
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    return jsonify({'success': True})
