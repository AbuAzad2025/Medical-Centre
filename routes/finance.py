"""
مسارات المالية - Finance Routes
Medical System Finance Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.visit import Visit
from models.payment import Payment
from models.invoice import Invoice
from services.gatekeeper_service import GatekeeperService
from models.audit_trail import AuditTrail
from app_factory import db
import logging
from datetime import datetime

finance_bp = Blueprint('finance', __name__)

@finance_bp.route('/finance/dashboard')
@login_required
def dashboard():
    """لوحة تحكم المالية"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات مالية
        total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.is_provisional == False
        ).scalar() or 0
        
        pending_payments = Payment.query.filter(
            Payment.is_provisional == True
        ).count()
        
        locked_visits = Visit.query.filter(
            Visit.financial_locked == True
        ).count()
        
        stats = {
            'total_revenue': total_revenue,
            'pending_payments': pending_payments,
            'locked_visits': locked_visits
        }
        
        return render_template('finance/dashboard.html', stats=stats)
        
    except Exception as e:
        logging.error(f"Error loading finance dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم المالية', 'error')
        return redirect(url_for('main.dashboard'))

@finance_bp.route('/post', methods=['POST'])
@login_required
def post_gl():
    """الترحيل المالي - Finance فقط"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        return jsonify({'error': 'ليس لديك صلاحية للترحيل المالي'}), 403
    
    try:
        data = request.get_json()
        visit_id = data.get('visit_id')
        
        if not visit_id:
            return jsonify({'error': 'معرف الزيارة مطلوب'}), 400
        
        # استخدام حراسة الخدمة
        success, message = GatekeeperService.post_gl(visit_id, current_user.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 422
            
    except Exception as e:
        logging.error(f"Error posting GL: {str(e)}")
        return jsonify({'error': f'خطأ في الترحيل المالي: {str(e)}'}), 500

@finance_bp.route('/visits/<int:visit_id>/archive', methods=['POST'])
@login_required
def archive_visit(visit_id):
    """أرشفة الزيارة - Finance فقط"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        return jsonify({'error': 'ليس لديك صلاحية لأرشفة الزيارات'}), 403
    
    try:
        # استخدام حراسة الخدمة
        success, message = GatekeeperService.archive_visit(visit_id, current_user.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 422
            
    except Exception as e:
        logging.error(f"Error archiving visit: {str(e)}")
        return jsonify({'error': f'خطأ في الأرشفة: {str(e)}'}), 500

# تم نقل مسار الزيارات إلى routes/reception.py لتجنب التكرار
# يمكن الوصول إليه عبر /reception/visits

@finance_bp.route('/payments')
@login_required
def payments():
    """عرض المدفوعات"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        payments = Payment.query.order_by(Payment.created_at.desc()).all()
        return render_template('finance/payments.html', payments=payments)
        
    except Exception as e:
        logging.error(f"Error loading payments: {str(e)}")
        flash('حدث خطأ في تحميل المدفوعات', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/invoices')
@login_required
def invoices():
    """عرض الفواتير"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        invoices = Invoice.query.order_by(Invoice.created_at.desc()).all()
        return render_template('finance/invoices.html', invoices=invoices)
        
    except Exception as e:
        logging.error(f"Error loading invoices: {str(e)}")
        flash('حدث خطأ في تحميل الفواتير', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/audit')
@login_required
def audit():
    """عرض التدقيق المالي"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        audit_entries = AuditTrail.query.filter(
            AuditTrail.entity_type.in_(['visit', 'payment', 'invoice'])
        ).order_by(AuditTrail.created_at.desc()).all()
        
        return render_template('finance/audit.html', audit_entries=audit_entries)
        
    except Exception as e:
        logging.error(f"Error loading audit: {str(e)}")
        flash('حدث خطأ في تحميل التدقيق', 'error')
        return redirect(url_for('finance.dashboard'))
