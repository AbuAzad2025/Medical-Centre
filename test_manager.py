"""Test manager dashboard directly"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.user import User
    from models.visit import Visit
    from models.patient import Patient
    from models.payment import Payment
    from sqlalchemy import func
    from datetime import date, datetime, timedelta, timezone
    
    try:
        print("Testing manager dashboard queries...")
        
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        print(f"1. Patient count: {Patient.query.count()}")
        print(f"2. New patients today: {Patient.query.filter(Patient.created_at >= start_of_day, Patient.created_at <= end_of_day).count()}")
        print(f"3. Visit count: {Visit.query.count()}")
        
        # Test the problematic strftime query
        print("\n4. Testing strftime query...")
        try:
            result = db.session.query(
                func.avg(
                    func.strftime('%s', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.strftime('%s', Visit.created_at)
                )
            ).filter(
                Visit.department_id == 1,
                Visit.status == 'ARCHIVED',
                Visit.created_at >= datetime.now(timezone.utc) - timedelta(days=30),
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            print(f"   strftime result: {result}")
        except Exception as e:
            print(f"   strftime ERROR: {type(e).__name__}: {e}")
            
        # Test extract(epoch) instead
        print("\n5. Testing extract epoch query...")
        try:
            result = db.session.query(
                func.avg(
                    func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                )
            ).filter(
                Visit.department_id == 1,
                Visit.status == 'ARCHIVED',
                Visit.created_at >= datetime.now(timezone.utc) - timedelta(days=30),
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            print(f"   extract epoch result: {result}")
        except Exception as e:
            print(f"   extract epoch ERROR: {type(e).__name__}: {e}")
            
    except Exception as e:
        print(f"OUTER ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
