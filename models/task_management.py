"""
نماذج إدارة المهام - Task Management Models
Medical System Task Management Models
"""

from datetime import datetime, timedelta
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class Task(db.Model):
    """نموذج المهام"""
    
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    task_type = db.Column(db.String(50), nullable=False)  # patient_care, administrative, maintenance, emergency
    
    # الحالة
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, in_progress, completed, cancelled
    priority = db.Column(db.String(20), nullable=False, default='medium')  # low, medium, high, urgent
    
    # التعيين
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # الكيان المرتبط
    related_entity_type = db.Column(db.String(50), nullable=True)  # patient, visit, appointment, department
    related_entity_id = db.Column(db.Integer, nullable=True)
    
    # التواريخ
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("task_type IN ('patient_care', 'administrative', 'maintenance', 'emergency', 'follow_up', 'reporting')", name='chk_task_type'),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'cancelled', 'on_hold')", name='chk_task_status'),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name='chk_task_priority'),
        Index('idx_task_title', 'title'),
        Index('idx_task_status', 'status'),
        Index('idx_task_priority', 'priority'),
        Index('idx_task_assigned', 'assigned_to'),
        Index('idx_task_entity', 'related_entity_type', 'related_entity_id'),
        Index('idx_task_due', 'due_date'),
        Index('idx_task_created', 'created_at'),
    )
    
    # العلاقات
    assignee = db.relationship('User', foreign_keys=[assigned_to], back_populates='assigned_tasks', lazy='select')
    assigner = db.relationship('User', foreign_keys=[assigned_by], back_populates='created_tasks', lazy='select')
    comments = db.relationship('TaskComment', back_populates='task', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('TaskAttachment', back_populates='task', lazy='dynamic', cascade='all, delete-orphan')
    project_tasks = db.relationship('ProjectTask', back_populates='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    def is_overdue(self):
        """هل المهمة متأخرة"""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return datetime.utcnow() > self.due_date
        return False
    
    def get_remaining_time(self):
        """الحصول على الوقت المتبقي"""
        if self.due_date and self.status not in ['completed', 'cancelled']:
            remaining = self.due_date - datetime.utcnow()
            if remaining.total_seconds() > 0:
                return remaining
        return None
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'status': self.status,
            'priority': self.priority,
            'assigned_to': self.assigned_to,
            'assignee_name': self.assignee.full_name if self.assignee else None,
            'assigned_by': self.assigned_by,
            'assigner_name': self.assigner.full_name if self.assigner else None,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_overdue': self.is_overdue(),
            'remaining_time': self.get_remaining_time().total_seconds() if self.get_remaining_time() else None
        }


class TaskComment(db.Model):
    """نموذج تعليقات المهام"""
    
    __tablename__ = 'task_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    comment_type = db.Column(db.String(20), nullable=False, default='comment')  # comment, update, status_change
    
    # المستخدم
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("comment_type IN ('comment', 'update', 'status_change', 'priority_change')", name='chk_comment_type'),
        Index('idx_task_comment_task', 'task_id'),
        Index('idx_task_comment_user', 'user_id'),
        Index('idx_task_comment_created', 'created_at'),
    )
    
    # العلاقات
    task = db.relationship('Task', back_populates='comments', lazy='select')
    user = db.relationship('User', foreign_keys=[user_id], back_populates='task_comments', lazy='select')
    
    def __repr__(self):
        return f'<TaskComment {self.id}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'comment': self.comment,
            'comment_type': self.comment_type,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'created_at': self.created_at.isoformat()
        }


class TaskAttachment(db.Model):
    """نموذج مرفقات المهام"""
    
    __tablename__ = 'task_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('file_uploads.id'), nullable=False)
    
    # التواريخ
    attached_at = db.Column(db.DateTime, default=datetime.utcnow)
    attached_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_task_attachment_task', 'task_id'),
        Index('idx_task_attachment_file', 'file_id'),
        Index('idx_task_attachment_user', 'attached_by'),
    )
    
    # العلاقات
    task = db.relationship('Task', back_populates='attachments', lazy='select')
    file = db.relationship('FileUpload', back_populates='task_attachments', lazy='select')
    attacher = db.relationship('User', foreign_keys=[attached_by], back_populates='task_attachments', lazy='select')
    
    def __repr__(self):
        return f'<TaskAttachment {self.id}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'file_id': self.file_id,
            'file_name': self.file.original_filename if self.file else None,
            'attached_at': self.attached_at.isoformat(),
            'attached_by': self.attached_by,
            'attacher_name': self.attacher.full_name if self.attacher else None
        }


class Project(db.Model):
    """نموذج المشاريع"""
    
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    project_type = db.Column(db.String(50), nullable=False)  # system_upgrade, maintenance, new_feature, emergency
    
    # الحالة
    status = db.Column(db.String(50), nullable=False, default='planning')  # planning, in_progress, completed, cancelled
    priority = db.Column(db.String(20), nullable=False, default='medium')  # low, medium, high, urgent
    
    # المسؤول
    project_manager = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # التواريخ
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("project_type IN ('system_upgrade', 'maintenance', 'new_feature', 'emergency', 'training', 'compliance')", name='chk_project_type'),
        CheckConstraint("status IN ('planning', 'in_progress', 'completed', 'cancelled', 'on_hold')", name='chk_project_status'),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'urgent')", name='chk_project_priority'),
        Index('idx_project_name', 'name'),
        Index('idx_project_status', 'status'),
        Index('idx_project_priority', 'priority'),
        Index('idx_project_manager', 'project_manager'),
        Index('idx_project_created', 'created_at'),
    )
    
    # العلاقات
    manager = db.relationship('User', foreign_keys=[project_manager], back_populates='managed_projects', lazy='select')
    creator = db.relationship('User', foreign_keys=[created_by], back_populates='created_projects', lazy='select')
    tasks = db.relationship('ProjectTask', back_populates='project', lazy='dynamic', cascade='all, delete-orphan')
    members = db.relationship('ProjectMember', back_populates='project', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Project {self.name}>'
    
    def get_progress(self):
        """الحصول على تقدم المشروع"""
        try:
            total_tasks = self.tasks.count()
            if total_tasks == 0:
                return 0
            
            completed_tasks = self.tasks.filter_by(status='completed').count()
            return (completed_tasks / total_tasks) * 100
        except Exception:
            return 0
    
    def is_overdue(self):
        """هل المشروع متأخر"""
        if self.end_date and self.status not in ['completed', 'cancelled']:
            return datetime.utcnow() > self.end_date
        return False
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'project_type': self.project_type,
            'status': self.status,
            'priority': self.priority,
            'project_manager': self.project_manager,
            'manager_name': self.manager.full_name if self.manager else None,
            'created_by': self.created_by,
            'creator_name': self.creator.full_name if self.creator else None,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'progress': self.get_progress(),
            'is_overdue': self.is_overdue()
        }


class ProjectTask(db.Model):
    """نموذج مهام المشاريع"""
    
    __tablename__ = 'project_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    
    # التواريخ
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_project_task_project', 'project_id'),
        Index('idx_project_task_task', 'task_id'),
        Index('idx_project_task_user', 'added_by'),
    )
    
    # العلاقات
    project = db.relationship('Project', back_populates='tasks', lazy='select')
    task = db.relationship('Task', back_populates='project_tasks', lazy='select')
    adder = db.relationship('User', foreign_keys=[added_by], back_populates='project_tasks', lazy='select')
    
    def __repr__(self):
        return f'<ProjectTask {self.id}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'task_id': self.task_id,
            'task_title': self.task.title if self.task else None,
            'added_at': self.added_at.isoformat(),
            'added_by': self.added_by,
            'adder_name': self.adder.full_name if self.adder else None
        }


class ProjectMember(db.Model):
    """نموذج أعضاء المشاريع"""
    
    __tablename__ = 'project_members'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='member')  # member, contributor, reviewer
    
    # التواريخ
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("role IN ('member', 'contributor', 'reviewer', 'observer')", name='chk_project_member_role'),
        Index('idx_project_member_project', 'project_id'),
        Index('idx_project_member_user', 'user_id'),
        Index('idx_project_member_role', 'role'),
    )
    
    # العلاقات
    project = db.relationship('Project', back_populates='members', lazy='select')
    user = db.relationship('User', foreign_keys=[user_id], back_populates='project_memberships', lazy='select')
    adder = db.relationship('User', foreign_keys=[added_by], back_populates='added_project_members', lazy='select')
    
    def __repr__(self):
        return f'<ProjectMember {self.id}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else None,
            'role': self.role,
            'joined_at': self.joined_at.isoformat(),
            'added_by': self.added_by,
            'adder_name': self.adder.full_name if self.adder else None
        }
