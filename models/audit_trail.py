"""
نماذج سجل التدقيق - Audit Trail Models
Medical System Audit Trail Models
"""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Index

from app.shared.mixins import TenantMixin
from app_factory import db
from utils.db_safety import safe_commit


class AuditTrail(TenantMixin, db.Model):
    """نموذج سجل التدقيق"""

    __tablename__ = 'audit_trails'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(
        db.String(50), nullable=False
    )  # user, patient, visit, appointment, payment, invoice
    entity_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create, update, delete, view, login, logout

    # المستخدم الذي قام بالعملية
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
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
        CheckConstraint(
            "entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department', 'service', 'user_session')",
            name='chk_entity_type',
        ),
        CheckConstraint(
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', 'APPROVE', 'REJECT', 'IMPERSONATE', 'PASSWORD_CHANGE', 'TERMINATE_OTHER_SESSIONS')",
            name='chk_action',
        ),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_created', 'created_at'),
    )

    # العلاقات
    # viewonly: the audit trail is append-only, and the ORM must not write to
    # it through this relationship either. The user_id column is set
    # explicitly by whoever writes the row; the relationship exists to read
    # the name of the actor, and nothing more.
    user = db.relationship('User', foreign_keys=[user_id], lazy='selectin', viewonly=True)

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
            'created_at': self.created_at.isoformat(),
        }


class SystemLog(TenantMixin, db.Model):
    """نموذج سجل النظام"""

    __tablename__ = 'system_logs'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    log_level = db.Column(db.String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_category = db.Column(
        db.String(50), nullable=False
    )  # authentication, database, payment, notification, system

    # الرسالة
    message = db.Column(db.Text, nullable=False)
    details = db.Column(db.Text, nullable=True)  # JSON string

    # المستخدم المرتبط
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    user_ip = db.Column(db.String(45), nullable=True)

    # البيانات المرتبطة
    related_entity_type = db.Column(db.String(50), nullable=True)
    related_entity_id = db.Column(db.Integer, nullable=True)

    # التواريخ
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint(
            "log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='chk_log_level'
        ),
        CheckConstraint(
            "log_category IN ('authentication', 'database', 'payment', 'notification', 'system', 'security', 'performance')",
            name='chk_log_category',
        ),
        Index('idx_log_level', 'log_level'),
        Index('idx_log_category', 'log_category'),
        Index('idx_log_user', 'user_id'),
        Index('idx_log_created', 'created_at'),
    )

    # العلاقات
    user = db.relationship(
        'User', foreign_keys=[user_id], back_populates='system_logs', lazy='selectin'
    )

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
            'created_at': self.created_at.isoformat(),
        }


class SlowQueryReport(TenantMixin, db.Model):
    __tablename__ = 'slow_query_reports'

    id = db.Column(db.Integer, primary_key=True)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)
    reset_time = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False, index=True)

    __table_args__ = (
        Index('idx_slow_query_report_period', 'period_start', 'period_end'),
        Index('idx_slow_query_report_created', 'created_at'),
    )

    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')
    entries = db.relationship(
        'SlowQueryEntry', back_populates='report', lazy='selectin', cascade='all, delete-orphan'
    )


class SlowQueryEntry(TenantMixin, db.Model):
    __tablename__ = 'slow_query_entries'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(
        db.Integer,
        db.ForeignKey('slow_query_reports.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
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


class SecurityEvent(TenantMixin, db.Model):
    """نموذج أحداث الأمان"""

    __tablename__ = 'security_events'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(
        db.String(50), nullable=False
    )  # login_failed, password_changed, permission_denied, suspicious_activity

    # تفاصيل الحدث
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # low, medium, high, critical

    # المستخدم المرتبط
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    user_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    # البيانات الإضافية
    additional_data = db.Column(db.Text, nullable=True)  # JSON string

    # الحالة
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # التواريخ
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('login_failed', 'password_changed', 'permission_denied', 'suspicious_activity', 'data_breach', 'unauthorized_access')",
            name='chk_event_type',
        ),
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='chk_severity'),
        Index('idx_security_event_type', 'event_type'),
        Index('idx_security_severity', 'severity'),
        Index('idx_security_user', 'user_id'),
        Index('idx_security_resolved', 'is_resolved'),
        Index('idx_security_created', 'created_at'),
    )

    # العلاقات
    user = db.relationship(
        'User', foreign_keys=[user_id], back_populates='security_events', lazy='selectin'
    )
    resolver = db.relationship(
        'User',
        foreign_keys=[resolved_by],
        back_populates='resolved_security_events',
        lazy='selectin',
    )

    def __repr__(self):
        return f'<SecurityEvent {self.event_type}:{self.severity} - {self.description[:50]}...>'

    def resolve(self, resolved_by_user_id, resolution_notes=None):
        """حل الحدث الأمني"""
        self.is_resolved = True
        self.resolved_by = resolved_by_user_id
        from datetime import datetime as _dt

        self.resolved_at = _dt.now(UTC)
        self.resolution_notes = resolution_notes
        safe_commit(db.session, error_message='database commit failed', reraise=True)


class LoginAttempt(TenantMixin, db.Model):
    __tablename__ = 'login_attempts'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    success = db.Column(db.Boolean, default=False, nullable=False, index=True)
    user_ip = db.Column(db.String(45), nullable=True, index=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    user = db.relationship('User', foreign_keys=[user_id], lazy='selectin')

    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'username': self.username,
            'user_id': self.user_id,
            'success': self.success,
            'user_name': self.user.full_name if self.user else None,
            'user_ip': self.user_ip,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Impersonation provenance
# ---------------------------------------------------------------------------
# While an owner is impersonating another user, current_user IS the impersonated
# user, so every audit row written during that window names them as the actor and
# the separate IMPERSONATE row is the only link back to the real operator.
# Answering "who really did this" then means correlating two tables by time.
#
# Stamp the operator onto any row flushed during an impersonated session. Doing
# it here rather than at each call site means every writer gets it, including
# ones that do not know impersonation exists.


@db.event.listens_for(db.session, 'before_flush')
def _stamp_impersonator_on_audit_rows(session, flush_context, instances):
    """Record who is really acting when the session is impersonating."""
    from flask import g, has_request_context
    from flask import session as flask_session

    impersonator_id = None
    impersonator_username = None

    if has_request_context():
        try:
            impersonator_id = flask_session.get('impersonator_id')
        except Exception:
            impersonator_id = None
        if impersonator_id is None:
            # The impersonating request has already finished by the time a later
            # row is flushed, so the request-scoped session no longer carries
            # it. The scoped session does.
            impersonator_id = session.info.get('impersonator_id')
            impersonator_username = session.info.get('impersonator_username')
        else:
            impersonator_username = getattr(g, 'impersonator_username', None)
    else:
        # No request at all - a background writer, or a caller that holds the
        # session but not the request. The scoped session is the only place
        # the impersonation is still recorded.
        impersonator_id = session.info.get('impersonator_id')
        impersonator_username = session.info.get('impersonator_username')

    if not impersonator_id:
        return

    for obj in session.new:
        if not isinstance(obj, AuditTrail):
            continue
        stamp = f'impersonated_by={impersonator_id}'
        if impersonator_username:
            stamp += f' ({impersonator_username})'
        existing = (obj.notes or '').strip()
        obj.notes = f'{existing}; {stamp}' if existing else stamp
