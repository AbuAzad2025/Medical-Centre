"""Check ALL tables for missing columns"""
import os, importlib
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    # Get all models
    from models import __all__ as model_names
    
    all_missing = []
    
    # Common model modules
    model_modules = [
        'models.user', 'models.patient', 'models.visit', 'models.payment',
        'models.invoice', 'models.department', 'models.service',
        'models.appointment', 'models.prescription', 'models.lab_request',
        'models.radiology_request', 'models.medication',
        'models.audit_trail', 'models.system_config',
        'models.exchange_rate', 'models.budget',
        'models.patient_satisfaction', 'models.queue_management',
        'models.notification', 'models.backup',
        'models.tenant', 'models.permissions',
        'models.nurse', 'models.emergency',
        'models.bed_management', 'models.or_management',
        'models.clinical_coding', 'models.data_warehouse',
        'models.population_health', 'models.patient_education',
        'models.nursing_assessment', 'models.pathway',
        'models.vaccination', 'models.barcode',
        'models.biometric', 'models.dicom',
        'models.telemedicine', 'models.sso',
        'models.mfa', 'models.security',
        'models.cds', 'models.emar',
        'models.what_if', 'models.advanced',
        'models.ai_imaging', 'models.document_ocr',
        'models.voice_dictation', 'models.report_builder',
        'models.patient_portal', 'models.referral',
        'models.finance', 'models.pharmacy',
        'models.booking', 'models.portal',
    ]
    
    for mod_name in model_modules:
        try:
            mod = importlib.import_module(mod_name)
            for name in dir(mod):
                obj = getattr(mod, name)
                if hasattr(obj, '__table__') and hasattr(obj.__table__, 'columns'):
                    table_name = obj.__tablename__
                    try:
                        actual_cols = {c['name'] for c in inspector.get_columns(table_name)}
                        expected_cols = {c.name for c in obj.__table__.columns}
                        missing = expected_cols - actual_cols
                        if missing:
                            all_missing.append((table_name, missing))
                    except Exception:
                        pass  # Table might not exist
        except Exception:
            pass
    
    print(f"Tables with missing columns: {len(all_missing)}")
    for table, missing in sorted(all_missing):
        print(f"\n{table}: {len(missing)} missing")
        for c in sorted(missing):
            print(f"  - {c}")
    
    if all_missing:
        with open('MISSING_COLUMNS.txt', 'w') as f:
            for table, missing in sorted(all_missing):
                f.write(f"{table}: {', '.join(sorted(missing))}\n")
        print("\nDetails saved to MISSING_COLUMNS.txt")
