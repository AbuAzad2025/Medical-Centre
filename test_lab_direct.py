"""Test lab dashboard queries directly"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from datetime import date

app = create_app()

with app.app_context():
    from models.lab_request import LabRequest
    today = date.today()
    
    queries = [
        ("LabRequest count", lambda: LabRequest.query.count()),
        ("today_requests", lambda: LabRequest.query.filter(db.func.date(LabRequest.created_at) == today).count()),
        ("pending_requests", lambda: LabRequest.query.filter(LabRequest.status == 'REQUESTED').count()),
        ("completed_today", lambda: LabRequest.query.filter(LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today).count()),
        ("recent_requests", lambda: LabRequest.query.order_by(LabRequest.created_at.desc()).limit(10).all()),
    ]
    
    for name, q in queries:
        try:
            result = q()
            print(f"{name}: OK = {result}")
        except Exception as e:
            print(f"{name}: ERROR = {type(e).__name__}: {str(e)[:200]}")
            db.session.rollback()
