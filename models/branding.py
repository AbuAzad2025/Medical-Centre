"""
نموذج العلامة التجارية - Branding Model
Medical System Branding Management
"""

from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin
import os

class BrandingSettings(TenantMixin, db.Model):
    """نموذج إعدادات العلامة التجارية"""
    
    __tablename__ = 'branding_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(200), nullable=False, default='المركز الصحي المتخصص')
    organization_name_en = db.Column(db.String(200), nullable=True)
    organization_address = db.Column(db.Text, nullable=True)
    organization_phone = db.Column(db.String(50), nullable=True)
    organization_email = db.Column(db.String(100), nullable=True)
    organization_website = db.Column(db.String(200), nullable=True)
    
    # الشعارات
    logo_path = db.Column(db.String(500), nullable=True)
    favicon_path = db.Column(db.String(500), nullable=True)
    watermark_path = db.Column(db.String(500), nullable=True)
    
    # الألوان
    primary_color = db.Column(db.String(7), default='#2563eb')
    secondary_color = db.Column(db.String(7), default='#10b981')
    accent_color = db.Column(db.String(7), default='#f59e0b')
    
    # ترويسة التقارير
    report_header_html = db.Column(db.Text, nullable=True)
    report_footer_html = db.Column(db.Text, nullable=True)
    
    # إعدادات إضافية
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])
    
    def __repr__(self):
        return f'<BrandingSettings {self.organization_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_name': self.organization_name,
            'organization_name_en': self.organization_name_en,
            'organization_address': self.organization_address,
            'organization_phone': self.organization_phone,
            'organization_email': self.organization_email,
            'organization_website': self.organization_website,
            'logo_path': self.logo_path,
            'favicon_path': self.favicon_path,
            'watermark_path': self.watermark_path,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color': self.accent_color,
            'report_header_html': self.report_header_html,
            'report_footer_html': self.report_footer_html,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def get_active_settings(cls):
        """الحصول على الإعدادات النشطة"""
        return cls.query.filter_by(is_active=True).first()
    
    @classmethod
    def create_default(cls, user_id):
        """إنشاء إعدادات افتراضية"""
        default_branding = cls(
            organization_name='المركز الصحي المتخصص',
            organization_name_en='Specialized Medical Center',
            organization_address='فلسطين',
            organization_phone='+970-123456789',
            organization_email='info@medical-center.com',
            created_by=user_id,
            updated_by=user_id
        )
        db.session.add(default_branding)
        db.session.commit()
        return default_branding


class SystemTheme(TenantMixin, db.Model):
    """نموذج الثيمات"""
    
    __tablename__ = 'system_themes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # ألوان الثيم
    primary_color = db.Column(db.String(7), nullable=False)
    secondary_color = db.Column(db.String(7), nullable=False)
    accent_color = db.Column(db.String(7), nullable=False)
    background_color = db.Column(db.String(7), nullable=False)
    text_color = db.Column(db.String(7), nullable=False)
    
    # إعدادات إضافية
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<SystemTheme {self.name}>'
    
    @classmethod
    def create_default_themes(cls):
        """إنشاء الثيمات الافتراضية"""
        themes = [
            {
                'name': 'Medical Blue',
                'name_ar': 'أزرق طبي',
                'description': 'ثيم أزرق مناسب للمراكز الطبية',
                'primary_color': '#2563eb',
                'secondary_color': '#10b981',
                'accent_color': '#f59e0b',
                'background_color': '#f8fafc',
                'text_color': '#1f2937'
            },
            {
                'name': 'Green Health',
                'name_ar': 'أخضر صحي',
                'description': 'ثيم أخضر للصحة والشفاء',
                'primary_color': '#059669',
                'secondary_color': '#0d9488',
                'accent_color': '#d97706',
                'background_color': '#f0fdf4',
                'text_color': '#064e3b'
            },
            {
                'name': 'Professional Gray',
                'name_ar': 'رمادي مهني',
                'description': 'ثيم رمادي مهني وأنيق',
                'primary_color': '#374151',
                'secondary_color': '#6b7280',
                'accent_color': '#f59e0b',
                'background_color': '#f9fafb',
                'text_color': '#111827'
            }
        ]
        
        for theme_data in themes:
            existing = cls.query.filter_by(name=theme_data['name']).first()
            if not existing:
                theme = cls(**theme_data)
                if theme_data['name'] == 'Medical Blue':
                    theme.is_default = True
                db.session.add(theme)
        
        db.session.commit()
