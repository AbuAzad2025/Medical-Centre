"""
نموذج تكامل الواتساب - WhatsApp Integration Models
Medical System WhatsApp Integration Models
"""

from datetime import datetime
from app_factory import db
import secrets
import string

class WhatsAppMessage(db.Model):
    """نموذج رسالة الواتساب"""
    
    __tablename__ = 'whatsapp_integration_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(100), unique=True, nullable=False)
    
    # معلومات المرسل
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    sent_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # معلومات الرسالة
    phone_number = db.Column(db.String(20), nullable=False)
    message_type = db.Column(db.String(50), nullable=False)  # report, appointment, reminder, etc.
    message_content = db.Column(db.Text, nullable=False)
    template_id = db.Column(db.String(100), nullable=True)
    
    # المرفقات
    attachment_type = db.Column(db.String(50), nullable=True)  # pdf, image, document
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_name = db.Column(db.String(200), nullable=True)
    
    # حالة الرسالة
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, read, failed
    whatsapp_message_id = db.Column(db.String(100), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    patient = db.relationship('Patient', backref='whatsapp_messages')
    sent_by_user = db.relationship('User', backref='sent_whatsapp_messages')
    
    def __repr__(self):
        return f'<WhatsAppMessage {self.message_id}>'
    
    @staticmethod
    def generate_message_id():
        """توليد معرف الرسالة"""
        while True:
            msg_id = f"WA{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.randbelow(1000):03d}"
            if not WhatsAppMessage.query.filter_by(message_id=msg_id).first():
                return msg_id
    
    def get_status_display(self):
        """حالة الرسالة للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'sent': 'تم الإرسال',
            'delivered': 'تم التسليم',
            'read': 'تم القراءة',
            'failed': 'فشل الإرسال'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'pending': 'warning',
            'sent': 'info',
            'delivered': 'primary',
            'read': 'success',
            'failed': 'danger'
        }
        return color_map.get(self.status, 'secondary')
    
    def get_message_type_display(self):
        """نوع الرسالة للعرض"""
        type_map = {
            'report': 'تقرير طبي',
            'appointment': 'موعد',
            'reminder': 'تذكير',
            'prescription': 'روشيتة',
            'lab_result': 'نتيجة مختبر',
            'radiology_result': 'نتيجة أشعة',
            'general': 'عام'
        }
        return type_map.get(self.message_type, self.message_type)
    
    def is_successful(self):
        """هل نجح الإرسال"""
        return self.status in ['sent', 'delivered', 'read']
    
    def is_failed(self):
        """هل فشل الإرسال"""
        return self.status == 'failed'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name if self.patient else None,
            'sent_by': self.sent_by,
            'sent_by_name': self.sent_by_user.full_name if self.sent_by_user else None,
            'phone_number': self.phone_number,
            'message_type': self.message_type,
            'message_type_display': self.get_message_type_display(),
            'message_content': self.message_content,
            'template_id': self.template_id,
            'attachment_type': self.attachment_type,
            'attachment_url': self.attachment_url,
            'attachment_name': self.attachment_name,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'whatsapp_message_id': self.whatsapp_message_id,
            'error_message': self.error_message,
            'is_successful': self.is_successful(),
            'is_failed': self.is_failed(),
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None
        }

class WhatsAppTemplate(db.Model):
    """نموذج قالب الواتساب"""
    
    __tablename__ = 'whatsapp_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    template_name = db.Column(db.String(100), nullable=False, unique=True)
    template_id = db.Column(db.String(100), nullable=False, unique=True)
    message_type = db.Column(db.String(50), nullable=False)
    
    # محتوى القالب
    header_text = db.Column(db.Text, nullable=True)
    body_text = db.Column(db.Text, nullable=False)
    footer_text = db.Column(db.Text, nullable=True)
    
    # متغيرات القالب
    variables = db.Column(db.Text, nullable=True)  # JSON string of variables
    
    # حالة القالب
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    is_active = db.Column(db.Boolean, default=True)
    
    # تواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<WhatsAppTemplate {self.template_name}>'
    
    def get_status_display(self):
        """حالة القالب للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'approved': 'معتمد',
            'rejected': 'مرفوض'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'pending': 'warning',
            'approved': 'success',
            'rejected': 'danger'
        }
        return color_map.get(self.status, 'secondary')
    
    def is_approved(self):
        """هل القالب معتمد"""
        return self.status == 'approved' and self.is_active
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'template_name': self.template_name,
            'template_id': self.template_id,
            'message_type': self.message_type,
            'header_text': self.header_text,
            'body_text': self.body_text,
            'footer_text': self.footer_text,
            'variables': self.variables,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'is_active': self.is_active,
            'is_approved': self.is_approved(),
            'created_at': self.created_at.isoformat(),
            'approved_at': self.approved_at.isoformat() if self.approved_at else None
        }

class WhatsAppConfig(db.Model):
    """نموذج إعدادات الواتساب"""
    
    __tablename__ = 'whatsapp_config'
    
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(100), nullable=False, unique=True)
    config_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<WhatsAppConfig {self.config_key}>'
    
    @staticmethod
    def get_config(key, default=None):
        """الحصول على إعداد"""
        config = WhatsAppConfig.query.filter_by(config_key=key).first()
        if config:
            return config.config_value
        return default
    
    @staticmethod
    def set_config(key, value, description=None, is_encrypted=False):
        """تعيين إعداد"""
        config = WhatsAppConfig.query.filter_by(config_key=key).first()
        if config:
            config.config_value = value
            config.description = description
            config.is_encrypted = is_encrypted
            config.updated_at = datetime.utcnow()
        else:
            config = WhatsAppConfig(
                config_key=key,
                config_value=value,
                description=description,
                is_encrypted=is_encrypted
            )
            db.session.add(config)
        
        db.session.commit()
        return config
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'description': self.description,
            'is_encrypted': self.is_encrypted,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
