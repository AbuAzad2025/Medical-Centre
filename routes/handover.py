"""Shift handover UI/API routes — open, close/transfer, acknowledge, list."""

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from services.shift_handover_service import HandoverError, ShiftHandoverService

handover_bp = Blueprint('handover', __name__)


def _err(e: HandoverError):
    """Map stable machine codes to Arabic operator-facing messages."""
    msg = {
        'role_required': 'حدد دور الشيفت',
        'already_open': 'يوجد شيفت مفتوح بالفعل لهذا الدور — يجب إغلاقه أولاً',
        'not_found': 'الشيفت غير موجود',
        'not_open': 'هذا الشيفت ليس مفتوحاً',
        'not_closed': 'لا يمكن التأكيد إلا على شيفت مغلق',
        'invalid_target': 'المستلم غير موجود أو غير مفعل',
        'role_mismatch': 'يجب أن يكون المستملّم من نفس دور الشيفت',
        'cash_diff_requires_note': 'يوجد فرق في الصندوق — اكتب سبباً في ملاحظة الإغلاق قبل المتابعة',
        'not_assignee': 'التأكيد متاح للمستلم المعيّن فقط',
    }.get(str(e), 'حدث خطأ أثناء معالجة الشيفت')
    return jsonify({'success': False, 'message': msg}), 400


@handover_bp.route('/', methods=['GET'])
@login_required
def handover_dashboard():
    shifts = ShiftHandoverService.list_shifts()
    return render_template('shift_handover/dashboard.html', shifts=shifts)


@handover_bp.route('/open', methods=['POST'])
@login_required
def handover_open():
    data = request.get_json(silent=True) or request.form
    try:
        result = ShiftHandoverService.open_shift(
            user_id=current_user.id,
            role=(data.get('role') or '').strip(),
            to_user_id=int(data['to_user_id']) if data.get('to_user_id') else None,
            notes=(data.get('notes') or '').strip(),
        )
    except (HandoverError, ValueError) as e:
        return (
            _err(e)
            if isinstance(e, HandoverError)
            else (jsonify({'success': False, 'message': 'بيانات غير صحيحة'}), 400)
        )
    return jsonify({'success': True, 'shift': result})


@handover_bp.route('/<int:shift_id>/close', methods=['POST'])
@login_required
def handover_close(shift_id: int):
    data = request.get_json(silent=True) or request.form
    to_user = data.get('to_user_id')
    try:
        result = ShiftHandoverService.close_shift(
            shift_id=shift_id,
            user_id=current_user.id,
            close_note=(data.get('close_note') or '').strip(),
            to_user_id=int(to_user) if to_user else None,
        )
    except (HandoverError, ValueError) as e:
        return (
            _err(e)
            if isinstance(e, HandoverError)
            else (jsonify({'success': False, 'message': 'بيانات غير صحيحة'}), 400)
        )
    return jsonify({'success': True, 'message': 'تم إغلاق الشيفت وتجميد اللقطات', 'shift': result})


@handover_bp.route('/<int:shift_id>/acknowledge', methods=['POST'])
@login_required
def handover_acknowledge(shift_id: int):
    try:
        result = ShiftHandoverService.acknowledge(shift_id, user_id=current_user.id)
    except HandoverError as e:
        return _err(e)
    return jsonify({'success': True, 'message': 'تم استلام الشيفت وتأكيده', 'shift': result})
