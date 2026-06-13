"""
مسارات المختبر - Laboratory Routes
Medical System Laboratory Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, make_response
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
from app_factory import db
import logging
from datetime import datetime, date, timezone, timedelta
import json
import base64
from io import BytesIO
import qrcode

lab_bp = Blueprint('lab', __name__)

def _log_lab_workflow(request_id, status, action, notes=None):
    try:
        from models.request_workflow import RequestWorkflow
        db.session.add(RequestWorkflow(
            request_id=request_id,
            request_type='lab',
            department='lab',
            status=status,
            action=action,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(current_user, 'id', None) or 0
        ))
    except Exception:
        pass

@lab_bp.route('/')
@login_required
def index():
    return redirect(url_for('lab.dashboard'))

@lab_bp.route('/dashboard')
@login_required
@role_required('lab', 'admin', 'manager')
def dashboard():
    """لوحة تحكم المختبر الذكية"""
    
    
    try:
        today = date.today()
        today_requests = LabRequest.query.filter(
            db.func.date(LabRequest.created_at) == today
        ).count()
        pending_requests = LabRequest.query.filter(
            LabRequest.status == 'REQUESTED'
        ).count()
        completed_today = LabRequest.query.filter(
            LabRequest.status == 'DONE',
            db.func.date(LabRequest.completed_at) == today
        ).count()
        total_tests = LabRequest.query.count()
        pending_tests = LabRequest.query.filter(
            LabRequest.status.in_(['REQUESTED', 'RECEIVED', 'ANALYZING', 'REVIEWED', 'APPROVED', 'IN_PROGRESS'])
        ).count()
        completed_tests = LabRequest.query.filter(
            LabRequest.status == 'DONE'
        ).count()
        requested_count = LabRequest.query.filter(
            LabRequest.status == 'REQUESTED'
        ).count()
        in_progress_count = LabRequest.query.filter(
            LabRequest.status.in_(['RECEIVED', 'ANALYZING', 'REVIEWED', 'APPROVED', 'IN_PROGRESS'])
        ).count()
        smart_analytics = get_lab_smart_analytics()
        test_optimization = get_lab_test_optimization()
        quality_control = get_lab_quality_control()
        equipment_monitoring = get_lab_equipment_monitoring()
        result_analysis = get_lab_result_analysis()
        workflow_automation = get_lab_workflow_automation()
        predictive_insights = get_lab_predictive_insights()
        stats = {
            'today_requests': today_requests,
            'pending_requests': pending_requests,
            'completed_today': completed_today,
            'requested_count': requested_count,
            'in_progress_count': in_progress_count,
            'total_tests': total_tests,
            'pending_tests': pending_tests,
            'completed_tests': completed_tests,
            'smart_analytics': smart_analytics,
            'test_optimization': test_optimization,
            'quality_control': quality_control,
            'equipment_monitoring': equipment_monitoring,
            'result_analysis': result_analysis,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights
        }
        recent_requests = LabRequest.query.order_by(LabRequest.created_at.desc()).limit(10).all()
        return render_template('lab/dashboard_new.html', stats=stats, recent_requests=recent_requests)
    
    except Exception as e:
        logging.error(f"Error in lab dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@lab_bp.route('/requests')
@login_required
@role_required('lab', 'manager')
def requests():
    """طلبات المختبر"""
    
    
    return redirect(url_for('lab.worklist'))

@lab_bp.route('/results')
@login_required
@role_required('lab', 'manager')
def results():
    """نتائج المختبر"""
    
    
    return redirect(url_for('lab.worklist', status='DONE_TODAY'))

@lab_bp.route('/tests')
@login_required
@role_required('lab', 'admin', 'manager')
def tests():
    """الفحوصات"""
    
    
    return redirect(url_for('lab.requests'))

@lab_bp.route('/reports')
@login_required
@role_required('lab', 'admin', 'manager')
def reports():
    """تقارير المختبر"""
    
    request_id = request.args.get('request_id', type=int)
    lab_request = None
    if request_id:
        lab_request = db.session.get(LabRequest, request_id)
    if not lab_request:
        lab_request = LabRequest.query.order_by(LabRequest.created_at.desc()).first()
    recent_requests = LabRequest.query.order_by(LabRequest.created_at.desc()).limit(20).all()
    return render_template('lab/report.html', lab_request=lab_request, recent_requests=recent_requests, today=date.today().strftime('%Y-%m-%d'))


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
        LabRequest.status == 'DONE',
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt
    )

    total_done_requests = done_requests_q.count()

    try:
        avg_tat_seconds = db.session.query(
            db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
        ).filter(
            LabRequest.status == 'DONE',
            LabRequest.completed_at.isnot(None),
        ).scalar()
    except Exception:
        db.session.rollback()
        avg_tat_seconds = None
    
    avg_tat_minutes = float(avg_tat_seconds or 0) / 60.0 if avg_tat_seconds is not None else 0.0

    total_validated_results = db.session.query(db.func.count(LabResult.id)).join(
        LabRequest, LabRequest.id == LabResult.request_id
    ).filter(
        LabRequest.status == 'DONE',
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt,
        LabResult.status == 'VALIDATED'
    ).scalar() or 0

    critical_validated_results = db.session.query(db.func.count(LabResult.id)).join(
        LabRequest, LabRequest.id == LabResult.request_id
    ).filter(
        LabRequest.status == 'DONE',
        LabRequest.completed_at.isnot(None),
        LabRequest.completed_at >= start_dt,
        LabRequest.completed_at <= end_dt,
        LabResult.status == 'VALIDATED',
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
            LabRequest.status == 'DONE',
            LabRequest.completed_at.isnot(None),
            LabRequest.completed_at >= start_dt,
            LabRequest.completed_at <= end_dt,
            LabResult.status == 'VALIDATED'
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
            LabRequest.status == 'DONE',
            LabRequest.completed_at.isnot(None),
            LabRequest.completed_at >= start_dt,
            LabRequest.completed_at <= end_dt,
            LabResult.status == 'VALIDATED'
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


@lab_bp.route('/reagents')
@login_required
@role_required('lab', 'admin', 'manager')
def reagents():
    search = (request.args.get('search') or '').strip()
    stock = (request.args.get('stock') or '').strip().lower()
    expiry = (request.args.get('expiry') or '').strip().lower()

    q = LabReagent.query
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                LabReagent.name.ilike(like),
                LabReagent.supplier.ilike(like),
                LabReagent.lot_number.ilike(like)
            )
        )
    if stock == 'low':
        q = q.filter(LabReagent.stock_quantity <= LabReagent.minimum_stock, LabReagent.stock_quantity > 0)
    elif stock == 'out':
        q = q.filter(LabReagent.stock_quantity <= 0)
    elif stock == 'normal':
        q = q.filter(LabReagent.stock_quantity > LabReagent.minimum_stock)

    today = date.today()
    soon_date = today + timedelta(days=30)
    if expiry == 'expired':
        q = q.filter(LabReagent.expiry_date.isnot(None), LabReagent.expiry_date < today)
    elif expiry == 'soon':
        q = q.filter(LabReagent.expiry_date.isnot(None), LabReagent.expiry_date <= soon_date)

    reagents_list = q.order_by(LabReagent.is_active.desc(), LabReagent.name.asc()).limit(1000).all()
    return render_template('lab/reagents.html', reagents=reagents_list, search=search, stock=stock, expiry=expiry, today=today, soon_date=soon_date)


@lab_bp.route('/reagents/add', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'admin', 'manager')
def add_reagent():
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            supplier = (request.form.get('supplier') or '').strip() or None
            lot_number = (request.form.get('lot_number') or '').strip() or None
            unit = (request.form.get('unit') or '').strip() or None
            stock_quantity = request.form.get('stock_quantity')
            minimum_stock = request.form.get('minimum_stock')
            expiry_raw = (request.form.get('expiry_date') or '').strip()
            notes = (request.form.get('notes') or '').strip() or None
            is_active = (request.form.get('is_active') or '') == 'on'

            if not name:
                flash('يرجى إدخال اسم المادة', 'warning')
                return redirect(url_for('lab.add_reagent'))
            try:
                stock_quantity = int(stock_quantity) if stock_quantity is not None and str(stock_quantity).strip() != '' else 0
            except Exception:
                stock_quantity = 0
            try:
                minimum_stock = int(minimum_stock) if minimum_stock is not None and str(minimum_stock).strip() != '' else 0
            except Exception:
                minimum_stock = 0

            expiry_date = None
            if expiry_raw:
                try:
                    expiry_date = datetime.strptime(expiry_raw, '%Y-%m-%d').date()
                except Exception:
                    expiry_date = None

            db.session.add(LabReagent(
                name=name,
                supplier=supplier,
                lot_number=lot_number,
                unit=unit,
                stock_quantity=stock_quantity,
                minimum_stock=minimum_stock,
                expiry_date=expiry_date,
                notes=notes,
                is_active=is_active
            ))
            db.session.commit()
            flash('تمت إضافة المادة', 'success')
            return redirect(url_for('lab.reagents'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding reagent: {str(e)}")
            flash('حدث خطأ أثناء الإضافة', 'error')
            return redirect(url_for('lab.add_reagent'))
    return render_template('lab/reagent_form.html', reagent=None)


@lab_bp.route('/reagents/<int:reagent_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'admin', 'manager')
def edit_reagent(reagent_id: int):
    reagent = db.session.get(LabReagent, reagent_id)
    if not reagent:
        flash('المادة غير موجودة', 'error')
        return redirect(url_for('lab.reagents'))
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            supplier = (request.form.get('supplier') or '').strip() or None
            lot_number = (request.form.get('lot_number') or '').strip() or None
            unit = (request.form.get('unit') or '').strip() or None
            stock_quantity = request.form.get('stock_quantity')
            minimum_stock = request.form.get('minimum_stock')
            expiry_raw = (request.form.get('expiry_date') or '').strip()
            notes = (request.form.get('notes') or '').strip() or None
            is_active = (request.form.get('is_active') or '') == 'on'

            if not name:
                flash('يرجى إدخال اسم المادة', 'warning')
                return redirect(url_for('lab.edit_reagent', reagent_id=reagent_id))
            try:
                stock_quantity = int(stock_quantity) if stock_quantity is not None and str(stock_quantity).strip() != '' else 0
            except Exception:
                stock_quantity = 0
            try:
                minimum_stock = int(minimum_stock) if minimum_stock is not None and str(minimum_stock).strip() != '' else 0
            except Exception:
                minimum_stock = 0

            expiry_date = None
            if expiry_raw:
                try:
                    expiry_date = datetime.strptime(expiry_raw, '%Y-%m-%d').date()
                except Exception:
                    expiry_date = None

            reagent.name = name
            reagent.supplier = supplier
            reagent.lot_number = lot_number
            reagent.unit = unit
            reagent.stock_quantity = stock_quantity
            reagent.minimum_stock = minimum_stock
            reagent.expiry_date = expiry_date
            reagent.notes = notes
            reagent.is_active = is_active
            reagent.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash('تم تحديث المادة', 'success')
            return redirect(url_for('lab.reagents'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editing reagent: {str(e)}")
            flash('حدث خطأ أثناء التحديث', 'error')
            return redirect(url_for('lab.edit_reagent', reagent_id=reagent_id))
    return render_template('lab/reagent_form.html', reagent=reagent)

@lab_bp.route('/print_request/<int:id>')
@login_required
@role_required('lab', 'admin', 'manager')
def print_request(id: int):
    """طباعة تقرير طلب المختبر"""
    
    try:
        lab_request = db.session.get(LabRequest, id)
        if not lab_request:
            flash('طلب المختبر غير موجود', 'error')
            return redirect(url_for('lab.requests'))
        age_years = None
        try:
            if lab_request.patient and lab_request.patient.birth_date:
                b = lab_request.patient.birth_date
                today = date.today()
                age_years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        except Exception:
            age_years = None
        payload = f"LAB|{lab_request.id}|{lab_request.patient_id}|{lab_request.created_at.isoformat()}"
        img = qrcode.make(payload)
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
        printed_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        html = render_template('lab/lab_requests_results_print_standalone.html', lab_request=lab_request, qr_data_uri=qr_data_uri, age_years=age_years, printed_at=printed_at)
        resp = make_response(html)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    except Exception as e:
        logging.error(f"Error printing lab request {id}: {str(e)}")
        flash('حدث خطأ في طباعة تقرير المختبر', 'error')
        return redirect(url_for('lab.requests'))

def get_lab_smart_analytics():
    """التحليلات الذكية للمختبر"""
    try:
        total_requests = LabRequest.query.count()
        completed_requests = LabRequest.query.filter(LabRequest.status == 'DONE').count()
        pending_requests = LabRequest.query.filter(
            LabRequest.status.in_(['REQUESTED', 'RECEIVED', 'ANALYZING', 'REVIEWED', 'APPROVED', 'IN_PROGRESS'])
        ).count()
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
            ).filter(LabRequest.status == 'DONE', LabRequest.completed_at.isnot(None)).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        return {
            'total_requests': total_requests,
            'completion_rate': round(completion_rate, 2),
            'pending_requests': pending_requests,
            'avg_processing_time': avg_processing_time,
            'efficiency_score': calculate_lab_efficiency(completion_rate, pending_requests),
            'status': 'excellent' if completion_rate > 90 else 'good' if completion_rate > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.debug(f"Error getting lab smart analytics: {str(e)}")
        return {}

def get_lab_test_optimization():
    """تحسين الفحوصات"""
    try:
        total_requests = LabRequest.query.count()
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
            ).filter(LabRequest.status == 'DONE', LabRequest.completed_at.isnot(None)).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        total_processed = LabRequest.query.filter(LabRequest.status == 'DONE').count()
        suggestions = generate_optimization_suggestions(avg_processing_time)
        return {
            'avg_processing_time': avg_processing_time,
            'total_processed': total_processed,
            'optimization_suggestions': suggestions,
            'efficiency_score': calculate_test_efficiency(avg_processing_time, total_requests)
        }
    except Exception as e:
        logging.debug(f"Error getting lab test optimization: {str(e)}")
        return {}

def get_lab_quality_control():
    """مراقبة الجودة"""
    try:
        total_completed = LabRequest.query.filter(LabRequest.status == 'DONE').count()
        qc_total = LabQualityControlEntry.query.count()
        qc_fail = LabQualityControlEntry.query.filter(LabQualityControlEntry.status == 'FAIL').count()
        quality_score = 100.0 - (float(qc_fail) / float(qc_total) * 100.0) if qc_total else 100.0
        standard_deviations = round((qc_fail / qc_total) * 3, 2) if qc_total else 0
        recheck_requests = LabRequest.query.filter(LabRequest.status == 'REVIEWED').count()
        return {
            'total_completed': total_completed,
            'quality_score': round(quality_score, 2),
            'standard_deviations': standard_deviations,
            'recheck_requests': recheck_requests
        }
    except Exception as e:
        logging.error(f"Error getting lab quality control: {str(e)}")
        return {}

def get_lab_equipment_monitoring():
    """مراقبة المعدات"""
    try:
        equipment_status = {
            'analyzers': 'operational',
            'centrifuges': 'operational',
            'microscopes': 'operational',
            'incubators': 'maintenance'
        }
        total_equipment = len(equipment_status)
        operational = len([v for v in equipment_status.values() if v == 'operational'])
        maintenance = len([v for v in equipment_status.values() if v == 'maintenance'])
        efficiency = round((operational / total_equipment) * 100, 2) if total_equipment else 0
        return {
            'total_equipment': total_equipment,
            'operational': operational,
            'maintenance': maintenance,
            'efficiency': efficiency
        }
    except Exception as e:
        logging.error(f"Error getting lab equipment monitoring: {str(e)}")
        return {}

def get_lab_result_analysis():
    """تحليل النتائج"""
    try:
        total_results = LabResult.query.count()
        abnormal_results = LabResult.query.filter(
            LabResult.is_critical == True,
            LabResult.status.in_(['READY', 'VALIDATED'])
        ).count()
        abnormal_rate = (abnormal_results / total_results * 100) if total_results else 0
        today = date.today()
        last_7 = LabResult.query.filter(LabResult.created_at >= (today - timedelta(days=7))).count()
        prev_7 = LabResult.query.filter(
            LabResult.created_at >= (today - timedelta(days=14)),
            LabResult.created_at < (today - timedelta(days=7))
        ).count()
        trend_analysis = 'تصاعدي' if last_7 > prev_7 else 'تنازلي' if last_7 < prev_7 else 'مستقر'
        return {
            'total_results': total_results,
            'abnormal_results': abnormal_results,
            'abnormal_rate': round(abnormal_rate, 2),
            'trend_analysis': trend_analysis
        }
    except Exception as e:
        logging.error(f"Error getting lab result analysis: {str(e)}")
        return {}

def get_lab_workflow_automation():
    """أتمتة سير العمل"""
    try:
        total_requests = LabRequest.query.count()
        done_requests = LabRequest.query.filter(LabRequest.status == 'DONE').count()
        automation_rate = round((done_requests / total_requests) * 100, 2) if total_requests else 0
        automated_tasks = done_requests
        time_saved = round(automation_rate * 1.2, 2)
        efficiency_gain = round(automation_rate * 0.8, 2)
        return {
            'automated_tasks': automated_tasks,
            'automation_rate': automation_rate,
            'time_saved': time_saved,
            'efficiency_gain': efficiency_gain
        }
    except Exception as e:
        logging.error(f"Error getting lab workflow automation: {str(e)}")
        return {}

def get_lab_predictive_insights():
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)
        weekly_requests = LabRequest.query.filter(LabRequest.created_at >= week_start).count()
        monthly_requests = LabRequest.query.filter(LabRequest.created_at >= month_start).count()
        prev_week = LabRequest.query.filter(
            LabRequest.created_at >= today - timedelta(days=14),
            LabRequest.created_at < week_start
        ).count()
        growth_rate = ((weekly_requests - prev_week) / prev_week * 100) if prev_week else 0
        predicted_demand = int(round((weekly_requests / 7) * 7))
        return {
            'weekly_requests': weekly_requests,
            'monthly_requests': monthly_requests,
            'predicted_demand': predicted_demand,
            'growth_rate': round(growth_rate, 2)
        }
    except Exception:
        return {}

def calculate_lab_efficiency(completion_rate, pending_requests):
    """حساب كفاءة المختبر"""
    try:
        base_score = completion_rate
        penalty = min(pending_requests * 2, 20)  # خصم لكل طلب معلق
        return max(base_score - penalty, 0)
    except:
        return 0

def calculate_test_efficiency(avg_time, total_tests):
    """حساب كفاءة الفحوصات"""
    try:
        if avg_time <= 2:  # ساعتان أو أقل
            return 95
        elif avg_time <= 4:  # 4 ساعات أو أقل
            return 85
        elif avg_time <= 6:  # 6 ساعات أو أقل
            return 75
        else:
            return 60
    except:
        return 0

def generate_optimization_suggestions(avg_time):
    """توليد اقتراحات التحسين"""
    suggestions = []
    
    if avg_time > 4:
        suggestions.append("تحسين تدفق العينات")
    if avg_time > 6:
        suggestions.append("إضافة معدات جديدة")
    if avg_time > 8:
        suggestions.append("زيادة عدد الفنيين")
    
    return suggestions
@lab_bp.route('/worklist')
@login_required
@role_required('lab', 'technician', 'admin', 'manager')
def worklist():
    try:
        today = date.today()
        status = (request.args.get('status') or 'REQUESTED').strip().upper()
        allowed = {'REQUESTED', 'RECEIVED', 'ANALYZING', 'REVIEWED', 'APPROVED', 'IN_PROGRESS', 'DONE', 'DONE_TODAY', 'ALL'}
        if status not in allowed:
            status = 'REQUESTED'

        q = LabRequest.query
        if status == 'DONE_TODAY':
            q = q.filter(LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today)
        elif status != 'ALL':
            q = q.filter(LabRequest.status == status)

        reqs = q.order_by(LabRequest.created_at.desc()).limit(200).all()

        counts = {
            'requested': LabRequest.query.filter(LabRequest.status == 'REQUESTED').count(),
            'in_progress': LabRequest.query.filter(LabRequest.status.in_(['RECEIVED', 'ANALYZING', 'REVIEWED', 'APPROVED', 'IN_PROGRESS'])).count(),
            'done_today': LabRequest.query.filter(LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today).count(),
        }
        return render_template('lab/process.html',
                               requests=reqs,
                               status=status,
                               counts=counts)
    except Exception as e:
        logging.error(f"Error loading lab worklist: {str(e)}")
        flash('حدث خطأ في تحميل قائمة العمل', 'error')
        return redirect(url_for('lab.dashboard'))

@lab_bp.route('/worklist/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_request(request_id):
    try:
        lab_request = db.session.get(LabRequest, request_id)
        if not lab_request:
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('lab.worklist'))

        if request.method == 'POST':
            action = (request.form.get('action') or 'save').strip().lower()
            if action in {'receive', 'analyze', 'review', 'approve', 'start'}:
                status_map = {
                    'receive': 'RECEIVED',
                    'analyze': 'ANALYZING',
                    'review': 'REVIEWED',
                    'approve': 'APPROVED',
                    'start': 'IN_PROGRESS'
                }
                new_status = status_map.get(action)
                if new_status and lab_request.status != new_status:
                    lab_request.status = new_status
                    lab_request.updated_at = datetime.now(timezone.utc)
                    _log_lab_workflow(lab_request.id, new_status, action)
            result_ids = request.form.getlist('result_id[]')
            test_codes = request.form.getlist('test_code[]')
            test_names = request.form.getlist('test_name[]')
            values = request.form.getlist('value[]')
            units = request.form.getlist('unit[]')
            ranges = request.form.getlist('reference_range[]')
            critical_flags = request.form.getlist('is_critical[]')
            statuses = request.form.getlist('status[]')
            notes_list = request.form.getlist('notes[]')

            any_change = False
            max_len = max(
                len(result_ids),
                len(test_codes),
                len(test_names),
                len(values),
                len(units),
                len(ranges),
                len(critical_flags),
                len(statuses),
                len(notes_list),
                0
            )
            for i in range(max_len):
                rid_raw = result_ids[i] if i < len(result_ids) else ''
                test_code = (test_codes[i] if i < len(test_codes) else '').strip()
                test_name = (test_names[i] if i < len(test_names) else '').strip()
                value = (values[i] if i < len(values) else '').strip()
                unit = (units[i] if i < len(units) else '').strip() or None
                reference_range = (ranges[i] if i < len(ranges) else '').strip() or None
                is_critical_val = (critical_flags[i] if i < len(critical_flags) else '').strip()
                is_critical = str(is_critical_val) in {'1', 'true', 'True', 'yes', 'on'}
                status_val = (statuses[i] if i < len(statuses) else '').strip().upper() or 'PENDING'
                notes = (notes_list[i] if i < len(notes_list) else '').strip() or None

                if not (test_code or test_name or value or unit or reference_range or notes):
                    continue

                if rid_raw and str(rid_raw).isdigit():
                    res = db.session.get(LabResult, int(rid_raw))
                    if not res or res.request_id != lab_request.id:
                        continue
                    res.performed_by = current_user.id
                    if test_code:
                        res.test_code = test_code
                    if test_name:
                        res.test_name = test_name
                    res.value = value or None
                    res.unit = unit
                    res.reference_range = reference_range
                    if status_val in {'PENDING', 'READY', 'VALIDATED'}:
                        res.status = status_val
                    res.notes = notes
                    res.is_critical = is_critical
                    any_change = True
                else:
                    if not (test_code and test_name):
                        continue
                    res = LabResult(
                        request_id=lab_request.id,
                        patient_id=lab_request.patient_id,
                        performed_by=current_user.id,
                        test_code=test_code,
                        test_name=test_name,
                        value=value or None,
                        unit=unit,
                        reference_range=reference_range,
                        status=status_val if status_val in {'PENDING', 'READY', 'VALIDATED'} else 'PENDING',
                        notes=notes,
                        is_critical=is_critical
                    )
                    db.session.add(res)
                    any_change = True

            if action == 'finalize':
                for res in lab_request.results:
                    if (res.value or '').strip():
                        res.status = 'VALIDATED'
                        res.performed_by = current_user.id
                lab_request.status = 'DONE'
                lab_request.completed_at = datetime.now(timezone.utc)
                lab_request.updated_at = datetime.now(timezone.utc)
                _log_lab_workflow(lab_request.id, 'DONE', 'finalize')
                any_change = True

                try:
                    from services.notification_service import NotificationService
                    doctor_id = lab_request.requester.id if lab_request.requester else None
                    has_critical = False
                    try:
                        for res in lab_request.results:
                            if res.is_critical and (res.value or '').strip():
                                has_critical = True
                                break
                    except Exception:
                        has_critical = False
                    if doctor_id:
                        NotificationService.send_notification(
                            recipient_id=doctor_id,
                            title='نتيجة فحص مختبر جاهزة',
                            message=f'تم اعتماد نتيجة فحص المختبر لطلب #{lab_request.id}' + (' (نتائج حرجة)' if has_critical else ''),
                            notification_type='error' if has_critical else 'info',
                            is_urgent=bool(has_critical)
                        )
                    if has_critical:
                        NotificationService.send_notification(
                            recipient_role='reception',
                            title='نتائج مختبر حرجة',
                            message=f'يوجد نتائج مختبر حرجة لطلب #{lab_request.id} للمريض #{lab_request.patient_id}',
                            notification_type='error',
                            is_urgent=True
                        )
                except Exception:
                    pass

            if any_change:
                try:
                    db.session.add(AuditTrail(
                        entity_type='lab_request',
                        entity_id=lab_request.id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='تحديث نتائج المختبر'
                    ))
                except Exception:
                    pass

            db.session.commit()
            flash('تم حفظ نتائج المختبر', 'success')
            return redirect(url_for('lab.worklist_request', request_id=lab_request.id))

        return render_template('lab/process.html', lab_request=lab_request)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in lab worklist request: {str(e)}")
        flash('حدث خطأ في إدارة الطلب', 'error')
        return redirect(url_for('lab.worklist'))

@lab_bp.route('/worklist/claim/<int:request_id>', methods=['POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_claim(request_id):
    try:
        req = db.session.get(LabRequest, request_id)
        if not req or req.status not in ('REQUESTED',):
            return jsonify({'success': False, 'message': 'الطلب غير صالح'}), 400
        req.status = 'RECEIVED'
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, 'RECEIVED', 'claim')
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم استلام الطلب'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error claiming lab request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@lab_bp.route('/worklist/complete/<int:request_id>', methods=['POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_complete(request_id):
    try:
        req = db.session.get(LabRequest, request_id)
        if not req:
            return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404
        # إنشاء نتيجة مبسطة إذا لم تُرفق
        result_payload = request.get_json() or {}
        if result_payload:
            res = LabResult(
                request_id=req.id,
                patient_id=req.patient_id,
                performed_by=current_user.id,
                test_code=result_payload.get('test_code') or 'GEN',
                test_name=result_payload.get('test_name') or 'Generic Test',
                value=result_payload.get('value'),
                unit=result_payload.get('unit'),
                reference_range=result_payload.get('reference_range'),
                status='VALIDATED',
                notes=result_payload.get('notes'),
                is_critical=bool(result_payload.get('is_critical') or False)
            )
            db.session.add(res)
        req.status = 'DONE'
        req.completed_at = datetime.now(timezone.utc)
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, 'DONE', 'complete')
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            # إشعار للطبيب الطالب إن وُجد
            doctor_id = req.requester.id if req.requester else None
            if doctor_id:
                NotificationService.send_notification(
                    recipient_id=doctor_id,
                    title='نتيجة فحص مختبر جاهزة',
                    message=f'تم اعتماد نتيجة فحص المختبر لطلب #{req.id}',
                    notification_type='info'
                )
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'تم إكمال الطلب'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error completing lab request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@lab_bp.route('/api/worklist')
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'doctor', 'super_admin')
def api_worklist():
    try:
        visit_id = request.args.get('visit_id', type=int)
        status = request.args.get('status', type=str)
        q = LabRequest.query
        if visit_id:
            q = q.filter(LabRequest.visit_id == visit_id)
        if status:
            q = q.filter(LabRequest.status == status)
        reqs = q.order_by(LabRequest.created_at.desc()).limit(50).all()
        data = []
        for r in reqs:
            data.append({
                'id': r.id,
                'visit_id': r.visit_id,
                'patient_id': r.patient_id,
                'status': r.status,
                'request_number': getattr(r, 'request_number', None)
            })
        return jsonify({'success': True, 'requests': data})
    except Exception as e:
        logging.error(f"Error loading lab api worklist: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@lab_bp.route('/api/fhir/servicerequest', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_fhir_lab_service_request():
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        visit_id = data.get('visit_id')
        requester_id = data.get('requester_id') or getattr(current_user, 'id', None)
        tests = data.get('tests') or []
        if not patient_id or not visit_id:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'patient_id and visit_id مطلوبان'}]}), 400
        req = LabRequest(
            visit_id=visit_id,
            patient_id=patient_id,
            requested_by=requester_id,
            status='REQUESTED',
            notes=data.get('notes')
        )
        req.request_number = f"LAB-{int(datetime.now(timezone.utc).timestamp())}"
        db.session.add(req)
        db.session.flush()
        for t in tests:
            if not isinstance(t, dict):
                continue
            code = (t.get('test_code') or '').strip()
            name = (t.get('test_name') or '').strip() or code or 'Test'
            if not code and not name:
                continue
            db.session.add(LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=code or name,
                test_name=name,
                status='PENDING'
            ))
        _log_lab_workflow(req.id, 'REQUESTED', 'fhir_service_request')
        db.session.commit()
        return jsonify({'resourceType': 'ServiceRequest', 'id': str(req.id), 'status': 'active', 'subject': {'reference': f'Patient/{patient_id}'}, 'encounter': {'reference': f'Encounter/{visit_id}'}}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing FHIR ServiceRequest: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر استيراد طلب المختبر'}]}), 500

@lab_bp.route('/api/fhir/observation', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_fhir_lab_observation_import():
    try:
        data = request.get_json() or {}
        request_id = data.get('request_id')
        patient_id = data.get('patient_id')
        test_code = (data.get('test_code') or '').strip()
        test_name = (data.get('test_name') or '').strip() or test_code or 'Test'
        value = data.get('value')
        unit = data.get('unit')
        reference_range = data.get('reference_range')
        if not request_id or not patient_id:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'request_id and patient_id مطلوبان'}]}), 400
        req = db.session.get(LabRequest, int(request_id))
        if not req:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'طلب المختبر غير موجود'}]}), 404
        res = None
        if test_code:
            res = LabResult.query.filter_by(request_id=req.id, test_code=test_code).first()
        if not res:
            res = LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=test_code or test_name,
                test_name=test_name,
                status='READY'
            )
            db.session.add(res)
        res.value = value
        res.unit = unit
        res.reference_range = reference_range
        res.status = 'VALIDATED'
        res.performed_by = getattr(current_user, 'id', None)
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, req.status, 'fhir_observation')
        db.session.commit()
        return jsonify({'resourceType': 'Observation', 'id': str(res.id), 'status': 'final'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing FHIR Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر استيراد نتيجة المختبر'}]}), 500

@lab_bp.route('/api/hl7/import', methods=['POST'])
@login_required
@role_required('lab', 'doctor', 'admin', 'manager')
def api_hl7_import():
    try:
        data = request.get_json() or {}
        patient_id = data.get('patient_id')
        visit_id = data.get('visit_id')
        tests = data.get('tests') or []
        if not patient_id or not visit_id:
            return jsonify({'success': False, 'message': 'patient_id و visit_id مطلوبان'}), 400
        req = LabRequest(
            visit_id=visit_id,
            patient_id=patient_id,
            requested_by=getattr(current_user, 'id', None),
            status='REQUESTED',
            notes=data.get('notes')
        )
        req.request_number = f"HL7-{int(datetime.now(timezone.utc).timestamp())}"
        db.session.add(req)
        db.session.flush()
        for t in tests:
            if not isinstance(t, dict):
                continue
            code = (t.get('test_code') or '').strip()
            name = (t.get('test_name') or '').strip() or code or 'Test'
            db.session.add(LabResult(
                request_id=req.id,
                patient_id=patient_id,
                test_code=code or name,
                test_name=name,
                value=t.get('value'),
                unit=t.get('unit'),
                reference_range=t.get('reference_range'),
                status='PENDING'
            ))
        _log_lab_workflow(req.id, 'REQUESTED', 'hl7_import')
        db.session.commit()
        return jsonify({'success': True, 'request_id': req.id}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing HL7 lab payload: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر استيراد HL7'}), 500

@lab_bp.route('/api/fhir/observation/lab/<int:result_id>')
@login_required
@role_required('lab', 'radiology', 'doctor', 'admin', 'manager')
def api_fhir_lab_observation(result_id):
    """تصدير نتيجة مختبر بصيغة FHIR Observation وربطها بـ Encounter"""
    try:
        res = db.session.get(LabResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'LabResult not found'}]}), 404
        req = db.session.get(LabRequest, res.request_id)
        visit_id = req.visit_id if req else None

        # تحويل الحالة إلى FHIR
        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        # محاولة تحويل القيمة إلى رقم
        value_str = (res.value or '').strip()
        value_num = None
        try:
            value_num = float(value_str)
        except Exception:
            value_num = None

        resource = {
            'resourceType': 'Observation',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:test-code', 'code': res.test_code}],
                'text': res.test_name
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            **({'valueQuantity': {'value': value_num, 'unit': res.unit}} if value_num is not None else {'valueString': value_str}),
            'referenceRange': ([{'text': res.reference_range}] if res.reference_range else []),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {}),
            'note': ([{'text': res.notes}] if res.notes else [])
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Lab Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير نتائج المختبر حالياً'}]}), 500

@lab_bp.route('/api/fhir/diagnosticreport/lab/<int:result_id>')
@login_required
@role_required('lab', 'radiology', 'doctor', 'admin', 'manager')
def api_fhir_lab_diagnostic_report(result_id):
    """تصدير تقرير مختبر بصيغة FHIR DiagnosticReport وربطه بـ Encounter"""
    try:
        res = db.session.get(LabResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على نتيجة المختبر المطلوبة'}]}), 404
        req = db.session.get(LabRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        resource = {
            'resourceType': 'DiagnosticReport',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v2-0074', 'code': 'LAB'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:test-code', 'code': res.test_code}],
                'text': res.test_name
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'issued': (res.updated_at.isoformat() if hasattr(res, 'updated_at') and res.updated_at else None),
            'result': [{'reference': f'Observation/{res.id}'}],
            'conclusion': (res.notes or ''),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {})
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Lab DiagnosticReport: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير تقرير المختبر حالياً'}]}), 500
