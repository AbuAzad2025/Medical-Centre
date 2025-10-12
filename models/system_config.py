"""
نماذج تكوين النظام - System Configuration Models
Medical System Configuration Models
"""

from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class SystemConfig(db.Model):
    """نموذج تكوين النظام"""
    
    __tablename__ = 'system_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    config_key = db.Column(db.String(100), nullable=False, unique=True)
    config_value = db.Column(db.Text, nullable=True)
    config_type = db.Column(db.String(50), nullable=False)  # string, integer, boolean, json, file
    
    # معلومات إضافية
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # general, security, notification, backup, system
    is_system = db.Column(db.Boolean, default=False)  # إعدادات النظام
    is_encrypted = db.Column(db.Boolean, default=False)  # مشفرة
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("config_type IN ('string', 'integer', 'boolean', 'json', 'file', 'password')", name='chk_config_type'),
        CheckConstraint("category IN ('general', 'security', 'notification', 'backup', 'system', 'database', 'email', 'sms')", name='chk_category'),
        Index('idx_config_key', 'config_key'),
        Index('idx_config_category', 'category'),
        Index('idx_config_system', 'is_system'),
    )
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_system_configs', lazy='select')
    updater = db.relationship('User', foreign_keys=[updated_by], back_populates='updated_system_configs', lazy='select')
    
    def __repr__(self):
        return f'<SystemConfig {self.config_key}>'
    
    def get_value(self):
        """الحصول على القيمة مع التحويل"""
        if self.config_type == 'boolean':
            return self.config_value.lower() in ('true', '1', 'yes', 'on')
        elif self.config_type == 'integer':
            try:
                return int(self.config_value)
            except (ValueError, TypeError):
                return 0
        elif self.config_type == 'json':
            try:
                import json
                return json.loads(self.config_value)
            except (ValueError, TypeError):
                return {}
        else:
            return self.config_value
    
    def set_value(self, value):
        """تعيين القيمة مع التحويل"""
        if self.config_type == 'boolean':
            self.config_value = str(bool(value)).lower()
        elif self.config_type == 'integer':
            self.config_value = str(int(value))
        elif self.config_type == 'json':
            import json
            self.config_value = json.dumps(value)
        else:
            self.config_value = str(value)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'config_key': self.config_key,
            'config_value': self.config_value,
            'config_type': self.config_type,
            'description': self.description,
            'category': self.category,
            'is_system': self.is_system,
            'is_encrypted': self.is_encrypted,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'updated_by': self.updated_by,
            'updater_name': self.updater.full_name if self.updater else None
        }


# تم دمج SystemSetting مع SystemConfig لتجنب التكرار