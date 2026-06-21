"""analytics routes - extracted from monolithic emergency.py"""

from routes.emergency import emergency_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.emergency import EmergencyCase
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from services.emergency_service import emergency_service
from app_factory import db
from sqlalchemy import and_, or_, desc, case
import logging, json
from datetime import datetime, date, timedelta, timezone


# =============================================
# ANALYTICS ROUTES
# =============================================

# ==================== الميزات الذكية للطوارئ ====================

def get_emergency_ai_triage():
    """ذكاء اصطناعي لتصنيف الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أولويات الحالات
        priority_analysis = {
            'critical': EmergencyCase.query.filter(EmergencyCase.severity == 'CRITICAL').count(),
            'urgent': EmergencyCase.query.filter(EmergencyCase.severity == 'HIGH').count(),
            'normal': EmergencyCase.query.filter(EmergencyCase.severity == 'MODERATE').count(),
            'low': EmergencyCase.query.filter(EmergencyCase.severity == 'LOW').count()
        }
        
        # تحليل أوقات الاستجابة
        response_times = []
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            end_time = getattr(case, 'treated_at', None) or getattr(case, 'completed_at', None)
            if end_time and case.created_at:
                response_time = (end_time - case.created_at).total_seconds() / 60
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # اقتراحات التحسين
        triage_suggestions = []
        
        if avg_response_time > 30:  # أكثر من 30 دقيقة
            triage_suggestions.append({
                'type': 'response_time',
                'title': 'تحسين أوقات الاستجابة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين عملية التصنيف لتسريع الاستجابة'
            })
        
        if priority_analysis['critical'] > 5:
            triage_suggestions.append({
                'type': 'critical_cases',
                'title': 'حالات حرجة عالية',
                'description': f'عدد الحالات الحرجة: {priority_analysis["critical"]}',
                'suggestion': 'مراجعة الموارد المتاحة للحالات الحرجة'
            })
        
        return {
            'priority_analysis': priority_analysis,
            'avg_response_time': round(avg_response_time, 2),
            'triage_suggestions': triage_suggestions,
            'efficiency_score': calculate_triage_efficiency(avg_response_time, priority_analysis)
        }
    except Exception as e:
        logging.error(f"Error getting emergency AI triage: {str(e)}")
        return {}

def get_critical_alert_system():
    """نظام التنبيهات الحرجة"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        alerts = []
        
        # تنبيهات الحالات الحرجة
        critical_cases = EmergencyCase.query.filter(
            EmergencyCase.severity == 'CRITICAL',
            EmergencyCase.status.in_([EmergencyStatus.WAITING, EmergencyStatus.TRIAGE, EmergencyStatus.RESUSCITATION, EmergencyStatus.TREATMENT])
        ).count()
        
        if critical_cases > 0:
            alerts.append({
                'type': 'critical',
                'title': 'حالات حرجة',
                'message': f'يوجد {critical_cases} حالة حرجة تحتاج انتباه فوري',
                'priority': 'high',
                'action': 'مراجعة فورية'
            })
        
        # تنبيهات أوقات الانتظار الطويلة
        long_waiting = EmergencyCase.query.filter(
            EmergencyCase.status == EmergencyStatus.WAITING,
            EmergencyCase.created_at < datetime.now() - timedelta(minutes=30)
        ).count()
        
        if long_waiting > 0:
            alerts.append({
                'type': 'waiting_time',
                'title': 'انتظار طويل',
                'message': f'يوجد {long_waiting} حالة تنتظر أكثر من 30 دقيقة',
                'priority': 'medium',
                'action': 'مراجعة الطابور'
            })
        
        # تنبيهات الموارد
        active_cases = EmergencyCase.query.filter(
            EmergencyCase.status.in_([EmergencyStatus.WAITING, EmergencyStatus.TRIAGE, EmergencyStatus.RESUSCITATION, EmergencyStatus.TREATMENT, EmergencyStatus.OBSERVATION])
        ).count()
        
        if active_cases > 20:
            alerts.append({
                'type': 'resource_usage',
                'title': 'استخدام الموارد',
                'message': f'عدد الحالات النشطة: {active_cases} - قريب من السعة القصوى',
                'priority': 'medium',
                'action': 'مراجعة الموارد'
            })
        
        return alerts
    except Exception as e:
        logging.error(f"Error getting critical alert system: {str(e)}")
        return []

def get_emergency_workflow_ai():
    """ذكاء اصطناعي لسير عمل الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل مراحل العلاج
        workflow_analysis = {
            'waiting': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.WAITING).count(),
            'triage': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.TRIAGE).count(),
            'resuscitation': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.RESUSCITATION).count(),
            'treatment': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.TREATMENT).count(),
            'observation': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.OBSERVATION).count(),
            'completed': EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.COMPLETED).count()
        }
        
        # تحليل أوقات المراحل
        stage_times = []
        completed_cases = EmergencyCase.query.filter(
            EmergencyCase.status == EmergencyStatus.COMPLETED,
            EmergencyCase.completed_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in completed_cases:
            end_time = getattr(case, 'treated_at', None) or getattr(case, 'completed_at', None)
            if end_time and case.created_at:
                total_time = (end_time - case.created_at).total_seconds() / 60
                stage_times.append(total_time)
        
        avg_total_time = sum(stage_times) / len(stage_times) if stage_times else 0
        
        # اقتراحات التحسين
        workflow_suggestions = []
        
        if workflow_analysis['triage'] > 10:
            workflow_suggestions.append({
                'type': 'triage_bottleneck',
                'title': 'عنق الزجاجة في التصنيف',
                'description': f'عدد الحالات في التصنيف: {workflow_analysis["triage"]}',
                'suggestion': 'زيادة الموارد في مرحلة التصنيف'
            })
        
        if avg_total_time > 60:  # أكثر من ساعة
            workflow_suggestions.append({
                'type': 'total_time',
                'title': 'تحسين الوقت الإجمالي',
                'description': f'متوسط الوقت الإجمالي: {avg_total_time:.1f} دقيقة',
                'suggestion': 'تحسين سير العمل لتقليل الوقت الإجمالي'
            })
        
        return {
            'workflow_analysis': workflow_analysis,
            'avg_total_time': round(avg_total_time, 2),
            'workflow_suggestions': workflow_suggestions,
            'efficiency_score': calculate_workflow_efficiency(workflow_analysis, avg_total_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency workflow AI: {str(e)}")
        return {}

def get_patient_vital_monitoring():
    """مراقبة العلامات الحيوية للمرضى"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل العلامات الحيوية
        vital_signs_analysis = {
            'normal': 0,
            'abnormal': 0,
            'critical': 0
        }
        
        # تحليل الحالات حسب العلامات الحيوية
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            if case.vital_signs:
                # تحليل مبسط للعلامات الحيوية
                vital_data = case.vital_signs
                if 'critical' in str(vital_data).lower():
                    vital_signs_analysis['critical'] += 1
                elif 'abnormal' in str(vital_data).lower():
                    vital_signs_analysis['abnormal'] += 1
                else:
                    vital_signs_analysis['normal'] += 1
        
        # توصيات المراقبة
        monitoring_recommendations = []
        
        if vital_signs_analysis['critical'] > 0:
            monitoring_recommendations.append({
                'type': 'critical_vitals',
                'title': 'علامات حيوية حرجة',
                'description': f'عدد الحالات بعلامات حرجة: {vital_signs_analysis["critical"]}',
                'suggestion': 'مراقبة مستمرة للحالات الحرجة'
            })
        
        if vital_signs_analysis['abnormal'] > 5:
            monitoring_recommendations.append({
                'type': 'abnormal_vitals',
                'title': 'علامات حيوية غير طبيعية',
                'description': f'عدد الحالات بعلامات غير طبيعية: {vital_signs_analysis["abnormal"]}',
                'suggestion': 'مراجعة بروتوكولات المراقبة'
            })
        
        return {
            'vital_signs_analysis': vital_signs_analysis,
            'monitoring_recommendations': monitoring_recommendations,
            'total_cases_monitored': sum(vital_signs_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting patient vital monitoring: {str(e)}")
        return {}

def get_emergency_resource_management():
    """إدارة موارد الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        # تحليل الموارد المتاحة
        total_staff = User.query.filter(User.role == 'emergency').count()
        active_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(hours=24)
        ).count()
        
        # تحليل الأحمال
        today = datetime.now().date()
        today_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # تحليل الكفاءة
        efficiency_score = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        # توصيات إدارة الموارد
        resource_recommendations = []
        
        if efficiency_score < 70:
            resource_recommendations.append({
                'type': 'staff_efficiency',
                'title': 'كفاءة الموظفين',
                'description': f'معدل كفاءة الموظفين: {efficiency_score:.1f}%',
                'suggestion': 'تحسين مشاركة الموظفين أو إضافة موارد'
            })
        
        if today_cases > 30:
            resource_recommendations.append({
                'type': 'workload',
                'title': 'عبء العمل',
                'description': f'عدد الحالات اليوم: {today_cases}',
                'suggestion': 'مراجعة توزيع الأحمال أو إضافة موارد'
            })
        
        return {
            'total_staff': total_staff,
            'active_staff': active_staff,
            'today_cases': today_cases,
            'efficiency_score': round(efficiency_score, 2),
            'resource_recommendations': resource_recommendations
        }
    except Exception as e:
        logging.error(f"Error getting emergency resource management: {str(e)}")
        return {}

def get_trauma_protocols():
    """بروتوكولات الصدمات"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أنواع الصدمات
        trauma_analysis = {
            'trauma_cases': 0,
            'medical_emergencies': 0,
            'surgical_emergencies': 0,
            'other': 0
        }
        
        # تحليل الحالات الحديثة
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=30)
        ).all()
        
        for case in recent_cases:
            if case.chief_complaint:
                complaint = case.chief_complaint.lower()
                if any(word in complaint for word in ['حادث', 'سقوط', 'ضربة', 'جرح']):
                    trauma_analysis['trauma_cases'] += 1
                elif any(word in complaint for word in ['ألم', 'صدر', 'قلب', 'تنفس']):
                    trauma_analysis['medical_emergencies'] += 1
                elif any(word in complaint for word in ['جراحة', 'عملية', 'بطن']):
                    trauma_analysis['surgical_emergencies'] += 1
                else:
                    trauma_analysis['other'] += 1
        
        # توصيات البروتوكولات
        protocol_recommendations = []
        
        if trauma_analysis['trauma_cases'] > 10:
            protocol_recommendations.append({
                'type': 'trauma_protocol',
                'title': 'بروتوكول الصدمات',
                'description': f'عدد حالات الصدمات: {trauma_analysis["trauma_cases"]}',
                'suggestion': 'مراجعة بروتوكولات الصدمات وتدريب الفريق'
            })
        
        if trauma_analysis['medical_emergencies'] > 15:
            protocol_recommendations.append({
                'type': 'medical_protocol',
                'title': 'بروتوكول الطوارئ الطبية',
                'description': f'عدد الطوارئ الطبية: {trauma_analysis["medical_emergencies"]}',
                'suggestion': 'تحسين بروتوكولات الطوارئ الطبية'
            })
        
        return {
            'trauma_analysis': trauma_analysis,
            'protocol_recommendations': protocol_recommendations,
            'total_cases_analyzed': sum(trauma_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting trauma protocols: {str(e)}")
        return {}

def get_emergency_analytics():
    """تحليلات الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.medication import Prescription
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from datetime import datetime, timedelta
        
        # تحليل الأداء
        total_cases = EmergencyCase.query.count()
        completed_cases = EmergencyCase.query.filter(EmergencyCase.status == EmergencyStatus.COMPLETED).count()
        completion_rate = (completed_cases / total_cases * 100) if total_cases > 0 else 0
        
        # تحليل الأوقات
        avg_treatment_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.completed_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == EmergencyStatus.COMPLETED,
            EmergencyCase.completed_at.isnot(None)
        ).scalar() or 0
        
        # تحليل الموارد
        prescriptions_count = Prescription.query.join(EmergencyCase).count()
        lab_requests_count = LabRequest.query.join(EmergencyCase).count()
        radiology_requests_count = RadiologyRequest.query.join(EmergencyCase).count()
        
        return {
            'completion_rate': round(completion_rate, 2),
            'avg_treatment_time': round(avg_treatment_time, 2),
            'prescriptions_count': prescriptions_count,
            'lab_requests_count': lab_requests_count,
            'radiology_requests_count': radiology_requests_count,
            'performance_score': calculate_emergency_performance_score(completion_rate, avg_treatment_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency analytics: {str(e)}")
        return {}

def get_smart_emergency_recommendations():
    """التوصيات الذكية للطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل النمو
        week_ago = datetime.now().date() - timedelta(days=7)
        cases_this_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago
        ).count()
        
        cases_last_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago - timedelta(days=7),
            EmergencyCase.created_at < week_ago
        ).count()
        
        growth_rate = ((cases_this_week - cases_last_week) / cases_last_week * 100) if cases_last_week > 0 else 0
        
        if growth_rate > 20:
            recommendations.append({
                'type': 'growth',
                'title': 'نمو سريع في الطوارئ',
                'description': f'زيادة {growth_rate:.1f}% في حالات الطوارئ',
                'suggestion': 'مراجعة الموارد والاستعداد للزيادة'
            })
        
        # تحليل الكفاءة
        avg_response_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.completed_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == EmergencyStatus.COMPLETED,
            EmergencyCase.completed_at.isnot(None)
        ).scalar() or 0
        
        if avg_response_time > 45:
            recommendations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتسريع الاستجابة'
            })
        
        # تحليل الموظفين
        active_emergency_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_emergency_staff = User.query.filter(User.role == 'emergency').count()
        
        if active_emergency_staff < total_emergency_staff * 0.8:
            recommendations.append({
                'type': 'staff_engagement',
                'title': 'مشاركة الموظفين',
                'description': f'فقط {active_emergency_staff} من {total_emergency_staff} موظف نشط',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart emergency recommendations: {str(e)}")
        return []
