"""reports routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from services.manager_service import manager_service
from app_factory import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# REPORTS ROUTES
# =============================================

@manager_bp.route('/reports')
@login_required
def reports():
    """التقارير"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/reports.html')


@manager_bp.route('/reports-center')
@login_required
def reports_center():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        from services.report_center_service import ReportCenterService
        from models.department import Department
        from models.user import User

        report = (request.args.get('report') or '').strip()
        start_raw = request.args.get('start_date')
        end_raw = request.args.get('end_date')
        department_id = request.args.get('department_id', type=int)

        start_date, end_date, start_dt, end_dt = ReportCenterService._parse_dates(start_raw, end_raw)
        result = None

        if report == 'compare_month':
            now = date.today()
            a_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                a_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            if now.month == 1:
                p_year, p_month = now.year - 1, 12
            else:
                p_year, p_month = now.year, now.month - 1
            b_start = datetime(p_year, p_month, 1, tzinfo=timezone.utc)
            if p_month == 12:
                b_end = datetime(p_year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                b_end = datetime(p_year, p_month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'compare_year':
            now = date.today()
            a_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
            a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            b_start = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc)
            b_end = datetime(now.year, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'transfers':
            result = {'transfers': ReportCenterService.department_transfers(start_dt, end_dt)}
        elif report == 'capacity':
            result = {'capacity': ReportCenterService.capacity_impact(start_date, end_date)}
        elif report == 'booking':
            booking = ReportCenterService.booking_report(start_dt, end_dt)
            dept_names = {d.id: (d.name_ar or d.name) for d in Department.query.all()}
            doctor_names = {u.id: u.full_name for u in User.query.filter_by(role='doctor').all()}
            booking['top_departments_named'] = [{'label': dept_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_departments', [])]
            booking['top_doctors_named'] = [{'label': doctor_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_doctors', [])]
            result = {'booking': booking}
        elif report == 'emergency_times':
            result = {'emergency_times': ReportCenterService.emergency_stage_times(start_dt, end_dt)}
        elif report == 'radiology_revision':
            result = {'radiology_revision': ReportCenterService.radiology_revision_rate(start_dt, end_dt)}

        departments = Department.query.filter_by(is_active=True).all()
        from app.shared.report_template_service import list_templates
        saved_templates = list_templates()
        return render_template(
            'manager/reports_center.html',
            report=report,
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            departments=departments,
            result=result,
            saved_templates=saved_templates,
        )
    except Exception as e:
        logging.error(f"Manager reports center error: {str(e)}")
        return render_template('manager/reports_center.html', report='', start_date=None, end_date=None, departments=[], result=None, saved_templates=[])

@manager_bp.route('/analytics')
@login_required
def analytics():
    """التحليلات"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/monitoring.html')

@manager_bp.route('/self-service')
@login_required
@role_required('manager', 'admin', 'super_admin')
def self_service():
    try:
        from services.advanced_report_service import AdvancedReportService
        report_type = (request.args.get('type') or 'patients').strip()
        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        start_date = datetime.strptime(start_raw, '%Y-%m-%d') if start_raw else None
        end_date = datetime.strptime(end_raw, '%Y-%m-%d') if end_raw else None
        if report_type == 'visits':
            data = AdvancedReportService.generate_visit_analytics(start_date, end_date)
        elif report_type == 'financial':
            data = AdvancedReportService.generate_financial_analytics(start_date, end_date)
        elif report_type == 'departments':
            data = AdvancedReportService.generate_department_analytics(start_date, end_date)
        else:
            data = AdvancedReportService.generate_patient_analytics(start_date, end_date)
            report_type = 'patients'
        return render_template('manager/self_service.html', report_type=report_type, data=data, start_date=start_raw, end_date=end_raw)
    except Exception as e:
        logging.error(f"Error in self service analytics: {str(e)}")
        return render_template('manager/self_service.html', report_type='patients', data={}, start_date='', end_date='')

@manager_bp.route('/kpi-dashboard')
@login_required
@manager_or_admin_only
def kpi_dashboard():
    """لوحة مؤشرات الأداء"""
    try:
        from services.report_service import ReportService
        
        # الحصول على تقرير الشهر الحالي
        report = ReportService.get_monthly_audit_report()
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('manager.dashboard'))
        
        # الحصول على إحصائيات الدفع القسري
        force_stats = GatekeeperService.get_force_payment_statistics(days=30)
        
        return render_template('manager/kpi_dashboard.html',
                             report=report,
                             force_stats=force_stats)
    
    except Exception as e:
        logging.error(f"Error loading KPI dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة المؤشرات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/drill-down/<report_type>')
@login_required
@role_required('manager', 'admin', 'super_admin')
def drill_down(report_type):
    """تقارير drill-down"""
    today = date.today()
    start = request.args.get('start', today.strftime('%Y-%m-%d'))
    end = request.args.get('end', today.strftime('%Y-%m-%d'))
    dept_id = request.args.get('department_id')
    try:
        start_dt = datetime.strptime(start, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end, '%Y-%m-%d').date()
    except ValueError:
        start_dt = end_dt = today

    if report_type == 'visits':
        title = 'تفاصيل الزيارات'
        q = Visit.query.filter(Visit.visit_date >= start_dt, Visit.visit_date <= end_dt)
        if dept_id:
            q = q.filter_by(department_id=int(dept_id))
        results = q.order_by(Visit.visit_date.desc()).limit(200).all()
    elif report_type == 'revenue':
        title = 'تفاصيل الإيرادات'
        q = Payment.query.filter(Payment.payment_date >= start_dt, Payment.payment_date <= end_dt)
        results = q.order_by(Payment.payment_date.desc()).limit(200).all()
    elif report_type == 'patients':
        title = 'المرضى الجدد'
        results = Patient.query.filter(Patient.created_at >= start_dt, Patient.created_at <= end_dt).order_by(Patient.created_at.desc()).limit(200).all()
    else:
        flash('نوع التقرير غير معروف', 'error')
        return redirect(url_for('manager.dashboard'))

    return render_template('manager/drill_down.html', report_type=report_type, title=title,
                           results=results, start=start, end=end, departments=Department.query.all())
