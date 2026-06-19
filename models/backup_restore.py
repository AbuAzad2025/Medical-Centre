"""
Backup Restore Log and Operations
"""
from datetime import datetime, timezone
from app_factory import db

class BackupRestoreLog(db.Model):
    __tablename__ = 'backup_restore_logs'

    id = db.Column(db.Integer, primary_key=True)
    backup_id = db.Column(db.Integer, db.ForeignKey('backups.id', ondelete='SET NULL'), nullable=True, index=True)

    operation = db.Column(db.String(20), nullable=False, index=True)  # restore | verify | delete
    status = db.Column(db.String(20), nullable=False, index=True)  # pending | running | success | failed | cancelled
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    source_path = db.Column(db.String(500), nullable=True)
    target_path = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON log of operations

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    backup = db.relationship('Backup', lazy='selectin')
    initiator = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<BackupRestoreLog {self.operation} {self.status}>"
