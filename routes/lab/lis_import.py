"""LIS import endpoints — manual CSV upload (preview → confirm).

Two-step flow keeps a human in the loop:
  1) POST /lab/lis/preview   → parse + map; returns matches & unmatched queue
  2) POST /lab/lis/confirm   → writes ONLY the confirmed matched rows
"""

from flask import jsonify, request
from flask_login import current_user, login_required

from routes.lab import lab_bp
from services.lis_import_service import (
    LISImportError,
    import_results,
    map_rows,
    parse_csv,
)
from utils.decorators import role_required


@lab_bp.route('/lis/preview', methods=['POST'])
@login_required
@role_required('lab', 'admin', 'super_admin', 'manager')
def lis_preview():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'success': False, 'message': 'اختر ملف CSV أولاً'}), 400

    try:
        parsed = parse_csv(file.read())
        mapping = map_rows(parsed['rows'])
    except LISImportError as e:
        code = str(e)
        msg = {
            'encoding': 'الملف يجب أن يكون بترميز UTF-8',
            'empty_file': 'الملف فارغ',
            'missing_header': 'ترويسة الملف غير صحيحة',
        }.get(code, 'بنية الملف غير صحيحة')
        if code.startswith('missing_columns:'):
            cols = code.split(':', 1)[1].replace(',', ' و ')
            msg = f'أعمدة إلزامية مفقودة في الترويسة: {cols}'
        return jsonify({'success': False, 'message': msg}), 400

    return jsonify(
        {
            'success': True,
            'matched': mapping['matched'],
            'unmatched': mapping['unmatched'],
            'parse_errors': parsed['errors'],
            'confirmable': len(mapping['matched']) > 0,
        }
    )


@lab_bp.route('/lis/confirm', methods=['POST'])
@login_required
@role_required('lab', 'admin', 'super_admin', 'manager')
def lis_confirm():
    payload = request.get_json(silent=True) or {}
    rows = payload.get('rows') or []
    if not rows:
        return jsonify({'success': False, 'message': 'لا توجد صفوف مؤكدة للاستيراد'}), 400

    if any('catalog' not in r for r in rows):
        mapping = map_rows(rows)
        rows = mapping['matched']

    result = import_results(rows, performed_by=current_user.id)
    skipped_n = len(result.get('skipped') or [])
    msg = f'تم استيراد {result["imported_count"]} نتيجة'
    if result['duplicates_count']:
        msg += f' (تجاهُل {result["duplicates_count"]} مكررة)'
    if skipped_n:
        msg += f' — {skipped_n} صف بدون رقم طلب تم تجاهله'

    return jsonify(
        {'success': True, 'message': msg, **{k: v for k, v in result.items() if k != 'skipped'}}
    )
