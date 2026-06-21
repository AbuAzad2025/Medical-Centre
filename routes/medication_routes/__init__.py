 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.medication import Medication, Prescription
from models.patient import Patient
from models.visit import Visit
from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from models.drug_interaction import DrugInteraction
from app_factory import db
import logging
from datetime import datetime, timezone, timedelta, date
import json
from sqlalchemy import func

medication_bp = Blueprint('medication', __name__)













def _generate_supply_request_number():
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"SR-{ts}"

















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
            Medication.stock_quantity.desc()
        ).limit(5).all()

        return {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'total_stock_value': float(total_stock_value),
            'low_stock_value': float(low_stock_value),
            'categories': [{'category': c.category, 'count': c.count, 'total_stock': c.total_stock} for c in categories],
            'most_used': [{'name': m.trade_name, 'usage_count': m.stock_quantity or 0} for m in most_used_medications],
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
    try:
        from datetime import datetime, timedelta
        from models.medication import PrescriptionItem, Prescription

        now = datetime.now(timezone.utc)
        weekly_demand = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=7)
        ).count()
        monthly_demand = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=30)
        ).count()
        prev_week = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=14),
            Prescription.created_at < now - timedelta(days=7)
        ).count()
        growth_rate = ((weekly_demand - prev_week) / prev_week * 100) if prev_week else 0

        low_stock = Medication.query.filter(Medication.stock_quantity <= Medication.minimum_stock).count()
        predicted_stock_needs = int(low_stock or 0)

        return {
            'weekly_demand': weekly_demand,
            'monthly_demand': monthly_demand,
            'growth_rate': round(growth_rate, 2),
            'peak_hours': [],
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

# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import catalog
from . import inventory
from . import prescriptions
from . import interactions
from . import external
from . import pos
from . import suppliers
