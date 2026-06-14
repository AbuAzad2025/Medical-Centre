"""Test manager dashboard directly to see exact error"""
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
    from models.department import Department
    from sqlalchemy import func
    from datetime import date, datetime, timedelta, timezone
    
    try:
        print("Testing manager dashboard logic...")
        
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        total_patients = Patient.query.count()
        print(f"1. total_patients: {total_patients}")
        
        new_patients_today = Patient.query.filter(
            Patient.created_at >= start_of_day,
            Patient.created_at <= end_of_day
        ).count()
        print(f"2. new_patients_today: {new_patients_today}")
        
        total_visits = Visit.query.count()
        print(f"3. total_visits: {total_visits}")
        
        visits_today = Visit.query.filter(
            Visit.created_at >= start_of_day,
            Visit.created_at <= end_of_day
        ).count()
        print(f"4. visits_today: {visits_today}")
        
        # Test strftime query (the problematic one)
        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        print(f"5. Testing strftime with start_30d={start_30d}...")
        
        try:
            avg_sec = db.session.query(
                func.avg(
                    func.strftime('%s', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.strftime('%s', Visit.created_at)
                )
            ).filter(
                Visit.department_id == 1,
                Visit.status == 'ARCHIVED',
                Visit.created_at >= start_30d,
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            print(f"   avg_sec (strftime): {avg_sec}")
        except Exception as e:
            print(f"   strftime ERROR: {type(e).__name__}: {e}")
        
        # Test with extract epoch
        try:
            avg_sec = db.session.query(
                func.avg(
                    func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                )
            ).filter(
                Visit.department_id == 1,
                Visit.status == 'ARCHIVED',
                Visit.created_at >= start_30d,
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            print(f"   avg_sec (extract): {avg_sec}")
        except Exception as e:
            print(f"   extract ERROR: {type(e).__name__}: {e}")
        
        print("\nAll direct queries passed!")
        
    except Exception as e:
        print(f"OUTER ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
