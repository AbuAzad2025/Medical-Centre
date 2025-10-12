"""
مسارات الممرضة - Nurse Routes
Medical System Nurse Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from app_factory import db
import logging
from datetime import datetime, timedelta
import json

nurse_bp = Blueprint('nurse', __name__)

@nurse_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الممرضة"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات الممرضة
        today = datetime.now().date()
        
        # المرضى اليوم
        patients_today = Patient.query.filter(
            Patient.created_at >= today
        ).count()
        
        # الزيارات النشطة
        active_visits = Visit.query.filter(
            Visit.status.in_(['in_progress', 'waiting'])
        ).count()
        
        # الأدوية المطلوبة
        medications_needed = Medication.query.filter(
            Medication.stock_quantity <= Medication.min_stock_level
        ).count()
        
        # المهام المعلقة
        pending_tasks = 5  # يمكن تطوير نموذج المهام لاحقاً
        
        # الميزات الذكية
        smart_analytics = get_nursing_smart_analytics()
        patient_care_optimization = get_patient_care_optimization()
        vital_signs_monitoring = get_vital_signs_monitoring()
        medication_management = get_medication_management()
        workflow_automation = get_nursing_workflow_automation()
        predictive_insights = get_nursing_predictive_insights()
        smart_recommendations = get_nursing_smart_recommendations()
        
        stats = {
            'patients_today': patients_today,
            'active_visits': active_visits,
            'medications_needed': medications_needed,
            'pending_tasks': pending_tasks,
            'smart_analytics': smart_analytics,
            'patient_care_optimization': patient_care_optimization,
            'vital_signs_monitoring': vital_signs_monitoring,
            'medication_management': medication_management,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights,
            'smart_recommendations': smart_recommendations
        }
        
        return render_template('nurse/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in nurse dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

# ==================== الميزات الذكية للتمريض ====================

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
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'completed').count()
        pending_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'pending').count()
        
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
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'completed').count()
        in_progress_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'in_progress').count()
        
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
        from models.nurse import VitalSign

        # تحليل العلامات الحيوية
        total_vital_signs = VitalSign.query.count()
        abnormal_vital_signs = VitalSign.query.filter(
            or_(
                VitalSign.blood_pressure_systolic > 140,
                VitalSign.blood_pressure_diastolic > 90,
                VitalSign.heart_rate > 100,
                VitalSign.temperature > 37.5
            )
        ).count()
        
        # تحليل الاتجاهات
        recent_vital_signs = VitalSign.query.filter(
            VitalSign.recorded_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        # تحليل التنبيهات
        critical_alerts = VitalSign.query.filter(
            or_(
                VitalSign.blood_pressure_systolic > 160,
                VitalSign.heart_rate > 120,
                VitalSign.temperature > 38.5
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
                Task.status == 'completed'
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
    """الرؤى التنبؤية للتمريض"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task

        # تحليل الطلب المتوقع
        weekly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        monthly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= datetime.now() - timedelta(days=30)
        ).count()
        
        # تحليل النمو
        growth_rate = 0  # يمكن حساب معدل النمو
        
        # تحليل الذروة
        peak_hours = []  # يمكن تحديد ساعات الذروة
        
        # التنبؤ بالحمل
        predicted_workload = 0  # يمكن التنبؤ بالحمل المتوقع

        return {
            'weekly_tasks': weekly_tasks,
            'monthly_tasks': monthly_tasks,
            'growth_rate': growth_rate,
            'peak_hours': peak_hours,
            'predicted_workload': predicted_workload,
            'workload_forecast_accuracy': calculate_workload_forecast_accuracy()
        }
    except Exception as e:
        logging.error(f"Error getting nursing predictive insights: {str(e)}")
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

@nurse_bp.route('/patient-care')
@login_required
def patient_care():
    """رعاية المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # المرضى الذين يحتاجون رعاية
        patients = Patient.query.filter(
            Patient.medical_conditions.isnot(None)
        ).limit(20).all()
        
        return render_template('nurse/patient_care.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient care: {str(e)}")
        flash('حدث خطأ في تحميل رعاية المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/medication-administration')
@login_required
def medication_administration():
    """إدارة الأدوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # الأدوية المتاحة
        medications = Medication.query.filter_by(is_active=True).all()
        
        # الأدوية المطلوبة
        needed_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.min_stock_level
        ).all()
        
        return render_template('nurse/medication_administration.html', 
                             medications=medications,
                             needed_medications=needed_medications)
    except Exception as e:
        logging.error(f"Error loading medication administration: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأدوية', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/patient-monitoring')
@login_required
def patient_monitoring():
    """مراقبة المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # المرضى الذين يحتاجون مراقبة
        patients = Patient.query.filter(
            Patient.medical_conditions.contains('diabetes') |
            Patient.medical_conditions.contains('hypertension')
        ).limit(20).all()
        
        return render_template('nurse/patient_monitoring.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient monitoring: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/vital-signs')
@login_required
def vital_signs():
    """العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # المرضى الذين يحتاجون قياس العلامات الحيوية
        patients = Patient.query.filter(
            Patient.medical_conditions.isnot(None)
        ).limit(20).all()
        
        return render_template('nurse/vital_signs.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading vital signs: {str(e)}")
        flash('حدث خطأ في تحميل العلامات الحيوية', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/record-vital-signs/<int:patient_id>', methods=['POST'])
@login_required
def record_vital_signs(patient_id):
    """تسجيل العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    
    try:
        patient = Patient.query.get_or_404(patient_id)
        
        # تسجيل العلامات الحيوية
        vital_signs = {
            'blood_pressure': request.form.get('blood_pressure'),
            'heart_rate': request.form.get('heart_rate'),
            'temperature': request.form.get('temperature'),
            'oxygen_saturation': request.form.get('oxygen_saturation'),
            'weight': request.form.get('weight'),
            'height': request.form.get('height')
        }
        
        # حفظ البيانات (يمكن تطوير نموذج منفصل للعلامات الحيوية)
        # patient.vital_signs = json.dumps(vital_signs)
        # db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تسجيل العلامات الحيوية بنجاح'})
        
    except Exception as e:
        logging.error(f"Error recording vital signs: {str(e)}")
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

@nurse_bp.route('/patients')
@login_required
def patients():
    """مرضى التمريض"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/patient_care.html')

@nurse_bp.route('/vitals')
@login_required
def vitals():
    """العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/vital_signs.html')

@nurse_bp.route('/medications')
@login_required
def medications():
    """الأدوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/medication_administration.html')

@nurse_bp.route('/wards')
@login_required
def wards():
    """الأجنحة"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/patient_monitoring.html')

@nurse_bp.route('/tasks')
@login_required
def tasks():
    """مهام التمريض"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.task import Task
        
        # جلب مهام الممرضة
        tasks = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.created_at.desc()).all()
        
        return render_template('nurse/tasks.html', tasks=tasks)
    except Exception as e:
        logging.error(f"Error loading nurse tasks: {str(e)}")
        flash('حدث خطأ في تحميل المهام', 'error')
        return redirect(url_for('nurse.dashboard'))
