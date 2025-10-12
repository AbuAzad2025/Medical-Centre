"""
مسارات الدفع - Payment Routes
Medical System Payment Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.payment import Payment, PaymentMethod
from models.patient import Patient
from models.visit import Visit
from models.invoice import Invoice
from app_factory import db
import logging
from datetime import datetime, timedelta
import json

payment_bp = Blueprint('payment', __name__)

@payment_bp.route('/payment/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الدفع"""
    if current_user.role not in ['accountant', 'reception', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات الدفع
        today = datetime.now().date()
        
        # المدفوعات اليوم
        payments_today = Payment.query.filter(
            Payment.created_at >= today
        ).count()
        
        # إجمال المدفوعات اليوم
        total_today = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.created_at >= today
        ).scalar() or 0
        
        # المدفوعات المعلقة
        pending_payments = Payment.query.filter_by(status='pending').count()
        
        # المدفوعات المرفوضة
        failed_payments = Payment.query.filter_by(status='failed').count()
        
        # طرق الدفع الأكثر استخداماً
        payment_methods = db.session.query(
            Payment.payment_method,
            db.func.count(Payment.id).label('count')
        ).group_by(Payment.payment_method).all()
        
        stats = {
            'payments_today': payments_today,
            'total_today': total_today,
            'pending_payments': pending_payments,
            'failed_payments': failed_payments,
            'payment_methods': payment_methods
        }
        
        return render_template('payment/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in payment dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@payment_bp.route('/payment/process/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def process_payment(visit_id):
    """معالجة دفع"""
    if current_user.role not in ['accountant', 'reception', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    visit = Visit.query.get_or_404(visit_id)
    
    if request.method == 'POST':
        try:
            payment = Payment(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                amount=float(request.form.get('amount')),
                payment_method=request.form.get('payment_method'),
                status='completed',
                created_by=current_user.id,
                notes=request.form.get('notes')
            )
            
            db.session.add(payment)
            db.session.commit()
            
            flash('تم معالجة الدفع بنجاح', 'success')
            return redirect(url_for('payment.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing payment: {str(e)}")
            flash(f'حدث خطأ في معالجة الدفع: {str(e)}', 'error')
    
    return render_template('payment/process.html', visit=visit)

@payment_bp.route('/payment/history')
@login_required
def payment_history():
    """تاريخ المدفوعات"""
    if current_user.role not in ['accountant', 'reception', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # فلترة المدفوعات
        status = request.args.get('status', '')
        payment_method = request.args.get('payment_method', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        query = Payment.query
        
        if status:
            query = query.filter(Payment.status == status)
        
        if payment_method:
            query = query.filter(Payment.payment_method == payment_method)
        
        if date_from:
            query = query.filter(Payment.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        
        if date_to:
            query = query.filter(Payment.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
        
        payments = query.order_by(Payment.created_at.desc()).all()
        
        return render_template('payment/history.html', 
                             payments=payments,
                             status=status,
                             payment_method=payment_method,
                             date_from=date_from,
                             date_to=date_to)
    except Exception as e:
        logging.error(f"Error loading payment history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ المدفوعات', 'error')
        return redirect(url_for('payment.dashboard'))

@payment_bp.route('/payment/methods')
@login_required
def payment_methods():
    """طرق الدفع"""
    if current_user.role not in ['admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        methods = PaymentMethod.query.all()
        return render_template('payment/methods.html', methods=methods)
    except Exception as e:
        logging.error(f"Error loading payment methods: {str(e)}")
        flash('حدث خطأ في تحميل طرق الدفع', 'error')
        return redirect(url_for('payment.dashboard'))

@payment_bp.route('/payment/reports')
@login_required
def payment_reports():
    """تقارير الدفع"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # تقرير المدفوعات اليومية
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        daily_payments = db.session.query(
            db.func.date(Payment.created_at).label('date'),
            db.func.count(Payment.id).label('count'),
            db.func.sum(Payment.amount).label('total')
        ).filter(
            Payment.created_at >= week_ago
        ).group_by(db.func.date(Payment.created_at)).all()
        
        # تقرير طرق الدفع
        method_stats = db.session.query(
            Payment.payment_method,
            db.func.count(Payment.id).label('count'),
            db.func.sum(Payment.amount).label('total')
        ).filter(
            Payment.created_at >= week_ago
        ).group_by(Payment.payment_method).all()
        
        return render_template('payment/reports.html', 
                             daily_payments=daily_payments,
                             method_stats=method_stats)
    except Exception as e:
        logging.error(f"Error loading payment reports: {str(e)}")
        flash('حدث خطأ في تحميل تقارير الدفع', 'error')
        return redirect(url_for('payment.dashboard'))
