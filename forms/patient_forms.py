"""
فورمز المرضى - النظام الصحي المتكامل
Patient Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, ValidationError
from datetime import date, datetime

class PatientRegistrationForm(FlaskForm):
    """فورم تسجيل مريض جديد"""
    
    # المعلومات الشخصية
    first_name = StringField('الاسم الأول', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('الاسم الأخير', validators=[DataRequired(), Length(min=2, max=50)])
    middle_name = StringField('الاسم الأوسط', validators=[Optional(), Length(max=50)])
    
    # معلومات الهوية
    national_id = StringField('رقم الهوية', validators=[DataRequired(), Length(min=9, max=20)])
    passport_number = StringField('رقم جواز السفر', validators=[Optional(), Length(max=20)])
    
    # معلومات الاتصال
    phone = StringField('رقم الهاتف', validators=[DataRequired(), Length(min=10, max=15)])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    address = TextAreaField('العنوان', validators=[DataRequired(), Length(max=500)])
    
    # المعلومات الطبية
    date_of_birth = DateField('تاريخ الميلاد', validators=[DataRequired()])
    gender = SelectField('الجنس', choices=[
        ('male', 'ذكر'),
        ('female', 'أنثى')
    ], validators=[DataRequired()])
    
    blood_type = SelectField('فصيلة الدم', choices=[
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-')
    ], validators=[Optional()])
    
    # معلومات الطوارئ
    emergency_contact_name = StringField('اسم جهة الاتصال في الطوارئ', validators=[DataRequired(), Length(max=100)])
    emergency_contact_phone = StringField('رقم جهة الاتصال في الطوارئ', validators=[DataRequired(), Length(min=10, max=15)])
    emergency_contact_relation = SelectField('صلة القرابة', choices=[
        ('parent', 'والد/والدة'),
        ('spouse', 'زوج/زوجة'),
        ('sibling', 'أخ/أخت'),
        ('child', 'ابن/ابنة'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات التأمين
    insurance_company = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    insurance_number = StringField('رقم التأمين', validators=[Optional(), Length(max=50)])
    insurance_expiry = DateField('انتهاء التأمين', validators=[Optional()])
    
    # معلومات إضافية
    medical_history = TextAreaField('التاريخ المرضي', validators=[Optional(), Length(max=1000)])
    allergies = TextAreaField('الحساسية', validators=[Optional(), Length(max=500)])
    current_medications = TextAreaField('الأدوية الحالية', validators=[Optional(), Length(max=500)])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة المريض
    is_active = BooleanField('نشط', default=True)
    
    submit = SubmitField('تسجيل المريض')
    
    def validate_date_of_birth(self, field):
        """التحقق من تاريخ الميلاد"""
        if field.data and field.data > date.today():
            raise ValidationError('تاريخ الميلاد لا يمكن أن يكون في المستقبل')
        
        # التحقق من العمر (أقل من 150 سنة)
        age = (date.today() - field.data).days // 365
        if age > 150:
            raise ValidationError('العمر غير منطقي')
    
    def validate_insurance_expiry(self, field):
        """التحقق من انتهاء التأمين"""
        if field.data and field.data < date.today():
            raise ValidationError('التأمين منتهي الصلاحية')

class PatientEditForm(FlaskForm):
    """فورم تعديل بيانات المريض"""
    
    # المعلومات الشخصية
    first_name = StringField('الاسم الأول', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('الاسم الأخير', validators=[DataRequired(), Length(min=2, max=50)])
    middle_name = StringField('الاسم الأوسط', validators=[Optional(), Length(max=50)])
    
    # معلومات الهوية
    national_id = StringField('رقم الهوية', validators=[DataRequired(), Length(min=9, max=20)])
    passport_number = StringField('رقم جواز السفر', validators=[Optional(), Length(max=20)])
    
    # معلومات الاتصال
    phone = StringField('رقم الهاتف', validators=[DataRequired(), Length(min=10, max=15)])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Email()])
    address = TextAreaField('العنوان', validators=[DataRequired(), Length(max=500)])
    
    # المعلومات الطبية
    date_of_birth = DateField('تاريخ الميلاد', validators=[DataRequired()])
    gender = SelectField('الجنس', choices=[
        ('male', 'ذكر'),
        ('female', 'أنثى')
    ], validators=[DataRequired()])
    
    blood_type = SelectField('فصيلة الدم', choices=[
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-')
    ], validators=[Optional()])
    
    # معلومات الطوارئ
    emergency_contact_name = StringField('اسم جهة الاتصال في الطوارئ', validators=[DataRequired(), Length(max=100)])
    emergency_contact_phone = StringField('رقم جهة الاتصال في الطوارئ', validators=[DataRequired(), Length(min=10, max=15)])
    emergency_contact_relation = SelectField('صلة القرابة', choices=[
        ('parent', 'والد/والدة'),
        ('spouse', 'زوج/زوجة'),
        ('sibling', 'أخ/أخت'),
        ('child', 'ابن/ابنة'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات التأمين
    insurance_company = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    insurance_number = StringField('رقم التأمين', validators=[Optional(), Length(max=50)])
    insurance_expiry = DateField('انتهاء التأمين', validators=[Optional()])
    
    # معلومات إضافية
    medical_history = TextAreaField('التاريخ المرضي', validators=[Optional(), Length(max=1000)])
    allergies = TextAreaField('الحساسية', validators=[Optional(), Length(max=500)])
    current_medications = TextAreaField('الأدوية الحالية', validators=[Optional(), Length(max=500)])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة المريض
    is_active = BooleanField('نشط', default=True)
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_date_of_birth(self, field):
        """التحقق من تاريخ الميلاد"""
        if field.data and field.data > date.today():
            raise ValidationError('تاريخ الميلاد لا يمكن أن يكون في المستقبل')
        
        # التحقق من العمر (أقل من 150 سنة)
        age = (date.today() - field.data).days // 365
        if age > 150:
            raise ValidationError('العمر غير منطقي')
    
    def validate_insurance_expiry(self, field):
        """التحقق من انتهاء التأمين"""
        if field.data and field.data < date.today():
            raise ValidationError('التأمين منتهي الصلاحية')

class PatientSearchForm(FlaskForm):
    """فورم البحث عن المرضى"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('name', 'الاسم'),
        ('national_id', 'رقم الهوية'),
        ('phone', 'رقم الهاتف'),
        ('insurance', 'رقم التأمين')
    ], validators=[DataRequired()])
    
    gender = SelectField('الجنس', choices=[
        ('', 'جميع الأجناس'),
        ('male', 'ذكر'),
        ('female', 'أنثى')
    ], validators=[Optional()])
    
    blood_type = SelectField('فصيلة الدم', choices=[
        ('', 'جميع الفصائل'),
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-')
    ], validators=[Optional()])
    
    age_from = IntegerField('العمر من', validators=[Optional(), NumberRange(min=0, max=150)])
    age_to = IntegerField('العمر إلى', validators=[Optional(), NumberRange(min=0, max=150)])
    
    is_active = SelectField('الحالة', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نشط'),
        ('false', 'غير نشط')
    ], validators=[Optional()])
    
    submit = SubmitField('بحث')
    
    def validate_age_to(self, field):
        """التحقق من نطاق العمر"""
        if self.age_from.data and field.data and field.data < self.age_from.data:
            raise ValidationError('العمر "إلى" يجب أن يكون أكبر من العمر "من"')