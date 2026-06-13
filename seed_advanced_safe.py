"""Seed demo data for advanced plan modules — safe incremental commits"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from datetime import datetime, date, timezone, time

app = create_app()

with app.app_context():
    from models.patient import Patient
    patient = Patient.query.first()
    if not patient:
        print("No patients found, cannot seed")
        exit(0)
    print(f"Patient ID: {patient.id}")

    # 1. Clinical Pathway (no FK dependencies)
    try:
        from models.clinical_pathway import ClinicalPathway, ClinicalPathwayStep
        if not ClinicalPathway.query.filter_by(name='Diabetes Management').first():
            p = ClinicalPathway(name='Diabetes Management', description='Standard care pathway for Type 2 Diabetes', specialty='Endocrinology', is_active=True)
            db.session.add(p)
            db.session.commit()
            s = ClinicalPathwayStep(pathway_id=p.id, step_number=1, title='Initial Assessment', description='HbA1c, fasting glucose, BMI', is_active=True)
            db.session.add(s)
            db.session.commit()
            print("Clinical Pathway seeded")
    except Exception as e:
        print(f"Pathway error: {e}")
        db.session.rollback()

    # 2. Data Warehouse (no FK dependencies)
    try:
        from models.data_warehouse import DataWarehouseSync, DailyVisitSummary
        if not DataWarehouseSync.query.filter_by(sync_name='daily_visits_summary').first():
            db.session.add(DataWarehouseSync(sync_name='daily_visits_summary', status='success', started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc), duration_seconds=12, source_rows=150, target_rows=150))
            db.session.commit()
        if not DailyVisitSummary.query.filter_by(date=date.today()).first():
            db.session.add(DailyVisitSummary(date=date.today(), total_visits=45, new_patients=12, follow_up_visits=30, emergency_visits=3, revenue_total=12500.0))
            db.session.commit()
        print("Data Warehouse seeded")
    except Exception as e:
        print(f"DW error: {e}")
        db.session.rollback()

    # 3. Population Health (no FK dependencies)
    try:
        from models.population_health import PopulationHealthIndicator, QualityMeasure, DiseaseRegistry
        if not PopulationHealthIndicator.query.filter_by(indicator_name='Diabetes Prevalence').first():
            db.session.add(PopulationHealthIndicator(indicator_name='Diabetes Prevalence', indicator_type='MORBIDITY', period_start=date(2026,1,1), period_end=date(2026,12,31), value=8.5, unit='PERCENT', numerator=850, denominator=10000))
        if not QualityMeasure.query.filter_by(measure_code='DM001').first():
            db.session.add(QualityMeasure(measure_code='DM001', measure_name='HbA1c Control', measure_name_ar='التحكم بسكر الدم', description='Percentage of patients with HbA1c < 7%', measure_type='OUTCOME', target_value=70.0, current_value=65.0, is_active=True))
        if not DiseaseRegistry.query.filter_by(disease_name='Type 2 Diabetes Mellitus').first():
            db.session.add(DiseaseRegistry(patient_id=patient.id, disease_name='Type 2 Diabetes Mellitus', disease_name_ar='سكري النوع الثاني', is_notifiable=True, onset_date=date(2026,1,1), diagnosis_date=date(2026,1,15)))
        db.session.commit()
        print("Population Health seeded")
    except Exception as e:
        print(f"Pop Health error: {e}")
        db.session.rollback()

    # 4. DICOM (depends on patient)
    try:
        from models.dicom_pacs import DICOMStudy, DICOMSeries, DICOMInstance
        study = DICOMStudy.query.filter_by(study_instance_uid='1.2.840.123456.1').first()
        if not study:
            study = DICOMStudy(study_instance_uid='1.2.840.123456.1', patient_id=patient.id, modality='CT', study_description='Chest CT without contrast', body_part='CHEST', status='RECEIVED', series_count=1, instance_count=3)
            db.session.add(study)
            db.session.commit()
        if not DICOMSeries.query.filter_by(study_id=study.id).first():
            series = DICOMSeries(study_id=study.id, series_instance_uid='1.2.840.123456.2', series_number=1, modality='CT', series_description='Chest axial', instance_count=3)
            db.session.add(series)
            db.session.commit()
            db.session.add(DICOMInstance(series_id=series.id, sop_instance_uid='1.2.840.123456.3', instance_number=1, file_path='/storage/dicom/demo.dcm', width=512, height=512))
            db.session.commit()
        print("DICOM seeded")
    except Exception as e:
        print(f"DICOM error: {e}")
        db.session.rollback()

    # 5. Care Plan + Tasks (depends on patient)
    try:
        from models.clinical_pathway import PatientCarePlan, CarePlanTask
        cp = PatientCarePlan.query.filter_by(patient_id=patient.id).first()
        if not cp:
            cp = PatientCarePlan(patient_id=patient.id, plan_name='Diabetes Care Plan', start_date=date.today(), status='ACTIVE', progress_percentage=25, is_active=True)
            db.session.add(cp)
            db.session.commit()
        if not CarePlanTask.query.filter_by(care_plan_id=cp.id).first():
            db.session.add(CarePlanTask(care_plan_id=cp.id, task_title='Check Blood Glucose', task_description='Fasting blood glucose check', due_date=date.today(), status='PENDING'))
            db.session.commit()
        print("Care Plans seeded")
    except Exception as e:
        print(f"Care Plan error: {e}")
        db.session.rollback()

    print("Done")
