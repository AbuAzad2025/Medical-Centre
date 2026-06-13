"""Simple test to find exact error"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.user import User
    from models.visit import Visit
    from models.patient import Patient
    from sqlalchemy import func
    from datetime import date, datetime, timedelta, timezone
    
    try:
        print("1. Patient count...")
        c = Patient.query.count()
        print(f"   OK: {c}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    try:
        print("2. Visit count...")
        c = Visit.query.count()
        print(f"   OK: {c}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    try:
        print("3. Payment query...")
        from models.payment import Payment
        r = db.session.query(func.sum(Payment.amount)).scalar() or 0
        print(f"   OK: {r}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
    
    try:
        print("4. strftime test...")
        result = db.session.query(
            func.avg(func.strftime('%s', Visit.created_at))
        ).scalar()
        print(f"   OK: {result}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
        
    try:
        print("5. extract epoch test...")
        result = db.session.query(
            func.avg(func.extract('epoch', Visit.created_at))
        ).scalar()
        print(f"   OK: {result}")
    except Exception as e:
        print(f"   ERROR: {type(e).__name__}: {e}")
