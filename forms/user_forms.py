"""
نماذج المستخدمين - User Forms
Medical System User Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, TelField, EmailField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional

class LoginForm(FlaskForm):
    """نموذج تسجيل الدخول"""
    
    username = StringField(
        'اسم المستخدم',
        validators=[DataRequired(message='اسم المستخدم مطلوب')],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل اسم المستخدم'}
    )
    
    password = PasswordField(
        'كلمة المرور',
        validators=[DataRequired(message='كلمة المرور مطلوبة')],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل كلمة المرور'}
    )
    
    remember_me = BooleanField(
        'تذكرني',
        render_kw={'class': 'form-check-input'}
    )

class UserForm(FlaskForm):
    """نموذج إضافة/تعديل المستخدم"""
    
    username = StringField(
        'اسم المستخدم',
        validators=[DataRequired(message='اسم المستخدم مطلوب'), Length(min=3, max=50)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل اسم المستخدم'}
    )
    
    full_name = StringField(
        'الاسم الكامل',
        validators=[DataRequired(message='الاسم الكامل مطلوب'), Length(min=2, max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل الاسم الكامل'}
    )
    
    email = EmailField(
        'البريد الإلكتروني',
        validators=[DataRequired(message='البريد الإلكتروني مطلوب'), Email(message='بريد إلكتروني غير صحيح')],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل البريد الإلكتروني'}
    )
    
    phone = TelField(
        'رقم الهاتف',
        validators=[Optional(), Length(min=10, max=15)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل رقم الهاتف'}
    )
    
    role = SelectField(
        'الدور',
        choices=[
            ('admin', 'مدير النظام'),
            ('manager', 'مدير المركز'),
            ('doctor', 'طبيب'),
            ('nurse', 'ممرض'),
            ('reception', 'موظف استقبال'),
            ('lab', 'فني مختبر'),
            ('radiology', 'فني أشعة'),
            ('emergency', 'طوارئ'),
            ('accountant', 'محاسب')
        ],
        validators=[DataRequired(message='الدور مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    department = StringField(
        'القسم',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل القسم'}
    )
    
    is_active = BooleanField(
        'نشط',
        render_kw={'class': 'form-check-input'}
    )

class ChangePasswordForm(FlaskForm):
    """نموذج تغيير كلمة المرور"""
    
    current_password = PasswordField(
        'كلمة المرور الحالية',
        validators=[DataRequired(message='كلمة المرور الحالية مطلوبة')],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل كلمة المرور الحالية'}
    )
    
    new_password = PasswordField(
        'كلمة المرور الجديدة',
        validators=[
            DataRequired(message='كلمة المرور الجديدة مطلوبة'),
            Length(min=6, message='كلمة المرور يجب أن تكون 6 أحرف على الأقل')
        ],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل كلمة المرور الجديدة'}
    )
    
    confirm_password = PasswordField(
        'تأكيد كلمة المرور',
        validators=[
            DataRequired(message='تأكيد كلمة المرور مطلوب'),
            EqualTo('new_password', message='كلمة المرور غير متطابقة')
        ],
        render_kw={'class': 'form-control', 'placeholder': 'أعد إدخال كلمة المرور الجديدة'}
    )
