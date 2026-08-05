"""quality routes - extracted from monolithic radiology.py"""

import logging
from datetime import UTC, date, datetime

# Imports
from flask import (
    g,
    jsonify,
    render_template,
    request,
)
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import OrderState, RadiologyResultStatus
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from routes.radiology import radiology_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

# =============================================
# QUALITY ROUTES
# =============================================


@radiology_bp.route('/quality')
@login_required
@role_required('radiology', 'admin', 'manager')
def quality():
    start_raw = (request.args.get('start_date') or '').strip()
    end_raw = (request.args.get('end_date') or '').strip()
    try:
        start_date = (
            datetime.strptime(start_raw, '%Y-%m-%d').date()
            if start_raw
            else (date.today().replace(day=1))
        )
    except Exception:
        start_date = date.today().replace(day=1)
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
    except Exception:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)

    from sqlalchemy import func

    total_done = db.session.scalar(select(func.count()).select_from(RadiologyRequest))

    try:
        avg_tat_seconds = db.session.execute(
            select(
                db.func.avg(
                    db.func.extract('epoch', RadiologyRequest.updated_at)
                    - db.func.extract('epoch', RadiologyRequest.created_at)
                )
            ).filter(
                RadiologyRequest.status == OrderState.DONE,
                RadiologyRequest.updated_at >= start_dt,
                RadiologyRequest.updated_at <= end_dt,
            )
        ).scalar()
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        avg_tat_seconds = None
    avg_tat_minutes = float(avg_tat_seconds or 0) / 60.0 if avg_tat_seconds is not None else 0.0

    total_validated_results = (
        db.session.execute(
            select(db.func.count(RadiologyResult.id))
            .join(RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id)
            .filter(
                RadiologyRequest.status == OrderState.DONE,
                RadiologyRequest.updated_at >= start_dt,
                RadiologyRequest.updated_at <= end_dt,
                RadiologyResult.status == RadiologyResultStatus.VALIDATED,
            )
        ).scalar()
        or 0
    )

    critical_validated_results = (
        db.session.execute(
            select(db.func.count(RadiologyResult.id))
            .join(RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id)
            .filter(
                RadiologyRequest.status == OrderState.DONE,
                RadiologyRequest.updated_at >= start_dt,
                RadiologyRequest.updated_at <= end_dt,
                RadiologyResult.status == RadiologyResultStatus.VALIDATED,
                RadiologyResult.is_critical,
            )
        ).scalar()
        or 0
    )

    critical_ratio = (
        (float(critical_validated_results) / float(total_validated_results))
        if total_validated_results
        else 0.0
    )

    modality_rows = []
    try:
        rows = (
            db.session.execute(
                select(
                    db.func.upper(RadiologyRequest.modality).label('modality'),
                    db.func.count(RadiologyRequest.id).label('cnt'),
                    db.func.avg(
                        db.func.extract('epoch', RadiologyRequest.updated_at)
                        - db.func.extract('epoch', RadiologyRequest.created_at)
                    ).label('avg_sec'),
                )
                .filter(
                    RadiologyRequest.status == OrderState.DONE,
                    RadiologyRequest.updated_at >= start_dt,
                    RadiologyRequest.updated_at <= end_dt,
                )
                .group_by(db.func.upper(RadiologyRequest.modality))
                .order_by(db.func.count(RadiologyRequest.id).desc())
            )
            .scalars()
            .all()
        )
        for r in rows:
            modality_rows.append(
                {
                    'modality': (r.modality or 'N/A'),
                    'count': int(r.cnt or 0),
                    'avg_minutes': float(r.avg_sec or 0) / 60.0,
                }
            )
    except Exception:
        modality_rows = []

    return render_template(
        'radiology/quality.html',
        start_date=start_date,
        end_date=end_date,
        total_done=total_done,
        avg_tat_minutes=avg_tat_minutes,
        total_validated_results=int(total_validated_results),
        critical_validated_results=int(critical_validated_results),
        critical_ratio=critical_ratio,
        modality_rows=modality_rows,
    )


@radiology_bp.route('/api/ai-assist', methods=['POST'])
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
def api_ai_assist():
    try:
        data = request.get_json(silent=True) or {}
        modality = (data.get('modality') or '').strip().upper()
        body_part = (data.get('body_part') or '').strip().lower()
        impression = (data.get('impression') or '').strip().lower()
        study_uid = (data.get('study_uid') or '').strip()
        pacs_url = (data.get('pacs_url') or '').strip()

        suggestions = []
        if modality == 'CT' and ('brain' in body_part or 'دماغ' in body_part):
            suggestions.append('تقييم نزف حاد أو كتلة داخل القحف إذا كانت الأعراض مناسبة.')
        if modality in {'XRAY', 'X-RAY', 'XR'} and ('chest' in body_part or 'صدر' in body_part):
            suggestions.append('تأكد من مراجعة علامات الارتشاح الرئوي والانصباب الجنبي.')
        if modality == 'US' and ('abdomen' in body_part or 'بطن' in body_part):
            suggestions.append('راجع المرارة والكبد والكلى بحثاً عن مؤشرات انسداد.')
        if 'نزف' in impression or 'bleed' in impression:
            suggestions.append('النتيجة توحي بخطورة محتملة، يوصى بإبلاغ الطبيب فوراً.')
        if not suggestions:
            suggestions.append('لا توجد توصيات آلية واضحة، يرجى ربط النتائج بالسياق السريري.')

        payload = {
            'suggestions': suggestions,
            'disclaimer': 'مخرجات مساعدة وليست تشخيصاً نهائياً.',
            'external_ref': pacs_url or (f'study:{study_uid}' if study_uid else None),
        }
        return jsonify({'success': True, 'data': payload}), 200
    except Exception:
        logging.exception('Error generating radiology AI assist: %s')
        return jsonify({'success': False, 'message': 'تعذر توليد توصيات AI'}), 500


@radiology_bp.route('/results/<int:result_id>/second-review', methods=['POST'])
@login_required
@role_required('radiology', 'admin', 'manager', 'super_admin')
def second_review_result(result_id):
    try:
        from models.radiology_result import RadiologyResult

        res = (
            db.session.execute(
                select(RadiologyResult).filter(
                    RadiologyResult.id == result_id, RadiologyResult.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )
        if not res:
            return jsonify({'success': False, 'message': 'النتيجة غير موجودة'}), 404
        res.reviewed_by = current_user.id
        res.reviewed_at = datetime.now(UTC)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True}), 200
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Second review radiology result error: %s')
        return jsonify({'success': False, 'message': 'تعذر حفظ المراجعة حالياً'}), 500
