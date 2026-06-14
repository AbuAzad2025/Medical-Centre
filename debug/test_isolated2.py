"""Test Visit count in isolation"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.visit import Visit
    try:
        print("Visit count...")
        c = Visit.query.count()
        print(f"OK: {c}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}")
        print(str(e)[:1000])
