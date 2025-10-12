"""
فورمز التسعير - النظام الصحي المتكامل
Pricing Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError

class DoctorPricingForm(FlaskForm):
    """فورم تسعير الأطباء"""
    
    # معلومات الطبيب
    doctor_id = SelectField('الطبيب', coerce=int, validators=[DataRequired()])
    
    # معلومات التسعير
    first_consultation_price = DecimalField('سعر الاستشارة الأولى', validators=[DataRequired(), NumberRange(min=0)])
    follow_up_price = DecimalField('سعر المتابعة', validators=[DataRequired(), NumberRange(min=0)])
    emergency_price = DecimalField('سعر الطوارئ', validators=[Optional(), NumberRange(min=0)])
    surgery_price = DecimalField('سعر العملية الجراحية', validators=[Optional(), NumberRange(min=0)])
    
    # معلومات العملة
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات إضافية
    consultation_duration = IntegerField('مدة الاستشارة (دقيقة)', validators=[Optional(), NumberRange(min=15, max=480)])
    follow_up_duration = IntegerField('مدة المتابعة (دقيقة)', validators=[Optional(), NumberRange(min=15, max=480)])
    
    # معلومات الخصم
    discount_percentage = DecimalField('نسبة الخصم (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    discount_reason = StringField('سبب الخصم', validators=[Optional(), Length(max=200)])
    
    # معلومات التأمين
    insurance_coverage = BooleanField('يغطي التأمين', default=True)
    insurance_percentage = DecimalField('نسبة التأمين (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة التسعير
    is_active = BooleanField('نشط', default=True)
    effective_date = StringField('تاريخ السريان', validators=[Optional(), Length(max=50)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    submit = SubmitField('حفظ التسعير')
    
    def validate_follow_up_price(self, field):
        """التحقق من سعر المتابعة"""
        if field.data and self.first_consultation_price.data and field.data > self.first_consultation_price.data:
            raise ValidationError('سعر المتابعة يجب أن يكون أقل من سعر الاستشارة الأولى')
    
    def validate_discount_percentage(self, field):
        """التحقق من نسبة الخصم"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة الخصم لا يمكن أن تكون أكبر من 100%')
    
    def validate_insurance_percentage(self, field):
        """التحقق من نسبة التأمين"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة التأمين لا يمكن أن تكون أكبر من 100%')

class LabTestPricingForm(FlaskForm):
    """فورم تسعير فحوصات المختبر"""
    
    # معلومات الفحص
    test_id = SelectField('الفحص', coerce=int, validators=[DataRequired()])
    
    # معلومات التسعير
    base_price = DecimalField('السعر الأساسي', validators=[DataRequired(), NumberRange(min=0)])
    urgent_price = DecimalField('سعر العاجل', validators=[Optional(), NumberRange(min=0)])
    insurance_price = DecimalField('سعر التأمين', validators=[Optional(), NumberRange(min=0)])
    
    # معلومات العملة
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات التوقيت
    normal_duration = IntegerField('مدة النتيجة العادية (ساعة)', validators=[Optional(), NumberRange(min=1, max=168)])
    urgent_duration = IntegerField('مدة النتيجة العاجلة (ساعة)', validators=[Optional(), NumberRange(min=1, max=168)])
    
    # معلومات الخصم
    discount_percentage = DecimalField('نسبة الخصم (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    discount_reason = StringField('سبب الخصم', validators=[Optional(), Length(max=200)])
    
    # معلومات التأمين
    insurance_coverage = BooleanField('يغطي التأمين', default=True)
    insurance_percentage = DecimalField('نسبة التأمين (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة التسعير
    is_active = BooleanField('نشط', default=True)
    effective_date = StringField('تاريخ السريان', validators=[Optional(), Length(max=50)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    submit = SubmitField('حفظ التسعير')
    
    def validate_urgent_price(self, field):
        """التحقق من سعر العاجل"""
        if field.data and self.base_price.data and field.data < self.base_price.data:
            raise ValidationError('سعر العاجل يجب أن يكون أكبر من السعر الأساسي')
    
    def validate_insurance_price(self, field):
        """التحقق من سعر التأمين"""
        if field.data and self.base_price.data and field.data > self.base_price.data:
            raise ValidationError('سعر التأمين يجب أن يكون أقل من السعر الأساسي')
    
    def validate_discount_percentage(self, field):
        """التحقق من نسبة الخصم"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة الخصم لا يمكن أن تكون أكبر من 100%')
    
    def validate_insurance_percentage(self, field):
        """التحقق من نسبة التأمين"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة التأمين لا يمكن أن تكون أكبر من 100%')

class RadiologyPricingForm(FlaskForm):
    """فورم تسعير فحوصات الأشعة"""
    
    # معلومات الفحص
    test_id = SelectField('الفحص', coerce=int, validators=[DataRequired()])
    
    # معلومات التسعير
    base_price = DecimalField('السعر الأساسي', validators=[DataRequired(), NumberRange(min=0)])
    urgent_price = DecimalField('سعر العاجل', validators=[Optional(), NumberRange(min=0)])
    insurance_price = DecimalField('سعر التأمين', validators=[Optional(), NumberRange(min=0)])
    
    # معلومات العملة
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات التوقيت
    normal_duration = IntegerField('مدة النتيجة العادية (ساعة)', validators=[Optional(), NumberRange(min=1, max=168)])
    urgent_duration = IntegerField('مدة النتيجة العاجلة (ساعة)', validators=[Optional(), NumberRange(min=1, max=168)])
    
    # معلومات الخصم
    discount_percentage = DecimalField('نسبة الخصم (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    discount_reason = StringField('سبب الخصم', validators=[Optional(), Length(max=200)])
    
    # معلومات التأمين
    insurance_coverage = BooleanField('يغطي التأمين', default=True)
    insurance_percentage = DecimalField('نسبة التأمين (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة التسعير
    is_active = BooleanField('نشط', default=True)
    effective_date = StringField('تاريخ السريان', validators=[Optional(), Length(max=50)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    submit = SubmitField('حفظ التسعير')
    
    def validate_urgent_price(self, field):
        """التحقق من سعر العاجل"""
        if field.data and self.base_price.data and field.data < self.base_price.data:
            raise ValidationError('سعر العاجل يجب أن يكون أكبر من السعر الأساسي')
    
    def validate_insurance_price(self, field):
        """التحقق من سعر التأمين"""
        if field.data and self.base_price.data and field.data > self.base_price.data:
            raise ValidationError('سعر التأمين يجب أن يكون أقل من السعر الأساسي')
    
    def validate_discount_percentage(self, field):
        """التحقق من نسبة الخصم"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة الخصم لا يمكن أن تكون أكبر من 100%')
    
    def validate_insurance_percentage(self, field):
        """التحقق من نسبة التأمين"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة التأمين لا يمكن أن تكون أكبر من 100%')

class ServicePricingForm(FlaskForm):
    """فورم تسعير الخدمات العامة"""
    
    # معلومات الخدمة
    service_id = SelectField('الخدمة', coerce=int, validators=[DataRequired()])
    
    # معلومات التسعير
    base_price = DecimalField('السعر الأساسي', validators=[DataRequired(), NumberRange(min=0)])
    urgent_price = DecimalField('سعر العاجل', validators=[Optional(), NumberRange(min=0)])
    insurance_price = DecimalField('سعر التأمين', validators=[Optional(), NumberRange(min=0)])
    
    # معلومات العملة
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات الخصم
    discount_percentage = DecimalField('نسبة الخصم (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    discount_reason = StringField('سبب الخصم', validators=[Optional(), Length(max=200)])
    
    # معلومات التأمين
    insurance_coverage = BooleanField('يغطي التأمين', default=True)
    insurance_percentage = DecimalField('نسبة التأمين (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    
    # معلومات إضافية
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    # حالة التسعير
    is_active = BooleanField('نشط', default=True)
    effective_date = StringField('تاريخ السريان', validators=[Optional(), Length(max=50)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    submit = SubmitField('حفظ التسعير')
    
    def validate_urgent_price(self, field):
        """التحقق من سعر العاجل"""
        if field.data and self.base_price.data and field.data < self.base_price.data:
            raise ValidationError('سعر العاجل يجب أن يكون أكبر من السعر الأساسي')
    
    def validate_insurance_price(self, field):
        """التحقق من سعر التأمين"""
        if field.data and self.base_price.data and field.data > self.base_price.data:
            raise ValidationError('سعر التأمين يجب أن يكون أقل من السعر الأساسي')
    
    def validate_discount_percentage(self, field):
        """التحقق من نسبة الخصم"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة الخصم لا يمكن أن تكون أكبر من 100%')
    
    def validate_insurance_percentage(self, field):
        """التحقق من نسبة التأمين"""
        if field.data and field.data > 100:
            raise ValidationError('نسبة التأمين لا يمكن أن تكون أكبر من 100%')

class PricingSearchForm(FlaskForm):
    """فورم البحث عن التسعير"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('doctor_name', 'اسم الطبيب'),
        ('test_name', 'اسم الفحص'),
        ('service_name', 'اسم الخدمة'),
        ('price_range', 'نطاق السعر')
    ], validators=[DataRequired()])
    
    pricing_type = SelectField('نوع التسعير', choices=[
        ('', 'جميع الأنواع'),
        ('doctor', 'أطباء'),
        ('lab', 'مختبر'),
        ('radiology', 'أشعة'),
        ('service', 'خدمات')
    ], validators=[Optional()])
    
    currency = SelectField('العملة', choices=[
        ('', 'جميع العملات'),
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[Optional()])
    
    price_from = DecimalField('السعر من', validators=[Optional(), NumberRange(min=0)])
    price_to = DecimalField('السعر إلى', validators=[Optional(), NumberRange(min=0)])
    
    is_active = SelectField('الحالة', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نشط'),
        ('false', 'غير نشط')
    ], validators=[Optional()])
    
    insurance_coverage = SelectField('يغطي التأمين', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نعم'),
        ('false', 'لا')
    ], validators=[Optional()])
    
    submit = SubmitField('بحث')
    
    def validate_price_to(self, field):
        """التحقق من نطاق السعر"""
        if self.price_from.data and field.data and field.data < self.price_from.data:
            raise ValidationError('السعر "إلى" يجب أن يكون أكبر من السعر "من"')
