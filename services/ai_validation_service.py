"""
خدمة التحقق الذكي للمساعد
AI Validation Service
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import logging

class AIValidationService:
    """خدمة التحقق الذكي من البيانات"""
    
    @staticmethod
    def validate_user_data(data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        التحقق من بيانات المستخدم
        Returns: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # التحقق من البريد الإلكتروني
        if 'email' in data:
            email = data['email']
            if not email or '@' not in email:
                errors.append("⚠️ البريد الإلكتروني غير صحيح")
            elif not email.endswith(('.com', '.net', '.org', '.edu')):
                warnings.append("⚠️ البريد الإلكتروني قد يكون غير صحيح")
        
        # التحقق من كلمة المرور
        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                errors.append("⚠️ كلمة المرور قصيرة جداً (يجب أن تكون 8 أحرف على الأقل)")
            if password.isdigit() or password.isalpha():
                warnings.append("⚠️ كلمة المرور ضعيفة - يُنصح باستخدام أحرف وأرقام ورموز")
        
        # التحقق من رقم الهاتف
        if 'phone' in data and data['phone']:
            phone = str(data['phone']).replace(' ', '').replace('-', '')
            if not phone.isdigit():
                errors.append("⚠️ رقم الهاتف يجب أن يحتوي على أرقام فقط")
            elif len(phone) < 9 or len(phone) > 15:
                warnings.append("⚠️ رقم الهاتف قد يكون غير صحيح")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def validate_patient_data(data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """التحقق من بيانات المريض"""
        errors = []
        warnings = []
        
        # التحقق من العمر
        if 'age' in data and data['age']:
            age = int(data['age'])
            if age < 0:
                errors.append("⚠️ العمر لا يمكن أن يكون سالباً")
            elif age > 150:
                errors.append("⚠️ العمر غير منطقي (أكبر من 150)")
            elif age > 120:
                warnings.append("⚠️ العمر كبير جداً - يرجى التأكد")
            elif age < 1:
                warnings.append("⚠️ المريض رضيع - يرجى التأكد من العمر")
        
        # التحقق من تاريخ الميلاد
        if 'birth_date' in data and data['birth_date']:
            try:
                birth_date = datetime.strptime(str(data['birth_date']), '%Y-%m-%d')
                today = datetime.now()
                
                if birth_date > today:
                    errors.append("⚠️ تاريخ الميلاد في المستقبل!")
                
                age_calculated = (today - birth_date).days // 365
                if age_calculated > 150:
                    errors.append("⚠️ تاريخ الميلاد غير منطقي")
                elif age_calculated < 0:
                    errors.append("⚠️ تاريخ الميلاد في المستقبل")
            except:
                errors.append("⚠️ تاريخ الميلاد بصيغة غير صحيحة")
        
        # التحقق من الجنس
        if 'gender' in data and data['gender']:
            if data['gender'].lower() not in ['male', 'female', 'ذكر', 'أنثى', 'm', 'f']:
                errors.append("⚠️ الجنس يجب أن يكون ذكر أو أنثى")
        
        # التحقق من رقم الهوية
        if 'national_id' in data and data['national_id']:
            national_id = str(data['national_id'])
            if not national_id.isdigit():
                errors.append("⚠️ رقم الهوية يجب أن يحتوي على أرقام فقط")
            elif len(national_id) != 9:
                warnings.append("⚠️ رقم الهوية عادة يكون 9 أرقام")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def validate_visit_data(data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """التحقق من بيانات الزيارة"""
        errors = []
        warnings = []
        
        # التحقق من تاريخ الزيارة
        if 'visit_date' in data and data['visit_date']:
            try:
                visit_date = datetime.strptime(str(data['visit_date']), '%Y-%m-%d')
                today = datetime.now()
                
                if visit_date > today + timedelta(days=365):
                    errors.append("⚠️ تاريخ الزيارة بعيد جداً في المستقبل")
                elif visit_date < today - timedelta(days=365):
                    warnings.append("⚠️ تاريخ الزيارة قديم جداً (أكثر من سنة)")
            except:
                errors.append("⚠️ تاريخ الزيارة بصيغة غير صحيحة")
        
        # التحقق من الأعراض
        if 'symptoms' in data and data['symptoms']:
            symptoms = str(data['symptoms'])
            if len(symptoms) < 3:
                warnings.append("⚠️ وصف الأعراض قصير جداً")
            elif len(symptoms) > 5000:
                warnings.append("⚠️ وصف الأعراض طويل جداً")
        
        # التحقق من التشخيص
        if 'diagnosis' in data and data['diagnosis']:
            diagnosis = str(data['diagnosis'])
            if len(diagnosis) < 3:
                warnings.append("⚠️ التشخيص قصير جداً")
        
        # التحقق من ضغط الدم
        if 'blood_pressure' in data and data['blood_pressure']:
            bp = str(data['blood_pressure'])
            if '/' in bp:
                try:
                    systolic, diastolic = map(int, bp.split('/'))
                    if systolic < 60 or systolic > 250:
                        errors.append(f"⚠️ ضغط الدم الانقباضي غير طبيعي: {systolic}")
                    elif systolic < 90 or systolic > 180:
                        warnings.append(f"⚠️ ضغط الدم الانقباضي خارج النطاق الطبيعي: {systolic}")
                    
                    if diastolic < 40 or diastolic > 150:
                        errors.append(f"⚠️ ضغط الدم الانبساطي غير طبيعي: {diastolic}")
                    elif diastolic < 60 or diastolic > 100:
                        warnings.append(f"⚠️ ضغط الدم الانبساطي خارج النطاق الطبيعي: {diastolic}")
                    
                    if systolic <= diastolic:
                        errors.append("⚠️ ضغط الدم غير منطقي (الانقباضي يجب أن يكون أكبر من الانبساطي)")
                except:
                    errors.append("⚠️ صيغة ضغط الدم غير صحيحة (يجب أن تكون مثل: 120/80)")
        
        # التحقق من درجة الحرارة
        if 'temperature' in data and data['temperature']:
            try:
                temp = float(data['temperature'])
                if temp < 30 or temp > 45:
                    errors.append(f"⚠️ درجة الحرارة غير منطقية: {temp}°C")
                elif temp < 35 or temp > 42:
                    warnings.append(f"⚠️ درجة الحرارة خطيرة: {temp}°C - يرجى التأكد")
                elif temp < 36 or temp > 38:
                    warnings.append(f"⚠️ درجة الحرارة غير طبيعية: {temp}°C")
            except:
                errors.append("⚠️ درجة الحرارة يجب أن تكون رقماً")
        
        # التحقق من نبضات القلب
        if 'heart_rate' in data and data['heart_rate']:
            try:
                hr = int(data['heart_rate'])
                if hr < 30 or hr > 250:
                    errors.append(f"⚠️ نبضات القلب غير منطقية: {hr}")
                elif hr < 50 or hr > 150:
                    warnings.append(f"⚠️ نبضات القلب غير طبيعية: {hr}")
            except:
                errors.append("⚠️ نبضات القلب يجب أن تكون رقماً")
        
        # التحقق من الوزن
        if 'weight' in data and data['weight']:
            try:
                weight = float(data['weight'])
                if weight < 0.5 or weight > 500:
                    errors.append(f"⚠️ الوزن غير منطقي: {weight} كجم")
                elif weight < 2 or weight > 300:
                    warnings.append(f"⚠️ الوزن غير عادي: {weight} كجم - يرجى التأكد")
            except:
                errors.append("⚠️ الوزن يجب أن يكون رقماً")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def validate_medication_data(data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """التحقق من بيانات الدواء"""
        errors = []
        warnings = []
        
        # التحقق من الجرعة
        if 'dosage' in data and data['dosage']:
            dosage = str(data['dosage'])
            if len(dosage) < 2:
                warnings.append("⚠️ وصف الجرعة قصير جداً")
        
        # التحقق من التكرار
        if 'frequency' in data and data['frequency']:
            try:
                freq = int(data['frequency'])
                if freq < 1:
                    errors.append("⚠️ التكرار يجب أن يكون على الأقل مرة واحدة")
                elif freq > 10:
                    warnings.append(f"⚠️ التكرار عالي جداً: {freq} مرات - يرجى التأكد")
            except:
                pass  # قد يكون نص مثل "3 مرات يومياً"
        
        # التحقق من المدة
        if 'duration' in data and data['duration']:
            try:
                duration = int(data['duration'])
                if duration < 1:
                    errors.append("⚠️ المدة يجب أن تكون على الأقل يوم واحد")
                elif duration > 365:
                    warnings.append(f"⚠️ المدة طويلة جداً: {duration} يوم - يرجى التأكد")
            except:
                pass
        
        # التحقق من السعر
        if 'price' in data and data['price']:
            try:
                price = float(data['price'])
                if price < 0:
                    errors.append("⚠️ السعر لا يمكن أن يكون سالباً")
                elif price > 10000:
                    warnings.append(f"⚠️ السعر مرتفع جداً: {price} - يرجى التأكد")
            except:
                errors.append("⚠️ السعر يجب أن يكون رقماً")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def validate_financial_data(data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """التحقق من البيانات المالية"""
        errors = []
        warnings = []
        
        # التحقق من المبلغ
        if 'amount' in data and data['amount'] is not None:
            try:
                amount = float(data['amount'])
                if amount < 0:
                    errors.append("⚠️ المبلغ لا يمكن أن يكون سالباً")
                elif amount > 100000:
                    warnings.append(f"⚠️ المبلغ كبير جداً: {amount} - يرجى التأكد")
                elif amount == 0:
                    warnings.append("⚠️ المبلغ صفر - يرجى التأكد")
            except:
                errors.append("⚠️ المبلغ يجب أن يكون رقماً")
        
        # التحقق من الخصم
        if 'discount' in data and data['discount']:
            try:
                discount = float(data['discount'])
                if discount < 0:
                    errors.append("⚠️ الخصم لا يمكن أن يكون سالباً")
                elif discount > 100:
                    errors.append("⚠️ الخصم لا يمكن أن يكون أكثر من 100%")
                elif discount > 50:
                    warnings.append(f"⚠️ الخصم كبير جداً: {discount}% - يرجى التأكد")
            except:
                errors.append("⚠️ الخصم يجب أن يكون رقماً")
        
        # التحقق من المبلغ المدفوع
        if 'paid_amount' in data and 'total_amount' in data:
            try:
                paid = float(data['paid_amount'])
                total = float(data['total_amount'])
                
                if paid > total * 1.5:
                    warnings.append(f"⚠️ المبلغ المدفوع ({paid}) أكبر بكثير من المبلغ الإجمالي ({total})")
            except:
                pass
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def validate_system_logic(operation: str, data: Dict[str, Any], db_session) -> Tuple[bool, List[str], List[str]]:
        """التحقق من المنطق العام للنظام"""
        errors = []
        warnings = []
        
        try:
            # التحقق من تعارض المواعيد
            if operation == 'create_appointment':
                from models.user import User
                from models.visit import Visit
                from datetime import datetime
                
                doctor_id = data.get('doctor_id')
                appointment_time = data.get('appointment_time')
                
                if doctor_id and appointment_time:
                    # التحقق من أن الطبيب موجود ونشط (الطبيب هو مستخدم بدور doctor)
                    doctor = db_session.query(User).filter_by(id=doctor_id, role='doctor').first()
                    if not doctor:
                        errors.append("⚠️ الطبيب غير موجود في النظام")
                    elif not doctor.is_active:
                        errors.append(f"⚠️ الطبيب {doctor.full_name} غير نشط حالياً")
                    
                    # التحقق من تعارض المواعيد
                    conflicting = db_session.query(Visit).filter(
                        Visit.doctor_id == doctor_id,
                        Visit.appointment_time == appointment_time,
                        Visit.status != 'cancelled'
                    ).first()
                    
                    if conflicting:
                        errors.append(f"⚠️ يوجد موعد آخر لنفس الطبيب في نفس الوقت")
            
            # التحقق من وجود المريض
            if operation in ['create_visit', 'create_appointment']:
                from models.patient import Patient
                
                patient_id = data.get('patient_id')
                if patient_id:
                    patient = db_session.query(Patient).get(patient_id)
                    if not patient:
                        errors.append("⚠️ المريض غير موجود في النظام")
            
            # التحقق من الصلاحيات
            if operation == 'delete_user':
                user_id = data.get('user_id')
                current_user_id = data.get('current_user_id')
                
                if user_id == current_user_id:
                    errors.append("⚠️ لا يمكنك حذف حسابك الخاص")
            
            # التحقق من حذف بيانات مرتبطة
            if operation == 'delete_patient':
                from models.visit import Visit
                
                patient_id = data.get('patient_id')
                visits_count = db_session.query(Visit).filter_by(patient_id=patient_id).count()
                
                if visits_count > 0:
                    warnings.append(f"هذا المريض لديه {visits_count} زيارة مسجلة وسيتم حذفها جميعاً")
            
        except Exception as e:
            logging.error(f"Validation error: {str(e)}")
            warnings.append("حدث خطأ أثناء التحقق ويرجى المراجعة اليدوية")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @staticmethod
    def format_validation_message(errors: List[str], warnings: List[str]) -> str:
        """تنسيق رسالة التحقق"""
        message = ""
        
        if errors:
            message += "أخطاء يجب تصحيحها:\n"
            for error in errors:
                message += f"خطأ: {error}\n"
            message += "\n"
        
        if warnings:
            message += "تحذيرات يمكن تجاوزها:\n"
            for warning in warnings:
                message += f"تحذير: {warning}\n"
            message += "\n"
        
        if errors:
            message += "لا يمكن حفظ البيانات حتى يتم تصحيح الأخطاء"
        elif warnings:
            message += "يمكنك المتابعة ولكن يفضل مراجعة التحذيرات"
        else:
            message += "جميع البيانات صحيحة"
        
        return message

