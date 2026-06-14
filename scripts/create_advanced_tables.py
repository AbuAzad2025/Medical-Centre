"""Create advanced plan tables directly via SQLAlchemy"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from models.emar import MedicationSchedule
from models.clinical_pathway import CarePlanTask
from models.data_warehouse import DataWarehouseSync
from models.dicom_pacs import DICOMInstance
from models.population_health import PopulationHealthIndicator

app = create_app()

with app.app_context():
    # Create only the tables that don't exist yet
    db.create_all()
    print("All advanced plan tables created successfully!")
    
    # Verify
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    expected = ['medication_schedules', 'care_plan_tasks', 'data_warehouse_syncs', 
                'dicom_instances', 'population_health_indicators']
    
    for t in expected:
        if t in tables:
            print(f"  [OK] {t}")
        else:
            print(f"  [MISSING] {t}")
