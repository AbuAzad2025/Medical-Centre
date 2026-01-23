"""
نماذج الفواتير - Invoice Forms
Medical System Invoice Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, DecimalField, BooleanField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from .base_forms import FormBase, SearchFormBase, PaymentMixin, MedicalEntityMixin, StatusMixin, DateRangeMixin

class InvoiceForm(FormBase, MedicalEntityMixin, StatusMixin, PaymentMixin):
    """نموذج الفاتورة"""
    
    invoice_number = StringField('رقم الفاتورة', validators=[DataRequired(message='رقم الفاتورة مطلوب'), Length(max=50, message='رقم الفاتورة يجب أن يكون أقل من 50 حرف')])
    total_amount = DecimalField('المبلغ الإجمالي', validators=[DataRequired(message='المبلغ الإجمالي مطلوب'), NumberRange(min=0.01, message='المبلغ يجب أن يكون أكبر من صفر')])
    paid_amount = DecimalField('المبلغ المدفوع', validators=[Optional(), NumberRange(min=0, message='المبلغ المدفوع يجب أن يكون أكبر من أو يساوي صفر')])
    remaining_amount = DecimalField('المبلغ المتبقي', validators=[Optional(), NumberRange(min=0, message='المبلغ المتبقي يجب أن يكون أكبر من أو يساوي صفر')])
    due_date = DateField('تاريخ الاستحقاق', validators=[Optional()])
    notes = TextAreaField('ملاحظات', validators=[Optional()])
    
    # حقول التأمين
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    insurance_number = StringField('رقم التأمين', validators=[Optional(), Length(max=50, message='رقم التأمين يجب أن يكون أقل من 50 حرف')])
    insurance_coverage = DecimalField('نسبة التغطية (%)', validators=[Optional(), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    
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
    
    def validate_invoice_number(self, field):
        """التحقق من عدم تكرار رقم الفاتورة"""
        from models.invoice import Invoice
        existing = Invoice.query.filter(Invoice.invoice_number == field.data).first()
        if existing:
            raise ValidationError('رقم الفاتورة مستخدم مسبقاً')

class InvoiceSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في الفواتير"""
    
    invoice_number = StringField('رقم الفاتورة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    doctor_name = StringField('اسم الطبيب', validators=[Optional()])
    amount_from = DecimalField('من مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    amount_to = DecimalField('إلى مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    status = SelectField('حالة الفاتورة', choices=[
        ('', 'جميع الحالات'),
        ('DRAFT', 'مسودة'),
        ('ISSUED', 'صادرة'),
        ('PAID', 'مدفوعة'),
        ('VOID', 'ملغاة')
    ], validators=[Optional()])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def get_status_choices(self):
        """خيارات حالة الفاتورة المطابقة للنموذج"""
        return [
            ('DRAFT', 'مسودة'),
            ('ISSUED', 'صادرة'),
            ('PAID', 'مدفوعة'),
            ('VOID', 'ملغاة'),
        ]
    
    def get_status_choices(self):
        """خيارات حالة المطالبة المطابقة للنموذج"""
        return [
            ('DRAFT', 'مسودة'),
            ('SUBMITTED', 'مقدمة'),
            ('APPROVED', 'معتمدة'),
            ('REJECTED', 'مرفوضة'),
            ('PAID', 'مدفوعة'),
        ]
    
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
        invoices = Invoice.query.filter(Invoice.status != 'PAID').all()
        def display_for(i):
            patient_name = i.visit.patient.full_name if (i.visit and i.visit.patient) else 'غير محدد'
            return f"فاتورة {i.invoice_number} - {patient_name} - {i.total_amount}"
        self.invoice_id.choices = [(i.id, display_for(i)) for i in invoices]
    
    def validate_receipt_number(self, field):
        """التحقق من عدم تكرار رقم السند"""
        from models.receipt import Receipt
        existing = Receipt.query.filter(Receipt.receipt_number == field.data).first()
        if existing:
            raise ValidationError('رقم السند مستخدم مسبقاً')

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
    refund_percentage = DecimalField('نسبة الاسترداد (%)', validators=[Optional(), NumberRange(min=0, max=100, message='نسبة الاسترداد يجب أن تكون بين 0 و 100')])
    admin_approval = BooleanField('موافقة الإدارة', default=False)
    admin_notes = TextAreaField('ملاحظات الإدارة', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_dynamic_choices()
    
    def load_dynamic_choices(self):
        """تحميل الخيارات الديناميكية"""
        # تحميل المدفوعات المكتملة
        from models.payment import Payment
        from models.payment import PaymentStatus
        payments = Payment.query.filter(Payment.status == PaymentStatus.CONFIRMED).all()
        self.original_payment_id.choices = [(p.id, f"دفع {p.id} - {p.patient.full_name} - {p.amount}") for p in payments]

class InsuranceClaimForm(FormBase, MedicalEntityMixin):
    """نموذج مطالبة التأمين"""
    
    claim_number = StringField('رقم المطالبة', validators=[DataRequired(message='رقم المطالبة مطلوب'), Length(max=50, message='رقم المطالبة يجب أن يكون أقل من 50 حرف')])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[DataRequired(message='شركة التأمين مطلوبة')])
    policy_number = StringField('رقم البوليصة', validators=[DataRequired(message='رقم البوليصة مطلوب'), Length(max=50, message='رقم البوليصة يجب أن يكون أقل من 50 حرف')])
    claim_amount = DecimalField('مبلغ المطالبة', validators=[DataRequired(message='مبلغ المطالبة مطلوب'), NumberRange(min=0.01, message='مبلغ المطالبة يجب أن يكون أكبر من صفر')])
    approved_amount = DecimalField('المبلغ المعتمد', validators=[Optional(), NumberRange(min=0, message='المبلغ المعتمد يجب أن يكون أكبر من أو يساوي صفر')])
    claim_date = DateField('تاريخ المطالبة', validators=[DataRequired(message='تاريخ المطالبة مطلوب')])
    approval_date = DateField('تاريخ الموافقة', validators=[Optional()])
    status = SelectField('الحالة', choices=[
        ('DRAFT', 'مسودة'),
        ('SUBMITTED', 'مقدمة'),
        ('APPROVED', 'معتمدة'),
        ('REJECTED', 'مرفوضة'),
        ('PAID', 'مدفوعة')
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
    
    def validate_claim_number(self, field):
        """التحقق من عدم تكرار رقم المطالبة"""
        from models.insurance import InsuranceClaim
        existing = InsuranceClaim.query.filter(InsuranceClaim.claim_number == field.data).first()
        if existing:
            raise ValidationError('رقم المطالبة مستخدم مسبقاً')

class InsuranceClaimSearchForm(SearchFormBase, DateRangeMixin):
    """نموذج البحث في مطالبات التأمين"""
    
    claim_number = StringField('رقم المطالبة', validators=[Optional()])
    patient_name = StringField('اسم المريض', validators=[Optional()])
    insurance_company_id = SelectField('شركة التأمين', coerce=int, validators=[Optional()])
    amount_from = DecimalField('من مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    amount_to = DecimalField('إلى مبلغ', validators=[Optional(), NumberRange(min=0, message='المبلغ يجب أن يكون أكبر من أو يساوي صفر')])
    
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
    coverage_percentage = DecimalField('نسبة التغطية (%)', validators=[DataRequired(message='نسبة التغطية مطلوبة'), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    max_coverage_amount = DecimalField('الحد الأقصى للتغطية', validators=[Optional(), NumberRange(min=0, message='الحد الأقصى يجب أن يكون أكبر من أو يساوي صفر')])
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
        patients = Patient.query.all()
        self.patient_id.choices = [(p.id, f"{p.full_name} - {p.national_id}") for p in patients]

class InsuranceProviderForm(FormBase):
    """نموذج مزود التأمين"""
    
    name = StringField('اسم الشركة', validators=[DataRequired(message='اسم الشركة مطلوب'), Length(max=200, message='اسم الشركة يجب أن يكون أقل من 200 حرف')])
    code = StringField('كود الشركة', validators=[DataRequired(message='كود الشركة مطلوب'), Length(max=50, message='كود الشركة يجب أن يكون أقل من 50 حرف')])
    contact_person = StringField('الشخص المسؤول', validators=[Optional(), Length(max=100, message='اسم الشخص المسؤول يجب أن يكون أقل من 100 حرف')])
    phone = StringField('الهاتف', validators=[Optional(), Length(max=20, message='رقم الهاتف يجب أن يكون أقل من 20 رقم')])
    email = StringField('البريد الإلكتروني', validators=[Optional(), Length(max=120, message='البريد الإلكتروني يجب أن يكون أقل من 120 حرف')])
    address = TextAreaField('العنوان', validators=[Optional()])
    coverage_percentage = DecimalField('نسبة التغطية الافتراضية (%)', validators=[DataRequired(message='نسبة التغطية مطلوبة'), NumberRange(min=0, max=100, message='نسبة التغطية يجب أن تكون بين 0 و 100')])
    max_coverage_amount = DecimalField('الحد الأقصى للتغطية', validators=[Optional(), NumberRange(min=0, message='الحد الأقصى يجب أن يكون أكبر من أو يساوي صفر')])
    is_active = BooleanField('نشط', default=True)
