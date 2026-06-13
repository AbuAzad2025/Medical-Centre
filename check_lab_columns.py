"""Check lab_requests columns"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    actual = {c['name'] for c in inspector.get_columns('lab_requests')}
    from models.lab_request import LabRequest
    expected = {c.name for c in LabRequest.__table__.columns}
    missing = expected - actual
    print(f"Missing in lab_requests: {sorted(missing)}")
