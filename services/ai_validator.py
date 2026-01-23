"""
خدمة التحقق الذكي من البيانات
AI Data Validation Service
"""

from datetime import datetime, timedelta, timezone

class AIValidator:
    """نظام التحقق الذكي من البيانات"""
    
    @staticmethod
    def validate_system_data():
        """التحقق من صحة بيانات النظام"""
        errors = []
        warnings = []
        
        try:
            from models.user import User
            from models.patient import Patient
            from models.visit import Visit
            from models.department import Department
            
            # 1. التحقق من المستخدمين
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            
            if total_users == 0:
                errors.append("⛔ خطأ حرج: لا يوجد مستخدمين في النظام!")
            
            if active_users == 0 and total_users > 0:
                warnings.append("⚠️ تحذير: جميع المستخدمين غير نشطين!")
            
            inactive_rate = ((total_users - active_users) / max(total_users, 1)) * 100
            if inactive_rate > 70:
                warnings.append(f"⚠️ تحذير: نسبة المستخدمين غير النشطين عالية جداً ({inactive_rate:.1f}%)")
            
            # 2. التحقق من الأطباء (الأطباء هم مستخدمين بدور doctor)
            total_doctors = User.query.filter_by(role='doctor').count()
            if total_doctors == 0:
                warnings.append("⚠️ تحذير: لا يوجد أطباء في النظام!")
            
            doctors_without_dept = User.query.filter_by(role='doctor', department_id=None).count()
            if doctors_without_dept > 0:
                warnings.append(f"⚠️ تحذير: يوجد {doctors_without_dept} طبيب بدون قسم")
            
            # 3. التحقق من الأقسام
            total_departments = Department.query.count()
            active_departments = Department.query.filter_by(is_active=True).count()
            
            if total_departments == 0:
                warnings.append("⚠️ تحذير: لا يوجد أقسام في النظام")
            
            if active_departments == 0 and total_departments > 0:
                errors.append("⛔ خطأ: جميع الأقسام غير نشطة!")
            
            # 4. التحقق من المرضى والزيارات
            total_patients = Patient.query.count()
            total_visits = Visit.query.count()
            
            if total_patients > 0 and total_visits == 0:
                warnings.append("⚠️ تحذير: يوجد مرضى ولكن لا توجد زيارات")
            
            # 5. التحقق من الزيارات المعلقة
            old_active_visits = Visit.query.filter(
                Visit.status == 'active',
                Visit.created_at < datetime.now(timezone.utc) - timedelta(days=1)
            ).count()
            
            if old_active_visits > 0:
                warnings.append(f"⚠️ تحذير: يوجد {old_active_visits} زيارة نشطة منذ أكثر من يوم")
            
            # 6. التحقق من التناسق
            visits_without_doctor = Visit.query.filter_by(doctor_id=None).count()
            if visits_without_doctor > 0:
                errors.append(f"⛔ خطأ: يوجد {visits_without_doctor} زيارة بدون طبيب!")
            
            visits_without_patient = Visit.query.filter_by(patient_id=None).count()
            if visits_without_patient > 0:
                errors.append(f"⛔ خطأ: يوجد {visits_without_patient} زيارة بدون مريض!")
            
            # 7. التحقق من البيانات المنطقية (تواريخ الميلاد)
            from datetime import date
            today = date.today()
            
            # التحقق من تواريخ الميلاد غير المنطقية
            patients_with_future_birth = Patient.query.filter(
                Patient.birth_date > today
            ).count()
            
            if patients_with_future_birth > 0:
                errors.append(f"⛔ خطأ: يوجد {patients_with_future_birth} مريض بتاريخ ميلاد في المستقبل!")
            
            # التحقق من تواريخ الميلاد القديمة جداً (أكثر من 150 سنة)
            very_old_date = date(today.year - 150, today.month, today.day)
            patients_too_old = Patient.query.filter(
                Patient.birth_date < very_old_date
            ).count()
            
            if patients_too_old > 0:
                warnings.append(f"⚠️ تحذير: يوجد {patients_too_old} مريض بعمر أكثر من 150 سنة!")
            
        except Exception as e:
            errors.append(f"⛔ خطأ في التحقق: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_issues': len(errors) + len(warnings)
        }
    
    @staticmethod
    def validate_before_action(action_type, data=None):
        """التحقق قبل تنفيذ أي إجراء"""
        issues = []
        
        if action_type == 'create_user':
            if data:
                if not data.get('username'):
                    issues.append("⛔ اسم المستخدم مطلوب")
                if not data.get('email'):
                    issues.append("⛔ البريد الإلكتروني مطلوب")
                if not data.get('password') or len(data.get('password', '')) < 6:
                    issues.append("⛔ كلمة المرور يجب أن تكون 6 أحرف على الأقل")
        
        elif action_type == 'create_patient':
            if data:
                if not data.get('first_name') and not data.get('full_name'):
                    issues.append("⛔ اسم المريض مطلوب")
                
                birth_date = data.get('birth_date')
                if birth_date:
                    from datetime import date
                    try:
                        if isinstance(birth_date, str):
                            birth_date = date.fromisoformat(birth_date)
                        if birth_date > date.today():
                            issues.append("⛔ تاريخ الميلاد لا يمكن أن يكون في المستقبل")
                    except:
                        issues.append("⛔ تاريخ ميلاد غير صحيح")
        
        elif action_type == 'create_visit':
            if data:
                if not data.get('patient_id'):
                    issues.append("⛔ المريض مطلوب")
                if not data.get('doctor_id'):
                    issues.append("⛔ الطبيب مطلوب")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
    
    @staticmethod
    def get_system_health_report():
        """تقرير صحة النظام الشامل"""
        validation = AIValidator.validate_system_data()
        
        if validation['valid']:
            status = "✅ ممتاز"
            color = "success"
        elif len(validation['errors']) > 0:
            status = "⛔ حرج"
            color = "danger"
        else:
            status = "⚠️ يحتاج انتباه"
            color = "warning"
        
        report = f"""🔍 **تقرير صحة النظام الذكي:**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📊 الحالة العامة:** {status}

**🔴 الأخطاء الحرجة:** {len(validation['errors'])}
**⚠️ التحذيرات:** {len(validation['warnings'])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        if validation['errors']:
            report += "\n**🔴 الأخطاء الحرجة التي تحتاج إصلاح فوري:**\n"
            for error in validation['errors']:
                report += f"{error}\n"
            report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if validation['warnings']:
            report += "\n**⚠️ التحذيرات التي تحتاج انتباه:**\n"
            for warning in validation['warnings']:
                report += f"{warning}\n"
            report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if validation['valid']:
            report += """
**✅ النظام يعمل بشكل صحيح:**
• جميع البيانات متسقة
• لا توجد أخطاء منطقية
• النظام جاهز للاستخدام

💡 **نصيحة:** استمر في المراقبة الدورية
"""
        else:
            report += """
**⚠️ يُنصح بإصلاح المشاكل قبل المتابعة:**
1. راجع الأخطاء الحرجة أولاً
2. قم بتصحيح البيانات غير المنطقية
3. تحقق من التناسق بين الجداول

💡 **نصيحة:** لا تتجاهل الأخطاء الحرجة!
"""
        
        return {
            'report': report,
            'status': status,
            'color': color,
            'validation': validation
        }

