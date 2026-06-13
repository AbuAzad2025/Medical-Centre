"""Check which columns are missing from the visits table"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    # Get actual columns from database
    actual_cols = {c['name'] for c in inspector.get_columns('visits')}
    
    # Get expected columns from model
    from models.visit import Visit
    expected_cols = {c.name for c in Visit.__table__.columns}
    
    missing = expected_cols - actual_cols
    extra = actual_cols - expected_cols
    
    print(f"Expected columns: {len(expected_cols)}")
    print(f"Actual columns: {len(actual_cols)}")
    print(f"\nMissing in DB (need migration): {len(missing)}")
    for c in sorted(missing):
        print(f"  - {c}")
    
    print(f"\nExtra in DB (not in model): {len(extra)}")
    for c in sorted(extra):
        print(f"  + {c}")
