"""
نماذج التقارير - Report Forms
Medical System Report Forms
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from wtforms.widgets import TextArea

class MedicalReportForm(FlaskForm):
    """نموذج إضافة/تعديل التقرير الطبي"""
    
    patient_id = SelectField(
        'المريض',
        coerce=int,
        validators=[DataRequired(message='المريض مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    doctor_id = SelectField(
        'الطبيب',
        coerce=int,
        validators=[DataRequired(message='الطبيب مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    visit_id = SelectField(
        'الزيارة',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    report_type = SelectField(
        'نوع التقرير',
        choices=[
            ('diagnosis', 'تقرير تشخيص'),
            ('lab', 'تقرير مختبر'),
            ('radiology', 'تقرير أشعة'),
            ('surgery', 'تقرير جراحة'),
            ('follow_up', 'تقرير متابعة'),
            ('emergency', 'تقرير طوارئ')
        ],
        validators=[DataRequired(message='نوع التقرير مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    title = StringField(
        'عنوان التقرير',
        validators=[DataRequired(message='عنوان التقرير مطلوب'), Length(max=200)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل عنوان التقرير'}
    )
    
    content = TextAreaField(
        'محتوى التقرير',
        validators=[DataRequired(message='محتوى التقرير مطلوب'), Length(max=5000)],
        render_kw={'class': 'form-control', 'rows': 6, 'placeholder': 'أدخل محتوى التقرير'}
    )
    
    findings = TextAreaField(
        'النتائج',
        validators=[Optional(), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل النتائج'}
    )
    
    recommendations = TextAreaField(
        'التوصيات',
        validators=[Optional(), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل التوصيات'}
    )

class LabResultForm(FlaskForm):
    """نموذج إضافة/تعديل نتيجة المختبر"""
    
    patient_id = SelectField(
        'المريض',
        coerce=int,
        validators=[DataRequired(message='المريض مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    visit_id = SelectField(
        'الزيارة',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    test_name = StringField(
        'اسم الفحص',
        validators=[DataRequired(message='اسم الفحص مطلوب'), Length(max=200)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل اسم الفحص'}
    )
    
    test_code = StringField(
        'كود الفحص',
        validators=[DataRequired(message='كود الفحص مطلوب'), Length(max=50)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل كود الفحص'}
    )
    
    result_value = StringField(
        'قيمة النتيجة',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل قيمة النتيجة'}
    )
    
    normal_range = StringField(
        'المعدل الطبيعي',
        validators=[Optional(), Length(max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل المعدل الطبيعي'}
    )
    
    unit = StringField(
        'الوحدة',
        validators=[Optional(), Length(max=50)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل الوحدة'}
    )
    
    status = SelectField(
        'الحالة',
        choices=[
            ('normal', 'طبيعي'),
            ('abnormal', 'غير طبيعي'),
            ('critical', 'حرج')
        ],
        validators=[DataRequired(message='الحالة مطلوبة')],
        render_kw={'class': 'form-control'}
    )
    
    notes = TextAreaField(
        'ملاحظات',
        validators=[Optional(), Length(max=500)],
        render_kw={'class': 'form-control', 'rows': 3, 'placeholder': 'أدخل الملاحظات'}
    )

class RadiologyResultForm(FlaskForm):
    """نموذج إضافة/تعديل نتيجة الأشعة"""
    
    patient_id = SelectField(
        'المريض',
        coerce=int,
        validators=[DataRequired(message='المريض مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    visit_id = SelectField(
        'الزيارة',
        coerce=int,
        validators=[Optional()],
        render_kw={'class': 'form-control'}
    )
    
    exam_type = SelectField(
        'نوع الفحص',
        choices=[
            ('X-Ray', 'أشعة سينية'),
            ('CT', 'أشعة مقطعية'),
            ('MRI', 'رنين مغناطيسي'),
            ('Ultrasound', 'موجات فوق صوتية'),
            ('Mammography', 'تصوير الثدي'),
            ('Bone Scan', 'مسح العظام')
        ],
        validators=[DataRequired(message='نوع الفحص مطلوب')],
        render_kw={'class': 'form-control'}
    )
    
    body_part = StringField(
        'جزء الجسم',
        validators=[DataRequired(message='جزء الجسم مطلوب'), Length(max=100)],
        render_kw={'class': 'form-control', 'placeholder': 'أدخل جزء الجسم'}
    )
    
    findings = TextAreaField(
        'النتائج',
        validators=[Optional(), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل النتائج'}
    )
    
    impression = TextAreaField(
        'الانطباع',
        validators=[Optional(), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل الانطباع'}
    )
    
    recommendations = TextAreaField(
        'التوصيات',
        validators=[Optional(), Length(max=1000)],
        render_kw={'class': 'form-control', 'rows': 4, 'placeholder': 'أدخل التوصيات'}
    )
