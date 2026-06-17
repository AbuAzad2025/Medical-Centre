"""staff routes - extracted from monolithic manager.py"""

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
# STAFF ROUTES
# =============================================

@manager_bp.route('/unit-control')
@login_required
@role_required('manager', 'admin')
def unit_control():
    """التحكم في الوحدات"""
    
    
    try:
        # جلب معلومات الوحدات
        units = [
            {'name': 'الاستقبال', 'status': 'active', 'users': User.query.filter_by(role='reception').count()},
            {'name': 'الطبيب', 'status': 'active', 'users': User.query.filter_by(role='doctor').count()},
            {'name': 'الطوارئ', 'status': 'active', 'users': User.query.filter_by(role='emergency').count()},
            {'name': 'المختبر', 'status': 'active', 'users': User.query.filter_by(role='lab').count()},
            {'name': 'الأشعة', 'status': 'active', 'users': User.query.filter_by(role='radiology').count()},
            {'name': 'المحاسب', 'status': 'active', 'users': User.query.filter_by(role='accountant').count()}
        ]
        
        return render_template('manager/unit_control.html', units=units)
    except Exception as e:
        logging.error(f"Error in unit control: {str(e)}")
        flash('حدث خطأ في تحميل التحكم في الوحدات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/user-management')
@login_required
def user_management():
    """إدارة المستخدمين"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

@manager_bp.route('/staff/schedule', methods=['GET', 'POST'])
@login_required
def staff_schedule():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            day_of_week = request.form.get('day_of_week', type=int)
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            is_active = request.form.get('is_active') == 'on'
            if not user_id or day_of_week is None or not start_time or not end_time:
                flash('الحقول مطلوبة', 'error')
                return redirect(url_for('manager.staff_schedule', user_id=user_id))
            from datetime import datetime as _dt
            st = _dt.strptime(start_time, '%H:%M').time()
            et = _dt.strptime(end_time, '%H:%M').time()
            s = StaffWorkSchedule.query.filter_by(user_id=user_id, day_of_week=day_of_week).first()
            if s:
                s.start_time = st
                s.end_time = et
                s.is_active = is_active
            else:
                s = StaffWorkSchedule(user_id=user_id, day_of_week=day_of_week, start_time=st, end_time=et, is_active=is_active)
                db.session.add(s)
            db.session.commit()
            flash('تم حفظ جدول العمل', 'success')
            return redirect(url_for('manager.staff_schedule', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في حفظ الجدول', 'error')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    schedules = []
    if user_id:
        schedules = StaffWorkSchedule.query.filter_by(user_id=user_id).order_by(StaffWorkSchedule.day_of_week.asc()).all()
    return render_template('manager/staff_schedule.html', users=users, schedules=schedules, selected_user_id=user_id)

@manager_bp.route('/staff/absence', methods=['GET', 'POST'])
@login_required
def staff_absence():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            reason = (request.form.get('reason') or '').strip() or None
            if not user_id or not start_date or not end_date:
                flash('الحقول مطلوبة', 'error')
                return redirect(url_for('manager.staff_absence', user_id=user_id))
            from datetime import datetime as _dt
            sd = _dt.strptime(start_date, '%Y-%m-%d').date()
            ed = _dt.strptime(end_date, '%Y-%m-%d').date()
            a = StaffAbsence(user_id=user_id, start_date=sd, end_date=ed, reason=reason)
            db.session.add(a)
            db.session.commit()
            flash('تم إضافة الغياب', 'success')
            return redirect(url_for('manager.staff_absence', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في إضافة الغياب', 'error')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    absences = []
    if user_id:
        absences = StaffAbsence.query.filter_by(user_id=user_id).order_by(StaffAbsence.start_date.desc()).all()
    return render_template('manager/staff_absence.html', users=users, absences=absences, selected_user_id=user_id)


@manager_bp.route('/staff/capacity')
@login_required
def staff_capacity():
    if current_user.role not in ['manager', 'admin', 'super_admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('manager.dashboard'))

    try:
        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        department_id = request.args.get('department_id', type=int)
        days = request.args.get('days', type=int)
        days = max(1, min(days or 14, 60))

        from datetime import datetime as _dt
        if start_raw:
            try:
                start_date = _dt.strptime(start_raw, '%Y-%m-%d').date()
            except Exception:
                start_date = date.today()
        else:
            start_date = date.today()

        if end_raw:
            try:
                end_date = _dt.strptime(end_raw, '%Y-%m-%d').date()
            except Exception:
                end_date = start_date + timedelta(days=days - 1)
        else:
            end_date = start_date + timedelta(days=days - 1)

        if end_date < start_date:
            end_date = start_date

        departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar.asc()).all()
        dept_ids = [department_id] if department_id else [d.id for d in departments]

        doctors_q = User.query.filter(User.role == 'doctor', User.is_active == True)
        if dept_ids:
            doctors_q = doctors_q.filter(User.department_id.in_(dept_ids))
        doctors = doctors_q.all()

        schedules = StaffWorkSchedule.query.filter(StaffWorkSchedule.user_id.in_([u.id for u in doctors])).all() if doctors else []
        sched_map = {}
        for s in schedules:
            sched_map.setdefault(s.user_id, {})[int(s.day_of_week)] = s

        abs_q = StaffAbsence.query.filter(
            StaffAbsence.user_id.in_([u.id for u in doctors]) if doctors else False,
            StaffAbsence.start_date <= end_date,
            StaffAbsence.end_date >= start_date
        )
        absences = abs_q.all() if doctors else []
        abs_map = {}
        for a in absences:
            abs_map.setdefault(a.user_id, []).append(a)

        by_day = []
        cur = start_date
        while cur <= end_date:
            day_row = {'date': cur, 'departments': []}
            for did in dept_ids:
                dept = next((d for d in departments if d.id == did), None)
                dept_doctors = [u for u in doctors if u.department_id == did]
                scheduled_slots = 0
                effective_slots = 0
                absent_count = 0
                for u in dept_doctors:
                    dow = cur.weekday()
                    s = sched_map.get(u.id, {}).get(dow)
                    if s and not s.is_active:
                        continue
                    start_hour = (s.start_time.hour if s else 9)
                    end_hour = (s.end_time.hour if s else 17)
                    slots = max(0, end_hour - start_hour)
                    scheduled_slots += slots
                    user_abs = False
                    for a in abs_map.get(u.id, []):
                        if a.start_date <= cur <= a.end_date:
                            user_abs = True
                            break
                    if user_abs:
                        absent_count += 1
                        continue
                    effective_slots += slots
                day_row['departments'].append({
                    'department_id': did,
                    'department_name': (dept.name_ar or dept.name) if dept else str(did),
                    'doctors': len(dept_doctors),
                    'absent_doctors': absent_count,
                    'scheduled_slots': scheduled_slots,
                    'effective_slots': effective_slots,
                    'lost_slots': max(0, scheduled_slots - effective_slots),
                })
            by_day.append(day_row)
            cur = cur + timedelta(days=1)

        return render_template(
            'manager/staff_capacity.html',
            departments=departments,
            selected_department_id=department_id,
            start_date=start_date,
            end_date=end_date,
            days=days,
            by_day=by_day
        )
    except Exception as e:
        logging.error(f"Staff capacity error: {str(e)}")
        flash('حدث خطأ في تحميل تقرير الاستيعاب', 'error')
        return redirect(url_for('manager.dashboard'))

# تم نقل /reports إلى admin.py - المدير يستخدم admin/reports

# ==================== الميزات الذكية للمانجر ====================

@manager_bp.route('/staff')
@login_required
def staff():
    """إدارة الموظفين"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/user_management.html')
