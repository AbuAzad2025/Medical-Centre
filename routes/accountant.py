"""
مسارات المحاسب - Accountant Routes
Medical System Accountant Routes
نسخة محسّنة مع تقارير التدقيق (الأسبوع الثاني)
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.payment import Payment
from models.invoice import Invoice
from models.user import User
from services.report_service import ReportService
from utils.decorators import accountant_only, can_access_financial_reports
from app_factory import db
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

accountant_bp = Blueprint('accountant', __name__)

@accountant_bp.route('/')
@login_required
def index():
    """توجيه تلقائي إلى لوحة التحكم"""
    return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم المحاسب"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات مالية
        today = date.today()
        this_month = today.replace(day=1)
        
        # إجمالي المدفوعات اليوم
        today_payments = Payment.query.filter(
            Payment.created_at >= today
        ).all()
        today_total = sum(payment.amount for payment in today_payments)
        
        # إجمالي المدفوعات الشهر
        month_payments = Payment.query.filter(
            Payment.created_at >= this_month
        ).all()
        month_total = sum(payment.amount for payment in month_payments)
        
        # الفواتير المفتوحة
        open_invoices = Invoice.query.filter(
            Invoice.payment_status.in_(['PENDING', 'PARTIAL'])
        ).count()
        
        # المبالغ المستحقة
        pending_amount = db.session.query(db.func.sum(Invoice.remaining_amount)).filter(
            Invoice.payment_status.in_(['PENDING', 'PARTIAL'])
        ).scalar() or 0
        
        # الميزات الذكية
        smart_analytics = get_accounting_smart_analytics()
        financial_forecasting = get_financial_forecasting()
        cash_flow_analysis = get_cash_flow_analysis()
        payment_optimization = get_payment_optimization()
        financial_health = get_financial_health_monitoring()
        smart_recommendations = get_smart_recommendations()
        
        stats = {
            'today_payments': len(today_payments),
            'today_total': float(today_total),
            'month_total': float(month_total),
            'open_invoices': open_invoices,
            'pending_amount': float(pending_amount),
            'smart_analytics': smart_analytics,
            'financial_forecasting': financial_forecasting,
            'cash_flow_analysis': cash_flow_analysis,
            'payment_optimization': payment_optimization,
            'financial_health': financial_health,
            'smart_recommendations': smart_recommendations
        }
        
        return render_template('accountant/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in accountant dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@accountant_bp.route('/open-invoices')
@login_required
def open_invoices():
    """الفواتير المفتوحة"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب الفواتير المفتوحة
        invoices = Invoice.query.filter(
            Invoice.payment_status.in_(['PENDING', 'PARTIAL'])
        ).order_by(Invoice.created_at.desc()).all()
        
        return render_template('accountant/open_invoices.html', invoices=invoices)
    except Exception as e:
        logging.error(f"Error loading open invoices: {str(e)}")
        flash('حدث خطأ في تحميل الفواتير المفتوحة', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/payments')
@login_required
def payments():
    """سجل المدفوعات"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب المدفوعات
        payments = Payment.query.order_by(Payment.created_at.desc()).all()
        
        return render_template('accountant/payments.html', payments=payments)
    except Exception as e:
        logging.error(f"Error loading payments: {str(e)}")
        flash('حدث خطأ في تحميل سجل المدفوعات', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/payment-documentation/<int:payment_id>')
@login_required
def payment_documentation(payment_id):
    """توثيق الدفع"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        payment = Payment.query.get_or_404(payment_id)
        return render_template('accountant/payment_documentation.html', payment=payment)
    except Exception as e:
        logging.error(f"Error loading payment documentation: {str(e)}")
        flash('حدث خطأ في تحميل توثيق الدفع', 'error')
        return redirect(url_for('accountant.payments'))

@accountant_bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    """طباعة وصل القبض"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        payment = Payment.query.get_or_404(payment_id)
        return render_template('accountant/receipt.html', payment=payment)
    except Exception as e:
        logging.error(f"Error generating receipt: {str(e)}")
        flash('حدث خطأ في إنشاء وصل القبض', 'error')
        return redirect(url_for('accountant.payments'))

@accountant_bp.route('/financial-report')
@login_required
def financial_report():
    """التقرير المالي"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # تحديد الفترة الزمنية
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
        
        # تحويل التواريخ
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # جلب البيانات المالية
        payments = Payment.query.filter(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).all()
        
        # حساب الإحصائيات
        total_payments = sum(payment.amount for payment in payments)
        cash_payments = sum(p.amount for p in payments if p.payment_method == 'cash')
        card_payments = sum(p.amount for p in payments if p.payment_method == 'card')
        insurance_payments = sum(p.amount for p in payments if p.payment_method == 'insurance')
        
        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'total_payments': float(total_payments),
            'cash_payments': float(cash_payments),
            'card_payments': float(card_payments),
            'insurance_payments': float(insurance_payments),
            'payments_count': len(payments)
        }
        
        return render_template('accountant/financial_report.html', report=report_data)
    except Exception as e:
        logging.error(f"Error generating financial report: {str(e)}")
        flash('حدث خطأ في إنشاء التقرير المالي', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/daily-summary')
@login_required
def daily_summary():
    """الملخص اليومي"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        today = date.today()
        
        # المدفوعات اليوم
        today_payments = Payment.query.filter(
            Payment.created_at == today
        ).all()
        
        # الزيارات المكتملة اليوم
        completed_visits = Visit.query.filter(
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.combine(today, datetime.min.time()),
            Visit.completed_at <= datetime.combine(today, datetime.max.time())
        ).all()
        
        # الفواتير الجديدة
        new_invoices = Invoice.query.filter(
            Invoice.created_at >= datetime.combine(today, datetime.min.time()),
            Invoice.created_at <= datetime.combine(today, datetime.max.time())
        ).all()
        
        summary = {
            'date': today,
            'payments_count': len(today_payments),
            'payments_total': sum(p.amount for p in today_payments),
            'completed_visits': len(completed_visits),
            'new_invoices': len(new_invoices),
            'payments': today_payments,
            'visits': completed_visits
        }
        
        return render_template('accountant/daily_summary.html', summary=summary)
    except Exception as e:
        logging.error(f"Error generating daily summary: {str(e)}")
        flash('حدث خطأ في إنشاء الملخص اليومي', 'error')
        return redirect(url_for('accountant.dashboard'))

# ==================== الميزات الذكية للمحاسبة ====================

def get_accounting_smart_analytics():
    """التحليلات الذكية للمحاسبة"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # تحليل المدفوعات
        total_payments = Payment.query.count()
        today_payments = Payment.query.filter(
            func.date(Payment.created_at) == today
        ).count()
        
        # تحليل الفواتير
        total_invoices = Invoice.query.count()
        open_invoices = Invoice.query.filter(Invoice.status == 'ISSUED').count()
        paid_invoices = Invoice.query.filter(Invoice.status == 'PAID').count()
        
        # معدل التحصيل
        collection_rate = (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
        
        # تحليل طرق الدفع
        payment_methods = db.session.query(
            Payment.method,
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('total')
        ).group_by(Payment.method).all()
        
        # تحليل الاتجاهات
        weekly_trend = Payment.query.filter(
            Payment.created_at >= datetime.combine(week_ago, datetime.min.time())
        ).count()
        
        monthly_trend = Payment.query.filter(
            Payment.created_at >= datetime.combine(month_ago, datetime.min.time())
        ).count()

        return {
            'total_payments': total_payments,
            'today_payments': today_payments,
            'total_invoices': total_invoices,
            'open_invoices': open_invoices,
            'paid_invoices': paid_invoices,
            'collection_rate': round(collection_rate, 2),
            'payment_methods': [{'method': p.method, 'count': p.count, 'total': float(p.total)} for p in payment_methods],
            'weekly_trend': weekly_trend,
            'monthly_trend': monthly_trend,
            'efficiency_score': calculate_accounting_efficiency(collection_rate, open_invoices)
        }
    except Exception as e:
        logging.error(f"Error getting accounting smart analytics: {str(e)}")
        return {}

def get_financial_forecasting():
    """التنبؤ المالي"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل الاتجاهات الشهرية
        monthly_data = []
        for i in range(6):  # آخر 6 أشهر
            month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=30)
            
            monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
                and_(
                    Payment.created_at >= month_start,
                    Payment.created_at < month_end
                )
            ).scalar() or 0
            
            monthly_data.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': float(monthly_revenue)
            })

        # التنبؤ بالشهر القادم
        if len(monthly_data) >= 3:
            recent_avg = sum([m['revenue'] for m in monthly_data[:3]]) / 3
            predicted_revenue = recent_avg * 1.1  # نمو متوقع 10%
        else:
            predicted_revenue = 0

        # تحليل الموسمية
        seasonal_analysis = analyze_seasonal_patterns(monthly_data)

        return {
            'monthly_data': monthly_data,
            'predicted_revenue': round(predicted_revenue, 2),
            'seasonal_analysis': seasonal_analysis,
            'growth_rate': calculate_growth_rate(monthly_data)
        }
    except Exception as e:
        logging.error(f"Error getting financial forecasting: {str(e)}")
        return {}

def get_cash_flow_analysis():
    """تحليل التدفق النقدي"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # التدفق النقدي اليومي
        daily_cash_flow = db.session.query(
            func.date(Payment.created_at).label('date'),
            func.sum(Payment.amount).label('amount')
        ).filter(
            Payment.created_at >= datetime.combine(week_ago, datetime.min.time())
        ).group_by(func.date(Payment.created_at)).all()

        # تحليل التدفق الأسبوعي
        weekly_inflow = db.session.query(func.sum(Payment.amount)).filter(
            Payment.created_at >= datetime.combine(week_ago, datetime.min.time())
        ).scalar() or 0

        # تحليل التدفق الشهري
        monthly_inflow = db.session.query(func.sum(Payment.amount)).filter(
            Payment.created_at >= datetime.combine(month_ago, datetime.min.time())
        ).scalar() or 0

        # تحليل المبالغ المستحقة
        pending_amount = db.session.query(func.sum(Invoice.total_amount - Invoice.paid_amount)).filter(
            Invoice.status == 'ISSUED'
        ).scalar() or 0

        return {
            'daily_cash_flow': [{'date': str(d.date), 'amount': float(d.amount)} for d in daily_cash_flow],
            'weekly_inflow': float(weekly_inflow),
            'monthly_inflow': float(monthly_inflow),
            'pending_amount': float(pending_amount),
            'cash_flow_health': calculate_cash_flow_health(weekly_inflow, pending_amount)
        }
    except Exception as e:
        logging.error(f"Error getting cash flow analysis: {str(e)}")
        return {}

def get_payment_optimization():
    """تحسين المدفوعات"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل طرق الدفع
        payment_method_analysis = db.session.query(
            Payment.method,
            func.count(Payment.id).label('count'),
            func.avg(Payment.amount).label('avg_amount'),
            func.sum(Payment.amount).label('total_amount')
        ).group_by(Payment.method).all()

        # تحليل أوقات الدفع
        payment_times = db.session.query(
            func.strftime('%H', Payment.created_at).label('hour'),
            func.count(Payment.id).label('count')
        ).group_by(func.strftime('%H', Payment.created_at)).all()

        # تحليل المدفوعات المتأخرة
        late_payments = Invoice.query.filter(
            and_(
                Invoice.status == 'ISSUED',
                Invoice.created_at < datetime.now() - timedelta(days=30)
            )
        ).count()

        # اقتراحات التحسين
        optimization_suggestions = generate_payment_optimization_suggestions(
            payment_method_analysis, late_payments
        )

        return {
            'payment_methods': [{
                'method': p.method,
                'count': p.count,
                'avg_amount': float(p.avg_amount),
                'total_amount': float(p.total_amount)
            } for p in payment_method_analysis],
            'payment_times': [{'hour': p.hour, 'count': p.count} for p in payment_times],
            'late_payments': late_payments,
            'optimization_suggestions': optimization_suggestions,
            'efficiency_score': calculate_payment_efficiency(payment_method_analysis)
        }
    except Exception as e:
        logging.error(f"Error getting payment optimization: {str(e)}")
        return {}

def get_financial_health_monitoring():
    """مراقبة الصحة المالية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        # مؤشرات الصحة المالية
        total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0
        total_invoices = Invoice.query.count()
        paid_invoices = Invoice.query.filter(Invoice.status == 'PAID').count()
        
        # معدل التحصيل
        collection_rate = (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
        
        # المبالغ المستحقة
        outstanding_amount = db.session.query(
            func.sum(Invoice.total_amount - Invoice.paid_amount)
        ).filter(Invoice.status == 'ISSUED').scalar() or 0

        # تحليل المخاطر
        risk_indicators = analyze_financial_risks(collection_rate, outstanding_amount, total_revenue)

        # التنبيهات المالية
        financial_alerts = generate_financial_alerts(collection_rate, outstanding_amount)

        return {
            'total_revenue': float(total_revenue),
            'collection_rate': round(collection_rate, 2),
            'outstanding_amount': float(outstanding_amount),
            'risk_indicators': risk_indicators,
            'financial_alerts': financial_alerts,
            'health_score': calculate_financial_health_score(collection_rate, outstanding_amount)
        }
    except Exception as e:
        logging.error(f"Error getting financial health monitoring: {str(e)}")
        return {}

def get_smart_recommendations():
    """التوصيات الذكية للمحاسبة"""
    try:
        recommendations = []
        
        # تحليل البيانات الحالية
        analytics = get_accounting_smart_analytics()
        forecasting = get_financial_forecasting()
        cash_flow = get_cash_flow_analysis()
        optimization = get_payment_optimization()
        health = get_financial_health_monitoring()

        # توصيات بناءً على التحليل
        if analytics.get('collection_rate', 0) < 80:
            recommendations.append({
                'title': 'تحسين معدل التحصيل',
                'description': f'معدل التحصيل الحالي {analytics.get("collection_rate", 0)}% منخفض. يُنصح بتحسين متابعة المدفوعات.',
                'priority': 'high',
                'category': 'collection'
            })

        if health.get('outstanding_amount', 0) > 10000:
            recommendations.append({
                'title': 'متابعة المبالغ المستحقة',
                'description': f'المبلغ المستحق {health.get("outstanding_amount", 0):.2f} شيكل مرتفع. يُنصح بمتابعة الفواتير المفتوحة.',
                'priority': 'high',
                'category': 'outstanding'
            })

        if optimization.get('late_payments', 0) > 5:
            recommendations.append({
                'title': 'تقليل المدفوعات المتأخرة',
                'description': f'عدد المدفوعات المتأخرة {optimization.get("late_payments", 0)} مرتفع. يُنصح بتحسين نظام المتابعة.',
                'priority': 'medium',
                'category': 'late_payments'
            })

        if forecasting.get('growth_rate', 0) < 5:
            recommendations.append({
                'title': 'تحسين النمو المالي',
                'description': 'معدل النمو المالي منخفض. يُنصح بتحليل أسباب الانخفاض ووضع استراتيجية تحسين.',
                'priority': 'medium',
                'category': 'growth'
            })

        return {
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r['priority'] == 'high']),
            'medium_priority': len([r for r in recommendations if r['priority'] == 'medium'])
        }
    except Exception as e:
        logging.error(f"Error getting smart recommendations: {str(e)}")
        return {'recommendations': [], 'total_recommendations': 0}

# ==================== دوال مساعدة ====================

def calculate_accounting_efficiency(collection_rate, open_invoices):
    """حساب كفاءة المحاسبة"""
    try:
        efficiency = (collection_rate * 0.7) + ((100 - open_invoices) * 0.3)
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def analyze_seasonal_patterns(monthly_data):
    """تحليل الأنماط الموسمية"""
    try:
        if len(monthly_data) < 3:
            return {'pattern': 'غير كافي للتحليل', 'confidence': 0}
        
        revenues = [m['revenue'] for m in monthly_data]
        avg_revenue = sum(revenues) / len(revenues)
        
        # تحليل الاتجاه
        if revenues[-1] > revenues[0]:
            trend = 'تصاعدي'
        elif revenues[-1] < revenues[0]:
            trend = 'تنازلي'
        else:
            trend = 'مستقر'
        
        return {
            'pattern': trend,
            'confidence': min(100, len(monthly_data) * 20),
            'avg_revenue': round(avg_revenue, 2)
        }
    except:
        return {'pattern': 'غير محدد', 'confidence': 0}

def calculate_growth_rate(monthly_data):
    """حساب معدل النمو"""
    try:
        if len(monthly_data) < 2:
            return 0
        
        recent = monthly_data[0]['revenue']
        previous = monthly_data[1]['revenue']
        
        if previous == 0:
            return 0
        
        growth = ((recent - previous) / previous) * 100
        return round(growth, 2)
    except:
        return 0

def calculate_cash_flow_health(weekly_inflow, pending_amount):
    """حساب صحة التدفق النقدي"""
    try:
        if pending_amount == 0:
            return 100
        
        ratio = weekly_inflow / pending_amount
        if ratio > 2:
            return 100
        elif ratio > 1:
            return 80
        elif ratio > 0.5:
            return 60
        else:
            return 40
    except:
        return 0

def generate_payment_optimization_suggestions(payment_methods, late_payments):
    """توليد اقتراحات تحسين المدفوعات"""
    suggestions = []
    
    try:
        # تحليل طرق الدفع
        cash_payments = next((p for p in payment_methods if p.method == 'CASH'), None)
        card_payments = next((p for p in payment_methods if p.method == 'CARD'), None)
        
        if cash_payments and card_payments:
            if cash_payments.count > card_payments.count * 2:
                suggestions.append('زيادة استخدام البطاقات الائتمانية لتقليل التعامل النقدي')
        
        # تحليل المدفوعات المتأخرة
        if late_payments > 10:
            suggestions.append('تحسين نظام متابعة المدفوعات المتأخرة')
        
        if not suggestions:
            suggestions.append('النظام يعمل بكفاءة جيدة')
            
    except Exception as e:
        suggestions.append('تحليل البيانات للتحسين')
    
    return suggestions

def calculate_payment_efficiency(payment_methods):
    """حساب كفاءة المدفوعات"""
    try:
        if not payment_methods:
            return 0
        
        total_payments = sum(p.count for p in payment_methods)
        if total_payments == 0:
            return 0
        
        # كفاءة بناءً على تنوع طرق الدفع
        method_diversity = len(payment_methods) / 3 * 100  # 3 طرق دفع مثالية
        return min(100, round(method_diversity, 2))
    except:
        return 0

def analyze_financial_risks(collection_rate, outstanding_amount, total_revenue):
    """تحليل المخاطر المالية"""
    risks = []
    
    try:
        if collection_rate < 70:
            risks.append({'type': 'مخاطر التحصيل', 'level': 'عالي', 'description': 'معدل التحصيل منخفض'})
        
        if outstanding_amount > total_revenue * 0.3:
            risks.append({'type': 'مخاطر السيولة', 'level': 'متوسط', 'description': 'المبالغ المستحقة مرتفعة'})
        
        if not risks:
            risks.append({'type': 'لا توجد مخاطر', 'level': 'منخفض', 'description': 'الوضع المالي مستقر'})
            
    except:
        risks.append({'type': 'خطأ في التحليل', 'level': 'غير محدد', 'description': 'تعذر تحليل المخاطر'})
    
    return risks

def generate_financial_alerts(collection_rate, outstanding_amount):
    """توليد التنبيهات المالية"""
    alerts = []
    
    try:
        if collection_rate < 60:
            alerts.append({
                'type': 'تحذير',
                'message': f'معدل التحصيل منخفض جداً: {collection_rate}%',
                'priority': 'high'
            })
        
        if outstanding_amount > 50000:
            alerts.append({
                'type': 'تنبيه',
                'message': f'المبلغ المستحق مرتفع: {outstanding_amount:.2f} شيكل',
                'priority': 'medium'
            })
        
        if not alerts:
            alerts.append({
                'type': 'معلومات',
                'message': 'الوضع المالي مستقر',
                'priority': 'low'
            })
            
    except:
        alerts.append({
            'type': 'خطأ',
            'message': 'تعذر تحليل التنبيهات',
            'priority': 'high'
        })
    
    return alerts

def calculate_financial_health_score(collection_rate, outstanding_amount):
    """حساب درجة الصحة المالية"""
    try:
        # حساب النقاط بناءً على معدل التحصيل
        collection_score = min(100, collection_rate)
        
        # حساب النقاط بناءً على المبالغ المستحقة
        if outstanding_amount == 0:
            outstanding_score = 100
        elif outstanding_amount < 10000:
            outstanding_score = 90
        elif outstanding_amount < 50000:
            outstanding_score = 70
        else:
            outstanding_score = 50
        
        # المتوسط المرجح
        health_score = (collection_score * 0.6) + (outstanding_score * 0.4)
        return round(health_score, 2)
    except:
        return 0

@accountant_bp.route('/invoices')
@login_required
def invoices():
    """الفواتير"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('accountant/pending_payments.html')

@accountant_bp.route('/reports')
@login_required
def reports():
    """التقارير المالية"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('accountant/financial_reports.html')

@accountant_bp.route('/financial')
@login_required
def financial():
    """الإدارة المالية"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('accountant/payment_management.html')

# ==================== مسارات التدقيق (الأسبوع الثاني) ====================

@accountant_bp.route('/audit/daily')
@accountant_bp.route('/audit/daily/<date_str>')
@login_required
@can_access_financial_reports
def daily_audit_report(date_str=None):
    """تقرير التدقيق اليومي"""
    try:
        # تحليل التاريخ
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today()
        
        # الحصول على التقرير
        report = ReportService.get_daily_audit_report(target_date)
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/daily_audit_report.html', 
                             report=report,
                             target_date=target_date)
    
    except ValueError:
        flash('تنسيق التاريخ غير صحيح', 'error')
        return redirect(url_for('accountant.dashboard'))
    except Exception as e:
        logging.error(f"Error in daily_audit_report: {str(e)}")
        flash(f'حدث خطأ: {str(e)}', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/monthly')
@accountant_bp.route('/audit/monthly/<int:year>/<int:month>')
@login_required
@can_access_financial_reports
def monthly_audit_report(year=None, month=None):
    """تقرير التدقيق الشهري"""
    try:
        # استخدام الشهر الحالي إذا لم يُحدد
        if not year:
            year = date.today().year
        if not month:
            month = date.today().month
        
        # الحصول على التقرير
        report = ReportService.get_monthly_audit_report(year, month)
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/monthly_audit_report.html',
                             report=report,
                             year=year,
                             month=month)
    
    except Exception as e:
        logging.error(f"Error in monthly_audit_report: {str(e)}")
        flash(f'حدث خطأ: {str(e)}', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/debts')
@login_required
@can_access_financial_reports
def debt_tracking_report():
    """تقرير تتبع الديون"""
    try:
        # الحصول على التقرير
        report = ReportService.get_debt_tracking_report()
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/debt_tracking_report.html',
                             report=report)
    
    except Exception as e:
        logging.error(f"Error in debt_tracking_report: {str(e)}")
        flash(f'حدث خطأ: {str(e)}', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/export/<report_type>')
@login_required
@can_access_financial_reports
def export_audit_report(report_type):
    """تصدير تقرير التدقيق"""
    try:
        format_type = request.args.get('format', 'json')
        
        # الحصول على التقرير المناسب
        if report_type == 'daily':
            date_str = request.args.get('date')
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
            report = ReportService.get_daily_audit_report(target_date)
        
        elif report_type == 'monthly':
            year = request.args.get('year', date.today().year, type=int)
            month = request.args.get('month', date.today().month, type=int)
            report = ReportService.get_monthly_audit_report(year, month)
        
        elif report_type == 'debts':
            report = ReportService.get_debt_tracking_report()
        
        else:
            flash('نوع تقرير غير معروف', 'error')
            return redirect(url_for('accountant.dashboard'))
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        # تصدير بالتنسيق المطلوب
        if format_type == 'json':
            return jsonify(report)
        else:
            flash('تنسيق التصدير غير مدعوم حالياً', 'warning')
            return redirect(url_for('accountant.dashboard'))
    
    except Exception as e:
        logging.error(f"Error exporting report: {str(e)}")
        flash(f'حدث خطأ في التصدير: {str(e)}', 'error')
        return redirect(url_for('accountant.dashboard'))


