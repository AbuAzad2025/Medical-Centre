"""
Two-Factor Authentication Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app_factory import db
from models import UserMFASettings, MFALoginAttempt
import pyotp
import qrcode
import qrcode.image.svg
import io
import base64
import json
import secrets
import hashlib
from datetime import datetime, timezone, timedelta

mfa_bp = Blueprint('mfa', __name__, url_prefix='/mfa')


@mfa_bp.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    mfa = UserMFASettings.query.filter_by(user_id=current_user.id).first()
    if not mfa:
        mfa = UserMFASettings(user_id=current_user.id)
        db.session.add(mfa)
        db.session.commit()

    if mfa.totp_enabled:
        flash('2FA مفعّل بالفعل', 'info')
        return redirect(url_for('mfa.status'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not mfa.totp_secret:
            flash('لم يتم إنشاء سر TOTP. يرجى تحديث الصفحة.', 'danger')
            return redirect(url_for('mfa.setup'))

        totp = pyotp.TOTP(mfa.totp_secret)
        if totp.verify(code, valid_window=1):
            mfa.totp_enabled = True
            mfa.totp_verified = True
            mfa.last_mfa_at = datetime.now(timezone.utc)
            # Generate backup codes
            codes = [secrets.token_hex(4) for _ in range(10)]
            mfa.backup_codes = json.dumps([hashlib.sha256(c.encode()).hexdigest() for c in codes])
            db.session.commit()
            flash('تم تفعيل 2FA بنجاح!', 'success')
            return render_template('mfa/backup_codes.html', codes=codes)
        else:
            flash('الرمز غير صحيح. حاول مرة أخرى.', 'danger')

    # Generate new secret if not exists
    if not mfa.totp_secret:
        mfa.totp_secret = pyotp.random_base32()
        db.session.commit()

    totp = pyotp.TOTP(mfa.totp_secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email or current_user.username,
        issuer_name="Azad Medical"
    )

    # Generate QR code
    factory = qrcode.image.svg.SvgImage
    qr = qrcode.make(provisioning_uri, image_factory=factory)
    buf = io.BytesIO()
    qr.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return render_template('mfa/setup.html', qr_code=qr_b64, secret=mfa.totp_secret)


@mfa_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    user_id = session.get('mfa_pending_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))

    mfa = UserMFASettings.query.filter_by(user_id=user_id).first()
    if not mfa or not mfa.totp_enabled:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        backup_code = request.form.get('backup_code', '').strip()

        success = False
        method = 'totp'

        if code:
            totp = pyotp.TOTP(mfa.totp_secret)
            if totp.verify(code, valid_window=1):
                success = True
        elif backup_code:
            if mfa.backup_codes:
                hashed = hashlib.sha256(backup_code.encode()).hexdigest()
                stored = json.loads(mfa.backup_codes) if mfa.backup_codes else []
                if hashed in stored:
                    success = True
                    method = 'backup'
                    # Remove used code
                    stored.remove(hashed)
                    mfa.backup_codes = json.dumps(stored)

        # Log attempt
        attempt = MFALoginAttempt(
            user_id=user_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string[:255] if request.user_agent else None,
            success=success,
            method=method,
            failure_reason=None if success else 'Invalid code'
        )
        db.session.add(attempt)

        if success:
            mfa.last_mfa_at = datetime.now(timezone.utc)
            db.session.commit()
            session.pop('mfa_pending_user_id', None)
            from flask_login import login_user
            from models import User
            user = User.query.get(user_id)
            login_user(user)
            flash('تم التحقق بنجاح', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            db.session.commit()
            flash('رمز التحقق غير صحيح', 'danger')

    return render_template('mfa/verify.html')


@mfa_bp.route('/status')
@login_required
def status():
    mfa = UserMFASettings.query.filter_by(user_id=current_user.id).first()
    return render_template('mfa/status.html', mfa=mfa)


@mfa_bp.route('/disable', methods=['POST'])
@login_required
def disable():
    mfa = UserMFASettings.query.filter_by(user_id=current_user.id).first()
    if mfa:
        mfa.totp_enabled = False
        mfa.totp_verified = False
        mfa.totp_secret = None
        mfa.backup_codes = None
        db.session.commit()
        flash('تم تعطيل 2FA', 'info')
    return redirect(url_for('mfa.status'))


@mfa_bp.route('/api/check', methods=['POST'])
def api_check():
    """API endpoint for 2FA verification during login flow"""
    data = request.get_json() or {}
    user_id = data.get('user_id') or session.get('mfa_pending_user_id')
    code = data.get('code', '').strip()

    if not user_id or not code:
        return {'success': False, 'error': 'Missing parameters'}, 400

    mfa = UserMFASettings.query.filter_by(user_id=user_id).first()
    if not mfa or not mfa.totp_enabled:
        return {'success': False, 'error': '2FA not enabled'}, 400

    totp = pyotp.TOTP(mfa.totp_secret)
    if totp.verify(code, valid_window=1):
        mfa.last_mfa_at = datetime.now(timezone.utc)
        db.session.commit()
        return {'success': True}
    return {'success': False, 'error': 'Invalid code'}, 401
