"""
نماذج إدارة الملفات - File Management Models
Medical System File Management Models
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db
from app.shared.mixins import TenantMixin
import os
import hashlib
import mimetypes

class FileUpload(db.Model):
    """نموذج رفع الملفات"""
    
    __tablename__ = 'file_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_hash = db.Column(db.String(64), nullable=True)  # SHA-256
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(100), nullable=False)  # MIME type
    file_extension = db.Column(db.String(10), nullable=False)
    
    # معلومات إضافية
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # comma-separated tags
    is_public = db.Column(db.Boolean, default=False)
    is_encrypted = db.Column(db.Boolean, default=False)
    
    # الكيان المرتبط
    related_entity_type = db.Column(db.String(50), nullable=True)  # patient, visit, appointment, lab_result, radiology_result
    related_entity_id = db.Column(db.Integer, nullable=True)
    
    # المستخدم
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # التواريخ
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_accessed = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("file_size > 0", name='chk_file_size'),
        CheckConstraint("related_entity_type IN ('patient', 'visit', 'appointment', 'lab_result', 'radiology_result', 'user', 'system')", name='chk_related_entity_type'),
        Index('idx_file_filename', 'filename'),
        Index('idx_file_type', 'file_type'),
        Index('idx_file_entity', 'related_entity_type', 'related_entity_id'),
        Index('idx_file_uploader', 'uploaded_by'),
        Index('idx_file_uploaded', 'uploaded_at'),
        Index('idx_file_expires', 'expires_at'),
    )
    
    # العلاقات
    uploader = db.relationship('User', foreign_keys=[uploaded_by], back_populates='uploaded_files', lazy='selectin')
    permissions = db.relationship('FilePermission', back_populates='file', lazy='dynamic', cascade='all, delete-orphan')
    task_attachments = db.relationship('TaskAttachment', back_populates='file', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<FileUpload {self.original_filename}>'
    
    def get_file_hash(self):
        """الحصول على hash الملف"""
        try:
            with open(self.file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None
    
    def is_expired(self):
        """هل انتهت صلاحية الملف"""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False
    
    def get_file_url(self):
        """الحصول على رابط الملف"""
        return f"/files/{self.id}"
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'file_extension': self.file_extension,
            'description': self.description,
            'tags': self.tags.split(',') if self.tags else [],
            'is_public': self.is_public,
            'is_encrypted': self.is_encrypted,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'uploaded_by': self.uploaded_by,
            'uploader_name': self.uploader.full_name if self.uploader else None,
            'uploaded_at': self.uploaded_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'file_url': self.get_file_url()
        }


class FileCategory(TenantMixin, db.Model):
    """نموذج فئات الملفات"""
    
    __tablename__ = 'file_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    # إعدادات الفئة
    allowed_extensions = db.Column(db.String(500), nullable=True)  # comma-separated extensions
    max_file_size = db.Column(db.Integer, nullable=True)  # in bytes
    is_active = db.Column(db.Boolean, default=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("max_file_size > 0", name='chk_max_file_size'),
        Index('idx_category_name', 'name'),
        Index('idx_category_active', 'is_active'),
    )
    
    # العلاقات
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_file_categories', lazy='selectin')
    
    def __repr__(self):
        return f'<FileCategory {self.name_ar}>'
    
    def get_allowed_extensions(self):
        """الحصول على الامتدادات المسموحة"""
        if self.allowed_extensions:
            return [ext.strip() for ext in self.allowed_extensions.split(',')]
        return []
    
    def set_allowed_extensions(self, extensions):
        """تعيين الامتدادات المسموحة"""
        if isinstance(extensions, list):
            self.allowed_extensions = ','.join(extensions)
        else:
            self.allowed_extensions = extensions
    
    def is_extension_allowed(self, extension):
        """التحقق من السماح بالامتداد"""
        allowed = self.get_allowed_extensions()
        if not allowed:
            return True
        return extension.lower() in [ext.lower() for ext in allowed]
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'allowed_extensions': self.get_allowed_extensions(),
            'max_file_size': self.max_file_size,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None
        }


class FilePermission(TenantMixin, db.Model):
    """نموذج صلاحيات الملفات"""
    
    __tablename__ = 'file_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('file_uploads.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)  # None = جميع المستخدمين
    role = db.Column(db.String(50), nullable=True)  # دور المستخدم
    
    # الصلاحيات
    can_view = db.Column(db.Boolean, default=False)
    can_download = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    
    # التواريخ
    granted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_file_permission_file', 'file_id'),
        Index('idx_file_permission_user', 'user_id'),
        Index('idx_file_permission_role', 'role'),
        Index('idx_file_permission_granted', 'granted_at'),
        Index('idx_file_permission_expires', 'expires_at'),
    )
    
    # العلاقات
    file = db.relationship('FileUpload', back_populates='permissions', lazy='selectin')
    user = db.relationship('User', foreign_keys=[user_id], back_populates='file_permissions', lazy='selectin')
    granter = db.relationship('User', foreign_keys=[granted_by], back_populates='granted_file_permissions', lazy='selectin')
    
    def __repr__(self):
        return f'<FilePermission {self.file.original_filename if self.file else "Unknown"}>'
    
    def is_expired(self):
        """هل انتهت صلاحية الصلاحية"""
        if self.expires_at:
            return datetime.now(timezone.utc) > self.expires_at
        return False
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'role': self.role,
            'can_view': self.can_view,
            'can_download': self.can_download,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'granted_at': self.granted_at.isoformat(),
            'granted_by': self.granted_by,
            'granter_name': self.granter.full_name if self.granter else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired()
        }
