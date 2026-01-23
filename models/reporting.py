"""
نموذج التقارير - Reporting Model
Medical System Reporting Model
"""

from datetime import datetime, timezone
from app_factory import db
import json

class Report(db.Model):
    """نموذج التقرير"""
    
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    report_type = db.Column(db.String(50), nullable=False)  # financial, medical, operational, statistical
    
    # إعدادات التقرير
    parameters = db.Column(db.Text, nullable=True)  # JSON format
    filters = db.Column(db.Text, nullable=True)  # JSON format
    grouping = db.Column(db.String(100), nullable=True)
    sorting = db.Column(db.String(100), nullable=True)
    
    # إعدادات العرض
    chart_type = db.Column(db.String(50), nullable=True)  # bar, line, pie, table
    display_format = db.Column(db.String(50), default='table')  # table, chart, pdf, excel
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # العلاقات
    creator = db.relationship('User', backref='created_reports')
    
    def __repr__(self):
        return f'<Report {self.name}>'
    
    def get_parameters_dict(self):
        """تحويل المعاملات إلى قاموس"""
        if self.parameters:
            return json.loads(self.parameters)
        return {}
    
    def set_parameters_dict(self, params):
        """تعيين المعاملات من قاموس"""
        self.parameters = json.dumps(params)
    
    def get_filters_dict(self):
        """تحويل الفلاتر إلى قاموس"""
        if self.filters:
            return json.loads(self.filters)
        return {}
    
    def set_filters_dict(self, filters):
        """تعيين الفلاتر من قاموس"""
        self.filters = json.dumps(filters)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'report_type': self.report_type,
            'parameters': self.get_parameters_dict(),
            'filters': self.get_filters_dict(),
            'grouping': self.grouping,
            'sorting': self.sorting,
            'chart_type': self.chart_type,
            'display_format': self.display_format,
            'is_active': self.is_active,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }

class ReportExecution(db.Model):
    """نموذج تنفيذ التقرير"""
    
    __tablename__ = 'report_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False)
    executed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # معاملات التنفيذ
    execution_parameters = db.Column(db.Text, nullable=True)  # JSON format
    execution_filters = db.Column(db.Text, nullable=True)  # JSON format
    
    # نتائج التنفيذ
    status = db.Column(db.String(20), default='pending')  # pending, running, completed, failed
    result_data = db.Column(db.Text, nullable=True)  # JSON format
    result_file_path = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # التوقيت
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    execution_time = db.Column(db.Float, nullable=True)  # بالثواني
    
    # العلاقات
    report = db.relationship('Report', backref='executions')
    executor = db.relationship('User', backref='executed_reports')
    
    def __repr__(self):
        return f'<ReportExecution {self.report.name if self.report else "Unknown"} - {self.status}>'
    
    def get_execution_parameters_dict(self):
        """تحويل معاملات التنفيذ إلى قاموس"""
        if self.execution_parameters:
            return json.loads(self.execution_parameters)
        return {}
    
    def set_execution_parameters_dict(self, params):
        """تعيين معاملات التنفيذ من قاموس"""
        self.execution_parameters = json.dumps(params)
    
    def get_execution_filters_dict(self):
        """تحويل فلاتر التنفيذ إلى قاموس"""
        if self.execution_filters:
            return json.loads(self.execution_filters)
        return {}
    
    def set_execution_filters_dict(self, filters):
        """تعيين فلاتر التنفيذ من قاموس"""
        self.execution_filters = json.dumps(filters)
    
    def get_result_data_dict(self):
        """تحويل بيانات النتيجة إلى قاموس"""
        if self.result_data:
            return json.loads(self.result_data)
        return {}
    
    def set_result_data_dict(self, data):
        """تعيين بيانات النتيجة من قاموس"""
        self.result_data = json.dumps(data)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'report_id': self.report_id,
            'executed_by': self.executed_by,
            'execution_parameters': self.get_execution_parameters_dict(),
            'execution_filters': self.get_execution_filters_dict(),
            'status': self.status,
            'result_data': self.get_result_data_dict(),
            'result_file_path': self.result_file_path,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time
        }

class ReportTemplate(db.Model):
    """نموذج قالب التقرير"""
    
    __tablename__ = 'report_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    template_type = db.Column(db.String(50), nullable=False)  # financial, medical, operational
    
    # محتوى القالب
    template_content = db.Column(db.Text, nullable=False)
    template_variables = db.Column(db.Text, nullable=True)  # JSON format
    
    # إعدادات القالب
    page_size = db.Column(db.String(20), default='A4')
    orientation = db.Column(db.String(20), default='portrait')
    margins = db.Column(db.String(50), default='1in')
    
    # الحالة
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # العلاقات
    creator = db.relationship('User', backref='created_report_templates')
    
    def __repr__(self):
        return f'<ReportTemplate {self.name}>'
    
    def get_template_variables_dict(self):
        """تحويل متغيرات القالب إلى قاموس"""
        if self.template_variables:
            return json.loads(self.template_variables)
        return {}
    
    def set_template_variables_dict(self, variables):
        """تعيين متغيرات القالب من قاموس"""
        self.template_variables = json.dumps(variables)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'template_type': self.template_type,
            'template_content': self.template_content,
            'template_variables': self.get_template_variables_dict(),
            'page_size': self.page_size,
            'orientation': self.orientation,
            'margins': self.margins,
            'is_active': self.is_active,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by
        }
