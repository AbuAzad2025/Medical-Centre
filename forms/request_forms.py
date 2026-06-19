"""
نماذج الطلبات - Request Forms
Medical System Request Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, DateTimeField, IntegerField, FloatField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from .base_forms import FormBase, SearchFormBase, MedicalEntityMixin, StatusMixin, PriorityMixin, DateRangeMixin

class LabRequestForm(FormBase, MedicalEntityMixin, StatusMixin, PriorityMixin):
    """نموذج طلب المختبر"""
    
    request_number = StringField('رقم الطلب', validators=[DataRequired(message='رقم الطلب مطلوب'), Length(max=50, message='رقم الطلب يجب أن يكون أقل من 50 حرف')])
    lab_test_id = SelectField('فحص المختبر', coerce=int, validators=[DataRequired(message='فحص المختبر مطلوب')])
    test_notes = TextAreaField('ملاحظات الفحص', validators=[Optional()])
    sample_type = SelectField('نوع العينة', choices=[
        ('blood', 'دم'),
        ('urine', 'بول'),
        ('stool', 'براز'),
        ('sputum', 'بلغم'),
        ('tissue', 'نسيج'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    sample_collected_at = DateTimeField('وقت جمع العينة', validators=[Optional()])
    assigned_to = SelectField('مُعيّن لـ', coerce=int, validators=[Optional()])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل فحوص المختبر
        from models.lab_request import LabRequest
        tests = LabRequest.query.filter_by(status='ACTIVE').all()
        self.lab_test_id.choices = [(t.id, f"{t.name_ar} - {t.name}") for t in tests]
        
        # تحميل فنيي المختبر
        from models.user import User
        technicians = User.query.filter(User.role.in_(['lab', 'admin', 'manager'])).all()
        self.assigned_to.choices = [('', 'اختر الفني')] + [(t.id, t.full_name) for t in technicians]

class LabRequestSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في طلبات المختبر"""
    
    request_number = StringField('رقم الطلب', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    lab_test_name = StringField('اسم الفحص', validators=[Optional()])
    priority = SelectField('الأولوية', choices=[
        ('', 'جميع الأولويات'),
        ('LOW', 'منخفضة'),
        ('NORMAL', 'عادية'),
        ('HIGH', 'عالية'),
        ('URGENT', 'عاجلة'),
        ('CRITICAL', 'حرجة')
    ], validators=[Optional()])
    assigned_to = SelectField('مُعيّن لـ', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل فنيي المختبر
        from models.user import User
        technicians = User.query.filter(User.role.in_(['lab', 'admin', 'manager'])).all()
        self.assigned_to.choices = [('', 'جميع الفنيين')] + [(t.id, t.full_name) for t in technicians]

class RadiologyRequestForm(FormBase, MedicalEntityMixin, StatusMixin, PriorityMixin):
    """نموذج طلب الأشعة"""
    
    request_number = StringField('رقم الطلب', validators=[DataRequired(message='رقم الطلب مطلوب'), Length(max=50, message='رقم الطلب يجب أن يكون أقل من 50 حرف')])
    radiology_test_id = SelectField('فحص الأشعة', coerce=int, validators=[DataRequired(message='فحص الأشعة مطلوب')])
    test_notes = TextAreaField('ملاحظات الفحص', validators=[Optional()])
    body_part = SelectField('جزء الجسم', choices=[
        ('head', 'الرأس'),
        ('chest', 'الصدر'),
        ('abdomen', 'البطن'),
        ('pelvis', 'الحوض'),
        ('spine', 'العمود الفقري'),
        ('limbs', 'الأطراف'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    contrast_required = BooleanField('يحتاج مادة تباين', default=False)
    images_taken_at = DateTimeField('وقت التقاط الصور', validators=[Optional()])
    assigned_to = SelectField('مُعيّن لـ', coerce=int, validators=[Optional()])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل فحوص الأشعة
        from models.radiology_result import RadiologyResult
        tests = RadiologyResult.query.filter_by(status='ACTIVE').all()
        self.radiology_test_id.choices = [(t.id, f"{t.name_ar} - {t.name}") for t in tests]
        
        # تحميل فنيي الأشعة
        from models.user import User
        technicians = User.query.filter(User.role.in_(['radiology', 'admin', 'manager'])).all()
        self.assigned_to.choices = [('', 'اختر الفني')] + [(t.id, t.full_name) for t in technicians]

class RadiologyRequestSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في طلبات الأشعة"""
    
    request_number = StringField('رقم الطلب', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    radiology_test_name = StringField('اسم الفحص', validators=[Optional()])
    priority = SelectField('الأولوية', choices=[
        ('', 'جميع الأولويات'),
        ('LOW', 'منخفضة'),
        ('NORMAL', 'عادية'),
        ('HIGH', 'عالية'),
        ('URGENT', 'عاجلة'),
        ('CRITICAL', 'حرجة')
    ], validators=[Optional()])
    assigned_to = SelectField('مُعيّن لـ', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل فنيي الأشعة
        from models.user import User
        technicians = User.query.filter(User.role.in_(['radiology', 'admin', 'manager'])).all()
        self.assigned_to.choices = [('', 'جميع الفنيين')] + [(t.id, t.full_name) for t in technicians]

class TriageForm(FormBase, MedicalEntityMixin):
    """نموذج فرز الطوارئ"""
    
    emergency_type = SelectField('نوع الطوارئ', choices=[
        ('trauma', 'إصابات'),
        ('cardiac', 'قلبية'),
        ('respiratory', 'تنفسية'),
        ('neurological', 'عصبية'),
        ('gastrointestinal', 'هضمية'),
        ('genitourinary', 'بولية تناسلية'),
        ('pediatric', 'أطفال'),
        ('psychiatric', 'نفسية'),
        ('other', 'أخرى')
    ], validators=[DataRequired(message='نوع الطوارئ مطلوب')])
    severity = SelectField('الخطورة', choices=[
        ('LOW', 'منخفضة'),
        ('MODERATE', 'متوسطة'),
        ('HIGH', 'عالية'),
        ('CRITICAL', 'حرجة')
    ], validators=[DataRequired(message='الخطورة مطلوبة')])
    chief_complaint = TextAreaField('الشكوى الرئيسية', validators=[DataRequired(message='الشكوى الرئيسية مطلوبة')])
    
    # العلامات الحيوية
    blood_pressure_systolic = IntegerField('ضغط الدم الانقباضي', validators=[Optional(), NumberRange(min=50, max=300, message='ضغط الدم الانقباضي يجب أن يكون بين 50 و 300')])
    blood_pressure_diastolic = IntegerField('ضغط الدم الانبساطي', validators=[Optional(), NumberRange(min=30, max=200, message='ضغط الدم الانبساطي يجب أن يكون بين 30 و 200')])
    heart_rate = IntegerField('معدل النبض', validators=[Optional(), NumberRange(min=30, max=300, message='معدل النبض يجب أن يكون بين 30 و 300')])
    respiratory_rate = IntegerField('معدل التنفس', validators=[Optional(), NumberRange(min=5, max=60, message='معدل التنفس يجب أن يكون بين 5 و 60')])
    temperature = FloatField('درجة الحرارة', validators=[Optional(), NumberRange(min=30, max=45, message='درجة الحرارة يجب أن تكون بين 30 و 45')])
    oxygen_saturation = IntegerField('تشبع الأكسجين (%)', validators=[Optional(), NumberRange(min=50, max=100, message='تشبع الأكسجين يجب أن يكون بين 50 و 100')])
    
    # تقييم إضافي
    pain_level = SelectField('مستوى الألم', choices=[
        ('0', '0 - لا يوجد ألم'),
        ('1', '1 - ألم خفيف'),
        ('2', '2 - ألم خفيف'),
        ('3', '3 - ألم خفيف'),
        ('4', '4 - ألم متوسط'),
        ('5', '5 - ألم متوسط'),
        ('6', '6 - ألم متوسط'),
        ('7', '7 - ألم شديد'),
        ('8', '8 - ألم شديد'),
        ('9', '9 - ألم شديد'),
        ('10', '10 - ألم لا يُحتمل')
    ], validators=[Optional()])
    consciousness_level = SelectField('مستوى الوعي', choices=[
        ('alert', 'واعي'),
        ('confused', 'مشوش'),
        ('drowsy', 'نعاس'),
        ('unconscious', 'فاقد الوعي')
    ], validators=[Optional()])
    
    triage_notes = TextAreaField('ملاحظات الفرز', validators=[Optional()])
    recommended_action = SelectField('الإجراء الموصى به', choices=[
        ('immediate', 'عاجل فوري'),
        ('urgent', 'عاجل'),
        ('priority', 'أولوية'),
        ('routine', 'عادي'),
        ('discharge', 'إخراج')
    ], validators=[DataRequired(message='الإجراء الموصى به مطلوب')])
    
    def validate_blood_pressure_systolic(self, field):
        """التحقق من ضغط الدم الانقباضي"""
        if field.data and self.blood_pressure_diastolic.data and field.data <= self.blood_pressure_diastolic.data:
            raise ValidationError('ضغط الدم الانقباضي يجب أن يكون أكبر من الانبساطي')

class QueueItemForm(FormBase, MedicalEntityMixin, StatusMixin, PriorityMixin):
    """نموذج إدارة عنصر الطابور"""
    
    queue_position = IntegerField('موضع الطابور', validators=[DataRequired(message='موضع الطابور مطلوب'), NumberRange(min=1, message='موضع الطابور يجب أن يكون أكبر من صفر')])
    estimated_wait_time = IntegerField('الوقت المتوقع للانتظار (دقيقة)', validators=[Optional(), NumberRange(min=0, message='الوقت المتوقع يجب أن يكون أكبر من أو يساوي صفر')])
    actual_wait_time = IntegerField('الوقت الفعلي للانتظار (دقيقة)', validators=[Optional(), NumberRange(min=0, message='الوقت الفعلي يجب أن يكون أكبر من أو يساوي صفر')])
    unit_name = SelectField('الوحدة', choices=[
        ('reception', 'الاستقبال'),
        ('doctor', 'الطبيب'),
        ('lab', 'المختبر'),
        ('radiology', 'الأشعة'),
        ('pharmacy', 'الصيدلية'),
        ('emergency', 'الطوارئ'),
        ('accounting', 'المحاسبة')
    ], validators=[DataRequired(message='الوحدة مطلوبة')])
    assigned_to = SelectField('مُعيّن لـ', coerce=int, validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المستخدمين حسب الدور
        from models.user import User
        users = User.query.filter(User.role.in_(['doctor', 'nurse', 'reception', 'lab', 'radiology', 'pharmacy', 'emergency', 'accountant', 'admin', 'manager'])).all()
        self.assigned_to.choices = [('', 'اختر المستخدم')] + [(u.id, f"{u.full_name} ({u.role})") for u in users]

class WorkflowStepForm(FormBase, StatusMixin):
    """نموذج خطوة الـ Workflow"""
    
    step_name = StringField('اسم الخطوة', validators=[DataRequired(message='اسم الخطوة مطلوب'), Length(max=100, message='اسم الخطوة يجب أن يكون أقل من 100 حرف')])
    step_order = IntegerField('ترتيب الخطوة', validators=[DataRequired(message='ترتيب الخطوة مطلوب'), NumberRange(min=1, message='ترتيب الخطوة يجب أن يكون أكبر من صفر')])
    description = TextAreaField('الوصف', validators=[Optional()])
    required_role = SelectField('الدور المطلوب', choices=[
        ('', 'اختر الدور'),
        ('reception', 'الاستقبال'),
        ('doctor', 'الطبيب'),
        ('nurse', 'الممرض'),
        ('lab', 'المختبر'),
        ('radiology', 'الأشعة'),
        ('pharmacy', 'الصيدلية'),
        ('emergency', 'الطوارئ'),
        ('accountant', 'المحاسب'),
        ('admin', 'المدير'),
        ('manager', 'المدير العام')
    ], validators=[Optional()])
    estimated_duration = IntegerField('المدة المتوقعة (دقيقة)', validators=[Optional(), NumberRange(min=1, message='المدة المتوقعة يجب أن تكون أكبر من صفر')])
    is_required = BooleanField('مطلوب', default=True)
    is_parallel = BooleanField('متوازي', default=False)
    workflow_type = SelectField('نوع الـ Workflow', choices=[
        ('patient_visit', 'زيارة المريض'),
        ('lab_request', 'طلب المختبر'),
        ('radiology_request', 'طلب الأشعة'),
        ('emergency_case', 'حالة طارئة'),
        ('payment_process', 'عملية الدفع'),
        ('appointment', 'موعد')
    ], validators=[DataRequired(message='نوع الـ Workflow مطلوب')])

class WorkflowTransferForm(FormBase, StatusMixin):
    """نموذج نقل الـ Workflow"""
    
    from_unit = SelectField('من الوحدة', choices=[
        ('reception', 'الاستقبال'),
        ('doctor', 'الطبيب'),
        ('lab', 'المختبر'),
        ('radiology', 'الأشعة'),
        ('pharmacy', 'الصيدلية'),
        ('emergency', 'الطوارئ'),
        ('accounting', 'المحاسبة')
    ], validators=[DataRequired(message='الوحدة المصدر مطلوبة')])
    to_unit = SelectField('إلى الوحدة', choices=[
        ('reception', 'الاستقبال'),
        ('doctor', 'الطبيب'),
        ('lab', 'المختبر'),
        ('radiology', 'الأشعة'),
        ('pharmacy', 'الصيدلية'),
        ('emergency', 'الطوارئ'),
        ('accounting', 'المحاسبة')
    ], validators=[DataRequired(message='الوحدة الهدف مطلوبة')])
    transfer_reason = TextAreaField('سبب النقل', validators=[DataRequired(message='سبب النقل مطلوب')])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional()])
    
    def validate_to_unit(self, field):
        """التحقق من الوحدة الهدف"""
        if field.data == self.from_unit.data:
            raise ValidationError('الوحدة الهدف يجب أن تكون مختلفة عن الوحدة المصدر')
