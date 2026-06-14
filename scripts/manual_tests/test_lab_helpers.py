"""Test lab helper functions"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    helpers = [
        'get_lab_smart_analytics',
        'get_lab_test_optimization',
        'get_lab_quality_control',
        'get_lab_equipment_monitoring',
        'get_lab_result_analysis',
        'get_lab_workflow_automation',
        'get_lab_predictive_insights',
    ]
    
    for h in helpers:
        try:
            func = globals().get(h) or locals().get(h)
            if not func:
                # Try importing from routes.lab
                import routes.lab as lab_module
                func = getattr(lab_module, h, None)
            if func:
                result = func()
                print(f"{h}: OK")
            else:
                print(f"{h}: NOT FOUND")
        except Exception as e:
            print(f"{h}: ERROR = {type(e).__name__}: {str(e)[:200]}")
            db.session.rollback()
