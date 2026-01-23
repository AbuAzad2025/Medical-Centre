"""
نماذج المدفوعات - Payment Forms
Medical System Payment Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DecimalField, DateField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from wtforms.widgets import TextArea

class PaymentForm(FlaskForm):
    """نموذج إضافة/تعديل المدفوعات"""
    
    visit_id = SelectField(
        'الزيارة',
        coerce=int,
        validators=[DataRequired(message='الزيارة مطلوبة')],
        render_kw={'class': 'form-control'}
    )
    
    amount = DecimalField(
        'المبلغ',
        validators=[DataRequired(message='المبلغ مطلوب'), NumberRange(min=0.01)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل المبلغ'}
    )
    
    payment_method = SelectField(
        'طريقة الدفع',
        choices=[
            ('CASH', 'نقدي'),
            ('CARD', 'بطاقة'),
            ('WIRE', 'تحويل'),
            ('INSURANCE', 'تأمين'),
            ('FORCE', 'قسري')
        ],
        validators=[DataRequired(message='طريقة الدفع مطلوبة')],
        render_kw={'class': 'form-control'}
    )
    
    payment_date = DateField(
        'تاريخ الدفع',
        validators=[DataRequired(message='تاريخ الدفع مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    reference_number = StringField(
        'رقم المرجع',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل رقم المرجع'}
    )
    
    notes = TextAreaField(
        'ملاحظات',
        validators=[Optional(), Length(max=500)],
        render_kw={'class': 'form-control', 'rows': 3, 'placeholder': 'أدخل الملاحظات'}
    )

class PaymentSearchForm(FlaskForm):
    """نموذج البحث في المدفوعات"""
    
    search_query = StringField(
        'كلمة البحث',
        validators=[Optional()],
        render_kw={'class': 'form-control', 'placeholder': 'ابحث بالاسم أو رقم المرجع'}
    )
    
    payment_method = SelectField(
        'طريقة الدفع',
        choices=[
            ('', 'جميع الطرق'),
            ('CASH', 'نقدي'),
            ('CARD', 'بطاقة'),
            ('WIRE', 'تحويل'),
            ('INSURANCE', 'تأمين'),
            ('FORCE', 'قسري')
        ],
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    status = SelectField(
        'الحالة',
        choices=[
            ('', 'جميع الحالات'),
            ('PENDING', 'معلق'),
            ('CONFIRMED', 'مؤكد'),
            ('CANCELLED', 'ملغي'),
            ('REFUNDED', 'مسترد')
        ],
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    date_from = DateField(
        'من تاريخ',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    date_to = DateField(
        'إلى تاريخ',
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    amount_from = DecimalField(
        'المبلغ من',
        validators=[Optional(), NumberRange(min=0)],
        render_kw={'class': 'form-control', 'placeholder': 'المبلغ من'}
    )
    
    amount_to = DecimalField(
        'المبلغ إلى',
        validators=[Optional(), NumberRange(min=0)],
        render_kw={'class': 'form-control', 'placeholder': 'المبلغ إلى'}
    )
