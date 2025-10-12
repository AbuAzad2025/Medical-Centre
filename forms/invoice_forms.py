"""
نماذج الفواتير - Invoice Forms
Medical System Invoice Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, FloatField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from .base_forms import FormBase, SearchFormBase, PaymentMixin, MedicalEntityMixin, StatusMixin, DateRangeMixin

class InvoiceForm(FormBase, MedicalEntityMixin, StatusMixin, PaymentMixin):
    """نموذج الفاتورة"""
    
    invoice_number = StringField('رقم الفاتورة', validators=[DataRequired(message='رقم الفاتورة مطلوب'), Length(max=50, message='رقم الفاتورة يجب أن يكون أقل من 50 حرف')])
    total_amount = FloatField('المبلغ الإجمالي', validators=[DataRequired(message='المبلغ الإجمالي مطلوب'), NumberRange(min=0.01, message='المبلغ يجب أن يكون أكبر من صفر')])
    paid_amount = FloatField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0, message='المبلغ المدفوع يجب أن يكون أكبر من أو يساوي صفر')])
    remaining_amount = FloatField('المبلغ المتبقي', validators=[Optional(), NumberRange(min=0, message='المبلغ المتبقي يجب أن يكون أكبر من أو يساوي صفر')])
    due_date = DateField('تاريخ الاستحقاق', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    # حقول التأمين
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    insurance_number = StringField('رقم التأمين', validators=[Optional(), Length(max=50, message='رقم التأمين يجب أن يكون أقل من 50 حرف')])
    insurance_coverage = FloatField('نسبة التغطية (%)', validators=[Optional(), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    
    # حقول الإدخال القوي
    force_payment = BooleanField('دفع قوي', default=False)
    force_payment_reason = TextAreaField('سبب الدفع القوي', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [('', 'اختر شركة التأمين')] + [(c.id, c.name) for c in companies]
    
    def validate_paid_amount(self, field):
        """التحقق من المبلغ المدفوع"""
        if field.data and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('المبلغ المدفوع لا يمكن أن يكون أكبر من المبلغ الإجمالي')
    
    def validate_remaining_amount(self, field):
        """التحقق من المبلغ المتبقي"""
        if field.data and self.total_amount.data and self.paid_amount.data:
            expected_remaining = self.total_amount.data - self.paid_amount.data
            if abs(field.data - expected_remaining) > 0.01:  # تحمل خطأ صغير
                raise ValidationError('المبلغ المتبقي لا يتطابق مع الحساب')

class InvoiceSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في الفواتير"""
    
    invoice_number = StringField('رقم الفاتورة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    amount_from = FloatField('من مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    amount_to = FloatField('إلى مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    payment_status = SelectField('حالة الدفع', choices=[
        ('', 'جميع الحالات'),
        ('PENDING', 'في الانتظار'),
        ('PAID', 'مدفوع'),
        ('PARTIAL', 'مدفوع جزئياً'),
        ('DEBT', 'دين'),
        ('CANCELLED', 'ملغي')
    ], validators=[Optional()])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [('', 'جميع الشركات')] + [(c.id, c.name) for c in companies]

class ReceiptForm(FormBase, PaymentMixin):
    """نموذج سند القبض"""
    
    receipt_number = StringField('رقم السند', validators=[DataRequired(message='رقم السند مطلوب'), Length(max=50, message='رقم السند يجب أن يكون أقل من 50 حرف')])
    invoice_id = SelectField('الفاتورة', coerce=int, validators=[DataRequired(message='الفاتورة مطلوبة')])
    payment_reference = StringField('مرجع الدفع', validators=[Optional(), Length(max=100, message='مرجع الدفع يجب أن يكون أقل من 100 حرف')])
    printed = BooleanField('مطبوع', default=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل الفواتير غير المدفوعة بالكامل
        from models.invoice import Invoice
        invoices = Invoice.query.filter(Invoice.payment_status != 'PAID').all()
        self.invoice_id.choices = [(i.id, f"فاتورة {i.invoice_number} - {i.patient.full_name} - {i.total_amount}") for i in invoices]

class RefundForm(FormBase, PaymentMixin):
    """نموذج الاسترداد"""
    
    refund_reason = SelectField('سبب الاسترداد', choices=[
        ('overpayment', 'دفع زائد'),
        ('cancellation', 'إلغاء الخدمة'),
        ('error', 'خطأ في الدفع'),
        ('duplicate', 'دفع مكرر'),
        ('other', 'أسباب أخرى')
    ], validators=[DataRequired(message='سبب الاسترداد مطلوب')])
    original_payment_id = SelectField('الدفع الأصلي', coerce=int, validators=[DataRequired(message='الدفع الأصلي مطلوب')])
    refund_percentage = FloatField('نسبة الاسترداد (%)', validators=[Optional(), NumberRange(min=0, max=100, message='نسبة الاسترداد يجب أن تكون بين 0 و 100')])
    admin_approval = BooleanField('موافقة الإدارة', default=False)
    admin_notes = TextAreaField('ملاحظات الإدارة', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المدفوعات المكتملة
        from models.payment import Payment
        payments = Payment.query.filter_by(payment_status='PAID').all()
        self.original_payment_id.choices = [(p.id, f"دفع {p.id} - {p.patient.full_name} - {p.amount}") for p in payments]

class InsuranceClaimForm(FormBase, MedicalEntityMixin):
    """نموذج مطالبة التأمين"""
    
    claim_number = StringField('رقم المطالبة', validators=[DataRequired(message='رقم المطالبة مطلوب'), Length(max=50, message='رقم المطالبة يجب أن يكون أقل من 50 حرف')])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[DataRequired(message='شركة التأمين مطلوبة')])
    policy_number = StringField('رقم البوليصة', validators=[DataRequired(message='رقم البوليصة مطلوب'), Length(max=50, message='رقم البوليصة يجب أن يكون أقل من 50 حرف')])
    claim_amount = FloatField('مبلغ المطالبة', validators=[DataRequired(message='مبلغ المطالبة مطلوب'), NumberRange(min=0.01, message='مبلغ المطالبة يجب أن يكون أكبر من صفر')])
    approved_amount = FloatField('المبلغ المعتمد', validators=[Optional(), NumberRange(min=0, message='المبلغ المعتمد يجب أن يكون أكبر من أو يساوي صفر')])
    claim_date = DateField('تاريخ المطالبة', validators=[DataRequired(message='تاريخ المطالبة مطلوب')])
    approval_date = DateField('تاريخ الموافقة', validators=[Optional()])
    status = SelectField('الحالة', choices=[
        ('PENDING', 'في الانتظار'),
        ('APPROVED', 'معتمد'),
        ('REJECTED', 'مرفوض'),
        ('PARTIAL', 'معتمد جزئياً'),
        ('PROCESSING', 'قيد المعالجة')
    ], validators=[DataRequired(message='الحالة مطلوبة')])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [(c.id, c.name) for c in companies]

class InsuranceClaimSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في مطالبات التأمين"""
    
    claim_number = StringField('رقم المطالبة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    amount_from = FloatField('من مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    amount_to = FloatField('إلى مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [('', 'جميع الشركات')] + [(c.id, c.name) for c in companies]

class InsurancePolicyForm(FormBase):
    """نموذج بوليصة التأمين"""
    
    policy_number = StringField('رقم البوليصة', validators=[DataRequired(message='رقم البوليصة مطلوب'), Length(max=50, message='رقم البوليصة يجب أن يكون أقل من 50 حرف')])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[DataRequired(message='شركة التأمين مطلوبة')])
    patient_id = SelectField('المريض', coerce=int, validators=[DataRequired(message='المريض مطلوب')])
    coverage_percentage = FloatField('نسبة التغطية (%)', validators=[DataRequired(message='نسبة التغطية مطلوبة'), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    max_coverage_amount = FloatField('الحد الأقصى للتغطية', validators=[Optional(), NumberRange(min=0, message='الحد الأقصى يجب أن يكون أكبر من أو يساوي صفر')])
    start_date = DateField('تاريخ البداية', validators=[DataRequired(message='تاريخ البداية مطلوب')])
    end_date = DateField('تاريخ النهاية', validators=[DataRequired(message='تاريخ النهاية مطلوب')])
    is_active = BooleanField('نشط', default=True)
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل شركات التأمين
        from models.insurance import InsuranceCompany
        companies = InsuranceCompany.query.filter_by(is_active=True).all()
        self.insurance_company_id.choices = [(c.id, c.name) for c in companies]
        
        # تحميل المرضى
        from models.patient import Patient
        patients = Patient.query.filter_by(status='ACTIVE').all()
        self.patient_id.choices = [(p.id, f"{p.full_name} - {p.national_id}") for p in patients]

class InsuranceProviderForm(FormBase):
    """نموذج مزود التأمين"""
    
    name = StringField('اسم الشركة', validators=[DataRequired(message='اسم الشركة مطلوب'), Length(max=200, message='اسم الشركة يجب أن يكون أقل من 200 حرف')])
    code = StringField('كود الشركة', validators=[DataRequired(message='كود الشركة مطلوب'), Length(max=50, message='كود الشركة يجب أن يكون أقل من 50 حرف')])
    contact_person = StringField('الشخص المسؤول', validators=[Optional(), Length(max=100, message='اسم الشخص المسؤول يجب أن يكون أقل من 100 حرف')])
    phone = StringField('الهاتف', validators=[Optional(), Length(max=20, message='رقم الهاتف يجب أن يكون أقل من 20 رقم')])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Length(max=120, message='البريد الإلكتروني يجب أن يكون أقل من 120 حرف')])
    address = TextAreaField('العنوان', validators=[Optional()])
    coverage_percentage = FloatField('نسبة التغطية الافتراضية (%)', validators=[DataRequired(message='نسبة التغطية مطلوبة'), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    max_coverage_amount = FloatField('الحد الأقصى للتغطية', validators=[Optional(), NumberRange(min=0, message='الحد الأقصى يجب أن يكون أكبر من أو يساوي صفر')])
    is_active = BooleanField('نشط', default=True)
