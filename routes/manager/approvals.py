"""approvals routes - extracted from monolithic manager.py"""

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
# APPROVALS ROUTES
# =============================================

# ==================== موافقات الدفع القسري (الأسبوع الثاني) ====================

@manager_bp.route('/force-payment-approvals')
@login_required
@manager_or_admin_only
def force_payment_approvals():
    """صفحة موافقات الدفع القسري"""
    try:
        # الدفعات القسرية المعلقة
        pending_approvals = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by == None
        ).order_by(Visit.created_at.desc()).all()
        
        # الدفعات القسرية المعتمدة (آخر 30 يوم)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        approved_payments = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by != None,
            Visit.force_payment_approved_at >= thirty_days_ago
        ).order_by(Visit.force_payment_approved_at.desc()).all()
        
        # إحصائيات
        stats = GatekeeperService.get_force_payment_statistics(days=30)
        
        return render_template('manager/force_payment_approvals.html',
                             pending_approvals=pending_approvals,
                             approved_payments=approved_payments,
                             stats=stats)
    
    except Exception as e:
        logging.error(f"Error loading force payment approvals: {str(e)}")
        flash('حدث خطأ في تحميل صفحة الموافقات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/approve-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
@prevent_self_approval
def approve_force_payment(visit_id):
    """الموافقة على دفع قسري"""
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من أنها زيارة دفع قسري
        if not visit.is_force_payment:
            flash('هذه ليست زيارة دفع قسري', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من أنها غير معتمدة
        if visit.force_payment_approved_by:
            flash('تم الموافقة على هذا الدفع مسبقاً', 'warning')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من الصلاحية
        is_valid, message = GatekeeperService.validate_force_payment(
            visit_id,
            current_user.id,
            visit.force_payment_reason
        )
        
        if not is_valid:
            flash(message, 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # الموافقة
        visit.force_payment_approved_by = current_user.id
        visit.force_payment_approved_at = datetime.now(timezone.utc)
        visit.payment_status = 'DEBT'  # تحديد كدين معتمد
        
        db.session.commit()
        
        # إدراج الزيارة في طابور القسم تلقائياً إذا لم تكن مدرجة
        try:
            from models.queue_management import QueueManagement
            existing_ticket = QueueManagement.query.filter_by(visit_id=visit_id, department_id=visit.department_id).first()
            if not existing_ticket:
                from routes.reception import add_patient_to_queue_auto
                add_patient_to_queue_auto(visit_id=visit_id, department_id=visit.department_id, doctor_id=visit.doctor_id)
        except Exception:
            pass
        
        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='APPROVE',
            entity_type='visit',
            entity_id=visit_id,
            description=f'موافقة على دفع قسري - {visit.force_payment_reason}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'تمت الموافقة على الدفع القسري للزيارة #{visit.id}', 'success')
        logging.info(f"Force payment approved: Visit {visit_id} by User {current_user.id}")
        
        return redirect(url_for('manager.force_payment_approvals'))
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error approving force payment: {str(e)}")
        flash('تعذر تنفيذ الموافقة حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))

@manager_bp.route('/reject-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
def reject_force_payment(visit_id):
    """رفض دفع قسري"""
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        rejection_reason = request.form.get('rejection_reason', '')
        
        # التحقق من أنها زيارة دفع قسري
        if not visit.is_force_payment:
            flash('هذه ليست زيارة دفع قسري', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # التحقق من السبب
        if not rejection_reason or len(rejection_reason.strip()) < 10:
            flash('يجب تقديم سبب واضح للرفض (10 أحرف على الأقل)', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
        
        # الرفض
        visit.is_force_payment = False
        visit.payment_method = 'CASH'
        visit.payment_status = 'PENDING'
        visit.force_payment_reason = f'[مرفوض] {visit.force_payment_reason}\nسبب الرفض: {rejection_reason}'
        
        db.session.commit()
        
        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='REJECT',
            entity_type='visit',
            entity_id=visit_id,
            description=f'رفض دفع قسري - {rejection_reason}',
            ip_address=request.remote_addr
        )
        db.session.add(audit)
        db.session.commit()
        
        flash(f'تم رفض الدفع القسري للزيارة #{visit.id}', 'warning')
        logging.info(f"Force payment rejected: Visit {visit_id} by User {current_user.id}")
        
        return redirect(url_for('manager.force_payment_approvals'))
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error rejecting force payment: {str(e)}")
        flash('تعذر تنفيذ الرفض حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))
