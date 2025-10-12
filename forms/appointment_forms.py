"""
فورمز المواعيد - النظام الصحي المتكامل
Appointment Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from datetime import date, datetime, time

class AppointmentForm(FlaskForm):
    """فورم إنشاء موعد جديد"""
    
    # معلومات المريض
    patient_id = SelectField('المريض', coerce=int, validators=[DataRequired()])
    
    # معلومات الطبيب
    doctor_id = SelectField('الطبيب', coerce=int, validators=[DataRequired()])
    
    # معلومات الموعد
    appointment_type = SelectField('نوع الموعد', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('surgery', 'عملية جراحية'),
        ('emergency', 'طوارئ'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    appointment_date = DateField('تاريخ الموعد', validators=[DataRequired()])
    appointment_time = TimeField('وقت الموعد', validators=[DataRequired()])
    duration = IntegerField('مدة الموعد (دقيقة)', validators=[Optional(), NumberRange(min=15, max=480)])
    
    # معلومات الحالة
    reason = TextAreaField('سبب الموعد', validators=[DataRequired(), Length(max=1000)])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الموعد
    status = SelectField('حالة الموعد', choices=[
        ('scheduled', 'مجدول'),
        ('confirmed', 'مؤكد'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
        ('no_show', 'لم يحضر')
    ], validators=[DataRequired()])
    
    # معلومات إضافية
    is_urgent = BooleanField('عاجل', default=False)
    is_recurring = BooleanField('متكرر', default=False)
    recurrence_pattern = SelectField('نمط التكرار', choices=[
        ('', 'لا يوجد تكرار'),
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('yearly', 'سنوي')
    ], validators=[Optional()])
    
    submit = SubmitField('إنشاء الموعد')
    
    def validate_appointment_date(self, field):
        """التحقق من تاريخ الموعد"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ الموعد لا يمكن أن يكون في الماضي')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and self.appointment_date.data and field.data <= self.appointment_date.data:
            raise ValidationError('تاريخ المتابعة يجب أن يكون بعد تاريخ الموعد')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class AppointmentEditForm(FlaskForm):
    """فورم تعديل الموعد"""
    
    # معلومات الموعد
    appointment_type = SelectField('نوع الموعد', choices=[
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('surgery', 'عملية جراحية'),
        ('emergency', 'طوارئ'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    appointment_date = DateField('تاريخ الموعد', validators=[DataRequired()])
    appointment_time = TimeField('وقت الموعد', validators=[DataRequired()])
    duration = IntegerField('مدة الموعد (دقيقة)', validators=[Optional(), NumberRange(min=15, max=480)])
    
    # معلومات الحالة
    reason = TextAreaField('سبب الموعد', validators=[DataRequired(), Length(max=1000)])
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الموعد
    status = SelectField('حالة الموعد', choices=[
        ('scheduled', 'مجدول'),
        ('confirmed', 'مؤكد'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
        ('no_show', 'لم يحضر')
    ], validators=[DataRequired()])
    
    # معلومات إضافية
    is_urgent = BooleanField('عاجل', default=False)
    is_recurring = BooleanField('متكرر', default=False)
    recurrence_pattern = SelectField('نمط التكرار', choices=[
        ('', 'لا يوجد تكرار'),
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('yearly', 'سنوي')
    ], validators=[Optional()])
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_appointment_date(self, field):
        """التحقق من تاريخ الموعد"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ الموعد لا يمكن أن يكون في الماضي')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and self.appointment_date.data and field.data <= self.appointment_date.data:
            raise ValidationError('تاريخ المتابعة يجب أن يكون بعد تاريخ الموعد')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class AppointmentSearchForm(FlaskForm):
    """فورم البحث عن المواعيد"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('patient_name', 'اسم المريض'),
        ('doctor_name', 'اسم الطبيب'),
        ('appointment_id', 'رقم الموعد'),
        ('reason', 'سبب الموعد')
    ], validators=[DataRequired()])
    
    appointment_type = SelectField('نوع الموعد', choices=[
        ('', 'جميع الأنواع'),
        ('consultation', 'استشارة'),
        ('follow_up', 'متابعة'),
        ('checkup', 'فحص دوري'),
        ('vaccination', 'تطعيم'),
        ('surgery', 'عملية جراحية'),
        ('emergency', 'طوارئ'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    
    status = SelectField('حالة الموعد', choices=[
        ('', 'جميع الحالات'),
        ('scheduled', 'مجدول'),
        ('confirmed', 'مؤكد'),
        ('in_progress', 'قيد التنفيذ'),
        ('completed', 'مكتمل'),
        ('cancelled', 'ملغي'),
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
    
    is_urgent = SelectField('عاجل', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نعم'),
        ('false', 'لا')
    ], validators=[Optional()])
    
    submit = SubmitField('بحث')
    
    def validate_date_to(self, field):
        """التحقق من نطاق التاريخ"""
        if self.date_from.data and field.data and field.data < self.date_from.data:
            raise ValidationError('التاريخ "إلى" يجب أن يكون بعد التاريخ "من"')