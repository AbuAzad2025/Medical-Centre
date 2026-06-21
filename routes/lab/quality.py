"""quality routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from services.lab_service import lab_service
from app_factory import db
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# QUALITY ROUTES
# =============================================

@lab_bp.route('/quality')
@login_required
@role_required('lab', 'admin', 'manager')
def quality():
    start_raw = (request.args.get('start_date') or '').strip()
    end_raw = (request.args.get('end_date') or '').strip()
    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
    except Exception:
        start_date = date.today() - timedelta(days=30)
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
    except Exception:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    done_requests_q = LabRequest.query.filter(
        LabRequest.status == OrderState.DONE,
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt
    )

    total_done_requests = done_requests_q.count()

    try:
        avg_tat_seconds = db.session.query(
            db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
        ).filter(
            LabRequest.status == OrderState.DONE,
            LabRequest.completed_at.isnot(None),
        ).scalar()
    except Exception:
        db.session.rollback()
        avg_tat_seconds = None
    
    avg_tat_minutes = float(avg_tat_seconds or 0) / 60.0 if avg_tat_seconds is not None else 0.0

    total_validated_results = db.session.query(db.func.count(LabResult.id)).join(
        LabRequest, LabRequest.id == LabResult.request_id
    ).filter(
        LabRequest.status == OrderState.DONE,
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt,
        LabResult.status == LabResultStatus.VALIDATED
    ).scalar() or 0

    critical_validated_results = db.session.query(db.func.count(LabResult.id)).join(
        LabRequest, LabRequest.id == LabResult.request_id
    ).filter(
        LabRequest.status == OrderState.DONE,
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt,
        LabResult.status == LabResultStatus.VALIDATED,
        LabResult.is_critical == True
    ).scalar() or 0

    critical_ratio = (float(critical_validated_results) / float(total_validated_results)) if total_validated_results else 0.0

    repeats = []
    try:
        dup_groups = db.session.query(
            LabResult.patient_id.label('patient_id'),
            LabResult.test_code.label('test_code'),
            db.func.count(LabResult.id).label('cnt')
        ).join(
            LabRequest, LabRequest.id == LabResult.request_id
        ).filter(
            LabRequest.status == OrderState.DONE,
            LabRequest.completed_at.isnot(None),
            LabRequest.completed_at >= start_dt,
            LabRequest.completed_at <= end_dt,
            LabResult.status == LabResultStatus.VALIDATED
        ).group_by(LabResult.patient_id, LabResult.test_code).having(db.func.count(LabResult.id) > 1).order_by(db.func.count(LabResult.id).desc()).limit(25).all()
        for g in dup_groups:
            repeats.append({'patient_id': g.patient_id, 'test_code': g.test_code, 'count': int(g.cnt or 0)})
    except Exception:
        repeats = []

    test_tat_rows = []
    try:
        rows = db.session.query(
            LabResult.test_code.label('test_code'),
            db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at)).label('avg_sec'),
            db.func.count(db.func.distinct(LabRequest.id)).label('requests_count'),
        ).join(
            LabRequest, LabRequest.id == LabResult.request_id
        ).filter(
            LabRequest.status == OrderState.DONE,
            LabRequest.completed_at.isnot(None),
            LabRequest.completed_at >= start_dt,
            LabRequest.completed_at <= end_dt,
            LabResult.status == LabResultStatus.VALIDATED
        ).group_by(LabResult.test_code).order_by(db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at)).desc()).limit(30).all()
        for r in rows:
            test_tat_rows.append({
                'test_code': r.test_code,
                'avg_minutes': float(r.avg_sec or 0) / 60.0,
                'requests_count': int(r.requests_count or 0)
            })
    except Exception:
        test_tat_rows = []

    qc_fail_count = LabQualityControlEntry.query.filter(
        LabQualityControlEntry.recorded_at >= start_dt,
        LabQualityControlEntry.recorded_at <= end_dt,
        LabQualityControlEntry.status == 'FAIL'
    ).count()
    qc_total_count = LabQualityControlEntry.query.filter(
        LabQualityControlEntry.recorded_at >= start_dt,
        LabQualityControlEntry.recorded_at <= end_dt
    ).count()

    return render_template(
        'lab/quality.html',
        start_date=start_date,
        end_date=end_date,
        total_done_requests=total_done_requests,
        avg_tat_minutes=avg_tat_minutes,
        total_validated_results=int(total_validated_results),
        critical_validated_results=int(critical_validated_results),
        critical_ratio=critical_ratio,
        repeats=repeats,
        test_tat_rows=test_tat_rows,
        qc_fail_count=qc_fail_count,
        qc_total_count=qc_total_count
    )


@lab_bp.route('/quality-control', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager')
def quality_control():
    if request.method == 'POST':
        try:
            test_code = (request.form.get('test_code') or '').strip()
            test_name = (request.form.get('test_name') or '').strip() or None
            control_level = (request.form.get('control_level') or 'NORMAL').strip().upper()
            measured_value = (request.form.get('measured_value') or '').strip()
            unit = (request.form.get('unit') or '').strip() or None
            expected_range = (request.form.get('expected_range') or '').strip() or None
            status_val = (request.form.get('status') or 'PASS').strip().upper()
            notes = (request.form.get('notes') or '').strip() or None

            if not test_code or not measured_value:
                flash('يرجى إدخال كود التحليل والقراءة', 'warning')
                return redirect(url_for('lab.quality_control'))
            if control_level not in {'LOW', 'NORMAL', 'HIGH'}:
                control_level = 'NORMAL'
            if status_val not in {'PASS', 'FAIL'}:
                status_val = 'PASS'

            db.session.add(LabQualityControlEntry(
                test_code=test_code,
                test_name=test_name,
                control_level=control_level,
                measured_value=measured_value,
                unit=unit,
                expected_range=expected_range,
                status=status_val,
                notes=notes,
                recorded_by=current_user.id,
                recorded_at=datetime.now(timezone.utc)
            ))
            db.session.commit()
            flash('تم تسجيل ضبط الجودة', 'success')
            return redirect(url_for('lab.quality_control'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error saving lab QC: {str(e)}")
            flash('حدث خطأ أثناء الحفظ', 'error')
            return redirect(url_for('lab.quality_control'))

    entries = LabQualityControlEntry.query.order_by(LabQualityControlEntry.recorded_at.desc()).limit(300).all()
    return render_template('lab/quality_control.html', entries=entries)
