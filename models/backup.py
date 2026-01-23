"""
نموذج النسخ الاحتياطي - Backup Model
Medical System Backup Model
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class Backup(db.Model):
    """نموذج النسخ الاحتياطي"""
    
    __tablename__ = 'backups'
    
    id = db.Column(db.Integer, primary_key=True)
    backup_name = db.Column(db.String(200), nullable=False)
    backup_type = db.Column(db.String(50), nullable=False)  # full, incremental, differential
    backup_size = db.Column(db.BigInteger, nullable=True)  # حجم النسخة بالبايت
    backup_path = db.Column(db.String(500), nullable=False)  # مسار النسخة
    backup_status = db.Column(db.String(50), nullable=False, default='PENDING')  # PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    
    # تفاصيل النسخة
    description = db.Column(db.Text, nullable=True)
    backup_notes = db.Column(db.Text, nullable=True)
    
    # معلومات الجدولة
    is_scheduled = db.Column(db.Boolean, default=False)
    schedule_type = db.Column(db.String(50), nullable=True)  # daily, weekly, monthly, custom
    schedule_cron = db.Column(db.String(100), nullable=True)  # cron expression
    next_backup = db.Column(db.DateTime, nullable=True)
    
    # معلومات الاستعادة
    restore_count = db.Column(db.Integer, default=0)
    last_restore = db.Column(db.DateTime, nullable=True)
    last_restore_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # معلومات التشفير
    is_encrypted = db.Column(db.Boolean, default=False)
    encryption_key = db.Column(db.String(500), nullable=True)  # مشفرة
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("backup_type IN ('full', 'incremental', 'differential')", name='chk_backup_type'),
        CheckConstraint("backup_status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED')", name='chk_backup_status'),
        CheckConstraint("schedule_type IN ('daily', 'weekly', 'monthly', 'custom')", name='chk_schedule_type'),
        Index('idx_backup_name', 'backup_name'),
        Index('idx_backup_type', 'backup_type'),
        Index('idx_backup_status', 'backup_status'),
        Index('idx_backup_created', 'created_at'),
        Index('idx_backup_scheduled', 'is_scheduled'),
    )
    
    # العلاقات (مبسطة)
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_backups', lazy='select')
    last_restore_user = db.relationship('User', foreign_keys=[last_restore_by], back_populates='restored_backups', lazy='select')
    logs = db.relationship('BackupLog', back_populates='backup', lazy='selectin', cascade='all, delete-orphan', passive_deletes=True)
    
    def __repr__(self):
        return f'<Backup {self.backup_name}>'
    
    def get_size_display(self):
        """الحصول على حجم النسخة للعرض"""
        if not self.backup_size:
            return "غير محدد"
        
        size = self.backup_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"
    
    def get_status_display(self):
        """الحصول على حالة النسخة للعرض"""
        status_map = {
            'PENDING': 'في الانتظار',
            'IN_PROGRESS': 'جاري التنفيذ',
            'COMPLETED': 'مكتملة',
            'FAILED': 'فشلت',
            'CANCELLED': 'ملغية'
        }
        return status_map.get(self.backup_status, self.backup_status)
    
    def get_type_display(self):
        """الحصول على نوع النسخة للعرض"""
        type_map = {
            'full': 'نسخة كاملة',
            'incremental': 'نسخة تدريجية',
            'differential': 'نسخة تفاضلية'
        }
        return type_map.get(self.backup_type, self.backup_type)
    
    def is_restorable(self):
        """التحقق من إمكانية الاستعادة"""
        return self.backup_status == 'COMPLETED' and self.backup_path
    
    def get_duration(self):
        """الحصول على مدة النسخ"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def get_duration_display(self):
        """الحصول على مدة النسخ للعرض"""
        duration = self.get_duration()
        if not duration:
            return "غير محدد"
        
        if duration < 60:
            return f"{duration:.1f} ثانية"
        elif duration < 3600:
            return f"{duration/60:.1f} دقيقة"
        else:
            return f"{duration/3600:.1f} ساعة"

class BackupLog(db.Model):
    """نموذج سجل النسخ الاحتياطي"""
    
    __tablename__ = 'backup_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    backup_id = db.Column(db.Integer, db.ForeignKey('backups.id'), nullable=False)
    log_type = db.Column(db.String(50), nullable=False)  # info, warning, error, success
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # تفاصيل إضافية
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("log_type IN ('info', 'warning', 'error', 'success', 'debug')", name='chk_log_type'),
        Index('idx_backup_log_backup', 'backup_id'),
        Index('idx_backup_log_type', 'log_type'),
        Index('idx_backup_log_created', 'created_at'),
    )
    
    # العلاقات
    backup = db.relationship('Backup', back_populates='logs', lazy='selectin')
    
    def __repr__(self):
        return f'<BackupLog {self.backup_id} - {self.log_type}>'
    
    def get_type_display(self):
        """الحصول على نوع السجل للعرض"""
        type_map = {
            'info': 'معلومات',
            'warning': 'تحذير',
            'error': 'خطأ',
            'success': 'نجح',
            'debug': 'تصحيح'
        }
        return type_map.get(self.log_type, self.log_type)
