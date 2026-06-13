"""Test emergency dashboard directly"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.user import User
    user = User.query.filter_by(username='emergency1').first()
    print(f"User: {user.username}, role={user.role}")
    
    from models.emergency import EmergencyCase
    try:
        print(f"EmergencyCase count: {EmergencyCase.query.count()}")
    except Exception as e:
        print(f"EmergencyCase count ERROR: {type(e).__name__}: {e}")
        
    # Test the dashboard logic
    from datetime import date, timedelta
    from sqlalchemy import case
    
    try:
        today = date.today()
        today_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        print(f"today_emergencies: {today_emergencies}")
    except Exception as e:
        print(f"today_emergencies ERROR: {type(e).__name__}: {e}")
        
    try:
        active_emergencies = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).count()
        print(f"active_emergencies: {active_emergencies}")
    except Exception as e:
        print(f"active_emergencies ERROR: {type(e).__name__}: {e}")
        
    try:
        prescriptions_today = 0
        from models.prescription import Prescription
        prescriptions_today = Prescription.query.join(EmergencyCase).filter(
            EmergencyCase.created_at >= today
        ).count()
        print(f"prescriptions_today: {prescriptions_today}")
    except Exception as e:
        print(f"prescriptions_today ERROR: {type(e).__name__}: {e}")
        
    try:
        pending_lab_requests = 0
        from models.lab_request import LabRequest
        pending_lab_requests = LabRequest.query.join(EmergencyCase).filter(
            LabRequest.status == 'PENDING'
        ).count()
        print(f"pending_lab_requests: {pending_lab_requests}")
    except Exception as e:
        print(f"pending_lab_requests ERROR: {type(e).__name__}: {e}")
