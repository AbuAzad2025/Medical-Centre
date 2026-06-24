 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from app_factory import db
from app.shared.enums import TaskState, VisitState
import logging
from datetime import datetime, timedelta, timezone, date
import json
from sqlalchemy import func, and_, or_, desc

nurse_bp = Blueprint('nurse', __name__)

from services.feature_gate_service import guard_module

@nurse_bp.before_request
def _guard_nursing_module():
    guard_module('nursing')


def _accessible_department_ids():
    try:
        from services.access_control_service import AccessControlService
        return AccessControlService.get_accessible_department_ids(current_user)
    except Exception:
        return []

def _nursing_protocols_key():
    return f'nursing_protocols_{current_user.id}'

def _default_nursing_protocols():
    return [
        {'id': 'fall_prevention', 'title': 'منع السقوط', 'steps': ['تقييم عوامل الخطر', 'تأمين السرير', 'مراجعة أدوية الدوخة']},
        {'id': 'pressure_ulcer', 'title': 'منع قرح الفراش', 'steps': ['تغيير الوضعية كل ساعتين', 'فحص الجلد', 'العناية بالتغذية']},
        {'id': 'pain_management', 'title': 'تقييم الألم', 'steps': ['قياس شدة الألم', 'إعطاء المسكنات', 'إعادة التقييم']}
    ]

def _get_nursing_protocols():
    from models.system_config import SystemConfig
    cfg = SystemConfig.query.filter_by(config_key=_nursing_protocols_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_nursing_protocols_key(),
            config_type='json',
            config_value='[]',
            category='system',
            description='بروتوكولات تمريضية',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        data = _default_nursing_protocols()
        cfg.set_value(data)
        db.session.commit()
        return data
    data = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(data, list) or not data:
        data = _default_nursing_protocols()
        cfg.config_type = 'json'
        cfg.set_value(data)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return data

def _save_nursing_protocols(items):
    from models.system_config import SystemConfig
    cfg = SystemConfig.query.filter_by(config_key=_nursing_protocols_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_nursing_protocols_key(),
            config_type='json',
            config_value='[]',
            category='system',
            description='بروتوكولات تمريضية',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    cfg.config_type = 'json'
    cfg.set_value(items)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()



def get_nursing_smart_analytics():
    """التحليلات الذكية للتمريض"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.nurse import Nurse
        from models.task_management import Task

        # تحليل الممرضات
        total_nurses = Nurse.query.filter(Nurse.is_active == True).count()
        total_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == TaskState.COMPLETED).count()
        pending_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == TaskState.PENDING).count()
        
        # تحليل المهام
        urgent_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'urgent').count()
        high_priority_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'high').count()
        
        # تحليل الأداء
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # تحليل أنواع المهام
        task_types = db.session.query(
        Task.task_type,
        func.count(Task.id).label('count')
    ).filter(Task.task_type == 'nursing').group_by(Task.task_type).all()

        return {
            'total_nurses': total_nurses,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'urgent_tasks': urgent_tasks,
            'high_priority_tasks': high_priority_tasks,
            'completion_rate': round(completion_rate, 2),
            'task_types': [{'type': t.task_type, 'count': t.count} for t in task_types],
            'efficiency_score': calculate_nursing_efficiency(completion_rate, pending_tasks, total_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting nursing smart analytics: {str(e)}")
        return {}

def get_patient_care_optimization():
    """تحسين رعاية المرضى"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task

        # تحليل المهام
        total_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == TaskState.COMPLETED).count()
        in_progress_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == TaskState.IN_PROGRESS).count()
        
        # تحليل الأولويات
        urgent_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'urgent').count()
        high_priority_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'high').count()
        
        # تحليل أوقات الإنجاز
        avg_completion_time = 0  # يمكن حساب متوسط وقت الإنجاز
        
        # اقتراحات التحسين
        optimization_suggestions = generate_patient_care_optimization_suggestions(
            urgent_tasks, high_priority_tasks, total_tasks
        )

        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'urgent_tasks': urgent_tasks,
            'high_priority_tasks': high_priority_tasks,
            'avg_completion_time': avg_completion_time,
            'optimization_suggestions': optimization_suggestions,
            'efficiency_score': calculate_patient_care_efficiency(completed_tasks, total_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting patient care optimization: {str(e)}")
        return {}

def get_vital_signs_monitoring():
    """مراقبة العلامات الحيوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.nurse import VitalSigns

        # تحليل العلامات الحيوية
        total_vital_signs = VitalSigns.query.count()
        abnormal_vital_signs = VitalSigns.query.filter(
            or_(
                VitalSigns.blood_pressure_systolic > 140,
                VitalSigns.blood_pressure_diastolic > 90,
                VitalSigns.heart_rate > 100,
                VitalSigns.temperature > 37.5
            )
        ).count()
        
        # تحليل الاتجاهات
        recent_vital_signs = VitalSigns.query.filter(
            VitalSigns.recorded_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        # تحليل التنبيهات
        critical_alerts = VitalSigns.query.filter(
            or_(
                VitalSigns.blood_pressure_systolic > 160,
                VitalSigns.heart_rate > 120,
                VitalSigns.temperature > 38.5
            )
        ).count()

        return {
            'total_vital_signs': total_vital_signs,
            'abnormal_vital_signs': abnormal_vital_signs,
            'recent_vital_signs': recent_vital_signs,
            'critical_alerts': critical_alerts,
            'monitoring_score': calculate_vital_signs_monitoring_score(abnormal_vital_signs, critical_alerts, total_vital_signs)
        }
    except Exception as e:
        logging.error(f"Error getting vital signs monitoring: {str(e)}")
        return {}

def get_medication_management():
    """إدارة الأدوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task
        from models.medication import Medication

        # تحليل إعطاء الأدوية
        medication_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_medication_tasks = Task.query.filter(
            and_(
                Task.task_type == 'nursing',
                Task.status == TaskState.COMPLETED
            )
        ).count()
        
        # تحليل الأدوية المطلوبة
        medications_needed = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل الأخطاء
        medication_errors = 0  # يمكن إضافة نموذج للأخطاء
        
        # تحليل التوقيت
        on_time_medications = 0  # يمكن حساب الأدوية في الوقت المحدد

        return {
            'medication_tasks': medication_tasks,
            'completed_medication_tasks': completed_medication_tasks,
            'medications_needed': medications_needed,
            'medication_errors': medication_errors,
            'on_time_medications': on_time_medications,
            'medication_efficiency': calculate_medication_efficiency(completed_medication_tasks, medication_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting medication management: {str(e)}")
        return {}

def get_nursing_workflow_automation():
    """أتمتة سير عمل التمريض"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task

        # تحليل المهام المؤتمتة
        automated_tasks = 0  # يمكن إضافة نموذج للمهام المؤتمتة
        manual_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        
        # تحليل أوقات المعالجة
        avg_processing_time = 0  # يمكن حساب متوسط وقت المعالجة
        
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
            'automation_score': calculate_nursing_automation_score(automated_tasks, manual_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting nursing workflow automation: {str(e)}")
        return {}

def get_nursing_predictive_insights():
    try:
        from datetime import datetime, timedelta
        from models.task_management import Task
        from models.nurse import VitalSigns
        from models.visit import Visit

        now = datetime.now(timezone.utc)
        weekly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=7)
        ).count()
        monthly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=30)
        ).count()
        prev_week = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=14),
            Task.created_at < now - timedelta(days=7)
        ).count()
        growth_rate = ((weekly_tasks - prev_week) / prev_week * 100) if prev_week else 0

        active_visits = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])).count()
        recent_vitals = VitalSigns.query.filter(VitalSigns.recorded_at >= now - timedelta(hours=6)).count()
        predicted_workload = int(active_visits + (recent_vitals / 10))

        return {
            'weekly_tasks': weekly_tasks,
            'monthly_tasks': monthly_tasks,
            'growth_rate': round(growth_rate, 2),
            'peak_hours': [],
            'predicted_workload': predicted_workload,
            'workload_forecast_accuracy': calculate_workload_forecast_accuracy()
        }
    except Exception as e:
        logging.error(f"Error getting nursing predictive insights: {str(e)}")
        return {}

def get_nursing_quality_indicators():
    try:
        from models.nurse import VitalSigns, MedicationAdministrationLog
        from models.task_management import Task
        now = datetime.now(timezone.utc)
        last_7 = now - timedelta(days=7)
        vitals_critical = VitalSigns.query.filter(
            VitalSigns.recorded_at >= last_7,
            VitalSigns.oxygen_saturation.isnot(None),
            VitalSigns.oxygen_saturation < 90
        ).count()
        overdue_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.in_([TaskState.PENDING, TaskState.IN_PROGRESS, 'on_hold'])
        ).count()
        med_logs = MedicationAdministrationLog.query.filter(
            MedicationAdministrationLog.administered_at >= last_7
        ).count()
        documentation_rate = 100 if med_logs else 80
        return {
            'critical_vitals_7d': int(vitals_critical or 0),
            'overdue_tasks': int(overdue_tasks or 0),
            'documentation_rate': int(documentation_rate),
            'safety_score': max(0, 100 - (int(vitals_critical or 0) * 2) - (int(overdue_tasks or 0)))
        }
    except Exception:
        return {}

def get_nursing_workload_prediction():
    try:
        from models.visit import Visit
        from models.task_management import Task
        active_visits = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])).count()
        pending_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status.in_([TaskState.PENDING, TaskState.IN_PROGRESS])).count()
        predicted = int(active_visits + (pending_tasks / 2))
        return {
            'active_visits': int(active_visits or 0),
            'pending_tasks': int(pending_tasks or 0),
            'predicted_load': predicted
        }
    except Exception:
        return {}

def get_nursing_smart_recommendations():
    """التوصيات الذكية للتمريض"""
    try:
        recommendations = []
        
        # تحليل البيانات الحالية
        analytics = get_nursing_smart_analytics()
        patient_care = get_patient_care_optimization()
        vital_signs = get_vital_signs_monitoring()
        medication = get_medication_management()
        workflow = get_nursing_workflow_automation()

        # توصيات بناءً على التحليل
        if analytics.get('urgent_tasks', 0) > 3:
            recommendations.append({
                'title': 'تسريع المهام العاجلة',
                'description': f'عدد المهام العاجلة {analytics.get("urgent_tasks", 0)} مرتفع. يُنصح بتسريع المعالجة.',
                'priority': 'high',
                'category': 'urgent_tasks'
            })

        if patient_care.get('completion_rate', 0) < 80:
            recommendations.append({
                'title': 'تحسين معدل إنجاز المهام',
                'description': f'معدل إنجاز المهام {patient_care.get("completion_rate", 0)}% منخفض. يُنصح بتحسين الكفاءة.',
                'priority': 'medium',
                'category': 'efficiency'
            })

        if vital_signs.get('critical_alerts', 0) > 0:
            recommendations.append({
                'title': 'متابعة العلامات الحيوية الحرجة',
                'description': f'يوجد {vital_signs.get("critical_alerts", 0)} تنبيه حرج للعلامات الحيوية. يُنصح بالمتابعة الفورية.',
                'priority': 'high',
                'category': 'vital_signs'
            })

        if medication.get('medication_errors', 0) > 0:
            recommendations.append({
                'title': 'تقليل أخطاء الأدوية',
                'description': f'يوجد {medication.get("medication_errors", 0)} خطأ في الأدوية. يُنصح بتحسين الدقة.',
                'priority': 'high',
                'category': 'medication_safety'
            })

        if workflow.get('automation_score', 0) < 30:
            recommendations.append({
                'title': 'زيادة أتمتة المهام',
                'description': f'درجة الأتمتة {workflow.get("automation_score", 0)}% منخفضة. يُنصح بزيادة الأتمتة.',
                'priority': 'medium',
                'category': 'automation'
            })

        return {
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r['priority'] == 'high']),
            'medium_priority': len([r for r in recommendations if r['priority'] == 'medium'])
        }
    except Exception as e:
        logging.error(f"Error getting nursing smart recommendations: {str(e)}")
        return {'recommendations': [], 'total_recommendations': 0}

# ==================== دوال مساعدة ====================

def calculate_nursing_efficiency(completion_rate, pending_tasks, total_tasks):
    """حساب كفاءة التمريض"""
    try:
        if total_tasks == 0:
            return 0
        
        efficiency = (completion_rate * 0.7) + ((total_tasks - pending_tasks) / total_tasks * 0.3)
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def generate_patient_care_optimization_suggestions(urgent_tasks, high_priority_tasks, total_tasks):
    """توليد اقتراحات تحسين رعاية المرضى"""
    suggestions = []
    
    try:
        if urgent_tasks > total_tasks * 0.1:
            suggestions.append('زيادة عدد الممرضات للمهام العاجلة')
        
        if high_priority_tasks > total_tasks * 0.3:
            suggestions.append('تحسين توزيع الأولويات')
        
        if not suggestions:
            suggestions.append('رعاية المرضى في حالة جيدة')
            
    except Exception as e:
        suggestions.append('تحليل البيانات للتحسين')
    
    return suggestions

def calculate_patient_care_efficiency(completed_tasks, total_tasks):
    """حساب كفاءة رعاية المرضى"""
    try:
        if total_tasks == 0:
            return 0
        
        efficiency = (completed_tasks / total_tasks) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_vital_signs_monitoring_score(abnormal_vital_signs, critical_alerts, total_vital_signs):
    """حساب درجة مراقبة العلامات الحيوية"""
    try:
        if total_vital_signs == 0:
            return 100
        
        monitoring_score = 100
        monitoring_score -= (abnormal_vital_signs / total_vital_signs) * 20
        monitoring_score -= (critical_alerts / total_vital_signs) * 30
        
        return min(100, max(0, round(monitoring_score, 2)))
    except:
        return 0

def calculate_medication_efficiency(completed_medication_tasks, medication_tasks):
    """حساب كفاءة إدارة الأدوية"""
    try:
        if medication_tasks == 0:
            return 0
        
        efficiency = (completed_medication_tasks / medication_tasks) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_nursing_automation_score(automated_tasks, manual_tasks):
    """حساب درجة أتمتة التمريض"""
    try:
        if automated_tasks + manual_tasks == 0:
            return 0
        
        automation_rate = (automated_tasks / (automated_tasks + manual_tasks)) * 100
        return min(100, max(0, round(automation_rate, 2)))
    except:
        return 0

def calculate_workload_forecast_accuracy():
    """حساب دقة التنبؤ بالحمل"""
    try:
        # يمكن تطوير خوارزمية أكثر تعقيداً هنا
        return 85  # قيمة افتراضية
    except:
        return 0

# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import care
from . import vitals
from . import medication
from . import tasks
from . import protocols
from . import wards
