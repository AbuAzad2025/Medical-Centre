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
    
    results = []
    
    def log(msg):
        results.append(msg)
        print(msg)
    
    try:
        log("Testing manager dashboard logic...")
        
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        total_patients = Patient.query.count()
        log(f"1. total_patients: {total_patients}")
        
        total_visits = Visit.query.count()
        log(f"2. total_visits: {total_visits}")
        
        # Test strftime query
        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        log(f"3. Testing strftime...")
        
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
            log(f"   strftime result: {avg_sec}")
        except Exception as e:
            log(f"   strftime ERROR: {type(e).__name__}: {str(e)[:200]}")
        
        # Test extract epoch
        log(f"4. Testing extract epoch...")
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
            log(f"   extract result: {avg_sec}")
        except Exception as e:
            log(f"   extract ERROR: {type(e).__name__}: {str(e)[:200]}")
        
        # Test today revenue
        log(f"5. Testing today_revenue...")
        try:
            from sqlalchemy import func
            today_revenue = db.session.query(func.sum(Payment.amount)).filter(
                func.date(Payment.payment_date) == today
            ).scalar() or 0
            log(f"   revenue: {today_revenue}")
        except Exception as e:
            log(f"   revenue ERROR: {type(e).__name__}: {str(e)[:200]}")
        
        log("\nAll direct queries completed!")
        
    except Exception as e:
        log(f"OUTER ERROR: {type(e).__name__}: {str(e)[:500]}")
        traceback.print_exc()
    
    with open('mgr_test_clean.txt', 'w', encoding='utf-8') as f:
        for r in results:
            f.write(r + '\n')
