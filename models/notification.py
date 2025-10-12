"""
نموذج الإشعارات المتطور - Advanced Notification Model
Medical System Advanced Notification Model
"""

from datetime import datetime
from sqlalchemy import Index, CheckConstraint, func
from app_factory import db
import json

# ===== النماذج الأساسية (موحدة) =====

class Notification(db.Model):
    """نموذج الإشعار المتطور"""
    
    __tablename__ = 'notifications'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # info, warning, error, success
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    
    # المستلم
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recipient_role = db.Column(db.String(50), nullable=True)
    recipient_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # المرسل
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # الحالة
    is_read = db.Column(db.Boolean, default=False)
    is_urgent = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # التوقيت
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    recipient = db.relationship('User', foreign_keys=[recipient_id], back_populates='notifications')
    sender = db.relationship('User', foreign_keys=[sender_id], back_populates='sent_notifications')
    department = db.relationship('Department', foreign_keys=[recipient_department_id])
    
    def __repr__(self):
        return f'<Notification {self.title}>'
    
    def mark_as_read(self):
        """تحديد الإشعار كمقروء"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()
    
    def is_expired(self):
        """التحقق من انتهاء صلاحية الإشعار"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'priority': self.priority,
            'recipient_id': self.recipient_id,
            'recipient_role': self.recipient_role,
            'recipient_department_id': self.recipient_department_id,
            'sender_id': self.sender_id,
            'is_read': self.is_read,
            'is_urgent': self.is_urgent,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }

class NotificationTemplate(db.Model):
    """نموذج قالب الإشعار"""
    
    __tablename__ = 'notification_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    template_type = db.Column(db.String(50), nullable=False)  # whatsapp, email, sms, push
    subject = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text, nullable=True)  # JSON format
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')
    
    def __repr__(self):
        return f'<NotificationTemplate {self.name}>'
    
    def render(self, variables=None):
        """تطبيق المتغيرات على القالب"""
        if not variables:
            variables = {}
        
        try:
            # تحليل المتغيرات المحفوظة
            template_vars = json.loads(self.variables) if self.variables else {}
            
            # دمج المتغيرات
            all_vars = {**template_vars, **variables}
            
            # تطبيق المتغيرات على المحتوى
            rendered_content = self.content
            for key, value in all_vars.items():
                rendered_content = rendered_content.replace(f'{{{key}}}', str(value))
            
            # تطبيق المتغيرات على العنوان
            rendered_subject = self.subject or ''
            for key, value in all_vars.items():
                rendered_subject = rendered_subject.replace(f'{{{key}}}', str(value))
            
            return {
                'subject': rendered_subject,
                'content': rendered_content,
                'notification_type': self.template_type
            }
        except Exception as e:
            return {
                'subject': self.subject or '',
                'content': self.content,
                'notification_type': self.template_type
            }
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'template_type': self.template_type,
            'subject': self.subject,
            'content': self.content,
            'variables': json.loads(self.variables) if self.variables else [],
            'is_active': self.is_active,
            'is_system': self.is_system,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class NotificationQueue(db.Model):
    """نموذج طابور الإشعارات"""
    
    __tablename__ = 'notification_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('notification_templates.id'), nullable=True)
    notification_type = db.Column(db.String(50), nullable=False)  # whatsapp, email, sms, push
    recipient = db.Column(db.String(200), nullable=False)  # phone, email, etc.
    subject = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text, nullable=True)  # JSON format
    priority = db.Column(db.String(50), default='normal')  # low, normal, high, urgent
    status = db.Column(db.String(50), default='pending')  # pending, sent, failed, cancelled
    scheduled_at = db.Column(db.DateTime, nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # العلاقات
    user = db.relationship('User', backref='notification_queue')
    template = db.relationship('NotificationTemplate', backref='queue_items')
    
    def __repr__(self):
        return f'<NotificationQueue {self.id}>'
    
    def get_notification_type_display(self):
        """نوع الإشعار للعرض"""
        type_map = {
            'whatsapp': 'واتساب',
            'email': 'بريد إلكتروني',
            'sms': 'رسالة نصية',
            'push': 'إشعار فوري'
        }
        return type_map.get(self.notification_type, self.notification_type)
    
    def get_priority_display(self):
        """أولوية الإشعار للعرض"""
        priority_map = {
            'low': 'منخفضة',
            'normal': 'عادية',
            'high': 'عالية',
            'urgent': 'عاجلة'
        }
        return priority_map.get(self.priority, self.priority)
    
    def get_status_display(self):
        """حالة الإشعار للعرض"""
        status_map = {
            'pending': 'في الانتظار',
            'sent': 'تم الإرسال',
            'failed': 'فشل الإرسال',
            'cancelled': 'ملغي'
        }
        return status_map.get(self.status, self.status)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'template_id': self.template_id,
            'notification_type': self.notification_type,
            'recipient': self.recipient,
            'subject': self.subject,
            'content': self.content,
            'variables': json.loads(self.variables) if self.variables else {},
            'priority': self.priority,
            'status': self.status,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class WhatsAppMessage(db.Model):
    """نموذج رسائل الواتساب"""
    
    __tablename__ = 'whatsapp_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default='text')  # text, template, media
    template_name = db.Column(db.String(100), nullable=True)
    media_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WhatsAppMessage {self.phone_number}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'message_content': self.message_content,
            'message_type': self.message_type,
            'template_name': self.template_name,
            'media_url': self.media_url,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class EmailMessage(db.Model):
    """نموذج رسائل البريد الإلكتروني"""
    
    __tablename__ = 'email_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(50), default='text/html')  # text/plain, text/html
    attachments = db.Column(db.Text, nullable=True)  # JSON format
    status = db.Column(db.String(20), default='pending')  # pending, sent, delivered, failed
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailMessage {self.recipient_email}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'recipient_email': self.recipient_email,
            'subject': self.subject,
            'content': self.content,
            'content_type': self.content_type,
            'attachments': json.loads(self.attachments) if self.attachments else [],
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'failed_at': self.failed_at.isoformat() if self.failed_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
