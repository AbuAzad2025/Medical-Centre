"""Telemedicine M1 — consultations with self-hosted Jitsi signed rooms.

Room access model:
  - POST /telemedicine/consultations            (doctor) create from visit
  - GET  /telemedicine/consult/<id>?token=...   room page; token REQUIRED and
          must be a valid HS256 JWT naming this consultation + role
  - POST /telemedicine/consult/<id>/start|end   doctor-only transitions
  - POST /telemedicine/consult/<id>/no-show     doctor marks patient absent

Tokens: short-lived (2h), signed with SECRET_KEY, carry consultation_id +
participant role.  A tampered/expired/wrong-id token renders a clean Arabic
error page — never a stack trace.
"""

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from flask import abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from models.consultation import Consultation
from routes.telemedicine_routes import telemedicine_bp
from utils.db_safety import safe_commit

TOKEN_TTL_MINUTES = 120


def _sign_room_token(consultation_id: int, role: str, name: str) -> str:
    """Short-lived HS256 JWT granting access to one consultation room."""
    secret = current_app.config['SECRET_KEY']
    now = datetime.now(UTC)
    payload = {
        'consultation_id': int(consultation_id),
        'role': 'moderator' if role == 'doctor' else 'participant',
        'name': name,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=TOKEN_TTL_MINUTES)).timestamp()),
    }
    return pyjwt.encode(payload, secret, algorithm='HS256')


def _verify_room_token(token: str, consultation_id: int) -> dict:
    if not token or not isinstance(token, str) or not token.strip():
        abort(401, description='رابط الغرفة غير صالح.')
    try:
        payload = pyjwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256'],
            options={'require': ['exp', 'iat', 'consultation_id']},
        )
    except pyjwt.ExpiredSignatureError:
        abort(401, description='انتهت صلاحية رابط الغرفة. اطلب رابطاً جديداً من العيادة.')
    except pyjwt.InvalidTokenError:
        abort(401, description='رابط الغرفة غير صالح.')
    try:
        token_cid = int(payload.get('consultation_id', -1))
    except (TypeError, ValueError):
        abort(401, description='رابط الغرفة غير صالح.')
    if token_cid != int(consultation_id):
        abort(401, description='هذا الرابط يخص غرفة أخرى.')
    return payload


@telemedicine_bp.route('/consultations', methods=['POST'])
@login_required
def create_consultation():
    """Doctor creates a tele-consultation for an existing visit."""
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'message': 'إنشاء الاستشارة متاح للأطباء فقط'}), 403

    data = request.get_json(silent=True) or request.form
    try:
        visit_id = int(data.get('visit_id') or 0)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'رقم الزيارة مطلوب'}), 400
    if not visit_id:
        return jsonify({'success': False, 'message': 'رقم الزيارة مطلوب'}), 400

    from models.visit import Visit

    visit = db.session.get(Visit, visit_id)
    if not visit or visit.tenant_id != getattr(current_user, 'tenant_id', None):
        return jsonify({'success': False, 'message': 'الزيارة غير موجودة'}), 404

    cons = Consultation(
        tenant_id=current_user.tenant_id,
        visit_id=visit.id,
        doctor_id=current_user.id,
        patient_id=visit.patient_id,
        status='SCHEDULED',
        scheduled_at=datetime.now(UTC),
        created_by_id=current_user.id,
    )
    db.session.add(cons)
    safe_commit(db.session, error_message='consultation create failed', reraise=True)

    token = _sign_room_token(cons.id, 'doctor', current_user.full_name or current_user.username)
    return (
        jsonify(
            {
                'success': True,
                'consultation': cons.to_dict(),
                'room_url': f'/telemedicine/consult/{cons.id}?token={token}',
            }
        ),
        201,
    )


@telemedicine_bp.route('/consult/<int:consultation_id>')
@login_required
def consult_room(consultation_id: int):
    """Embedded Jitsi room — requires a valid per-room token."""
    token = request.args.get('token') or ''
    claims = _verify_room_token(token, consultation_id)

    cons = db.session.get(Consultation, consultation_id)
    if not cons or cons.tenant_id != getattr(current_user, 'tenant_id', None):
        abort(404)

    domain = current_app.config.get('TELEMEDICINE_JITSI_DOMAIN', 'meet.jit.si')
    return render_template(
        'telemedicine/consult_room.html',
        cons=cons,
        jitsi_domain=domain,
        room_name=f'mc-{cons.tenant_id}-c{cons.id}',
        jwt_token=token,
        participant_role=claims.get('role'),
        participant_name=claims.get('name'),
    )


def _transition(consultation_id: int, new_status: str, extra=None):
    """Doctor-only lifecycle transition with basic state guards."""
    if current_user.role != 'doctor':
        return jsonify({'success': False, 'message': 'هذا الإجراء متاح للطبيب فقط'}), 403

    cons = db.session.get(Consultation, consultation_id)
    if not cons or cons.tenant_id != getattr(current_user, 'tenant_id', None):
        return jsonify({'success': False, 'message': 'الاستشارة غير موجودة'}), 404

    allowed_from = {
        'LIVE': ('SCHEDULED',),
        'COMPLETED': ('LIVE',),
        'CANCELLED': ('SCHEDULED',),
        'NO_SHOW': ('SCHEDULED', 'LIVE'),
    }.get(new_status, ())

    if cons.status not in allowed_from:
        return (
            jsonify(
                {
                    'success': False,
                    'message': f'لا يمكن تغيير حالة الاستشارة من {cons.status} إلى {new_status}',
                }
            ),
            409,
        )

    cons.status = new_status
    now = datetime.now(UTC)
    if new_status == 'LIVE':
        cons.started_at = now
    elif new_status in ('COMPLETED', 'NO_SHOW', 'CANCELLED'):
        cons.ended_at = now
    if extra:
        for k, v in extra.items():
            setattr(cons, k, v)

    safe_commit(db.session, error_message='consultation transition failed', reraise=True)
    return jsonify({'success': True, 'consultation': cons.to_dict()})


@telemedicine_bp.route('/consult/<int:cid>/start', methods=['POST'])
@login_required
def start_consult(cid):
    return _transition(cid, 'LIVE')


@telemedicine_bp.route('/consult/<int:cid>/end', methods=['POST'])
@login_required
def end_consult(cid):
    notes_val = None
    if request.is_json:
        j = request.get_json(silent=True) or {}
        notes_val = j.get('notes')
    if not notes_val:
        notes_val = request.form.get('notes')
    return _transition(
        cid,
        'COMPLETED',
        extra={'notes': notes_val or None},
    )


@telemedicine_bp.route('/consult/<int:cid>/cancel', methods=['POST'])
@login_required
def cancel_consult(cid):
    return _transition(cid, 'CANCELLED')


@telemedicine_bp.route('/consult/<int:cid>/no-show', methods=['POST'])
@login_required
def no_show_consult(cid):
    return _transition(cid, 'NO_SHOW')
