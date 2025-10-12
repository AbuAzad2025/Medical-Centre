"""
مسارات الأدوية - Medication Routes
Medical System Medication Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.medication import Medication
from models.patient import Patient
from models.visit import Visit
from app_factory import db
import logging
from datetime import datetime
import json

medication_bp = Blueprint('medication', __name__)

@medication_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الأدوية"""
    if current_user.role not in ['doctor', 'nurse', 'pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات الأدوية
        total_medications = Medication.query.count()
        active_medications = Medication.query.filter_by(is_active=True).count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.min_stock_level
        ).count()
        
        # الأدوية منخفضة المخزون
        low_stock = Medication.query.filter(
            Medication.stock_quantity <= Medication.min_stock_level
        ).limit(10).all()
        
        # الأدوية الأكثر استخداماً
        most_used = Medication.query.order_by(
            Medication.usage_count.desc()
        ).limit(5).all()
        
        # الميزات الذكية
        smart_analytics = get_pharmacy_smart_analytics()
        inventory_optimization = get_inventory_optimization()
        safety_monitoring = get_medication_safety_monitoring()
        prescription_analytics = get_prescription_analytics()
        drug_interaction_checker = get_drug_interaction_checker()
        workflow_automation = get_pharmacy_workflow_automation()
        predictive_insights = get_pharmacy_predictive_insights()
        smart_recommendations = get_pharmacy_smart_recommendations()
        
        stats = {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'low_stock': low_stock,
            'most_used': most_used,
            'smart_analytics': smart_analytics,
            'inventory_optimization': inventory_optimization,
            'safety_monitoring': safety_monitoring,
            'prescription_analytics': prescription_analytics,
            'drug_interaction_checker': drug_interaction_checker,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights,
            'smart_recommendations': smart_recommendations
        }
        
        return render_template('medication/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in medication dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@medication_bp.route('/list')
@login_required
def list_medications():
    """قائمة الأدوية"""
    if current_user.role not in ['doctor', 'nurse', 'pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب الأدوية مع فلترة
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        
        query = Medication.query
        
        if search:
            query = query.filter(
                Medication.name.contains(search) |
                Medication.generic_name.contains(search)
            )
        
        if category:
            query = query.filter(Medication.category == category)
        
        medications = query.order_by(Medication.name).all()
        
        return render_template('medication/list.html', 
                             medications=medications,
                             search=search,
                             category=category)
    except Exception as e:
        logging.error(f"Error listing medications: {str(e)}")
        flash('حدث خطأ في تحميل قائمة الأدوية', 'error')
        return redirect(url_for('medication.dashboard'))

@medication_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_medication():
    """إضافة دواء جديد"""
    if current_user.role not in ['pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            medication = Medication(
                name=request.form.get('name'),
                generic_name=request.form.get('generic_name'),
                category=request.form.get('category'),
                dosage_form=request.form.get('dosage_form'),
                strength=request.form.get('strength'),
                unit=request.form.get('unit'),
                stock_quantity=int(request.form.get('stock_quantity', 0)),
                min_stock_level=int(request.form.get('min_stock_level', 10)),
                price=float(request.form.get('price', 0)),
                is_active=True
            )
            
            db.session.add(medication)
            db.session.commit()
            
            flash('تم إضافة الدواء بنجاح', 'success')
            return redirect(url_for('medication.list_medications'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding medication: {str(e)}")
            flash(f'حدث خطأ في إضافة الدواء: {str(e)}', 'error')
    
    return render_template('medication/add.html')

@medication_bp.route('/edit/<int:medication_id>', methods=['GET', 'POST'])
@login_required
def edit_medication(medication_id):
    """تعديل دواء"""
    if current_user.role not in ['pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    medication = Medication.query.get_or_404(medication_id)
    
    if request.method == 'POST':
        try:
            medication.name = request.form.get('name')
            medication.generic_name = request.form.get('generic_name')
            medication.category = request.form.get('category')
            medication.dosage_form = request.form.get('dosage_form')
            medication.strength = request.form.get('strength')
            medication.unit = request.form.get('unit')
            medication.stock_quantity = int(request.form.get('stock_quantity', 0))
            medication.min_stock_level = int(request.form.get('min_stock_level', 10))
            medication.price = float(request.form.get('price', 0))
            
            db.session.commit()
            
            flash('تم تحديث الدواء بنجاح', 'success')
            return redirect(url_for('medication.list_medications'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editing medication: {str(e)}")
            flash(f'حدث خطأ في تحديث الدواء: {str(e)}', 'error')
    
    return render_template('medication/edit.html', medication=medication)

@medication_bp.route('/stock-alerts')
@login_required
def stock_alerts():
    """تنبيهات المخزون"""
    if current_user.role not in ['pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # الأدوية منخفضة المخزون
        low_stock = Medication.query.filter(
            Medication.stock_quantity <= Medication.min_stock_level
        ).all()
        
        # الأدوية المنتهية الصلاحية قريباً
        expiring_soon = Medication.query.filter(
            Medication.expiry_date <= datetime.now() + timedelta(days=30)
        ).all()
        
        return render_template('medication/stock_alerts.html', 
                             low_stock=low_stock,
                             expiring_soon=expiring_soon)
    except Exception as e:
        logging.error(f"Error loading stock alerts: {str(e)}")
        flash('حدث خطأ في تحميل تنبيهات المخزون', 'error')
        return redirect(url_for('medication.dashboard'))

@medication_bp.route('/prescriptions')
@login_required
def prescriptions():
    """الروشتات"""
    if current_user.role not in ['pharmacist', 'admin', 'manager', 'doctor']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.prescription import Prescription
        
        # جلب جميع الروشتات
        prescriptions = Prescription.query.order_by(Prescription.created_at.desc()).all()
        
        return render_template('medication/prescriptions.html', prescriptions=prescriptions)
    
    except Exception as e:
        logging.error(f"Error loading prescriptions: {str(e)}")
        flash('حدث خطأ في تحميل الروشتات', 'error')
        return redirect(url_for('medication.dashboard'))

# ==================== الميزات الذكية للصيدلية ====================

def get_pharmacy_smart_analytics():
    """التحليلات الذكية للصيدلية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل الأدوية
        total_medications = Medication.query.count()
        active_medications = Medication.query.filter(Medication.is_active == True).count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل المخزون
        total_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).scalar() or 0
        low_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).scalar() or 0
        
        # تحليل الفئات
        categories = db.session.query(
            Medication.category,
            func.count(Medication.id).label('count'),
            func.sum(Medication.stock_quantity).label('total_stock')
        ).group_by(Medication.category).all()
        
        # تحليل الاستخدام
        most_used_medications = Medication.query.order_by(
            Medication.usage_count.desc()
        ).limit(5).all()

        return {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'total_stock_value': float(total_stock_value),
            'low_stock_value': float(low_stock_value),
            'categories': [{'category': c.category, 'count': c.count, 'total_stock': c.total_stock} for c in categories],
            'most_used': [{'name': m.trade_name, 'usage_count': m.usage_count or 0} for m in most_used_medications],
            'efficiency_score': calculate_pharmacy_efficiency(active_medications, low_stock_medications, total_medications)
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy smart analytics: {str(e)}")
        return {}

def get_inventory_optimization():
    """تحسين المخزون"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        # تحليل المخزون
        total_medications = Medication.query.count()
        low_stock_count = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل انتهاء الصلاحية
        expiring_soon = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date <= datetime.now().date() + timedelta(days=30)
            )
        ).count()
        
        # تحليل القيمة
        total_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).scalar() or 0
        low_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).scalar() or 0
        
        # اقتراحات التحسين
        optimization_suggestions = generate_inventory_optimization_suggestions(
            low_stock_count, expiring_soon, total_medications
        )

        return {
            'total_medications': total_medications,
            'low_stock_count': low_stock_count,
            'expiring_soon': expiring_soon,
            'total_value': float(total_value),
            'low_stock_value': float(low_stock_value),
            'optimization_suggestions': optimization_suggestions,
            'efficiency_score': calculate_inventory_efficiency(low_stock_count, expiring_soon, total_medications)
        }
    except Exception as e:
        logging.error(f"Error getting inventory optimization: {str(e)}")
        return {}

def get_medication_safety_monitoring():
    """مراقبة سلامة الأدوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        # تحليل انتهاء الصلاحية
        expired_medications = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date < datetime.now().date()
            )
        ).count()
        
        expiring_soon = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date <= datetime.now().date() + timedelta(days=30)
            )
        ).count()
        
        # تحليل التفاعلات الدوائية
        medications_with_interactions = Medication.query.filter(
            Medication.drug_interactions.isnot(None)
        ).count()
        
        # تحليل الآثار الجانبية
        medications_with_side_effects = Medication.query.filter(
            Medication.side_effects.isnot(None)
        ).count()
        
        # تحليل الموانع
        medications_with_contraindications = Medication.query.filter(
            Medication.contraindications.isnot(None)
        ).count()

        return {
            'expired_medications': expired_medications,
            'expiring_soon': expiring_soon,
            'medications_with_interactions': medications_with_interactions,
            'medications_with_side_effects': medications_with_side_effects,
            'medications_with_contraindications': medications_with_contraindications,
            'safety_score': calculate_safety_score(expired_medications, expiring_soon, medications_with_interactions)
        }
    except Exception as e:
        logging.error(f"Error getting medication safety monitoring: {str(e)}")
        return {}

def get_prescription_analytics():
    """تحليلات الوصفات الطبية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.medication import Prescription

        # تحليل الوصفات
        total_prescriptions = Prescription.query.count()
        active_prescriptions = Prescription.query.filter(Prescription.status == 'active').count()
        dispensed_prescriptions = Prescription.query.filter(Prescription.status == 'dispensed').count()
        
        # تحليل التكلفة
        total_cost = db.session.query(func.sum(Prescription.total_cost)).scalar() or 0
        avg_cost = db.session.query(func.avg(Prescription.total_cost)).scalar() or 0
        
        # تحليل الاتجاهات
        weekly_prescriptions = Prescription.query.filter(
            Prescription.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        monthly_prescriptions = Prescription.query.filter(
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).count()

        return {
            'total_prescriptions': total_prescriptions,
            'active_prescriptions': active_prescriptions,
            'dispensed_prescriptions': dispensed_prescriptions,
            'total_cost': float(total_cost),
            'avg_cost': float(avg_cost),
            'weekly_prescriptions': weekly_prescriptions,
            'monthly_prescriptions': monthly_prescriptions,
            'dispensing_rate': (dispensed_prescriptions / total_prescriptions * 100) if total_prescriptions > 0 else 0
        }
    except Exception as e:
        logging.error(f"Error getting prescription analytics: {str(e)}")
        return {}

def get_drug_interaction_checker():
    """فحص التفاعلات الدوائية"""
    try:
        from sqlalchemy import func, and_

        # تحليل الأدوية مع التفاعلات
        medications_with_interactions = Medication.query.filter(
            Medication.drug_interactions.isnot(None)
        ).count()
        
        # تحليل شدة التفاعلات
        severe_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('severe')
            )
        ).count()
        
        moderate_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('moderate')
            )
        ).count()
        
        mild_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('mild')
            )
        ).count()

        return {
            'medications_with_interactions': medications_with_interactions,
            'severe_interactions': severe_interactions,
            'moderate_interactions': moderate_interactions,
            'mild_interactions': mild_interactions,
            'interaction_risk_score': calculate_interaction_risk_score(severe_interactions, moderate_interactions, mild_interactions)
        }
    except Exception as e:
        logging.error(f"Error getting drug interaction checker: {str(e)}")
        return {}

def get_pharmacy_workflow_automation():
    """أتمتة سير عمل الصيدلية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل المهام المؤتمتة
        automated_tasks = 0  # يمكن إضافة نموذج للمهام المؤتمتة
        manual_tasks = 0  # يمكن إضافة نموذج للمهام اليدوية
        
        # تحليل أوقات المعالجة
        avg_processing_time = 0  # يمكن حساب متوسط وقت معالجة الوصفات
        
        # تحليل الكفاءة
        efficiency_metrics = {
            'automation_rate': 0,
            'time_saved': 0,
            'error_reduction': 0,
            'productivity_gain': 0
        }

        return {
            'automated_tasks': automated_tasks,
            'manual_tasks': manual_tasks,
            'avg_processing_time': avg_processing_time,
            'efficiency_metrics': efficiency_metrics,
            'automation_score': calculate_automation_score(automated_tasks, manual_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy workflow automation: {str(e)}")
        return {}

def get_pharmacy_predictive_insights():
    """الرؤى التنبؤية للصيدلية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل الطلب المتوقع
        weekly_demand = 0  # يمكن حساب الطلب الأسبوعي
        monthly_demand = 0  # يمكن حساب الطلب الشهري
        
        # تحليل النمو
        growth_rate = 0  # يمكن حساب معدل النمو
        
        # تحليل الذروة
        peak_hours = []  # يمكن تحديد ساعات الذروة
        
        # التنبؤ بالمخزون
        predicted_stock_needs = 0  # يمكن التنبؤ باحتياجات المخزون

        return {
            'weekly_demand': weekly_demand,
            'monthly_demand': monthly_demand,
            'growth_rate': growth_rate,
            'peak_hours': peak_hours,
            'predicted_stock_needs': predicted_stock_needs,
            'demand_forecast_accuracy': calculate_demand_forecast_accuracy()
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy predictive insights: {str(e)}")
        return {}

def get_pharmacy_smart_recommendations():
    """التوصيات الذكية للصيدلية"""
    try:
        recommendations = []
        
        # تحليل البيانات الحالية
        analytics = get_pharmacy_smart_analytics()
        inventory = get_inventory_optimization()
        safety = get_medication_safety_monitoring()
        prescriptions = get_prescription_analytics()
        interactions = get_drug_interaction_checker()

        # توصيات بناءً على التحليل
        if analytics.get('low_stock_medications', 0) > 5:
            recommendations.append({
                'title': 'تحسين إدارة المخزون',
                'description': f'عدد الأدوية منخفضة المخزون {analytics.get("low_stock_medications", 0)} مرتفع. يُنصح بتحسين إدارة المخزون.',
                'priority': 'high',
                'category': 'inventory'
            })

        if safety.get('expired_medications', 0) > 0:
            recommendations.append({
                'title': 'إزالة الأدوية المنتهية الصلاحية',
                'description': f'يوجد {safety.get("expired_medications", 0)} دواء منتهي الصلاحية. يُنصح بإزالته فوراً.',
                'priority': 'high',
                'category': 'safety'
            })

        if safety.get('expiring_soon', 0) > 3:
            recommendations.append({
                'title': 'متابعة الأدوية القريبة من انتهاء الصلاحية',
                'description': f'يوجد {safety.get("expiring_soon", 0)} دواء قريب من انتهاء الصلاحية. يُنصح بمتابعته.',
                'priority': 'medium',
                'category': 'safety'
            })

        if interactions.get('severe_interactions', 0) > 0:
            recommendations.append({
                'title': 'مراجعة التفاعلات الدوائية الشديدة',
                'description': f'يوجد {interactions.get("severe_interactions", 0)} تفاعل دوائي شديد. يُنصح بمراجعته.',
                'priority': 'high',
                'category': 'safety'
            })

        if prescriptions.get('dispensing_rate', 0) < 80:
            recommendations.append({
                'title': 'تحسين معدل صرف الوصفات',
                'description': f'معدل صرف الوصفات {prescriptions.get("dispensing_rate", 0)}% منخفض. يُنصح بتحسين العملية.',
                'priority': 'medium',
                'category': 'efficiency'
            })

        return {
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r['priority'] == 'high']),
            'medium_priority': len([r for r in recommendations if r['priority'] == 'medium'])
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy smart recommendations: {str(e)}")
        return {'recommendations': [], 'total_recommendations': 0}

# ==================== دوال مساعدة ====================

def calculate_pharmacy_efficiency(active_medications, low_stock_medications, total_medications):
    """حساب كفاءة الصيدلية"""
    try:
        if total_medications == 0:
            return 0
        
        efficiency = (active_medications / total_medications * 0.7) + ((total_medications - low_stock_medications) / total_medications * 0.3)
        return min(100, max(0, round(efficiency * 100, 2)))
    except:
        return 0

def generate_inventory_optimization_suggestions(low_stock_count, expiring_soon, total_medications):
    """توليد اقتراحات تحسين المخزون"""
    suggestions = []
    
    try:
        if low_stock_count > total_medications * 0.1:
            suggestions.append('زيادة الحد الأدنى للمخزون للأدوية المهمة')
        
        if expiring_soon > 5:
            suggestions.append('تحسين نظام متابعة انتهاء الصلاحية')
        
        if not suggestions:
            suggestions.append('المخزون في حالة جيدة')
            
    except Exception as e:
        suggestions.append('تحليل البيانات للتحسين')
    
    return suggestions

def calculate_inventory_efficiency(low_stock_count, expiring_soon, total_medications):
    """حساب كفاءة المخزون"""
    try:
        if total_medications == 0:
            return 0
        
        efficiency = ((total_medications - low_stock_count - expiring_soon) / total_medications) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_safety_score(expired_medications, expiring_soon, medications_with_interactions):
    """حساب درجة السلامة"""
    try:
        safety_score = 100
        
        # خصم نقاط للأدوية المنتهية الصلاحية
        safety_score -= expired_medications * 10
        
        # خصم نقاط للأدوية القريبة من انتهاء الصلاحية
        safety_score -= expiring_soon * 2
        
        # خصم نقاط للتفاعلات الدوائية
        safety_score -= medications_with_interactions * 1
        
        return min(100, max(0, round(safety_score, 2)))
    except:
        return 0

def calculate_interaction_risk_score(severe_interactions, moderate_interactions, mild_interactions):
    """حساب درجة مخاطر التفاعلات"""
    try:
        risk_score = (severe_interactions * 10) + (moderate_interactions * 5) + (mild_interactions * 2)
        return min(100, max(0, round(risk_score, 2)))
    except:
        return 0

def calculate_automation_score(automated_tasks, manual_tasks):
    """حساب درجة الأتمتة"""
    try:
        if automated_tasks + manual_tasks == 0:
            return 0
        
        automation_rate = (automated_tasks / (automated_tasks + manual_tasks)) * 100
        return min(100, max(0, round(automation_rate, 2)))
    except:
        return 0

def calculate_demand_forecast_accuracy():
    """حساب دقة التنبؤ بالطلب"""
    try:
        # يمكن تطوير خوارزمية أكثر تعقيداً هنا
        return 85  # قيمة افتراضية
    except:
        return 0
