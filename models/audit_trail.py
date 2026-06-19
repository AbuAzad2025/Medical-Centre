"""
نماذج سجل التدقيق - Audit Trail Models
Medical System Audit Trail Models
"""

from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class AuditTrail(db.Model):
    """نموذج سجل التدقيق"""
    
    __tablename__ = 'audit_trails'
    
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)  # user, patient, visit, appointment, payment, invoice
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, view, login, logout
    
    # المستخدم الذي قام بالعملية
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_ip = db.Column(db.String(45), nullable=True)  # IP address
    user_agent = db.Column(db.Text, nullable=True)  # User agent string
    
    # البيانات القديمة والجديدة
    old_values = db.Column(db.Text, nullable=True)  # JSON string
    new_values = db.Column(db.Text, nullable=True)  # JSON string
    
    # تفاصيل إضافية
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department')", name='chk_entity_type'),
        CheckConstraint("action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access')", name='chk_action'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_created', 'created_at'),
    )
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], back_populates='audit_trails', lazy='selectin')
    
    def __repr__(self):
        return f'<AuditTrail {self.entity_type}:{self.entity_id} - {self.action}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'action': self.action,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'user_ip': self.user_ip,
            'user_agent': self.user_agent,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'description': self.description,
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }


class SystemLog(db.Model):
    """نموذج سجل النظام"""
    
    __tablename__ = 'system_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    log_level = db.Column(db.String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_category = db.Column(db.String(50), nullable=False)  # authentication, database, payment, notification, system
    
    # الرسالة
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # JSON string
    
    # المستخدم المرتبط
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_ip = db.Column(db.String(45), nullable=True)
    
    # البيانات المرتبطة
    related_entity_type = db.Column(db.String(50), nullable=True)
    related_entity_id = db.Column(db.Integer, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='chk_log_level'),
        CheckConstraint("log_category IN ('authentication', 'database', 'payment', 'notification', 'system', 'security', 'performance')", name='chk_log_category'),
        Index('idx_log_level', 'log_level'),
        Index('idx_log_category', 'log_category'),
        Index('idx_log_user', 'user_id'),
        Index('idx_log_created', 'created_at'),
    )
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], back_populates='system_logs', lazy='selectin')
    
    def __repr__(self):
        return f'<SystemLog {self.log_level}:{self.log_category} - {self.message[:50]}...>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'log_level': self.log_level,
            'log_category': self.log_category,
            'message': self.message,
            'details': self.details,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'user_ip': self.user_ip,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'created_at': self.created_at.isoformat()
        }


class SlowQueryReport(db.Model):
    __tablename__ = 'slow_query_reports'

    id = db.Column(db.Integer, primary_key=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    reset_time = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False, index=True)

    __table_args__ = (
        Index('idx_slow_query_report_period', 'period_start', 'period_end'),
        Index('idx_slow_query_report_created', 'created_at'),
    )

    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')
    entries = db.relationship('SlowQueryEntry', back_populates='report', lazy='selectin', cascade='all, delete-orphan')


class SlowQueryEntry(db.Model):
    __tablename__ = 'slow_query_entries'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('slow_query_reports.id', ondelete='CASCADE'), nullable=False, index=True)
    query = db.Column(db.Text, nullable=False)
    calls = db.Column(db.Integer, default=0, nullable=False)
    total_time = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    mean_time = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    rows = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        Index('idx_slow_query_entry_report', 'report_id'),
        Index('idx_slow_query_entry_mean', 'mean_time'),
    )

    report = db.relationship('SlowQueryReport', back_populates='entries', lazy='selectin')


class SecurityEvent(db.Model):
    """نموذج أحداث الأمان"""
    
    __tablename__ = 'security_events'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # login_failed, password_changed, permission_denied, suspicious_activity
    
    # تفاصيل الحدث
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # low, medium, high, critical
    
    # المستخدم المرتبط
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    user_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    
    # البيانات الإضافية
    additional_data = db.Column(db.Text, nullable=True)  # JSON string
    
    # الحالة
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("event_type IN ('login_failed', 'password_changed', 'permission_denied', 'suspicious_activity', 'data_breach', 'unauthorized_access')", name='chk_event_type'),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='chk_severity'),
        Index('idx_security_event_type', 'event_type'),
        Index('idx_security_severity', 'severity'),
        Index('idx_security_user', 'user_id'),
        Index('idx_security_resolved', 'is_resolved'),
        Index('idx_security_created', 'created_at'),
    )
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], back_populates='security_events', lazy='selectin')
    resolver = db.relationship('User', foreign_keys=[resolved_by], back_populates='resolved_security_events', lazy='selectin')
    
    def __repr__(self):
        return f'<SecurityEvent {self.event_type}:{self.severity} - {self.description[:50]}...>'
    
    def resolve(self, resolved_by_user_id, resolution_notes=None):
        """حل الحدث الأمني"""
        self.is_resolved = True
        self.resolved_by = resolved_by_user_id
        from datetime import timezone, datetime as _dt
        self.resolved_at = _dt.now(timezone.utc)
        self.resolution_notes = resolution_notes
        db.session.commit()


class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    success = db.Column(db.Boolean, default=False, nullable=False, index=True)
    user_ip = db.Column(db.String(45), nullable=True, index=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = db.relationship('User', foreign_keys=[user_id], lazy='selectin')
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'description': self.description,
            'severity': self.severity,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'user_ip': self.user_ip,
            'user_agent': self.user_agent,
            'additional_data': self.additional_data,
            'is_resolved': self.is_resolved,
            'resolved_by': self.resolved_by,
            'resolver_name': self.resolver.full_name if self.resolver else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat()
        }
