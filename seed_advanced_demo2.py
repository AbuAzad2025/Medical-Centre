"""Seed demo data for advanced plan modules — minimal safe version"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from datetime import datetime, date, timezone, time

app = create_app()

with app.app_context():
    from models.patient import Patient
    from models.user import User
    from models.medication import Prescription, PrescriptionItem, Medication
    from models.emar import eMARAdministration, MedicationSchedule
    from models.clinical_pathway import ClinicalPathway, ClinicalPathwayStep, PatientCarePlan, CarePlanTask
    from models.data_warehouse import DataWarehouseSync, DailyVisitSummary
    from models.dicom_pacs import DICOMStudy, DICOMSeries, DICOMInstance
    from models.population_health import PopulationHealthIndicator, QualityMeasure, DiseaseRegistry

    patient = Patient.query.first()
    if not patient:
        print("No patients found, skipping eMAR/DICOM seed")
        patient = None
    else:
        print(f"Using patient ID {patient.id}")

    # 1. eMAR
    if patient:
        med = Medication.query.filter_by(trade_name='Paracetamol').first()
        if not med:
            med = Medication(scientific_name='Paracetamol', trade_name='Paracetamol', dosage_form='Tablet', strength='500mg', stock_quantity=100, price=5.0, category='Analgesic', is_active=True)
            db.session.add(med)
            db.session.commit()

        presc = Prescription.query.filter_by(patient_id=patient.id).first()
        if not presc:
            presc = Prescription(patient_id=patient.id, doctor_id=1, prescription_number='RX-2026-001', status='ACTIVE', created_at=datetime.now(timezone.utc))
            db.session.add(presc)
            db.session.commit()

        item = PrescriptionItem.query.filter_by(prescription_id=presc.id).first()
        if not item:
            item = PrescriptionItem(prescription_id=presc.id, medication_id=med.id, dosage='1 tablet twice daily', quantity=20, duration_days=10, unit_price=5.0, total_price=100.0)
            db.session.add(item)
            db.session.commit()

        if not MedicationSchedule.query.filter_by(prescription_item_id=item.id).first():
            db.session.add(MedicationSchedule(prescription_item_id=item.id, scheduled_time=time(8,0), dose='1 tablet', frequency='BID', window_before=30, window_after=60, is_active=True))

        if not eMARAdministration.query.filter_by(patient_id=patient.id).first():
            db.session.add(eMARAdministration(patient_id=patient.id, prescription_id=presc.id, prescription_item_id=item.id, medication_id=med.id, scheduled_time=datetime.now(timezone.utc), status='SCHEDULED', dose_given='1 tablet', route='Oral'))

    # 2. Clinical Pathway
    pathway = ClinicalPathway.query.filter_by(name='Diabetes Management').first()
    if not pathway:
        pathway = ClinicalPathway(name='Diabetes Management', description='Standard care pathway for Type 2 Diabetes', category='CHRONIC', is_active=True)
        db.session.add(pathway)
        db.session.commit()

    if not ClinicalPathwayStep.query.filter_by(pathway_id=pathway.id).first():
        db.session.add(ClinicalPathwayStep(pathway_id=pathway.id, step_number=1, title='Initial Assessment', description='HbA1c, fasting glucose, BMI', is_active=True))

    if patient and not PatientCarePlan.query.filter_by(patient_id=patient.id).first():
        cp = PatientCarePlan(patient_id=patient.id, plan_name='Diabetes Care Plan', start_date=date.today(), status='ACTIVE', progress_percentage=25, is_active=True)
        db.session.add(cp)
        db.session.commit()
        if not CarePlanTask.query.filter_by(care_plan_id=cp.id).first():
            db.session.add(CarePlanTask(care_plan_id=cp.id, task_title='Check Blood Glucose', task_description='Fasting blood glucose check', due_date=date.today(), status='PENDING'))

    # 3. Data Warehouse
    if not DataWarehouseSync.query.filter_by(sync_name='daily_visits_summary').first():
        db.session.add(DataWarehouseSync(sync_name='daily_visits_summary', status='success', started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc), duration_seconds=12, source_rows=150, target_rows=150))

    if not DailyVisitSummary.query.filter_by(date=date.today()).first():
        db.session.add(DailyVisitSummary(date=date.today(), total_visits=45, new_patients=12, follow_up_visits=30, emergency_visits=3, revenue_total=12500.0))

    # 4. DICOM
    if patient:
        study = DICOMStudy.query.filter_by(study_instance_uid='1.2.840.123456.1').first()
        if not study:
            study = DICOMStudy(study_instance_uid='1.2.840.123456.1', patient_id=patient.id, modality='CT', study_description='Chest CT without contrast', body_part='CHEST', status='RECEIVED', series_count=1, instance_count=3)
            db.session.add(study)
            db.session.commit()

        if not DICOMSeries.query.filter_by(study_id=study.id).first():
            series = DICOMSeries(study_id=study.id, series_instance_uid='1.2.840.123456.2', series_number=1, modality='CT', series_description='Chest axial', instance_count=3)
            db.session.add(series)
            db.session.commit()

            if not DICOMInstance.query.filter_by(series_id=series.id).first():
                db.session.add(DICOMInstance(series_id=series.id, sop_instance_uid='1.2.840.123456.3', instance_number=1, file_path='/storage/dicom/demo.dcm', width=512, height=512))

    # 5. Population Health
    if not PopulationHealthIndicator.query.filter_by(indicator_name='Diabetes Prevalence').first():
        db.session.add(PopulationHealthIndicator(indicator_name='Diabetes Prevalence', indicator_type='MORBIDITY', period_start=date(2026,1,1), period_end=date(2026,12,31), value=8.5, unit='PERCENT', numerator=850, denominator=10000))

    if not QualityMeasure.query.filter_by(measure_code='DM001').first():
        db.session.add(QualityMeasure(measure_code='DM001', measure_name='HbA1c Control', measure_name_ar='التحكم بسكر الدم', description='Percentage of patients with HbA1c < 7%', measure_type='OUTCOME', target_value=70.0, current_value=65.0, is_active=True))

    if not DiseaseRegistry.query.filter_by(icd10_code='E11').first():
        db.session.add(DiseaseRegistry(icd10_code='E11', disease_name='Type 2 Diabetes Mellitus', disease_name_ar='سكري النوع الثاني', category='ENDOCRINE', prevalence_count=120, incidence_count=15, report_period_start=date(2026,1,1), report_period_end=date(2026,6,30)))

    db.session.commit()
    print("All advanced module demo data seeded successfully!")
