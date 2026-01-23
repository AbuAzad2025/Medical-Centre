"""
نماذج النظام والصلاحيات - System Forms
Medical System System Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, DateTimeField, IntegerField, DecimalField, BooleanField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError, Email, EqualTo
from .base_forms import FormBase, SearchFormBase, StatusMixin, DateRangeMixin, AuditMixin, NotificationMixin, FileUploadMixin

class RoleForm(FormBase, StatusMixin):
    """نموذج الدور"""
    
    name = StringField('اسم الدور', validators=[DataRequired(message='اسم الدور مطلوب'), Length(max=50, message='اسم الدور يجب أن يكون أقل من 50 حرف')])
    name_ar = StringField('اسم الدور (عربي)', validators=[DataRequired(message='اسم الدور بالعربي مطلوب'), Length(max=50, message='اسم الدور بالعربي يجب أن يكون أقل من 50 حرف')])
    description = TextAreaField('الوصف', validators=[Optional()])
    is_system = BooleanField('دور نظام', default=False)
    permissions = TextAreaField('الصلاحيات (JSON)', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class PermissionAssignmentForm(FormBase, StatusMixin):
    """نموذج تعيين الصلاحيات"""
    
    role_id = SelectField('الدور', coerce=int, validators=[DataRequired(message='الدور مطلوب')])
    permission_id = SelectField('الصلاحية', coerce=int, validators=[DataRequired(message='الصلاحية مطلوبة')])
    granted_by = SelectField('مُعطى من قبل', coerce=int, validators=[DataRequired(message='المُعطي مطلوب')])
    expires_at = DateField('تاريخ الانتهاء', validators=[Optional()])
    reason = TextAreaField('السبب', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الأدوار
        from models.unified_models import UnifiedRole
        roles = UnifiedRole.query.filter_by(status='ACTIVE').all()
        self.role_id.choices = [(r.id, f"{r.name_ar} ({r.name})") for r in roles]
        
        # تحميل الصلاحيات
        from models.unified_models import UnifiedPermission
        permissions = UnifiedPermission.query.filter_by(status='ACTIVE').all()
        self.permission_id.choices = [(p.id, f"{p.permission_name_ar} ({p.permission_name})") for p in permissions]
        
        # تحميل المستخدمين
        from models.user import User
        users = User.query.filter_by(is_active=True).all()
        self.granted_by.choices = [(u.id, u.full_name) for u in users]

class DepartmentWorkflowConfigForm(FormBase, StatusMixin):
    """نموذج إعدادات workflow القسم"""
    
    department_id = SelectField('القسم', coerce=int, validators=[DataRequired(message='القسم مطلوب')])
    workflow_type = SelectField('نوع الـ Workflow', choices=[
        ('patient_visit', 'زيارة المريض'),
        ('lab_request', 'طلب المختبر'),
        ('radiology_request', 'طلب الأشعة'),
        ('emergency_case', 'حالة طارئة'),
        ('payment_process', 'عملية الدفع'),
        ('appointment', 'موعد')
    ], validators=[DataRequired(message='نوع الـ Workflow مطلوب')])
    auto_assign = BooleanField('تعيين تلقائي', default=False)
    max_queue_size = IntegerField('الحد الأقصى لحجم الطابور', validators=[Optional(), NumberRange(min=1, message='الحد الأقصى يجب أن يكون أكبر من صفر')])
    estimated_processing_time = IntegerField('الوقت المتوقع للمعالجة (دقيقة)', validators=[Optional(), NumberRange(min=1, message='الوقت المتوقع يجب أن يكون أكبر من صفر')])
    notification_enabled = BooleanField('تفعيل الإشعارات', default=True)
    escalation_time = IntegerField('وقت التصعيد (دقيقة)', validators=[Optional(), NumberRange(min=0, message='وقت التصعيد يجب أن يكون أكبر من أو يساوي صفر')])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الأقسام
        from models.department import Department
        departments = Department.query.filter_by(is_active=True).all()
        self.department_id.choices = [(d.id, d.name_ar) for d in departments]

class FileUploadForm(FormBase, FileUploadMixin, StatusMixin):
    """نموذج رفع الملفات"""
    
    filename = StringField('اسم الملف', validators=[DataRequired(message='اسم الملف مطلوب'), Length(max=255, message='اسم الملف يجب أن يكون أقل من 255 حرف')])
    original_filename = StringField('الاسم الأصلي', validators=[DataRequired(message='الاسم الأصلي مطلوب'), Length(max=255, message='الاسم الأصلي يجب أن يكون أقل من 255 حرف')])
    file_size = IntegerField('حجم الملف (بايت)', validators=[DataRequired(message='حجم الملف مطلوب'), NumberRange(min=1, message='حجم الملف يجب أن يكون أكبر من صفر')])
    mime_type = StringField('نوع الملف', validators=[DataRequired(message='نوع الملف مطلوب'), Length(max=100, message='نوع الملف يجب أن يكون أقل من 100 حرف')])
    file_hash = StringField('تشفير الملف', validators=[Optional(), Length(max=64, message='تشفير الملف يجب أن يكون أقل من 64 حرف')])
    
    # العلاقات
    patient_id = SelectField('المريض', coerce=int, validators=[Optional()])
    visit_id = SelectField('الزيارة', coerce=int, validators=[Optional()])
    lab_request_id = SelectField('طلب المختبر', coerce=int, validators=[Optional()])
    radiology_request_id = SelectField('طلب الأشعة', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المرضى
        from models.patient import Patient
        patients = Patient.query.filter_by(status='ACTIVE').all()
        self.patient_id.choices = [('', 'اختر المريض')] + [(p.id, f"{p.full_name} - {p.national_id}") for p in patients]
        
        # تحميل الزيارات
        from models.visit import Visit
        visits = Visit.query.filter_by(status='ACTIVE').order_by(Visit.created_at.desc()).limit(100).all()
        self.visit_id.choices = [('', 'اختر الزيارة')] + [(v.id, f"زيارة {v.id} - {v.patient.full_name}") for v in visits]
        
        # تحميل طلبات المختبر
        from models.lab_request import LabRequest
        lab_requests = LabRequest.query.filter_by(status='ACTIVE').order_by(LabRequest.created_at.desc()).limit(50).all()
        self.lab_request_id.choices = [('', 'اختر طلب المختبر')] + [(lr.id, f"طلب {lr.id} - {lr.patient.full_name}") for lr in lab_requests]
        
        # تحميل طلبات الأشعة
        from models.radiology_request import RadiologyRequest
        radiology_requests = RadiologyRequest.query.filter_by(status='ACTIVE').order_by(RadiologyRequest.created_at.desc()).limit(50).all()
        self.radiology_request_id.choices = [('', 'اختر طلب الأشعة')] + [(rr.id, f"طلب {rr.id} - {rr.patient.full_name}") for rr in radiology_requests]

class BackupSettingsForm(FormBase, StatusMixin):
    """نموذج إعدادات النسخ الاحتياطي"""
    
    backup_name = StringField('اسم النسخة الاحتياطية', validators=[DataRequired(message='اسم النسخة الاحتياطية مطلوب'), Length(max=200, message='اسم النسخة الاحتياطية يجب أن يكون أقل من 200 حرف')])
    backup_type = SelectField('نوع النسخة الاحتياطية', choices=[
        ('full', 'كاملة'),
        ('incremental', 'تزايدية'),
        ('differential', 'تفاضلية')
    ], validators=[DataRequired(message='نوع النسخة الاحتياطية مطلوب')])
    backup_path = StringField('مسار النسخة الاحتياطية', validators=[DataRequired(message='مسار النسخة الاحتياطية مطلوب'), Length(max=500, message='مسار النسخة الاحتياطية يجب أن يكون أقل من 500 حرف')])
    is_scheduled = BooleanField('مجدولة', default=False)
    schedule_cron = StringField('جدولة CRON', validators=[Optional(), Length(max=100, message='جدولة CRON يجب أن تكون أقل من 100 حرف')])
    retention_days = IntegerField('أيام الاحتفاظ', validators=[Optional(), NumberRange(min=1, message='أيام الاحتفاظ يجب أن تكون أكبر من صفر')])
    compression_enabled = BooleanField('تفعيل الضغط', default=True)
    encryption_enabled = BooleanField('تفعيل التشفير', default=False)
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class RunBackupForm(FormBase):
    """نموذج تشغيل النسخ الاحتياطي"""
    
    backup_name = StringField('اسم النسخة الاحتياطية', validators=[DataRequired(message='اسم النسخة الاحتياطية مطلوب'), Length(max=200, message='اسم النسخة الاحتياطية يجب أن يكون أقل من 200 حرف')])
    backup_type = SelectField('نوع النسخة الاحتياطية', choices=[
        ('full', 'كاملة'),
        ('incremental', 'تزايدية'),
        ('differential', 'تفاضلية')
    ], validators=[DataRequired(message='نوع النسخة الاحتياطية مطلوب')])
    backup_path = StringField('مسار النسخة الاحتياطية', validators=[DataRequired(message='مسار النسخة الاحتياطية مطلوب'), Length(max=500, message='مسار النسخة الاحتياطية يجب أن يكون أقل من 500 حرف')])
    compression_enabled = BooleanField('تفعيل الضغط', default=True)
    encryption_enabled = BooleanField('تفعيل التشفير', default=False)
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class AuditSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في التدقيق"""
    
    entity_type = SelectField('نوع الكيان', choices=[
        ('', 'جميع الأنواع'),
        ('user', 'مستخدم'),
        ('patient', 'مريض'),
        ('visit', 'زيارة'),
        ('appointment', 'موعد'),
        ('payment', 'دفع'),
        ('invoice', 'فاتورة'),
        ('lab_request', 'طلب مختبر'),
        ('radiology_request', 'طلب أشعة'),
        ('emergency', 'طوارئ')
    ], validators=[Optional()])
    action = SelectField('الإجراء', choices=[
        ('', 'جميع الإجراءات'),
        ('CREATE', 'إنشاء'),
        ('UPDATE', 'تحديث'),
        ('DELETE', 'حذف'),
        ('VIEW', 'عرض'),
        ('LOGIN', 'تسجيل دخول'),
        ('LOGOUT', 'تسجيل خروج'),
        ('APPROVE', 'موافقة'),
        ('REJECT', 'رفض')
    ], validators=[Optional()])
    user_name = StringField('اسم المستخدم', validators=[Optional()])
    entity_id = IntegerField('معرف الكيان', validators=[Optional(), NumberRange(min=1, message='معرف الكيان يجب أن يكون أكبر من صفر')])

class FinancialAuditSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في التدقيق المالي"""
    
    transaction_type = SelectField('نوع المعاملة', choices=[
        ('', 'جميع الأنواع'),
        ('INCOME', 'دخل'),
        ('EXPENSE', 'مصروف'),
        ('REFUND', 'استرداد'),
        ('PAYMENT', 'دفع'),
        ('INVOICE', 'فاتورة')
    ], validators=[Optional()])
    payment_method = SelectField('طريقة الدفع', choices=[
        ('', 'جميع الطرق'),
        ('CASH', 'نقدي'),
        ('CARD', 'بطاقة ائتمان'),
        ('WIRE', 'تحويل بنكي'),
        ('INSURANCE', 'تأمين'),
        ('FORCE', 'قسري')
    ], validators=[Optional()])
    payment_status = SelectField('حالة الدفع', choices=[
        ('', 'جميع الحالات'),
        ('PENDING', 'في الانتظار'),
        ('PAID', 'مدفوع'),
        ('PARTIAL', 'مدفوع جزئياً'),
        ('CANCELLED', 'ملغي')
    ], validators=[Optional()])
    amount_from = DecimalField('من مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    amount_to = DecimalField('إلى مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    user_name = StringField('اسم المستخدم', validators=[Optional()])

class AIAnalyticsConfigForm(FormBase, StatusMixin):
    """نموذج إعدادات التحليلات الذكية"""
    
    config_name = StringField('اسم الإعداد', validators=[DataRequired(message='اسم الإعداد مطلوب'), Length(max=100, message='اسم الإعداد يجب أن يكون أقل من 100 حرف')])
    config_type = SelectField('نوع الإعداد', choices=[
        ('patient_analytics', 'تحليلات المرضى'),
        ('financial_analytics', 'تحليلات مالية'),
        ('workflow_analytics', 'تحليلات سير العمل'),
        ('performance_analytics', 'تحليلات الأداء'),
        ('predictive_analytics', 'تحليلات تنبؤية')
    ], validators=[DataRequired(message='نوع الإعداد مطلوب')])
    config_value = TextAreaField('قيمة الإعداد (JSON)', validators=[DataRequired(message='قيمة الإعداد مطلوبة')])
    description = TextAreaField('الوصف', validators=[Optional()])
    is_active = BooleanField('نشط', default=True)
    auto_update = BooleanField('تحديث تلقائي', default=False)
    update_frequency = SelectField('تكرار التحديث', choices=[
        ('hourly', 'كل ساعة'),
        ('daily', 'يومي'),
        ('weekly', 'أسبوعي'),
        ('monthly', 'شهري'),
        ('manual', 'يدوي')
    ], validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class SystemConfigForm(FormBase, StatusMixin):
    """نموذج إعدادات النظام"""
    
    setting_key = StringField('مفتاح الإعداد', validators=[DataRequired(message='مفتاح الإعداد مطلوب'), Length(max=100, message='مفتاح الإعداد يجب أن يكون أقل من 100 حرف')])
    setting_value = TextAreaField('قيمة الإعداد', validators=[DataRequired(message='قيمة الإعداد مطلوبة')])
    setting_type = SelectField('نوع الإعداد', choices=[
        ('STRING', 'نص'),
        ('INTEGER', 'رقم صحيح'),
        ('FLOAT', 'رقم عشري'),
        ('BOOLEAN', 'منطقي'),
        ('JSON', 'JSON'),
        ('DATE', 'تاريخ'),
        ('DATETIME', 'تاريخ ووقت')
    ], validators=[DataRequired(message='نوع الإعداد مطلوب')])
    category = SelectField('الفئة', choices=[
        ('general', 'عام'),
        ('security', 'أمان'),
        ('database', 'قاعدة البيانات'),
        ('email', 'البريد الإلكتروني'),
        ('backup', 'النسخ الاحتياطي'),
        ('notification', 'الإشعارات'),
        ('payment', 'المدفوعات'),
        ('workflow', 'سير العمل'),
        ('analytics', 'التحليلات'),
        ('integration', 'التكامل')
    ], validators=[DataRequired(message='الفئة مطلوبة')])
    description = TextAreaField('الوصف', validators=[Optional()])
    is_encrypted = BooleanField('مشفّر', default=False)
    is_system = BooleanField('إعداد نظام', default=False)
    notes = TextAreaField('ملاحظات', validators=[Optional()])

class UserRoleAssignmentForm(FormBase, StatusMixin):
    """نموذج تعيين أدوار المستخدمين"""
    
    user_id = SelectField('المستخدم', coerce=int, validators=[DataRequired(message='المستخدم مطلوب')])
    role_id = SelectField('الدور', coerce=int, validators=[DataRequired(message='الدور مطلوب')])
    assigned_by = SelectField('مُعيّن من قبل', coerce=int, validators=[DataRequired(message='المُعيّن مطلوب')])
    expires_at = DateField('تاريخ الانتهاء', validators=[Optional()])
    reason = TextAreaField('السبب', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المستخدمين
        from models.user import User
        users = User.query.filter_by(is_active=True).all()
        self.user_id.choices = [(u.id, f"{u.full_name} ({u.role})") for u in users]
        
        # تحميل الأدوار
        from models.unified_models import UnifiedRole
        roles = UnifiedRole.query.filter_by(status='ACTIVE').all()
        self.role_id.choices = [(r.id, f"{r.name_ar} ({r.name})") for r in roles]
        
        # تحميل المستخدمين للمُعيّن
        self.assigned_by.choices = [(u.id, u.full_name) for u in users]

class NotificationForm(FormBase, NotificationMixin, StatusMixin):
    """نموذج الإشعارات"""
    
    user_id = SelectField('المستخدم', coerce=int, validators=[DataRequired(message='المستخدم مطلوب')])
    sender_id = SelectField('المرسل', coerce=int, validators=[Optional()])
    is_read = BooleanField('مقروء', default=False)
    read_at = DateTimeField('وقت القراءة', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المستخدمين
        from models.user import User
        users = User.query.filter_by(is_active=True).all()
        self.user_id.choices = [(u.id, f"{u.full_name} ({u.role})") for u in users]
        self.sender_id.choices = [('', 'اختر المرسل')] + [(u.id, f"{u.full_name} ({u.role})") for u in users]

class SystemLogSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في سجلات النظام"""
    
    log_level = SelectField('مستوى السجل', choices=[
        ('', 'جميع المستويات'),
        ('DEBUG', 'تصحيح'),
        ('INFO', 'معلومات'),
        ('WARNING', 'تحذير'),
        ('ERROR', 'خطأ'),
        ('CRITICAL', 'حرج')
    ], validators=[Optional()])
    module = StringField('الوحدة', validators=[Optional()])
    user_name = StringField('اسم المستخدم', validators=[Optional()])
    message = StringField('الرسالة', validators=[Optional()])

class SecurityEventSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في أحداث الأمان"""
    
    event_type = SelectField('نوع الحدث', choices=[
        ('', 'جميع الأنواع'),
        ('login_success', 'تسجيل دخول ناجح'),
        ('login_failed', 'فشل تسجيل الدخول'),
        ('password_change', 'تغيير كلمة المرور'),
        ('permission_denied', 'رفض الصلاحية'),
        ('suspicious_activity', 'نشاط مشبوه'),
        ('data_access', 'الوصول للبيانات'),
        ('system_change', 'تغيير النظام')
    ], validators=[Optional()])
    severity = SelectField('الخطورة', choices=[
        ('', 'جميع المستويات'),
        ('LOW', 'منخفضة'),
        ('MEDIUM', 'متوسطة'),
        ('HIGH', 'عالية'),
        ('CRITICAL', 'حرجة')
    ], validators=[Optional()])
    user_name = StringField('اسم المستخدم', validators=[Optional()])
    ip_address = StringField('عنوان IP', validators=[Optional()])
    resolved = BooleanField('محلول', validators=[Optional()])
