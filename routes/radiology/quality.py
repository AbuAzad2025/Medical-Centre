"""quality routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_test import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app_factory import db
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


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
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today().replace(day=1))
    except Exception:
        start_date = date.today().replace(day=1)
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
    except Exception:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    done_q = RadiologyRequest.query.filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt
    )
    total_done = done_q.count()

    try:
        avg_tat_seconds = db.session.query(
            db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
        ).filter(
            RadiologyRequest.status == 'DONE',
            RadiologyRequest.updated_at >= start_dt,
            RadiologyRequest.updated_at <= end_dt
        ).scalar()
    except Exception:
        db.session.rollback()
        avg_tat_seconds = None
    avg_tat_minutes = float(avg_tat_seconds or 0) / 60.0 if avg_tat_seconds is not None else 0.0

    total_validated_results = db.session.query(db.func.count(RadiologyResult.id)).join(
        RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id
    ).filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt,
        RadiologyResult.status == 'VALIDATED'
    ).scalar() or 0

    critical_validated_results = db.session.query(db.func.count(RadiologyResult.id)).join(
        RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id
    ).filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt,
        RadiologyResult.status == 'VALIDATED',
        RadiologyResult.is_critical == True
    ).scalar() or 0

    critical_ratio = (float(critical_validated_results) / float(total_validated_results)) if total_validated_results else 0.0

    modality_rows = []
    try:
        rows = db.session.query(
            db.func.upper(RadiologyRequest.modality).label('modality'),
            db.func.count(RadiologyRequest.id).label('cnt'),
            db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at)).label('avg_sec'),
        ).filter(
            RadiologyRequest.status == 'DONE',
            RadiologyRequest.updated_at >= start_dt,
            RadiologyRequest.updated_at <= end_dt
        ).group_by(db.func.upper(RadiologyRequest.modality)).order_by(db.func.count(RadiologyRequest.id).desc()).all()
        for r in rows:
            modality_rows.append({
                'modality': (r.modality or 'N/A'),
                'count': int(r.cnt or 0),
                'avg_minutes': float(r.avg_sec or 0) / 60.0
            })
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
        modality_rows=modality_rows
    )

@radiology_bp.route('/api/ai-assist', methods=['POST'])
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
def api_ai_assist():
    try:
        data = request.get_json() or {}
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
            'external_ref': pacs_url or (f"study:{study_uid}" if study_uid else None)
        }
        return jsonify({'success': True, 'data': payload}), 200
    except Exception as e:
        logging.error(f"Error generating radiology AI assist: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر توليد توصيات AI'}), 500


@radiology_bp.route('/results/<int:result_id>/second-review', methods=['POST'])
@login_required
@role_required('radiology', 'admin', 'manager', 'super_admin')
def second_review_result(result_id):
    try:
        from models.radiology_test import RadiologyResult
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'success': False, 'message': 'النتيجة غير موجودة'}), 404
        res.reviewed_by = current_user.id
        res.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Second review radiology result error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر حفظ المراجعة حالياً'}), 500
