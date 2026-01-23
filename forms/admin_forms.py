"""
فورمز الإدارة - النظام الصحي المتكامل
Admin Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField, PasswordField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, Email, ValidationError
from datetime import date, datetime

class DepartmentForm(FlaskForm):
    """فورم إدارة الأقسام"""
    
    # معلومات القسم الأساسية
    name = StringField('اسم القسم', validators=[DataRequired(), Length(min=2, max=100)])
    name_ar = StringField('اسم القسم بالعربية', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('كود القسم', validators=[DataRequired(), Length(min=2, max=20)])
    
    # معلومات القسم
    description = TextAreaField('وصف القسم', validators=[Optional(), Length(max=1000)])
    location = StringField('موقع القسم', validators=[Optional(), Length(max=200)])
    floor = IntegerField('الطابق', validators=[Optional(), NumberRange(min=-5, max=50)])
    room_number = StringField('رقم الغرفة', validators=[Optional(), Length(max=20)])
    
    # معلومات الإدارة
    head_doctor_id = SelectField('رئيس القسم', coerce=int, validators=[Optional()])
    manager_id = SelectField('مدير القسم', coerce=int, validators=[Optional()])
    
    # معلومات السعة
    capacity = IntegerField('السعة', validators=[Optional(), NumberRange(min=1, max=1000)])
    current_patients = IntegerField('المرضى الحاليين', validators=[Optional(), NumberRange(min=0, max=1000)])
    
    # معلومات الاتصال
    phone = StringField('رقم الهاتف', validators=[Optional(), Length(max=20)])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    
    # معلومات إضافية
    is_active = BooleanField('نشط', default=True)
    is_emergency = BooleanField('قسم طوارئ', default=False)
    requires_appointment = BooleanField('يتطلب موعد', default=True)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ القسم')
    
    def validate_current_patients(self, field):
        """التحقق من عدد المرضى الحاليين"""
        if field.data and self.capacity.data and field.data > self.capacity.data:
            raise ValidationError('عدد المرضى الحاليين لا يمكن أن يكون أكبر من السعة')

class DepartmentEditForm(FlaskForm):
    """فورم تعديل القسم"""
    
    # معلومات القسم الأساسية
    name = StringField('اسم القسم', validators=[DataRequired(), Length(min=2, max=100)])
    name_ar = StringField('اسم القسم بالعربية', validators=[DataRequired(), Length(min=2, max=100)])
    code = StringField('كود القسم', validators=[DataRequired(), Length(min=2, max=20)])
    
    # معلومات القسم
    description = TextAreaField('وصف القسم', validators=[Optional(), Length(max=1000)])
    location = StringField('موقع القسم', validators=[Optional(), Length(max=200)])
    floor = IntegerField('الطابق', validators=[Optional(), NumberRange(min=-5, max=50)])
    room_number = StringField('رقم الغرفة', validators=[Optional(), Length(max=20)])
    
    # معلومات الإدارة
    head_doctor_id = SelectField('رئيس القسم', coerce=int, validators=[Optional()])
    manager_id = SelectField('مدير القسم', coerce=int, validators=[Optional()])
    
    # معلومات السعة
    capacity = IntegerField('السعة', validators=[Optional(), NumberRange(min=1, max=1000)])
    current_patients = IntegerField('المرضى الحاليين', validators=[Optional(), NumberRange(min=0, max=1000)])
    
    # معلومات الاتصال
    phone = StringField('رقم الهاتف', validators=[Optional(), Length(max=20)])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    
    # معلومات إضافية
    is_active = BooleanField('نشط', default=True)
    is_emergency = BooleanField('قسم طوارئ', default=False)
    requires_appointment = BooleanField('يتطلب موعد', default=True)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_current_patients(self, field):
        """التحقق من عدد المرضى الحاليين"""
        if field.data and self.capacity.data and field.data > self.capacity.data:
            raise ValidationError('عدد المرضى الحاليين لا يمكن أن يكون أكبر من السعة')

class UserForm(FlaskForm):
    """فورم إدارة المستخدمين"""
    
    # المعلومات الشخصية
    first_name = StringField('الاسم الأول', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('الاسم الأخير', validators=[DataRequired(), Length(min=2, max=50)])
    middle_name = StringField('الاسم الأوسط', validators=[Optional(), Length(max=50)])
    
    # معلومات الهوية
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    phone = StringField('رقم الهاتف', validators=[Optional(), Length(max=20)])
    doctor_room = StringField('غرفة الطبيب', validators=[Optional(), Length(max=50)])
    
    # معلومات المهنة
    role = SelectField('الدور', choices=[
        ('admin', 'مدير النظام'),
        ('manager', 'مدير المركز'),
        ('doctor', 'طبيب'),
        ('nurse', 'ممرض'),
        ('reception', 'استقبال'),
        ('lab', 'مختبر'),
        ('radiology', 'أشعة'),
        ('emergency', 'طوارئ'),
        ('accountant', 'محاسب')
    ], validators=[DataRequired()])
    
    department_id = SelectField('القسم', coerce=int, validators=[Optional()])
    specialization = StringField('التخصص', validators=[Optional(), Length(max=100)])
    professional_number = StringField('الرقم المهني', validators=[Optional(), Length(max=50)])
    
    # معلومات الراتب
    salary = DecimalField('الراتب', validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات الصلاحيات
    can_manage_patients = BooleanField('إدارة المرضى', default=False)
    can_manage_appointments = BooleanField('إدارة المواعيد', default=False)
    can_manage_visits = BooleanField('إدارة الزيارات', default=False)
    can_manage_medications = BooleanField('إدارة الأدوية', default=False)
    can_manage_emergency = BooleanField('إدارة الطوارئ', default=False)
    can_view_reports = BooleanField('عرض التقارير', default=False)
    
    # معلومات الحساب
    is_active = BooleanField('نشط', default=True)
    is_verified = BooleanField('متحقق', default=False)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ المستخدم')

class UserEditForm(FlaskForm):
    """فورم تعديل المستخدم"""
    
    # المعلومات الشخصية
    first_name = StringField('الاسم الأول', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('الاسم الأخير', validators=[DataRequired(), Length(min=2, max=50)])
    middle_name = StringField('الاسم الأوسط', validators=[Optional(), Length(max=50)])
    
    # معلومات الهوية
    username = StringField('اسم المستخدم', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('البريد الإلكتروني', validators=[DataRequired(), Email()])
    phone = StringField('رقم الهاتف', validators=[Optional(), Length(max=20)])
    doctor_room = StringField('غرفة الطبيب', validators=[Optional(), Length(max=50)])
    
    # معلومات المهنة
    role = SelectField('الدور', choices=[
        ('admin', 'مدير النظام'),
        ('manager', 'مدير المركز'),
        ('doctor', 'طبيب'),
        ('nurse', 'ممرض'),
        ('reception', 'استقبال'),
        ('lab', 'مختبر'),
        ('radiology', 'أشعة'),
        ('emergency', 'طوارئ'),
        ('accountant', 'محاسب')
    ], validators=[DataRequired()])
    
    department_id = SelectField('القسم', coerce=int, validators=[Optional()])
    specialization = StringField('التخصص', validators=[Optional(), Length(max=100)])
    professional_number = StringField('الرقم المهني', validators=[Optional(), Length(max=50)])
    
    # معلومات الراتب
    salary = DecimalField('الراتب', validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات الصلاحيات
    can_manage_patients = BooleanField('إدارة المرضى', default=False)
    can_manage_appointments = BooleanField('إدارة المواعيد', default=False)
    can_manage_visits = BooleanField('إدارة الزيارات', default=False)
    can_manage_medications = BooleanField('إدارة الأدوية', default=False)
    can_manage_emergency = BooleanField('إدارة الطوارئ', default=False)
    can_view_reports = BooleanField('عرض التقارير', default=False)
    
    # معلومات الحساب
    is_active = BooleanField('نشط', default=True)
    is_verified = BooleanField('متحقق', default=False)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ التعديلات')

class PasswordResetForm(FlaskForm):
    """فورم إعادة تعيين كلمة المرور"""
    
    new_password = PasswordField('كلمة المرور الجديدة', validators=[DataRequired(), Length(min=6, max=100)])
    confirm_password = PasswordField('تأكيد كلمة المرور', validators=[DataRequired()])
    
    submit = SubmitField('تحديث كلمة المرور')
    
    def validate_confirm_password(self, field):
        """التحقق من تطابق كلمة المرور"""
        if field.data != self.new_password.data:
            raise ValidationError('كلمة المرور غير متطابقة')

class SystemSettingsForm(FlaskForm):
    """فورم إعدادات النظام"""
    
    # معلومات النظام
    system_name = StringField('اسم النظام', validators=[DataRequired(), Length(max=100)])
    system_name_ar = StringField('اسم النظام بالعربية', validators=[DataRequired(), Length(max=100)])
    system_version = StringField('إصدار النظام', validators=[Optional(), Length(max=20)])
    
    # معلومات الاتصال
    contact_email = StringField('البريد الإلكتروني للاتصال', validators=[Optional(), Email()])
    contact_phone = StringField('رقم الهاتف للاتصال', validators=[Optional(), Length(max=20)])
    contact_address = TextAreaField('عنوان الاتصال', validators=[Optional(), Length(max=500)])
    
    # معلومات العملة
    default_currency = SelectField('العملة الافتراضية', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات الوقت
    timezone = StringField('المنطقة الزمنية', validators=[Optional(), Length(max=50)])
    date_format = SelectField('تنسيق التاريخ', choices=[
        ('DD/MM/YYYY', 'يوم/شهر/سنة'),
        ('MM/DD/YYYY', 'شهر/يوم/سنة'),
        ('YYYY-MM-DD', 'سنة-شهر-يوم')
    ], validators=[DataRequired()])
    
    # معلومات النظام
    max_patients_per_day = IntegerField('الحد الأقصى للمرضى يومياً', validators=[Optional(), NumberRange(min=1, max=10000)])
    max_appointments_per_doctor = IntegerField('الحد الأقصى للمواعيد لكل طبيب', validators=[Optional(), NumberRange(min=1, max=1000)])
    
    # معلومات النسخ الاحتياطي
    backup_enabled = BooleanField('تفعيل النسخ الاحتياطي', default=True)
    backup_frequency = SelectField('تكرار النسخ الاحتياطي', choices=[
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري')
    ], validators=[DataRequired()])
    
    # معلومات الأمان
    session_timeout = IntegerField('مهلة الجلسة (دقيقة)', validators=[Optional(), NumberRange(min=5, max=1440)])
    password_expiry_days = IntegerField('انتهاء كلمة المرور (يوم)', validators=[Optional(), NumberRange(min=0, max=365)])
    max_login_attempts = IntegerField('الحد الأقصى لمحاولات تسجيل الدخول', validators=[Optional(), NumberRange(min=3, max=10)])
    
    # معلومات إضافية
    maintenance_mode = BooleanField('وضع الصيانة', default=False)
    debug_mode = BooleanField('وضع التطوير', default=False)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ الإعدادات')
