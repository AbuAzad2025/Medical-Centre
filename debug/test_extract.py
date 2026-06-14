import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from sqlalchemy import func
from datetime import date

app = create_app()

with app.app_context():
    from models.payment import Payment
    
    # Test func.date
    try:
        today = date.today()
        r = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) == today
        ).scalar()
        print("func.date OK:", r)
    except Exception as e:
        db.session.rollback()
        print("func.date ERROR:", type(e).__name__, str(e)[:200])
    
    # Test extract epoch
    from models.visit import Visit
    try:
        r = db.session.query(
            func.avg(func.extract('epoch', Visit.created_at))
        ).scalar()
        print("extract epoch OK:", r)
    except Exception as e:
        db.session.rollback()
        print("extract epoch ERROR:", type(e).__name__, str(e)[:200])
    
    # Test cast to Date
    try:
        from sqlalchemy import cast, Date
        r = db.session.query(func.sum(Payment.amount)).filter(
            cast(Payment.payment_date, Date) == today
        ).scalar()
        print("cast Date OK:", r)
    except Exception as e:
        db.session.rollback()
        print("cast Date ERROR:", type(e).__name__, str(e)[:200])
