"""
محرك الذكاء الاصطناعي المتطور جداً
Advanced NLP-Powered AI Engine for Medical System
يقوم بفهم الأسئلة المعقدة وتحليل قاعدة البيانات والإجابة بذكاء
"""

import re
from datetime import datetime, timedelta, date
from app.shared.enums import AppointmentState
from sqlalchemy import inspect, func, text
import logging

class SmartAIEngine:
    """محرك الذكاء الاصطناعي الشامل مع NLP متقدم"""
    
    def __init__(self, db):
        self.db = db
        self.inspector = inspect(db.engine)
        
        # قاموس الكلمات المفتاحية المتقدم
        self.keywords = {
            'analysis': ['حلل', 'تحليل', 'analyze', 'analysis', 'فحص', 'اختبر', 'تدقيق', 'مراجعة'],
            'errors': ['خطأ', 'أخطاء', 'error', 'errors', 'مشكلة', 'مشاكل', 'عطل', 'أعطال', 'bug'],
            'users': ['مستخدم', 'مستخدمين', 'user', 'users', 'موظف', 'موظفين', 'staff'],
            'doctors': ['طبيب', 'أطباء', 'دكتور', 'دكاترة', 'doctor', 'doctors', 'طبيبة'],
            'patients': ['مريض', 'مرضى', 'patient', 'patients', 'مريضة'],
            'visits': ['زيارة', 'زيارات', 'visit', 'visits'],
            'departments': ['قسم', 'أقسام', 'department', 'departments'],
            'performance': ['أداء', 'performance', 'كفاءة', 'efficiency'],
            'statistics': ['إحصائيات', 'statistics', 'stats', 'أرقام', 'بيانات'],
            'problems': ['مشكلة', 'مشاكل', 'problem', 'problems', 'عيب', 'عيوب'],
            'inactive': ['غير نشط', 'معطل', 'inactive', 'disabled', 'متوقف'],
            'active': ['نشط', 'active', 'enabled', 'يعمل'],
            'report': ['تقرير', 'report', 'ملخص', 'summary'],
            'count': ['كم', 'عدد', 'count', 'how many', 'كم عدد'],
            'who': ['من', 'who', 'مين'],
            'what': ['ماذا', 'what', 'ما', 'شو', 'ايش'],
            'when': ['متى', 'when', 'وقت'],
            'where': ['أين', 'where', 'وين', 'فين'],
            'why': ['لماذا', 'why', 'ليش', 'ليه'],
            'how': ['كيف', 'how', 'كيفية']
        }
        
    def _extract_intent(self, message):
        """استخراج النية من السؤال باستخدام NLP متقدم"""
        message_lower = message.lower()
        intents = []
        
        # تحليل الكلمات المفتاحية
        for intent_type, keywords in self.keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                intents.append(intent_type)
        
        return intents
    
    def _extract_entities(self, message):
        """استخراج الكيانات من السؤال (أسماء، أرقام، تواريخ)"""
        entities = {
            'names': [],
            'numbers': [],
            'dates': []
        }
        
        # استخراج الأسماء (كلمات تبدأ بحرف كبير أو بعد "الدكتور" أو "المريض")
        name_patterns = [
            r'(?:الدكتور|دكتور|د\.|طبيب)\s+(\w+)',
            r'(?:المريض|مريض)\s+(\w+)',
            r'(?:الموظف|موظف)\s+(\w+)'
        ]
        for pattern in name_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            entities['names'].extend(matches)
        
        # استخراج الأرقام
        numbers = re.findall(r'\d+', message)
        entities['numbers'] = [int(n) for n in numbers]
        
        return entities
        
    def process_query(self, user_message):
        """
        معالجة السؤال وإرجاع الإجابة باستخدام NLP متقدم
        """
        try:
            message = user_message.strip()
            message_lower = message.lower()
            
            # استخراج النية والكيانات
            intents = self._extract_intent(message)
            entities = self._extract_entities(message)
            
            # معالجة الأسئلة المعقدة باستخدام NLP
            # مثال: "حلل أخطاء المستخدمين"
            if 'analysis' in intents and 'errors' in intents and 'users' in intents:
                return self._analyze_user_errors()
            
            # مثال: "حلل مشاكل الأطباء"
            if 'analysis' in intents and ('errors' in intents or 'problems' in intents) and 'doctors' in intents:
                return self._analyze_doctor_problems()
            
            # مثال: "ما هي مشاكل الأقسام غير النشطة"
            if ('problems' in intents or 'errors' in intents) and 'departments' in intents:
                return self._analyze_department_problems()
            
            # 1. التحقق من العمليات الحسابية
            if self._is_calculation(message_lower):
                return self._handle_calculation(message_lower)
            
            # 2. أسئلة عن الإحصائيات العامة
            if any(word in message for word in ['كم', 'عدد', 'count', 'how many', 'كم عدد']):
                return self._handle_count_query(message)
            
            # 3. أسئلة عن المستخدمين
            if any(word in message for word in ['مستخدم', 'user', 'موظف', 'staff']):
                return self._handle_user_query(message)
            
            # 4. أسئلة عن الأطباء
            if any(word in message for word in ['طبيب', 'دكتور', 'doctor', 'طبيبة']):
                return self._handle_doctor_query(message)
            
            # 5. أسئلة عن المرضى
            if any(word in message for word in ['مريض', 'patient', 'مريضة']):
                return self._handle_patient_query(message)
            
            # 6. أسئلة عن الأقسام
            if any(word in message for word in ['قسم', 'department', 'أقسام']):
                return self._handle_department_query(message)
            
            # 7. أسئلة عن الزيارات
            if any(word in message for word in ['زيارة', 'visit', 'زيارات']):
                return self._handle_visit_query(message)
            
            # 8. أسئلة عن المواعيد
            if any(word in message for word in ['موعد', 'appointment', 'مواعيد', 'حجز']):
                return self._handle_appointment_query(message)
            
            # 9. أسئلة عن الخدمات
            if any(word in message for word in ['خدمة', 'service', 'خدمات']):
                return self._handle_service_query(message)
            
            # 10. تحليل النظام
            if any(word in message for word in ['حلل', 'تحليل', 'analyze', 'analysis']):
                return self._handle_system_analysis()
            
            # 11. تقارير
            if any(word in message for word in ['تقرير', 'report']):
                return self._handle_report_generation()
            
            # 12. جداول قاعدة البيانات
            if any(word in message for word in ['جدول', 'table', 'جداول', 'قاعدة البيانات', 'database']):
                return self._handle_database_query(message)
            
            # 13. البحث العام في قاعدة البيانات
            return self._handle_general_search(message)
            
        except Exception as e:
            logging.error(f"AI Engine Error: {str(e)}")
            return {
                'response': f"عذراً، حدث خطأ في معالجة سؤالك: {str(e)}",
                'actions': []
            }
    
    def _is_calculation(self, message):
        """التحقق إذا كان السؤال عملية حسابية"""
        calc_patterns = [
            r'\d+\s*[\+\-\*\/×÷]\s*\d+',
            r'احسب',
            r'calculate',
            r'حاسبة',
            r'calculator'
        ]
        return any(re.search(pattern, message) for pattern in calc_patterns)
    
    def _handle_calculation(self, message):
        """معالجة العمليات الحسابية"""
        try:
            # استخراج العملية الحسابية
            calc_match = re.search(r'(\d+\.?\d*)\s*([\+\-\*\/×÷])\s*(\d+\.?\d*)', message)
            
            if calc_match:
                num1 = float(calc_match.group(1))
                operator = calc_match.group(2)
                num2 = float(calc_match.group(3))
                
                # تنفيذ العملية
                if operator in ['+', 'plus']:
                    result = num1 + num2
                    op_ar = 'جمع'
                elif operator in ['-', 'minus']:
                    result = num1 - num2
                    op_ar = 'طرح'
                elif operator in ['*', '×', 'multiply']:
                    result = num1 * num2
                    op_ar = 'ضرب'
                elif operator in ['/', '÷', 'divide']:
                    if num2 == 0:
                        return {
                            'response': '❌ خطأ: لا يمكن القسمة على صفر!',
                            'actions': []
                        }
                    result = num1 / num2
                    op_ar = 'قسمة'
                else:
                    return {
                        'response': '❌ عملية حسابية غير مدعومة',
                        'actions': []
                    }
                
                response = f"""
🧮 **نتيجة العملية الحسابية:**

**العملية:** {num1} {operator} {num2}
**النتيجة:** {result:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **يمكنك إجراء عمليات حسابية أخرى:**
- جمع: 5 + 3
- طرح: 10 - 4
- ضرب: 6 × 7
- قسمة: 20 ÷ 4
"""
                return {'response': response, 'actions': []}
            else:
                return {
                    'response': '🧮 الآلة الحاسبة جاهزة! أدخل عملية حسابية مثل: 5 + 3 أو 10 × 2',
                    'actions': []
                }
                
        except Exception as e:
            return {
                'response': f'❌ خطأ في العملية الحسابية: {str(e)}',
                'actions': []
            }
    
    def _handle_count_query(self, message):
        """معالجة أسئلة العد"""
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        from models.service import ServiceMaster
        from models.appointment import Appointment
        
        response = "📊 **إحصائيات النظام:**\n\n"
        
        # إحصائيات المستخدمين
        if 'مستخدم' in message or 'user' in message or 'موظف' in message:
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            response += f"👥 **المستخدمون:**\n"
            response += f"├─ إجمالي المستخدمين: {total_users}\n"
            response += f"└─ المستخدمون النشطون: {active_users}\n\n"
        
        # إحصائيات الأطباء
        if 'طبيب' in message or 'doctor' in message or 'دكتور' in message:
            total_doctors = User.query.filter_by(role='doctor').count()
            active_doctors = User.query.filter_by(role='doctor', is_active=True).count()
            response += f"👨‍⚕️ **الأطباء:**\n"
            response += f"├─ إجمالي الأطباء: {total_doctors}\n"
            response += f"└─ الأطباء النشطون: {active_doctors}\n\n"
        
        # إحصائيات المرضى
        if 'مريض' in message or 'patient' in message:
            total_patients = Patient.query.count()
            response += f"🏥 **المرضى:**\n"
            response += f"└─ إجمالي المرضى: {total_patients}\n\n"
        
        # إحصائيات الزيارات
        if 'زيارة' in message or 'visit' in message:
            total_visits = Visit.query.count()
            today_visits = Visit.query.filter(
                func.date(Visit.created_at) == date.today()
            ).count()
            response += f"📋 **الزيارات:**\n"
            response += f"├─ إجمالي الزيارات: {total_visits}\n"
            response += f"└─ زيارات اليوم: {today_visits}\n\n"
        
        # إحصائيات الأقسام
        if 'قسم' in message or 'department' in message:
            total_departments = Department.query.count()
            active_departments = Department.query.filter_by(is_active=True).count()
            response += f"🏢 **الأقسام:**\n"
            response += f"├─ إجمالي الأقسام: {total_departments}\n"
            response += f"└─ الأقسام النشطة: {active_departments}\n\n"
        
        # إحصائيات الخدمات
        if 'خدمة' in message or 'service' in message:
            total_services = ServiceMaster.query.count()
            active_services = ServiceMaster.query.filter_by(is_active=True).count()
            response += f"⚕️ **الخدمات:**\n"
            response += f"├─ إجمالي الخدمات: {total_services}\n"
            response += f"└─ الخدمات النشطة: {active_services}\n\n"
        
        # إحصائيات المواعيد
        if 'موعد' in message or 'appointment' in message:
            total_appointments = Appointment.query.count()
            today_appointments = Appointment.query.filter(
                func.date(Appointment.starts_at) == date.today()
            ).count()
            response += f"📅 **المواعيد:**\n"
            response += f"├─ إجمالي المواعيد: {total_appointments}\n"
            response += f"└─ مواعيد اليوم: {today_appointments}\n\n"
        
        # إذا لم يتم تحديد شيء محدد، أظهر كل شيء
        if response == "📊 **إحصائيات النظام:**\n\n":
            total_users = User.query.count()
            total_doctors = User.query.filter_by(role='doctor').count()
            total_patients = Patient.query.count()
            total_visits = Visit.query.count()
            total_departments = Department.query.count()
            total_services = ServiceMaster.query.count()
            
            response += f"👥 المستخدمون: {total_users}\n"
            response += f"👨‍⚕️ الأطباء: {total_doctors}\n"
            response += f"🏥 المرضى: {total_patients}\n"
            response += f"📋 الزيارات: {total_visits}\n"
            response += f"🏢 الأقسام: {total_departments}\n"
            response += f"⚕️ الخدمات: {total_services}\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_user_query(self, message):
        """معالجة أسئلة عن المستخدمين"""
        from models.user import User
        
        # البحث عن اسم محدد
        name_match = re.search(r'(مستخدم|user)\s+(\w+)', message)
        if name_match:
            name = name_match.group(2)
            users = User.query.filter(
                User.full_name.ilike(f'%{name}%')
            ).all()
            
            if users:
                response = f"👥 **نتائج البحث عن '{name}':**\n\n"
                for user in users[:5]:
                    response += f"**{user.full_name}**\n"
                    response += f"├─ الدور: {user.role}\n"
                    response += f"├─ البريد: {user.email or 'غير محدد'}\n"
                    response += f"├─ الحالة: {'نشط' if user.is_active else 'غير نشط'}\n"
                    response += f"└─ تاريخ الإنشاء: {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'غير محدد'}\n\n"
                return {'response': response, 'actions': []}
        
        # إحصائيات عامة
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        inactive_users = total_users - active_users
        
        # توزيع الأدوار
        roles_dist = self.db.session.query(
            User.role, func.count(User.id)
        ).group_by(User.role).all()
        
        response = f"""
👥 **معلومات المستخدمين:**

**📊 الإحصائيات:**
├─ إجمالي المستخدمين: {total_users}
├─ المستخدمون النشطون: {active_users}
└─ المستخدمون غير النشطين: {inactive_users}

**📈 توزيع الأدوار:**
"""
        for role, count in roles_dist:
            role_ar = {
                'super_admin': 'مدير النظام',
                'admin': 'مدير',
                'doctor': 'طبيب',
                'nurse': 'ممرض',
                'receptionist': 'موظف استقبال',
                'accountant': 'محاسب',
                'pharmacist': 'صيدلي',
                'lab_tech': 'فني مختبر'
            }.get(role, role)
            response += f"├─ {role_ar}: {count}\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_doctor_query(self, message):
        """معالجة أسئلة عن الأطباء"""
        from models.user import User
        from models.visit import Visit
        
        # البحث عن طبيب محدد
        name_match = re.search(r'(طبيب|دكتور|doctor)\s+(\w+)', message, re.IGNORECASE)
        if name_match:
            name = name_match.group(2)
            doctors = User.query.filter(
                User.role == 'doctor',
                User.full_name.ilike(f'%{name}%')
            ).all()
            
            if doctors:
                response = f"👨‍⚕️ **معلومات عن الدكتور '{name}':**\n\n"
                for doctor in doctors[:3]:
                    # إحصائيات الطبيب
                    total_visits = Visit.query.filter_by(doctor_id=doctor.id).count()
                    today_visits = Visit.query.filter(
                        Visit.doctor_id == doctor.id,
                        func.date(Visit.created_at) == date.today()
                    ).count()
                    
                    response += f"**د. {doctor.full_name}**\n"
                    response += f"├─ التخصص: {doctor.specialization or 'غير محدد'}\n"
                    response += f"├─ القسم: {doctor.department.name if doctor.department else 'غير محدد'}\n"
                    response += f"├─ الحالة: {'نشط' if doctor.is_active else 'غير نشط'}\n"
                    response += f"├─ إجمالي الزيارات: {total_visits}\n"
                    response += f"└─ زيارات اليوم: {today_visits}\n\n"
                
                return {'response': response, 'actions': []}
            else:
                return {
                    'response': f"❌ لم يتم العثور على طبيب باسم '{name}'",
                    'actions': []
                }
        
        # إحصائيات عامة عن الأطباء
        total_doctors = User.query.filter_by(role='doctor').count()
        active_doctors = User.query.filter_by(role='doctor', is_active=True).count()
        
        # أكثر الأطباء نشاطاً
        top_doctors = self.db.session.query(
            User.full_name,
            func.count(Visit.id).label('visit_count')
        ).join(Visit, Visit.doctor_id == User.id)\
         .filter(User.role == 'doctor')\
         .group_by(User.id, User.full_name)\
         .order_by(func.count(Visit.id).desc())\
         .limit(5).all()
        
        response = f"""
👨‍⚕️ **معلومات الأطباء:**

**📊 الإحصائيات:**
├─ إجمالي الأطباء: {total_doctors}
└─ الأطباء النشطون: {active_doctors}

**⭐ أكثر الأطباء نشاطاً:**
"""
        for i, (name, count) in enumerate(top_doctors, 1):
            response += f"{i}. د. {name}: {count} زيارة\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_patient_query(self, message):
        """معالجة أسئلة عن المرضى"""
        from models.patient import Patient
        from models.visit import Visit
        
        # البحث عن مريض محدد
        name_match = re.search(r'(مريض|patient)\s+(\w+)', message, re.IGNORECASE)
        if name_match:
            name = name_match.group(2)
            patients = Patient.query.filter(
                Patient.full_name.ilike(f'%{name}%')
            ).all()
            
            if patients:
                response = f"🏥 **معلومات عن المريض '{name}':**\n\n"
                for patient in patients[:3]:
                    # إحصائيات المريض
                    total_visits = Visit.query.filter_by(patient_id=patient.id).count()
                    last_visit = Visit.query.filter_by(patient_id=patient.id)\
                        .order_by(Visit.created_at.desc()).first()
                    
                    # حساب العمر
                    age = None
                    if patient.birth_date:
                        today = date.today()
                        age = today.year - patient.birth_date.year - (
                            (today.month, today.day) < (patient.birth_date.month, patient.birth_date.day)
                        )
                    
                    response += f"**{patient.full_name}**\n"
                    response += f"├─ الرقم الطبي: {patient.medical_number}\n"
                    response += f"├─ العمر: {age if age else 'غير محدد'} سنة\n"
                    response += f"├─ الجنس: {patient.gender}\n"
                    response += f"├─ الهاتف: {patient.phone or 'غير محدد'}\n"
                    response += f"├─ إجمالي الزيارات: {total_visits}\n"
                    response += f"└─ آخر زيارة: {last_visit.created_at.strftime('%Y-%m-%d') if last_visit else 'لا توجد'}\n\n"
                
                return {'response': response, 'actions': []}
        
        # إحصائيات عامة
        total_patients = Patient.query.count()
        male_patients = Patient.query.filter_by(gender='male').count()
        female_patients = Patient.query.filter_by(gender='female').count()
        
        # مرضى جدد اليوم
        new_today = Patient.query.filter(
            func.date(Patient.created_at) == date.today()
        ).count()
        
        response = f"""
🏥 **معلومات المرضى:**

**📊 الإحصائيات:**
├─ إجمالي المرضى: {total_patients}
├─ ذكور: {male_patients}
├─ إناث: {female_patients}
└─ مرضى جدد اليوم: {new_today}
"""
        
        return {'response': response, 'actions': []}
    
    def _handle_department_query(self, message):
        """معالجة أسئلة عن الأقسام"""
        from models.department import Department
        from models.user import User
        
        # البحث عن قسم محدد
        name_match = re.search(r'(قسم|department)\s+(\w+)', message, re.IGNORECASE)
        if name_match:
            name = name_match.group(2)
            departments = Department.query.filter(
                Department.name.ilike(f'%{name}%')
            ).all()
            
            if departments:
                response = f"🏢 **معلومات عن القسم '{name}':**\n\n"
                for dept in departments:
                    # عدد الموظفين
                    staff_count = User.query.filter_by(department_id=dept.id).count()
                    doctors_count = User.query.filter_by(
                        department_id=dept.id,
                        role='doctor'
                    ).count()
                    
                    response += f"**{dept.name}**\n"
                    response += f"├─ الوصف: {dept.description or 'غير محدد'}\n"
                    response += f"├─ الحالة: {'نشط' if dept.is_active else 'غير نشط'}\n"
                    response += f"├─ عدد الموظفين: {staff_count}\n"
                    response += f"└─ عدد الأطباء: {doctors_count}\n\n"
                
                return {'response': response, 'actions': []}
        
        # إحصائيات عامة
        total_departments = Department.query.count()
        active_departments = Department.query.filter_by(is_active=True).count()
        
        # الأقسام مع عدد الموظفين
        dept_stats = self.db.session.query(
            Department.name,
            func.count(User.id).label('staff_count')
        ).outerjoin(User, User.department_id == Department.id)\
         .group_by(Department.id, Department.name)\
         .order_by(func.count(User.id).desc())\
         .limit(5).all()
        
        response = f"""
🏢 **معلومات الأقسام:**

**📊 الإحصائيات:**
├─ إجمالي الأقسام: {total_departments}
└─ الأقسام النشطة: {active_departments}

**👥 الأقسام حسب عدد الموظفين:**
"""
        for name, count in dept_stats:
            response += f"├─ {name}: {count} موظف\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_visit_query(self, message):
        """معالجة أسئلة عن الزيارات"""
        from models.visit import Visit
        
        total_visits = Visit.query.count()
        today_visits = Visit.query.filter(
            func.date(Visit.created_at) == date.today()
        ).count()
        
        # زيارات الأسبوع
        week_ago = date.today() - timedelta(days=7)
        week_visits = Visit.query.filter(
            Visit.created_at >= week_ago
        ).count()
        
        # زيارات الشهر
        month_ago = date.today() - timedelta(days=30)
        month_visits = Visit.query.filter(
            Visit.created_at >= month_ago
        ).count()
        
        # حالات الزيارات
        status_dist = self.db.session.query(
            Visit.status,
            func.count(Visit.id)
        ).group_by(Visit.status).all()
        
        response = f"""
📋 **معلومات الزيارات:**

**📊 الإحصائيات:**
├─ إجمالي الزيارات: {total_visits}
├─ زيارات اليوم: {today_visits}
├─ زيارات الأسبوع: {week_visits}
└─ زيارات الشهر: {month_visits}

**📈 توزيع حالات الزيارات:**
"""
        for status, count in status_dist:
            status_ar = {
                'active': 'نشطة',
                'completed': 'مكتملة',
                'cancelled': 'ملغاة',
                'pending': 'قيد الانتظار'
            }.get(status, status)
            response += f"├─ {status_ar}: {count}\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_appointment_query(self, message):
        """معالجة أسئلة عن المواعيد"""
        from models.appointment import Appointment
        
        total_appointments = Appointment.query.count()
        today_appointments = Appointment.query.filter(
            func.date(Appointment.starts_at) == date.today()
        ).count()
        
        # مواعيد قادمة
        upcoming = Appointment.query.filter(
            Appointment.starts_at > datetime.now(),
            Appointment.status == AppointmentState.SCHEDULED
        ).count()
        
        # مواعيد متأخرة
        overdue = Appointment.query.filter(
            Appointment.starts_at < datetime.now(),
            Appointment.status == AppointmentState.SCHEDULED
        ).count()
        
        response = f"""
📅 **معلومات المواعيد:**

**📊 الإحصائيات:**
├─ إجمالي المواعيد: {total_appointments}
├─ مواعيد اليوم: {today_appointments}
├─ مواعيد قادمة: {upcoming}
└─ مواعيد متأخرة: {overdue}
"""
        
        if overdue > 0:
            response += f"\n⚠️ **تحذير:** يوجد {overdue} موعد متأخر يحتاج متابعة!"
        
        return {'response': response, 'actions': []}
    
    def _handle_service_query(self, message):
        """معالجة أسئلة عن الخدمات"""
        from models.service import ServiceMaster
        
        total_services = ServiceMaster.query.count()
        active_services = ServiceMaster.query.filter_by(is_active=True).count()
        
        # الخدمات الأكثر استخداماً (يمكن تطويرها)
        services = ServiceMaster.query.filter_by(is_active=True).limit(10).all()
        
        response = f"""
⚕️ **معلومات الخدمات:**

**📊 الإحصائيات:**
├─ إجمالي الخدمات: {total_services}
└─ الخدمات النشطة: {active_services}

**📋 الخدمات المتاحة:**
"""
        for service in services:
            price = f"{service.base_price:,.2f} ريال" if service.base_price else "غير محدد"
            response += f"├─ {service.name}: {price}\n"
        
        return {'response': response, 'actions': []}
    
    def _handle_system_analysis(self):
        """تحليل شامل للنظام"""
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        
        # جمع الإحصائيات
        total_users = User.query.count()
        total_patients = Patient.query.count()
        total_visits = Visit.query.count()
        total_departments = Department.query.count()
        
        today_visits = Visit.query.filter(
            func.date(Visit.created_at) == date.today()
        ).count()
        
        # تقييم الأداء
        performance_score = 0
        if total_users > 0:
            performance_score += 20
        if total_patients > 10:
            performance_score += 20
        if total_visits > 50:
            performance_score += 30
        if total_departments > 0:
            performance_score += 15
        if today_visits > 0:
            performance_score += 15
        
        status = "ممتاز" if performance_score >= 80 else "جيد" if performance_score >= 60 else "متوسط"
        
        response = f"""
📊 **تحليل شامل للنظام:**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🎯 تقييم الأداء العام:** {status}
**📈 درجة الأداء:** {performance_score}/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**👥 المستخدمون:**
├─ إجمالي المستخدمين: {total_users}
└─ معدل النشاط: {(User.query.filter_by(is_active=True).count() / total_users * 100) if total_users > 0 else 0:.1f}%

**🏥 المرضى:**
├─ إجمالي المرضى: {total_patients}
└─ مرضى جدد اليوم: {Patient.query.filter(func.date(Patient.created_at) == date.today()).count()}

**📋 الزيارات:**
├─ إجمالي الزيارات: {total_visits}
├─ زيارات اليوم: {today_visits}
└─ متوسط الزيارات اليومية: {(total_visits / 30):.1f}

**🏢 الأقسام:**
├─ إجمالي الأقسام: {total_departments}
└─ الأقسام النشطة: {Department.query.filter_by(is_active=True).count()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 التوصيات:**
"""
        
        # توصيات ذكية
        if total_patients < 10:
            response += "• يُنصح بزيادة التسويق لجذب المزيد من المرضى\n"
        if today_visits == 0:
            response += "• لا توجد زيارات اليوم - تحقق من المواعيد\n"
        if total_departments == 0:
            response += "• يُنصح بإضافة أقسام للنظام\n"
        
        response += "\n✅ النظام يعمل بشكل جيد!"
        
        return {'response': response, 'actions': []}
    
    def _handle_report_generation(self):
        """إنشاء تقرير شامل"""
        return self._handle_system_analysis()
    
    def _handle_database_query(self, message):
        """معالجة أسئلة عن قاعدة البيانات"""
        # الحصول على جميع الجداول
        tables = self.inspector.get_table_names()
        
        response = f"""
🗄️ **معلومات قاعدة البيانات:**

**📋 الجداول المتاحة ({len(tables)}):**

"""
        for i, table in enumerate(tables, 1):
            # الحصول على عدد الأعمدة
            columns = self.inspector.get_columns(table)
            response += f"{i}. **{table}** ({len(columns)} عمود)\n"
        
        response += "\n💡 **للاستعلام عن جدول محدد:**\n"
        response += "اكتب: 'معلومات عن جدول [اسم الجدول]'"
        
        return {'response': response, 'actions': []}
    
    def _handle_general_search(self, message):
        """البحث العام في النظام"""
        response = """
🤖 **المساعد الذكي جاهز للمساعدة!**

**يمكنني الإجابة على أسئلة مثل:**

📊 **الإحصائيات:**
• كم عدد المرضى؟
• كم طبيب لدينا؟
• كم زيارة اليوم؟

👥 **المستخدمون:**
• معلومات عن المستخدمين
• من هو الدكتور [الاسم]؟
• ماذا يعمل الطبيب [الاسم]؟

🏥 **المرضى:**
• معلومات عن المريض [الاسم]
• كم مريض جديد اليوم؟

🏢 **الأقسام:**
• ما هي الأقسام المتاحة؟
• معلومات عن قسم [الاسم]

📋 **التحليلات:**
• حلل النظام
• أنشئ تقرير شامل

🧮 **الحاسبة:**
• احسب 5 + 3
• 10 × 2

💡 **جرب أي سؤال وسأحاول مساعدتك!**
"""
        return {'response': response, 'actions': []}
    
    def _analyze_user_errors(self):
        """تحليل متقدم لأخطاء ومشاكل المستخدمين"""
        from models.user import User
        from models.visit import Visit
        from models.audit_trail import AuditTrail
        
        # جمع البيانات
        total_users = User.query.count()
        inactive_users = User.query.filter_by(is_active=False).all()
        users_without_email = User.query.filter(
            (User.email == None) | (User.email == '')
        ).all()
        users_without_phone = User.query.filter(
            (User.phone == None) | (User.phone == '')
        ).all()
        
        # المستخدمين الذين لم يسجلوا دخول أبداً
        users_never_logged_in = User.query.filter(
            User.last_login == None
        ).all()
        
        # المستخدمين بدون أدوار أو صلاحيات
        users_without_role = User.query.filter(
            (User.role == None) | (User.role == '')
        ).all()
        
        # الأطباء بدون قسم
        doctors_without_dept = User.query.filter(
            User.role == 'doctor',
            User.department_id == None
        ).all()
        
        # الأطباء بدون زيارات
        doctors = User.query.filter_by(role='doctor').all()
        doctors_no_visits = []
        for doctor in doctors:
            visit_count = Visit.query.filter_by(doctor_id=doctor.id).count()
            if visit_count == 0:
                doctors_no_visits.append(doctor)
        
        # تحليل الأخطاء
        errors = []
        warnings = []
        suggestions = []
        
        if len(inactive_users) > 0:
            errors.append(f"🔴 **{len(inactive_users)} مستخدم غير نشط** - قد يحتاجون تفعيل أو حذف")
            for user in inactive_users[:5]:
                errors.append(f"   • {user.full_name} ({user.username}) - غير نشط منذ {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'غير معروف'}")
        
        if len(users_without_email) > 0:
            warnings.append(f"⚠️ **{len(users_without_email)} مستخدم بدون بريد إلكتروني**")
            for user in users_without_email[:3]:
                warnings.append(f"   • {user.full_name}")
        
        if len(users_without_phone) > 0:
            warnings.append(f"⚠️ **{len(users_without_phone)} مستخدم بدون رقم هاتف**")
        
        if len(users_never_logged_in) > 0:
            errors.append(f"🔴 **{len(users_never_logged_in)} مستخدم لم يسجل دخول أبداً**")
            for user in users_never_logged_in[:5]:
                errors.append(f"   • {user.full_name} - تم إنشاؤه {user.created_at.strftime('%Y-%m-%d') if user.created_at else 'غير معروف'}")
        
        if len(users_without_role) > 0:
            errors.append(f"🔴 **{len(users_without_role)} مستخدم بدون دور محدد**")
        
        if len(doctors_without_dept) > 0:
            errors.append(f"🔴 **{len(doctors_without_dept)} طبيب بدون قسم**")
            for doctor in doctors_without_dept:
                errors.append(f"   • د. {doctor.full_name}")
        
        if len(doctors_no_visits) > 0:
            warnings.append(f"⚠️ **{len(doctors_no_visits)} طبيب بدون زيارات**")
            for doctor in doctors_no_visits[:5]:
                warnings.append(f"   • د. {doctor.full_name}")
        
        # اقتراحات الحلول
        if len(inactive_users) > 0:
            suggestions.append("💡 **حذف أو تفعيل المستخدمين غير النشطين**")
        
        if len(users_without_email) > 0:
            suggestions.append("💡 **إضافة البريد الإلكتروني للمستخدمين**")
        
        if len(doctors_without_dept) > 0:
            suggestions.append("💡 **تعيين الأطباء إلى أقسامهم المناسبة**")
        
        if len(users_never_logged_in) > 0:
            suggestions.append("💡 **إرسال تذكير للمستخدمين الجدد لتسجيل الدخول**")
        
        # بناء التقرير
        response = f"""
🔍 **تحليل متقدم لأخطاء ومشاكل المستخدمين**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **ملخص سريع:**
├─ إجمالي المستخدمين: {total_users}
├─ مستخدمون غير نشطين: {len(inactive_users)}
├─ بدون بريد إلكتروني: {len(users_without_email)}
├─ بدون رقم هاتف: {len(users_without_phone)}
├─ لم يسجلوا دخول أبداً: {len(users_never_logged_in)}
├─ بدون دور محدد: {len(users_without_role)}
├─ أطباء بدون قسم: {len(doctors_without_dept)}
└─ أطباء بدون زيارات: {len(doctors_no_visits)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 **الأخطاء الحرجة:**

{chr(10).join(errors) if errors else '✅ لا توجد أخطاء حرجة!'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **التحذيرات:**

{chr(10).join(warnings) if warnings else '✅ لا توجد تحذيرات!'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **الاقتراحات والحلول:**

{chr(10).join(suggestions) if suggestions else '✅ النظام يعمل بشكل ممتاز!'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **تقييم الصحة العامة:**
{'🟢 ممتاز' if len(errors) == 0 and len(warnings) <= 1 else '🟡 جيد' if len(errors) <= 1 else '🔴 يحتاج تحسين'}

**💡 نصيحة:** ابدأ بحل الأخطاء الحرجة أولاً!
"""
        
        return {'response': response, 'actions': []}
    
    def _analyze_doctor_problems(self):
        """تحليل مشاكل الأطباء"""
        from models.user import User
        from models.visit import Visit
        from models.department import Department
        
        doctors = User.query.filter_by(role='doctor').all()
        total_doctors = len(doctors)
        
        problems = []
        
        # الأطباء غير النشطين
        inactive_doctors = [d for d in doctors if not d.is_active]
        if inactive_doctors:
            problems.append(f"🔴 **{len(inactive_doctors)} طبيب غير نشط**")
        
        # الأطباء بدون قسم
        doctors_no_dept = [d for d in doctors if not d.department_id]
        if doctors_no_dept:
            problems.append(f"🔴 **{len(doctors_no_dept)} طبيب بدون قسم**")
            for doc in doctors_no_dept[:3]:
                problems.append(f"   • د. {doc.full_name}")
        
        # الأطباء بدون زيارات
        doctors_no_visits = []
        for doctor in doctors:
            visits = Visit.query.filter_by(doctor_id=doctor.id).count()
            if visits == 0:
                doctors_no_visits.append(doctor)
        
        if doctors_no_visits:
            problems.append(f"⚠️ **{len(doctors_no_visits)} طبيب بدون زيارات**")
        
        # الأطباء بزيارات قليلة جداً
        low_activity_doctors = []
        for doctor in doctors:
            visits = Visit.query.filter_by(doctor_id=doctor.id).count()
            if 0 < visits < 5:
                low_activity_doctors.append((doctor, visits))
        
        if low_activity_doctors:
            problems.append(f"⚠️ **{len(low_activity_doctors)} طبيب بنشاط منخفض**")
        
        response = f"""
👨‍⚕️ **تحليل مشاكل الأطباء**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **الإحصائيات:**
├─ إجمالي الأطباء: {total_doctors}
├─ أطباء غير نشطين: {len(inactive_doctors)}
├─ أطباء بدون قسم: {len(doctors_no_dept)}
├─ أطباء بدون زيارات: {len(doctors_no_visits)}
└─ أطباء بنشاط منخفض: {len(low_activity_doctors)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 **المشاكل المكتشفة:**

{chr(10).join(problems) if problems else '✅ لا توجد مشاكل!'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **التوصيات:**
• تعيين الأطباء إلى أقسامهم
• تفعيل الأطباء غير النشطين أو حذفهم
• مراجعة جداول الأطباء ذوي النشاط المنخفض
"""
        
        return {'response': response, 'actions': []}
    
    def _analyze_department_problems(self):
        """تحليل مشاكل الأقسام"""
        from models.department import Department
        from models.user import User
        
        departments = Department.query.all()
        total_depts = len(departments)
        
        problems = []
        
        # الأقسام غير النشطة
        inactive_depts = [d for d in departments if not d.is_active]
        if inactive_depts:
            problems.append(f"🔴 **{len(inactive_depts)} قسم غير نشط**")
            for dept in inactive_depts:
                problems.append(f"   • {dept.name}")
        
        # الأقسام بدون موظفين
        depts_no_staff = []
        for dept in departments:
            staff_count = User.query.filter_by(department_id=dept.id).count()
            if staff_count == 0:
                depts_no_staff.append(dept)
        
        if depts_no_staff:
            problems.append(f"⚠️ **{len(depts_no_staff)} قسم بدون موظفين**")
            for dept in depts_no_staff:
                problems.append(f"   • {dept.name}")
        
        # الأقسام بدون أطباء
        depts_no_doctors = []
        for dept in departments:
            doctors_count = User.query.filter_by(
                department_id=dept.id,
                role='doctor'
            ).count()
            if doctors_count == 0:
                depts_no_doctors.append(dept)
        
        if depts_no_doctors:
            problems.append(f"⚠️ **{len(depts_no_doctors)} قسم بدون أطباء**")
        
        response = f"""
🏢 **تحليل مشاكل الأقسام**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **الإحصائيات:**
├─ إجمالي الأقسام: {total_depts}
├─ أقسام غير نشطة: {len(inactive_depts)}
├─ أقسام بدون موظفين: {len(depts_no_staff)}
└─ أقسام بدون أطباء: {len(depts_no_doctors)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 **المشاكل المكتشفة:**

{chr(10).join(problems) if problems else '✅ لا توجد مشاكل!'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **التوصيات:**
• تفعيل الأقسام غير النشطة أو حذفها
• تعيين موظفين للأقسام الفارغة
• توزيع الأطباء على الأقسام بشكل متوازن
"""
        
        return {'response': response, 'actions': []}
