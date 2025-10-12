"""
نماذج الإشعارات - Notification Forms
Medical System Notification Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField
from wtforms.validators import DataRequired, Length, Optional
from wtforms.widgets import TextArea

class NotificationForm(FlaskForm):
    """نموذج إضافة/تعديل الإشعار"""
    
    title = StringField(
        'عنوان الإشعار',
        validators=[DataRequired(message='عنوان الإشعار مطلوب'), Length(max=200)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل عنوان الإشعار'}
    )
    
    content = TextAreaField(
        'محتوى الإشعار',
        validators=[DataRequired(message='محتوى الإشعار مطلوب'), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل محتوى الإشعار'}
    )
    
    notification_type = SelectField(
        'نوع الإشعار',
        choices=[
            ('info', 'معلومات'),
            ('warning', 'تحذير'),
            ('error', 'خطأ'),
            ('success', 'نجاح'),
            ('reminder', 'تذكير'),
            ('alert', 'تنبيه')
        ],
        validators=[DataRequired(message='نوع الإشعار مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    priority = SelectField(
        'الأولوية',
        choices=[
            ('low', 'منخفضة'),
            ('normal', 'عادية'),
            ('high', 'عالية'),
            ('urgent', 'عاجلة')
        ],
        validators=[DataRequired(message='الأولوية مطلوبة')],
        render_kw={'class': 'form-control'}
    )
    
    is_active = BooleanField(
        'نشط',
        render_kw={'class': 'form-check-input'}
    )

class NotificationTemplateForm(FlaskForm):
    """نموذج إضافة/تعديل قالب الإشعار"""
    
    name = StringField(
        'اسم القالب',
        validators=[DataRequired(message='اسم القالب مطلوب'), Length(max=200)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل اسم القالب'}
    )
    
    template_type = SelectField(
        'نوع القالب',
        choices=[
            ('whatsapp', 'واتساب'),
            ('email', 'بريد إلكتروني'),
            ('sms', 'رسالة نصية'),
            ('push', 'إشعار فوري')
        ],
        validators=[DataRequired(message='نوع القالب مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    subject = StringField(
        'الموضوع',
        validators=[Optional(), Length(max=200)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل الموضوع'}
    )
    
    content = TextAreaField(
        'محتوى القالب',
        validators=[DataRequired(message='محتوى القالب مطلوب'), Length(max=2000)],
        render_kw={'class': 'form-control', 'rows': 6, 'placeholder': 'أدخل محتوى القالب'}
    )
    
    variables = TextAreaField(
        'المتغيرات',
        validators=[Optional(), Length(max=500)],
        render_kw={'class': 'form-control', 'rows': 3, 'placeholder': 'أدخل المتغيرات (JSON)'}
    )
    
    is_active = BooleanField(
        'نشط',
        render_kw={'class': 'form-check-input'}
    )
