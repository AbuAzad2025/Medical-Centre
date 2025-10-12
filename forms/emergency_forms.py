"""
فورمز الطوارئ - النظام الصحي المتكامل
Emergency Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, TimeField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError
from datetime import date, datetime, time

class EmergencyForm(FlaskForm):
    """فورم إنشاء حالة طوارئ جديدة"""
    
    # معلومات المريض
    patient_id = SelectField('المريض', coerce=int, validators=[DataRequired()])
    
    # معلومات الطوارئ
    emergency_type = SelectField('نوع الطوارئ', choices=[
        ('trauma', 'إصابة'),
        ('cardiac', 'قلبي'),
        ('respiratory', 'تنفسي'),
        ('neurological', 'عصبي'),
        ('gastrointestinal', 'هضمي'),
        ('obstetric', 'ولادة'),
        ('pediatric', 'أطفال'),
        ('psychiatric', 'نفسي'),
        ('toxicological', 'تسمم'),
        ('burn', 'حروق'),
        ('allergic', 'حساسية'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    severity = SelectField('درجة الخطورة', choices=[
        ('critical', 'حرج'),
        ('urgent', 'عاجل'),
        ('moderate', 'متوسط'),
        ('mild', 'خفيف')
    ], validators=[DataRequired()])
    
    # معلومات الحالة
    chief_complaint = TextAreaField('الشكوى الرئيسية', validators=[DataRequired(), Length(max=1000)])
    symptoms = TextAreaField('الأعراض', validators=[Optional(), Length(max=1000)])
    vital_signs = TextAreaField('العلامات الحيوية', validators=[Optional(), Length(max=500)])
    
    # معلومات التشخيص
    initial_diagnosis = TextAreaField('التشخيص الأولي', validators=[Optional(), Length(max=1000)])
    final_diagnosis = TextAreaField('التشخيص النهائي', validators=[Optional(), Length(max=1000)])
    treatment_given = TextAreaField('العلاج المقدم', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات النقل
    transfer_required = BooleanField('مطلوب نقل', default=False)
    transfer_to = StringField('نقل إلى', validators=[Optional(), Length(max=200)])
    transfer_reason = TextAreaField('سبب النقل', validators=[Optional(), Length(max=500)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    is_active = BooleanField('نشط', default=True)
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    submit = SubmitField('إنشاء حالة الطوارئ')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ المتابعة لا يمكن أن يكون في الماضي')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class EmergencyEditForm(FlaskForm):
    """فورم تعديل حالة الطوارئ"""
    
    # معلومات الطوارئ
    emergency_type = SelectField('نوع الطوارئ', choices=[
        ('trauma', 'إصابة'),
        ('cardiac', 'قلبي'),
        ('respiratory', 'تنفسي'),
        ('neurological', 'عصبي'),
        ('gastrointestinal', 'هضمي'),
        ('obstetric', 'ولادة'),
        ('pediatric', 'أطفال'),
        ('psychiatric', 'نفسي'),
        ('toxicological', 'تسمم'),
        ('burn', 'حروق'),
        ('allergic', 'حساسية'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    severity = SelectField('درجة الخطورة', choices=[
        ('critical', 'حرج'),
        ('urgent', 'عاجل'),
        ('moderate', 'متوسط'),
        ('mild', 'خفيف')
    ], validators=[DataRequired()])
    
    # معلومات الحالة
    chief_complaint = TextAreaField('الشكوى الرئيسية', validators=[DataRequired(), Length(max=1000)])
    symptoms = TextAreaField('الأعراض', validators=[Optional(), Length(max=1000)])
    vital_signs = TextAreaField('العلامات الحيوية', validators=[Optional(), Length(max=500)])
    
    # معلومات التشخيص
    initial_diagnosis = TextAreaField('التشخيص الأولي', validators=[Optional(), Length(max=1000)])
    final_diagnosis = TextAreaField('التشخيص النهائي', validators=[Optional(), Length(max=1000)])
    treatment_given = TextAreaField('العلاج المقدم', validators=[Optional(), Length(max=1000)])
    
    # معلومات المتابعة
    follow_up_required = BooleanField('مطلوب متابعة', default=False)
    follow_up_date = DateField('تاريخ المتابعة', validators=[Optional()])
    follow_up_notes = TextAreaField('ملاحظات المتابعة', validators=[Optional(), Length(max=500)])
    
    # معلومات النقل
    transfer_required = BooleanField('مطلوب نقل', default=False)
    transfer_to = StringField('نقل إلى', validators=[Optional(), Length(max=200)])
    transfer_reason = TextAreaField('سبب النقل', validators=[Optional(), Length(max=500)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    is_active = BooleanField('نشط', default=True)
    
    # معلومات الدفع
    payment_status = SelectField('حالة الدفع', choices=[
        ('pending', 'معلق'),
        ('paid', 'مدفوع'),
        ('partial', 'مدفوع جزئياً'),
        ('insurance', 'تأمين')
    ], validators=[DataRequired()])
    
    total_amount = DecimalField('المبلغ الإجمالي', validators=[Optional(), NumberRange(min=0)])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الطوارئ
    status = SelectField('حالة الطوارئ', choices=[
        ('active', 'نشط'),
        ('resolved', 'محلول'),
        ('transferred', 'منقول'),
        ('cancelled', 'ملغي')
    ], validators=[DataRequired()])
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_follow_up_date(self, field):
        """التحقق من تاريخ المتابعة"""
        if field.data and field.data < date.today():
            raise ValidationError('تاريخ المتابعة لا يمكن أن يكون في الماضي')
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')

class EmergencySearchForm(FlaskForm):
    """فورم البحث عن حالات الطوارئ"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('patient_name', 'اسم المريض'),
        ('emergency_id', 'رقم الطوارئ'),
        ('diagnosis', 'التشخيص')
    ], validators=[DataRequired()])
    
    emergency_type = SelectField('نوع الطوارئ', choices=[
        ('', 'جميع الأنواع'),
        ('trauma', 'إصابة'),
        ('cardiac', 'قلبي'),
        ('respiratory', 'تنفسي'),
        ('neurological', 'عصبي'),
        ('gastrointestinal', 'هضمي'),
        ('obstetric', 'ولادة'),
        ('pediatric', 'أطفال'),
        ('psychiatric', 'نفسي'),
        ('toxicological', 'تسمم'),
        ('burn', 'حروق'),
        ('allergic', 'حساسية'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    
    severity = SelectField('درجة الخطورة', choices=[
        ('', 'جميع الدرجات'),
        ('critical', 'حرج'),
        ('urgent', 'عاجل'),
        ('moderate', 'متوسط'),
        ('mild', 'خفيف')
    ], validators=[Optional()])
    
    status = SelectField('حالة الطوارئ', choices=[
        ('', 'جميع الحالات'),
        ('active', 'نشط'),
        ('resolved', 'محلول'),
        ('transferred', 'منقول'),
        ('cancelled', 'ملغي')
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
    
    submit = SubmitField('بحث')
    
    def validate_date_to(self, field):
        """التحقق من نطاق التاريخ"""
        if self.date_from.data and field.data and field.data < self.date_from.data:
            raise ValidationError('التاريخ "إلى" يجب أن يكون بعد التاريخ "من"')