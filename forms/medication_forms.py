"""
فورمز الأدوية - النظام الصحي المتكامل
Medication Forms - Integrated Medical System
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DecimalField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError

class MedicationForm(FlaskForm):
    """فورم إضافة دواء جديد"""
    
    # معلومات الدواء الأساسية
    name = StringField('اسم الدواء', validators=[DataRequired(), Length(min=2, max=100)])
    generic_name = StringField('الاسم العلمي', validators=[Optional(), Length(max=100)])
    brand_name = StringField('اسم العلامة التجارية', validators=[Optional(), Length(max=100)])
    
    # تصنيف الدواء
    category = SelectField('فئة الدواء', choices=[
        ('antibiotic', 'مضاد حيوي'),
        ('painkiller', 'مسكن'),
        ('anti_inflammatory', 'مضاد للالتهاب'),
        ('antihistamine', 'مضاد للهيستامين'),
        ('antacid', 'مضاد للحموضة'),
        ('vitamin', 'فيتامين'),
        ('supplement', 'مكمل غذائي'),
        ('hormone', 'هرمون'),
        ('cardiovascular', 'قلبي وعائي'),
        ('respiratory', 'تنفسي'),
        ('gastrointestinal', 'هضمي'),
        ('neurological', 'عصبي'),
        ('dermatological', 'جلدي'),
        ('ophthalmic', 'عيني'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات الجرعة
    dosage_form = SelectField('شكل الجرعة', choices=[
        ('tablet', 'أقراص'),
        ('capsule', 'كبسولات'),
        ('syrup', 'شراب'),
        ('injection', 'حقن'),
        ('cream', 'كريم'),
        ('ointment', 'مرهم'),
        ('drops', 'قطرات'),
        ('spray', 'بخاخ'),
        ('patch', 'لصقة'),
        ('suppository', 'تحاميل'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    strength = StringField('قوة الدواء', validators=[DataRequired(), Length(max=50)])
    unit = SelectField('الوحدة', choices=[
        ('mg', 'ملغ'),
        ('g', 'غرام'),
        ('ml', 'مل'),
        ('mcg', 'ميكروغرام'),
        ('IU', 'وحدة دولية'),
        ('%', 'نسبة مئوية'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات الاستخدام
    indication = TextAreaField('الاستطباب', validators=[DataRequired(), Length(max=1000)])
    contraindications = TextAreaField('موانع الاستخدام', validators=[Optional(), Length(max=1000)])
    side_effects = TextAreaField('الآثار الجانبية', validators=[Optional(), Length(max=1000)])
    interactions = TextAreaField('التفاعلات الدوائية', validators=[Optional(), Length(max=1000)])
    
    # معلومات الجرعة
    adult_dose = StringField('جرعة البالغين', validators=[Optional(), Length(max=200)])
    pediatric_dose = StringField('جرعة الأطفال', validators=[Optional(), Length(max=200)])
    elderly_dose = StringField('جرعة كبار السن', validators=[Optional(), Length(max=200)])
    
    # معلومات التخزين
    storage_conditions = StringField('شروط التخزين', validators=[Optional(), Length(max=200)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    # معلومات إضافية
    manufacturer = StringField('الشركة المصنعة', validators=[Optional(), Length(max=100)])
    country = StringField('البلد', validators=[Optional(), Length(max=50)])
    barcode = StringField('الباركود', validators=[Optional(), Length(max=50)])
    
    # معلومات السعر
    cost_price = DecimalField('سعر التكلفة', validators=[Optional(), NumberRange(min=0)])
    selling_price = DecimalField('سعر البيع', validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات المخزون
    current_stock = IntegerField('المخزون الحالي', validators=[Optional(), NumberRange(min=0)])
    minimum_stock = IntegerField('الحد الأدنى للمخزون', validators=[Optional(), NumberRange(min=0)])
    maximum_stock = IntegerField('الحد الأقصى للمخزون', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الدواء
    is_active = BooleanField('نشط', default=True)
    requires_prescription = BooleanField('يتطلب وصفة طبية', default=True)
    is_controlled = BooleanField('مادة خاضعة للرقابة', default=False)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('إضافة الدواء')
    
    def validate_selling_price(self, field):
        """التحقق من سعر البيع"""
        if field.data and self.cost_price.data and field.data < self.cost_price.data:
            raise ValidationError('سعر البيع يجب أن يكون أكبر من سعر التكلفة')
    
    def validate_maximum_stock(self, field):
        """التحقق من الحد الأقصى للمخزون"""
        if field.data and self.minimum_stock.data and field.data < self.minimum_stock.data:
            raise ValidationError('الحد الأقصى للمخزون يجب أن يكون أكبر من الحد الأدنى')

class MedicationEditForm(FlaskForm):
    """فورم تعديل الدواء"""
    
    # معلومات الدواء الأساسية
    name = StringField('اسم الدواء', validators=[DataRequired(), Length(min=2, max=100)])
    generic_name = StringField('الاسم العلمي', validators=[Optional(), Length(max=100)])
    brand_name = StringField('اسم العلامة التجارية', validators=[Optional(), Length(max=100)])
    
    # تصنيف الدواء
    category = SelectField('فئة الدواء', choices=[
        ('antibiotic', 'مضاد حيوي'),
        ('painkiller', 'مسكن'),
        ('anti_inflammatory', 'مضاد للالتهاب'),
        ('antihistamine', 'مضاد للهيستامين'),
        ('antacid', 'مضاد للحموضة'),
        ('vitamin', 'فيتامين'),
        ('supplement', 'مكمل غذائي'),
        ('hormone', 'هرمون'),
        ('cardiovascular', 'قلبي وعائي'),
        ('respiratory', 'تنفسي'),
        ('gastrointestinal', 'هضمي'),
        ('neurological', 'عصبي'),
        ('dermatological', 'جلدي'),
        ('ophthalmic', 'عيني'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات الجرعة
    dosage_form = SelectField('شكل الجرعة', choices=[
        ('tablet', 'أقراص'),
        ('capsule', 'كبسولات'),
        ('syrup', 'شراب'),
        ('injection', 'حقن'),
        ('cream', 'كريم'),
        ('ointment', 'مرهم'),
        ('drops', 'قطرات'),
        ('spray', 'بخاخ'),
        ('patch', 'لصقة'),
        ('suppository', 'تحاميل'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    strength = StringField('قوة الدواء', validators=[DataRequired(), Length(max=50)])
    unit = SelectField('الوحدة', choices=[
        ('mg', 'ملغ'),
        ('g', 'غرام'),
        ('ml', 'مل'),
        ('mcg', 'ميكروغرام'),
        ('IU', 'وحدة دولية'),
        ('%', 'نسبة مئوية'),
        ('other', 'أخرى')
    ], validators=[DataRequired()])
    
    # معلومات الاستخدام
    indication = TextAreaField('الاستطباب', validators=[DataRequired(), Length(max=1000)])
    contraindications = TextAreaField('موانع الاستخدام', validators=[Optional(), Length(max=1000)])
    side_effects = TextAreaField('الآثار الجانبية', validators=[Optional(), Length(max=1000)])
    interactions = TextAreaField('التفاعلات الدوائية', validators=[Optional(), Length(max=1000)])
    
    # معلومات الجرعة
    adult_dose = StringField('جرعة البالغين', validators=[Optional(), Length(max=200)])
    pediatric_dose = StringField('جرعة الأطفال', validators=[Optional(), Length(max=200)])
    elderly_dose = StringField('جرعة كبار السن', validators=[Optional(), Length(max=200)])
    
    # معلومات التخزين
    storage_conditions = StringField('شروط التخزين', validators=[Optional(), Length(max=200)])
    expiry_date = StringField('تاريخ الانتهاء', validators=[Optional(), Length(max=50)])
    
    # معلومات إضافية
    manufacturer = StringField('الشركة المصنعة', validators=[Optional(), Length(max=100)])
    country = StringField('البلد', validators=[Optional(), Length(max=50)])
    barcode = StringField('الباركود', validators=[Optional(), Length(max=50)])
    
    # معلومات السعر
    cost_price = DecimalField('سعر التكلفة', validators=[Optional(), NumberRange(min=0)])
    selling_price = DecimalField('سعر البيع', validators=[Optional(), NumberRange(min=0)])
    currency = SelectField('العملة', choices=[
        ('شيكل', 'شيكل'),
        ('دولار', 'دولار'),
        ('يورو', 'يورو')
    ], validators=[DataRequired()])
    
    # معلومات المخزون
    current_stock = IntegerField('المخزون الحالي', validators=[Optional(), NumberRange(min=0)])
    minimum_stock = IntegerField('الحد الأدنى للمخزون', validators=[Optional(), NumberRange(min=0)])
    maximum_stock = IntegerField('الحد الأقصى للمخزون', validators=[Optional(), NumberRange(min=0)])
    
    # حالة الدواء
    is_active = BooleanField('نشط', default=True)
    requires_prescription = BooleanField('يتطلب وصفة طبية', default=True)
    is_controlled = BooleanField('مادة خاضعة للرقابة', default=False)
    
    # ملاحظات
    notes = TextAreaField('ملاحظات إضافية', validators=[Optional(), Length(max=1000)])
    
    submit = SubmitField('حفظ التعديلات')
    
    def validate_selling_price(self, field):
        """التحقق من سعر البيع"""
        if field.data and self.cost_price.data and field.data < self.cost_price.data:
            raise ValidationError('سعر البيع يجب أن يكون أكبر من سعر التكلفة')
    
    def validate_maximum_stock(self, field):
        """التحقق من الحد الأقصى للمخزون"""
        if field.data and self.minimum_stock.data and field.data < self.minimum_stock.data:
            raise ValidationError('الحد الأقصى للمخزون يجب أن يكون أكبر من الحد الأدنى')

class MedicationSearchForm(FlaskForm):
    """فورم البحث عن الأدوية"""
    
    search_term = StringField('كلمة البحث', validators=[Optional(), Length(max=100)])
    search_type = SelectField('نوع البحث', choices=[
        ('name', 'اسم الدواء'),
        ('generic_name', 'الاسم العلمي'),
        ('brand_name', 'اسم العلامة التجارية'),
        ('barcode', 'الباركود')
    ], validators=[DataRequired()])
    
    category = SelectField('فئة الدواء', choices=[
        ('', 'جميع الفئات'),
        ('antibiotic', 'مضاد حيوي'),
        ('painkiller', 'مسكن'),
        ('anti_inflammatory', 'مضاد للالتهاب'),
        ('antihistamine', 'مضاد للهيستامين'),
        ('antacid', 'مضاد للحموضة'),
        ('vitamin', 'فيتامين'),
        ('supplement', 'مكمل غذائي'),
        ('hormone', 'هرمون'),
        ('cardiovascular', 'قلبي وعائي'),
        ('respiratory', 'تنفسي'),
        ('gastrointestinal', 'هضمي'),
        ('neurological', 'عصبي'),
        ('dermatological', 'جلدي'),
        ('ophthalmic', 'عيني'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    
    dosage_form = SelectField('شكل الجرعة', choices=[
        ('', 'جميع الأشكال'),
        ('tablet', 'أقراص'),
        ('capsule', 'كبسولات'),
        ('syrup', 'شراب'),
        ('injection', 'حقن'),
        ('cream', 'كريم'),
        ('ointment', 'مرهم'),
        ('drops', 'قطرات'),
        ('spray', 'بخاخ'),
        ('patch', 'لصقة'),
        ('suppository', 'تحاميل'),
        ('other', 'أخرى')
    ], validators=[Optional()])
    
    is_active = SelectField('الحالة', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نشط'),
        ('false', 'غير نشط')
    ], validators=[Optional()])
    
    requires_prescription = SelectField('يتطلب وصفة طبية', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نعم'),
        ('false', 'لا')
    ], validators=[Optional()])
    
    is_controlled = SelectField('مادة خاضعة للرقابة', choices=[
        ('', 'جميع الحالات'),
        ('true', 'نعم'),
        ('false', 'لا')
    ], validators=[Optional()])
    
    submit = SubmitField('بحث')