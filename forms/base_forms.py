"""
النماذج الأساسية الموحدة - Base Forms
Medical System Base Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, DateTimeField, IntegerField, DecimalField, BooleanField, HiddenField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, NumberRange, Optional, ValidationError
from wtforms.widgets import TextArea
from datetime import datetime, date
from app_factory import db

class FormBase(FlaskForm):
    """النموذج الأساسي لجميع النماذج"""
    
    def validate_date_range(self, field, start_field_name, end_field_name):
        """التحقق من صحة نطاق التواريخ"""
        if hasattr(self, start_field_name) and hasattr(self, end_field_name):
            start_date = getattr(self, start_field_name).data
            end_date = getattr(self, end_field_name).data
            
            if start_date and end_date and start_date > end_date:
                raise ValidationError('تاريخ البداية يجب أن يكون قبل تاريخ النهاية')

class SearchFormBase(FormBase):
    """النموذج الأساسي للبحث"""
    
    search_term = StringField('البحث', validators=[Optional()])
    date_from = DateField('من تاريخ', validators=[Optional()])
    date_to = DateField('إلى تاريخ', validators=[Optional()])
    status = SelectField('الحالة', choices=[('', 'جميع الحالات')], validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إضافة خيارات الحالة الديناميكية
        self.status.choices = [('', 'جميع الحالات')] + self.get_status_choices()
    
    def get_status_choices(self):
        """الحصول على خيارات الحالة - يجب تخصيصها في كل نموذج"""
        return [
            ('ACTIVE', 'نشط'),
            ('INACTIVE', 'غير نشط'),
            ('PENDING', 'في الانتظار'),
            ('COMPLETED', 'مكتمل'),
            ('CANCELLED', 'ملغي')
        ]

class PaymentMixin:
    """خلطة الدفع للمعاملات المالية"""
    
    amount = DecimalField('المبلغ', validators=[DataRequired(message='المبلغ مطلوب'), NumberRange(min=0.01, message='المبلغ يجب أن يكون أكبر من صفر')])
    payment_method = SelectField('طريقة الدفع', choices=[
        ('CASH', 'نقدي'),
        ('CARD', 'بطاقة'),
        ('WIRE', 'تحويل'),
        ('INSURANCE', 'تأمين'),
        ('FORCE', 'قسري')
    ], validators=[DataRequired(message='طريقة الدفع مطلوبة')])
    payment_date = DateField('تاريخ الدفع', default=date.today, validators=[DataRequired(message='تاريخ الدفع مطلوب')])
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class PricingBaseForm(FormBase):
    """النموذج الأساسي للتسعير"""
    
    base_price = DecimalField('السعر الأساسي', validators=[DataRequired(message='السعر الأساسي مطلوب'), NumberRange(min=0, message='السعر يجب أن يكون أكبر من أو يساوي صفر')])
    urgent_price = DecimalField('سعر الطوارئ', validators=[Optional(), NumberRange(min=0, message='سعر الطوارئ يجب أن يكون أكبر من أو يساوي صفر')])
    insurance_price = DecimalField('سعر التأمين', validators=[Optional(), NumberRange(min=0, message='سعر التأمين يجب أن يكون أكبر من أو يساوي صفر')])
    discount_percentage = DecimalField('نسبة الخصم (%)', validators=[Optional(), NumberRange(min=0, max=100, message='نسبة الخصم يجب أن تكون بين 0 و 100')])
    is_active = BooleanField('نشط', default=True)
    
    def validate_urgent_price(self, field):
        """التحقق من سعر الطوارئ"""
        if field.data and self.base_price.data and field.data < self.base_price.data:
            raise ValidationError('سعر الطوارئ يجب أن يكون أكبر من أو يساوي السعر الأساسي')
    
    def validate_insurance_price(self, field):
        """التحقق من سعر التأمين"""
        if field.data and self.base_price.data and field.data > self.base_price.data:
            raise ValidationError('سعر التأمين يجب أن يكون أقل من أو يساوي السعر الأساسي')

class MedicalEntityMixin:
    """خلطة الكيانات الطبية"""
    
    patient_id = SelectField('المريض', coerce=int, validators=[DataRequired(message='المريض مطلوب')])
    doctor_id = SelectField('الطبيب', coerce=int, validators=[Optional()])
    visit_id = SelectField('الزيارة', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تحميل الخيارات الديناميكية
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية - يجب تخصيصها في كل نموذج"""
        # تحميل المرضى
        from models.patient import Patient
        patients = Patient.query.filter_by(status='ACTIVE').all()
        self.patient_id.choices = [(p.id, f"{p.full_name} - {p.national_id}") for p in patients]
        
        # تحميل الأطباء
        from models.user import User
        doctors = User.query.filter(User.role.in_(['doctor', 'admin', 'manager'])).all()
        self.doctor_id.choices = [('', 'اختر الطبيب')] + [(d.id, d.full_name) for d in doctors]
        
        # تحميل الزيارات
        from models.visit import Visit
        visits = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS', 'COMPLETED'])).order_by(Visit.created_at.desc()).limit(100).all()
        self.visit_id.choices = [('', 'اختر الزيارة')] + [(v.id, f"زيارة {v.id} - {v.patient.full_name}") for v in visits]

class StatusMixin:
    """خلطة الحالة"""
    
    status = SelectField('الحالة', choices=[
        ('ACTIVE', 'نشط'),
        ('INACTIVE', 'غير نشط'),
        ('PENDING', 'في الانتظار'),
        ('COMPLETED', 'مكتمل'),
        ('CANCELLED', 'ملغي'),
        ('IN_PROGRESS', 'قيد التنفيذ'),
        ('READY', 'جاهز'),
        ('ARCHIVED', 'مؤرشف')
    ], validators=[DataRequired(message='الحالة مطلوبة')])

class PriorityMixin:
    """خلطة الأولوية"""
    
    priority = SelectField('الأولوية', choices=[
        ('LOW', 'منخفضة'),
        ('NORMAL', 'عادية'),
        ('HIGH', 'عالية'),
        ('URGENT', 'عاجلة'),
        ('CRITICAL', 'حرجة')
    ], default='NORMAL', validators=[DataRequired(message='الأولوية مطلوبة')])

class DateRangeMixin:
    """خلطة نطاق التواريخ"""
    
    start_date = DateField('تاريخ البداية', validators=[Optional()])
    end_date = DateField('تاريخ النهاية', validators=[Optional()])
    
    def validate_end_date(self, field):
        """التحقق من تاريخ النهاية"""
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError('تاريخ النهاية يجب أن يكون بعد تاريخ البداية')

class FileUploadMixin:
    """خلطة رفع الملفات"""
    
    file = HiddenField('الملف')  # سيتم التعامل معه عبر JavaScript
    file_description = TextAreaField('وصف الملف', validators=[Optional()])
    file_category = SelectField('فئة الملف', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تحميل فئات الملفات
        from models.unified_files import FileCategory
        categories = FileCategory.query.filter_by(status='ACTIVE').all()
        self.file_category.choices = [('', 'اختر فئة الملف')] + [(c.id, c.name_ar) for c in categories]

class NotificationMixin:
    """خلطة الإشعارات"""
    
    title = StringField('العنوان', validators=[DataRequired(message='العنوان مطلوب'), Length(max=200, message='العنوان يجب أن يكون أقل من 200 حرف')])
    message = TextAreaField('الرسالة', validators=[DataRequired(message='الرسالة مطلوبة')])
    notification_type = SelectField('نوع الإشعار', choices=[
        ('info', 'معلومات'),
        ('warning', 'تحذير'),
        ('error', 'خطأ'),
        ('success', 'نجاح')
    ], validators=[DataRequired(message='نوع الإشعار مطلوب')])
    priority = SelectField('الأولوية', choices=[
        ('LOW', 'منخفضة'),
        ('NORMAL', 'عادية'),
        ('HIGH', 'عالية'),
        ('URGENT', 'عاجلة')
    ], default='NORMAL', validators=[DataRequired(message='الأولوية مطلوبة')])

class AuditMixin:
    """خلطة التدقيق"""
    
    action = SelectField('الإجراء', choices=[
        ('CREATE', 'إنشاء'),
        ('UPDATE', 'تحديث'),
        ('DELETE', 'حذف'),
        ('VIEW', 'عرض'),
        ('LOGIN', 'تسجيل دخول'),
        ('LOGOUT', 'تسجيل خروج'),
        ('APPROVE', 'موافقة'),
        ('REJECT', 'رفض')
    ], validators=[DataRequired(message='الإجراء مطلوب')])
    description = TextAreaField('الوصف', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
