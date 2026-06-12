"""
Biometric Authentication (WebAuthn/FIDO2) Routes
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app_factory import db
from models import BiometricCredential, BiometricAuthChallenge
from datetime import datetime, timezone, timedelta
import secrets

biometric_bp = Blueprint('biometric', __name__, url_prefix='/biometric')


@biometric_bp.route('/')
@login_required
def status():
    credentials = BiometricCredential.query.filter_by(user_id=current_user.id).all()
    return render_template('biometric/status.html', credentials=credentials)


@biometric_bp.route('/register-challenge', methods=['POST'])
@login_required
def register_challenge():
    challenge = secrets.token_urlsafe(32)
    ch = BiometricAuthChallenge(
        user_id=current_user.id,
        challenge=challenge,
        challenge_type='registration',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db.session.add(ch)
    db.session.commit()
    return jsonify({
        'challenge': challenge,
        'rp_name': 'Azad Medical',
        'rp_id': request.host.split(':')[0],
        'user_id': str(current_user.id),
        'user_name': current_user.username
    })


@biometric_bp.route('/register-complete', methods=['POST'])
@login_required
def register_complete():
    data = request.get_json() or {}
    cred = BiometricCredential(
        user_id=current_user.id,
        credential_id=data.get('credential_id', ''),
        public_key=data.get('public_key', ''),
        device_type=data.get('device_type', 'security_key'),
        device_name=data.get('device_name', 'Unknown Device')
    )
    db.session.add(cred)
    db.session.commit()
    return jsonify({'success': True})


@biometric_bp.route('/authenticate-challenge', methods=['POST'])
def authenticate_challenge():
    challenge = secrets.token_urlsafe(32)
    ch = BiometricAuthChallenge(
        challenge=challenge,
        challenge_type='authentication',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    db.session.add(ch)
    db.session.commit()
    return jsonify({'challenge': challenge})


@biometric_bp.route('/remove/<int:cred_id>', methods=['POST'])
@login_required
def remove_credential(cred_id):
    cred = BiometricCredential.query.filter_by(id=cred_id, user_id=current_user.id).first_or_404()
    db.session.delete(cred)
    db.session.commit()
    return jsonify({'success': True})
