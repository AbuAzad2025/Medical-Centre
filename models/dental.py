from datetime import datetime, timezone
from app_factory import db

TOOTH_STATES = {
    'sound': {'label': 'سليم', 'color': '#10b981'},
    'caries': {'label': 'تسوس', 'color': '#ef4444'},
    'filling': {'label': 'حشوة', 'color': '#3b82f6'},
    'crown': {'label': 'تاج', 'color': '#f59e0b'},
    'root_canal': {'label': 'علاج عصب', 'color': '#8b5cf6'},
    'missing': {'label': 'مفقود', 'color': '#6b7280'},
    'extraction': {'label': 'مستأصل', 'color': '#1f2937'},
    'implant': {'label': 'زراعة', 'color': '#06b6d4'},
    'bridge': {'label': 'جسر', 'color': '#84cc16'},
    'fracture': {'label': 'كسر', 'color': '#dc2626'},
    'abscess': {'label': 'خراج', 'color': '#be185d'},
}

class DentalChart(db.Model):
    __tablename__ = 'dental_charts'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teeth = db.relationship('DentalTooth', back_populates='chart', lazy='dynamic',
                            cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'doctor_id': self.doctor_id,
            'notes': self.notes,
            'teeth': [t.to_dict() for t in self.teeth],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DentalTooth(db.Model):
    __tablename__ = 'dental_teeth'

    id = db.Column(db.Integer, primary_key=True)
    chart_id = db.Column(db.Integer, db.ForeignKey('dental_charts.id', ondelete='CASCADE'), nullable=False, index=True)
    fdi_number = db.Column(db.String(2), nullable=False)  # 11-48
    state = db.Column(db.String(20), nullable=False, default='sound')
    surfaces = db.Column(db.JSON, nullable=True)  # {'occlusal': 'caries', 'buccal': 'sound', ...}
    notes = db.Column(db.Text, nullable=True)
    chart = db.relationship('DentalChart', back_populates='teeth')


    def to_dict(self):
        return {
            'id': self.id,
            'fdi_number': self.fdi_number,
            'state': self.state,
            'state_label': TOOTH_STATES.get(self.state, {}).get('label', self.state),
            'state_color': TOOTH_STATES.get(self.state, {}).get('color', '#999'),
            'surfaces': self.surfaces or {},
            'notes': self.notes
        }
