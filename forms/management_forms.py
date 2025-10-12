"""
نماذج الإدارة والجدولة - Management Forms
Medical System Management Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, DateTimeField, IntegerField, FloatField, BooleanField, TimeField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from .base_forms import FormBase, SearchFormBase, MedicalEntityMixin, StatusMixin, DateRangeMixin

class DoctorScheduleForm(FormBase, StatusMixin):
    """نموذج جدولة الطبيب"""
    
    doctor_id = SelectField('الطبيب', coerce=int, validators=[DataRequired(message='الطبيب مطلوب')])
    schedule_date = DateField('تاريخ الجدولة', validators=[DataRequired(message='تاريخ الجدولة مطلوب')])
    start_time = TimeField('وقت البداية', validators=[DataRequired(message='وقت البداية مطلوب')])
    end_time = TimeField('وقت النهاية', validators=[DataRequired(message='وقت النهاية مطلوب')])
    max_patients = IntegerField('الحد الأقصى للمرضى', validators=[DataRequired(message='الحد الأقصى للمرضى مطلوب'), NumberRange(min=1, message='الحد الأقصى للمرضى يجب أن يكون أكبر من صفر')])
    appointment_duration = IntegerField('مدة الموعد (دقيقة)', validators=[DataRequired(message='مدة الموعد مطلوبة'), NumberRange(min=5, message='مدة الموعد يجب أن تكون 5 دقائق على الأقل')])
    break_duration = IntegerField('مدة الاستراحة (دقيقة)', validators=[Optional(), NumberRange(min=0, message='مدة الاستراحة يجب أن تكون أكبر من أو تساوي صفر')])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الأطباء
        from models.user import User
        doctors = User.query.filter(User.role.in_(['doctor', 'admin', 'manager'])).all()
        self.doctor_id.choices = [(d.id, d.full_name) for d in doctors]
    
    def validate_end_time(self, field):
        """التحقق من وقت النهاية"""
        if field.data and self.start_time.data and field.data <= self.start_time.data:
            raise ValidationError('وقت النهاية يجب أن يكون بعد وقت البداية')

class AvailabilityExceptionForm(FormBase, StatusMixin):
    """نموذج استثناءات التوفر"""
    
    doctor_id = SelectField('الطبيب', coerce=int, validators=[DataRequired(message='الطبيب مطلوب')])
    exception_type = SelectField('نوع الاستثناء', choices=[
        ('unavailable', 'غير متوفر'),
        ('limited', 'متوفر محدود'),
        ('emergency_only', 'طوارئ فقط'),
        ('consultation_only', 'استشارة فقط')
    ], validators=[DataRequired(message='نوع الاستثناء مطلوب')])
    start_datetime = DateTimeField('وقت البداية', validators=[DataRequired(message='وقت البداية مطلوب')])
    end_datetime = DateTimeField('وقت النهاية', validators=[DataRequired(message='وقت النهاية مطلوب')])
    reason = TextAreaField('السبب', validators=[DataRequired(message='السبب مطلوب')])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الأطباء
        from models.user import User
        doctors = User.query.filter(User.role.in_(['doctor', 'admin', 'manager'])).all()
        self.doctor_id.choices = [(d.id, d.full_name) for d in doctors]
    
    def validate_end_datetime(self, field):
        """التحقق من وقت النهاية"""
        if field.data and self.start_datetime.data and field.data <= self.start_datetime.data:
            raise ValidationError('وقت النهاية يجب أن يكون بعد وقت البداية')

class OnlineBookingForm(FormBase, MedicalEntityMixin):
    """نموذج الحجز الإلكتروني"""
    
    appointment_date = DateField('تاريخ الموعد', validators=[DataRequired(message='تاريخ الموعد مطلوب')])
    appointment_time = TimeField('وقت الموعد', validators=[DataRequired(message='وقت الموعد مطلوب')])
    appointment_type = SelectField('نوع الموعد', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('routine', 'عادي')
    ], validators=[DataRequired(message='نوع الموعد مطلوب')])
    reason = TextAreaField('سبب الزيارة', validators=[DataRequired(message='سبب الزيارة مطلوب')])
    preferred_doctor = SelectField('الطبيب المفضل', coerce=int, validators=[Optional()])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    insurance_number = StringField('رقم التأمين', validators=[Optional(), Length(max=50, message='رقم التأمين يجب أن يكون أقل من 50 حرف')])
    contact_phone = StringField('رقم الهاتف للتواصل', validators=[DataRequired(message='رقم الهاتف مطلوب'), Length(max=20, message='رقم الهاتف يجب أن يكون أقل من 20 رقم')])
    contact_email = StringField('البريد الإلكتروني', validators=[Optional(), Length(max=120, message='البريد الإلكتروني يجب أن يكون أقل من 120 حرف')])
    special_requirements = TextAreaField('متطلبات خاصة', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الأطباء
        from models.user import User
        doctors = User.query.filter(User.role.in_(['doctor', 'admin', 'manager'])).all()
        self.preferred_doctor.choices = [('', 'اختر الطبيب')] + [(d.id, d.full_name) for d in doctors]
        
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [('', 'اختر شركة التأمين')] + [(c.id, c.name) for c in companies]

class MedicalRecordForm(FormBase, MedicalEntityMixin, StatusMixin):
    """نموذج السجل الطبي (SOAP)"""
    
    record_type = SelectField('نوع السجل', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('surgery', 'عملية'),
        ('procedure', 'إجراء')
    ], validators=[DataRequired(message='نوع السجل مطلوب')])
    
    # SOAP Format
    subjective = TextAreaField('الذاتي (Subjective)', validators=[DataRequired(message='الذاتي مطلوب')])
    objective = TextAreaField('الموضوعي (Objective)', validators=[DataRequired(message='الموضوعي مطلوب')])
    assessment = TextAreaField('التقييم (Assessment)', validators=[DataRequired(message='التقييم مطلوب')])
    plan = TextAreaField('الخطة (Plan)', validators=[DataRequired(message='الخطة مطلوبة')])
    
    # معلومات إضافية
    diagnosis = TextAreaField('التشخيص', validators=[Optional()])
    treatment_plan = TextAreaField('خطة العلاج', validators=[Optional()])
    follow_up_required = BooleanField('يحتاج متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and self.follow_up_required.data and field.data <= date.today():
            raise ValidationError('تاريخ المتابعة يجب أن يكون في المستقبل')

class PrescriptionForm(FormBase, MedicalEntityMixin, StatusMixin):
    """نموذج الوصفة الطبية"""
    
    prescription_number = StringField('رقم الوصفة', validators=[DataRequired(message='رقم الوصفة مطلوب'), Length(max=50, message='رقم الوصفة يجب أن يكون أقل من 50 حرف')])
    prescription_date = DateField('تاريخ الوصفة', validators=[DataRequired(message='تاريخ الوصفة مطلوب')])
    diagnosis = TextAreaField('التشخيص', validators=[DataRequired(message='التشخيص مطلوب')])
    instructions = TextAreaField('التعليمات', validators=[DataRequired(message='التعليمات مطلوبة')])
    duration = IntegerField('مدة العلاج (أيام)', validators=[DataRequired(message='مدة العلاج مطلوبة'), NumberRange(min=1, message='مدة العلاج يجب أن تكون أكبر من صفر')])
    refill_allowed = BooleanField('يُسمح بإعادة الصرف', default=False)
    refill_count = IntegerField('عدد المرات المسموح بها', validators=[Optional(), NumberRange(min=0, message='عدد المرات يجب أن يكون أكبر من أو يساوي صفر')])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def validate_refill_count(self, field):
        """التحقق من عدد المرات المسموح بها"""
        if field.data and self.refill_allowed.data and field.data == 0:
            raise ValidationError('إذا كان يُسمح بإعادة الصرف، يجب تحديد عدد المرات')

class PrescriptionItemForm(FormBase):
    """نموذج عنصر الوصفة الطبية"""
    
    prescription_id = SelectField('الوصفة الطبية', coerce=int, validators=[DataRequired(message='الوصفة الطبية مطلوبة')])
    medication_name = StringField('اسم الدواء', validators=[DataRequired(message='اسم الدواء مطلوب'), Length(max=200, message='اسم الدواء يجب أن يكون أقل من 200 حرف')])
    dosage = StringField('الجرعة', validators=[DataRequired(message='الجرعة مطلوبة'), Length(max=100, message='الجرعة يجب أن تكون أقل من 100 حرف')])
    frequency = StringField('التكرار', validators=[DataRequired(message='التكرار مطلوب'), Length(max=100, message='التكرار يجب أن يكون أقل من 100 حرف')])
    quantity = IntegerField('الكمية', validators=[DataRequired(message='الكمية مطلوبة'), NumberRange(min=1, message='الكمية يجب أن تكون أكبر من صفر')])
    instructions = TextAreaField('تعليمات الاستخدام', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الوصفات الطبية
        from models.medication import Prescription
        prescriptions = Prescription.query.filter_by(status='ACTIVE').all()
        self.prescription_id.choices = [(p.id, f"وصفة {p.prescription_number} - {p.patient.full_name}") for p in prescriptions]

class FollowUpPlanForm(FormBase, MedicalEntityMixin, StatusMixin):
    """نموذج خطة المتابعة"""
    
    plan_name = StringField('اسم الخطة', validators=[DataRequired(message='اسم الخطة مطلوب'), Length(max=200, message='اسم الخطة يجب أن يكون أقل من 200 حرف')])
    plan_type = SelectField('نوع الخطة', choices=[
        ('medication', 'دوائية'),
        ('therapy', 'علاجية'),
        ('lifestyle', 'نمط الحياة'),
        ('monitoring', 'مراقبة'),
        ('surgery', 'جراحية'),
        ('other', 'أخرى')
    ], validators=[DataRequired(message='نوع الخطة مطلوب')])
    start_date = DateField('تاريخ البداية', validators=[DataRequired(message='تاريخ البداية مطلوب')])
    end_date = DateField('تاريخ النهاية', validators=[Optional()])
    frequency = SelectField('التكرار', choices=[
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('quarterly', 'ربع سنوي'),
        ('yearly', 'سنوي'),
        ('as_needed', 'حسب الحاجة')
    ], validators=[DataRequired(message='التكرار مطلوب')])
    description = TextAreaField('الوصف', validators=[DataRequired(message='الوصف مطلوب')])
    goals = TextAreaField('الأهداف', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def validate_end_date(self, field):
        """التحقق من تاريخ النهاية"""
        if field.data and self.start_date.data and field.data <= self.start_date.data:
            raise ValidationError('تاريخ النهاية يجب أن يكون بعد تاريخ البداية')

class MedicalRecordSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في السجلات الطبية"""
    
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    record_type = SelectField('نوع السجل', choices=[
        ('', 'جميع الأنواع'),
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('surgery', 'عملية'),
        ('procedure', 'إجراء')
    ], validators=[Optional()])
    diagnosis = StringField('التشخيص', validators=[Optional()])

class PrescriptionSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في الوصفات الطبية"""
    
    prescription_number = StringField('رقم الوصفة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    medication_name = StringField('اسم الدواء', validators=[Optional()])
    diagnosis = StringField('التشخيص', validators=[Optional()])

class FollowUpPlanSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في خطط المتابعة"""
    
    plan_name = StringField('اسم الخطة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    plan_type = SelectField('نوع الخطة', choices=[
        ('', 'جميع الأنواع'),
        ('medication', 'دوائية'),
        ('therapy', 'علاجية'),
        ('lifestyle', 'نمط الحياة'),
        ('monitoring', 'مراقبة'),
        ('surgery', 'جراحية'),
        ('other', 'أخرى')
    ], validators=[Optional()])
