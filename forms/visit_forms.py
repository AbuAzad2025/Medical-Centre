"""
فورمز الزيارات - النظام الصحي المتكامل
Visit Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from datetime import date, datetime, time

class VisitForm(FlaskForm):
    """فورم إنشاء زيارة جديدة"""
    
    # معلومات المريض
    patient_id = SelectField('المريض', coerce=int, validators=[DataRequired()])
    
    # معلومات الطبيب
    doctor_id = SelectField('الطبيب', coerce=int, validators=[DataRequired()])
    
    # معلومات الزيارة
    visit_type = SelectField('نوع الزيارة', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('surgery', 'عملية جراحية'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    visit_date = DateField('تاريخ الزيارة', validators=[DataRequired()])
    visit_time = TimeField('وقت الزيارة', validators=[DataRequired()])
    
    # معلومات الحالة
    chief_complaint = TextAreaField('الشكوى الرئيسية', validators=[DataRequired(), Length(max=1000)])
    symptoms = TextAreaField('الأعراض', validators=[Optional(), Length(max=1000)])
    vital_signs = TextAreaField('العلامات الحيوية', validators=[Optional(), Length(max=500)])
    
    # معلومات التشخيص
    diagnosis = TextAreaField('التشخيص', validators=[Optional(), Length(max=1000)])
    treatment_plan = TextAreaField('خطة العلاج', validators=[Optional(), Length(max=1000)])
    medications_prescribed = TextAreaField('الأدوية الموصوفة', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    is_emergency = BooleanField('حالة طوارئ', default=False)
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    submit = SubmitField('إنشاء الزيارة')
    
    def validate_visit_date(self, field):
        """التحقق من تاريخ الزيارة"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ الزيارة لا يمكن أن يكون في الماضي')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and self.visit_date.data and field.data <= self.visit_date.data:
            raise ValidationError('تاريخ المتابعة يجب أن يكون بعد تاريخ الزيارة')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class VisitEditForm(FlaskForm):
    """فورم تعديل الزيارة"""
    
    # معلومات الزيارة
    visit_type = SelectField('نوع الزيارة', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('surgery', 'عملية جراحية'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    visit_date = DateField('تاريخ الزيارة', validators=[DataRequired()])
    visit_time = TimeField('وقت الزيارة', validators=[DataRequired()])
    
    # معلومات الحالة
    chief_complaint = TextAreaField('الشكوى الرئيسية', validators=[DataRequired(), Length(max=1000)])
    symptoms = TextAreaField('الأعراض', validators=[Optional(), Length(max=1000)])
    vital_signs = TextAreaField('العلامات الحيوية', validators=[Optional(), Length(max=500)])
    
    # معلومات التشخيص
    diagnosis = TextAreaField('التشخيص', validators=[Optional(), Length(max=1000)])
    treatment_plan = TextAreaField('خطة العلاج', validators=[Optional(), Length(max=1000)])
    medications_prescribed = TextAreaField('الأدوية الموصوفة', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    is_emergency = BooleanField('حالة طوارئ', default=False)
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الزيارة
    status = SelectField('حالة الزيارة', choices=[
        ('scheduled', 'مجدولة'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتملة'),
        ('cancelled', 'ملغية'),
        ('no_show', 'لم يحضر')
    ], validators=[DataRequired()])
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_visit_date(self, field):
        """التحقق من تاريخ الزيارة"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ الزيارة لا يمكن أن يكون في الماضي')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and self.visit_date.data and field.data <= self.visit_date.data:
            raise ValidationError('تاريخ المتابعة يجب أن يكون بعد تاريخ الزيارة')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class VisitSearchForm(FlaskForm):
    """فورم البحث عن الزيارات"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('patient_name', 'اسم المريض'),
        ('doctor_name', 'اسم الطبيب'),
        ('visit_id', 'رقم الزيارة'),
        ('diagnosis', 'التشخيص')
    ], validators=[DataRequired()])
    
    visit_type = SelectField('نوع الزيارة', choices=[
        ('', 'جميع الأنواع'),
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('emergency', 'طوارئ'),
        ('surgery', 'عملية جراحية'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    
    status = SelectField('حالة الزيارة', choices=[
        ('', 'جميع الحالات'),
        ('scheduled', 'مجدولة'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتملة'),
        ('cancelled', 'ملغية'),
        ('no_show', 'لم يحضر')
    ], validators=[Optional()])
    
    payment_status = SelectField('حالة الدفع', choices=[
        ('', 'جميع الحالات'),
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[Optional()])
    
    date_from = DateField('من تاريخ', validators=[Optional()])
    date_to = DateField('إلى تاريخ', validators=[Optional()])
    
    is_emergency = SelectField('حالة الطوارئ', choices=[
        ('', 'جميع الحالات'),
        ('true', 'طوارئ'),
        ('false', 'عادية')
    ], validators=[Optional()])
    
    submit = SubmitField('بحث')
    
    def validate_date_to(self, field):
        """التحقق من نطاق التاريخ"""
        if self.date_from.data and field.data and field.data < self.date_from.data:
            raise ValidationError('التاريخ "إلى" يجب أن يكون بعد التاريخ "من"')