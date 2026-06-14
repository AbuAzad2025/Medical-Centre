"""Isolated test for exact error"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.patient import Patient
    try:
        print("Patient count...")
        c = Patient.query.count()
        print(f"OK: {c}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}")
        print(str(e)[:500])
