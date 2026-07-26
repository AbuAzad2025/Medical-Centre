"""approvals routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, g
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
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from sqlalchemy import func, select
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone
from app.shared.enums import PaymentStatus


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
        # Ticket 2: defence-in-depth — list only visits in the current tenant
        tenant_filter = {'tenant_id': g.tenant_id} if hasattr(g, 'tenant_id') and g.tenant_id is not None else {}

        # الدفعات القسرية المعلقة
        pending_approvals = db.session.execute(select(Visit).filter_by(**tenant_filter).filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by == None
        ).order_by(Visit.created_at.desc())).scalars().all()

        # الدفعات القسرية المعتمدة (آخر 30 يوم)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        approved_payments = db.session.execute(select(Visit).filter_by(**tenant_filter).filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by != None,
            Visit.force_payment_approved_at >= thirty_days_ago
        ).order_by(Visit.force_payment_approved_at.desc())).scalars().all()
        
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
        from utils.tenant_query import get_tenant_record, TenantContextError
        try:
            visit = get_tenant_record(Visit, visit_id)
        except TenantContextError:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
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
        visit.payment_status = PaymentStatus.DEBT  # تحديد كدين معتمد

        safe_commit(db.session, error_message="database commit failed", reraise=True)

        # Ticket 1: Manager approval of a force-payment is purely an
        # administrative/financial review.  It does NOT grant queue-entry
        # authorization.  Queue entry still follows the same backend rule:
        # normal visits must be PAID; emergency is the only exception.

        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='APPROVE',
            entity_type='visit',
            entity_id=visit_id,
            description=f'موافقة على دفع قسري - {visit.force_payment_reason}',
            user_ip=request.remote_addr
        )
        db.session.add(audit)
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        flash(f'تمت الموافقة على الدفع القسري للزيارة #{visit.id}', 'success')
        logging.info(f"Force payment approved: Visit {visit_id} by User {current_user.id}")

        return redirect(url_for('manager.force_payment_approvals'))

    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error approving force payment: {str(e)}")
        flash('تعذر تنفيذ الموافقة حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))

@manager_bp.route('/reject-force-payment/<int:visit_id>', methods=['POST'])
@login_required
@can_approve_force_payment
def reject_force_payment(visit_id):
    """رفض دفع قسري"""
    try:
        from utils.tenant_query import get_tenant_record, TenantContextError
        try:
            visit = get_tenant_record(Visit, visit_id)
        except TenantContextError:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('manager.force_payment_approvals'))
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
        visit.payment_status = PaymentStatus.PENDING
        visit.force_payment_reason = f'[مرفوض] {visit.force_payment_reason}\nسبب الرفض: {rejection_reason}'

        safe_commit(db.session, error_message="database commit failed", reraise=True)

        # تسجيل في التدقيق
        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='REJECT',
            entity_type='visit',
            entity_id=visit_id,
            description=f'رفض دفع قسري - {rejection_reason}',
            user_ip=request.remote_addr
        )
        db.session.add(audit)
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        flash(f'تم رفض الدفع القسري للزيارة #{visit.id}', 'warning')
        logging.info(f"Force payment rejected: Visit {visit_id} by User {current_user.id}")

        return redirect(url_for('manager.force_payment_approvals'))

    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error rejecting force payment: {str(e)}")
        flash('تعذر تنفيذ الرفض حالياً، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('manager.force_payment_approvals'))


# ==================== موافقات الخدمات المخصصة (Ticket 6) ====================

@manager_bp.route('/custom-service-approvals')
@login_required
@manager_or_admin_only
def custom_service_approvals():
    """صفحة موافقات الخدمات المخصصة"""
    try:
        from models.service import ServiceMaster
        pending = db.session.execute(select(ServiceMaster).filter(
            ServiceMaster.is_custom == True,
            ServiceMaster.is_active == False,
            ServiceMaster.approved_by == None,
            ServiceMaster.tenant_id == current_user.tenant_id
        ).order_by(ServiceMaster.created_at.desc())).scalars().all()

        approved = db.session.execute(select(ServiceMaster).filter(
            ServiceMaster.is_custom == True,
            ServiceMaster.is_active == True,
            ServiceMaster.approved_by != None,
            ServiceMaster.tenant_id == current_user.tenant_id
        ).order_by(ServiceMaster.approved_at.desc())).scalars().all()

        return render_template('manager/custom_service_approvals.html',
                             pending_services=pending,
                             approved_services=approved)
    except Exception as e:
        logging.error(f"Error loading custom service approvals: {str(e)}")
        flash('حدث خطأ في تحميل صفحة الموافقات', 'error')
        return redirect(url_for('manager.dashboard'))


@manager_bp.route('/approve-custom-service/<int:service_id>', methods=['POST'])
@login_required
@manager_or_admin_only
def approve_custom_service(service_id):
    """الموافقة على خدمة مخصصة وتحويلها إلى كتالوج قابل لإعادة الاستخدام"""
    try:
        from models.service import ServiceMaster
        from utils.tenant_query import get_tenant_record, TenantContextError
        try:
            svc = get_tenant_record(ServiceMaster, service_id)
        except TenantContextError:
            flash('الخدمة غير موجودة', 'error')
            return redirect(url_for('manager.custom_service_approvals'))

        if not svc.is_custom:
            flash('هذه ليست خدمة مخصصة', 'error')
            return redirect(url_for('manager.custom_service_approvals'))
        if svc.approved_by:
            flash('تمت الموافقة على هذه الخدمة مسبقاً', 'warning')
            return redirect(url_for('manager.custom_service_approvals'))

        svc.is_active = True
        svc.approved_by = current_user.id
        svc.approved_at = datetime.now(timezone.utc)
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='APPROVE',
            entity_type='service',
            entity_id=service_id,
            description=f'موافقة على خدمة مخصصة - {svc.name}',
            user_ip=request.remote_addr
        )
        db.session.add(audit)
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        flash(f'تمت الموافقة على الخدمة المخصصة {svc.name}', 'success')
        logging.info(f"Custom service approved: {service_id} by User {current_user.id}")
        return redirect(url_for('manager.custom_service_approvals'))

    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error approving custom service: {str(e)}")
        flash('تعذر تنفيذ الموافقة حالياً', 'error')
        return redirect(url_for('manager.custom_service_approvals'))


@manager_bp.route('/reject-custom-service/<int:service_id>', methods=['POST'])
@login_required
@manager_or_admin_only
def reject_custom_service(service_id):
    """رفض خدمة مخصصة (تبقى غير نشطة ولا تُستخدم في الكتالوج)"""
    try:
        from models.service import ServiceMaster
        from utils.tenant_query import get_tenant_record, TenantContextError
        try:
            svc = get_tenant_record(ServiceMaster, service_id)
        except TenantContextError:
            flash('الخدمة غير موجودة', 'error')
            return redirect(url_for('manager.custom_service_approvals'))

        if not svc.is_custom:
            flash('هذه ليست خدمة مخصصة', 'error')
            return redirect(url_for('manager.custom_service_approvals'))

        rejection_reason = request.form.get('rejection_reason', '')
        svc.is_active = False
        svc.approved_by = current_user.id
        svc.approved_at = datetime.now(timezone.utc)
        svc.description = f"[مرفوض] {svc.description or ''}\nسبب الرفض: {rejection_reason}"
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        from models.audit_trail import AuditTrail
        audit = AuditTrail(
            user_id=current_user.id,
            action='REJECT',
            entity_type='service',
            entity_id=service_id,
            description=f'رفض خدمة مخصصة - {svc.name} - {rejection_reason}',
            user_ip=request.remote_addr
        )
        db.session.add(audit)
        safe_commit(db.session, error_message="database commit failed", reraise=True)

        flash(f'تم رفض الخدمة المخصصة {svc.name}', 'warning')
        logging.info(f"Custom service rejected: {service_id} by User {current_user.id}")
        return redirect(url_for('manager.custom_service_approvals'))

    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        logging.error(f"Error rejecting custom service: {str(e)}")
        flash('تعذر تنفيذ الرفض حالياً', 'error')
        return redirect(url_for('manager.custom_service_approvals'))