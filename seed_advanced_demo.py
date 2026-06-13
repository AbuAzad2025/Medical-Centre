"""Seed demo data for advanced plan modules"""
import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from datetime import datetime, date, timezone, time

app = create_app()

with app.app_context():
    from models.patient import Patient
    from models.user import User
    
    # Get or create a test patient
    patient = Patient.query.filter_by(national_id='DEMO-001').first()
    if not patient:
        patient = Patient(
            first_name='Demo',
            last_name='Patient',
            first_name_ar='مريض',
            last_name_ar='تجريبي',
            national_id='DEMO-001',
            phone='0500000000',
            gender='M',
            birth_date=date(1990, 1, 1),
            address='عنوان تجريبي'
        )
        db.session.add(patient)
        db.session.commit()
    
    # 1. eMAR — Medication Schedule + Administration
    from models.medication import Prescription, PrescriptionItem, Medication
    from models.emar import eMARAdministration, MedicationSchedule
    
    # Create a demo medication if not exists
    med = Medication.query.filter_by(trade_name='Paracetamol').first()
    if not med:
        med = Medication(
            scientific_name='Paracetamol',
            trade_name='Paracetamol',
            dosage_form='Tablet',
            strength='500mg',
            stock_quantity=100,
            price=5.0,
            category='Analgesic',
            is_active=True
        )
        db.session.add(med)
        db.session.commit()
    
    # Create a prescription
    presc = Prescription.query.filter_by(patient_id=patient.id).first()
    if not presc:
        presc = Prescription(
            patient_id=patient.id,
            doctor_id=1,
            status='ACTIVE',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(presc)
        db.session.commit()
    
    # Create prescription item
    item = PrescriptionItem.query.filter_by(prescription_id=presc.id).first()
    if not item:
        item = PrescriptionItem(
            prescription_id=presc.id,
            medication_id=med.id,
            dosage='1 tablet twice daily',
            quantity=20,
            duration_days=10,
            unit_price=5.0,
            total_price=100.0
        )
        db.session.add(item)
        db.session.commit()
    
    # Create medication schedule
    sched = MedicationSchedule.query.filter_by(prescription_item_id=item.id).first()
    if not sched:
        sched = MedicationSchedule(
            prescription_item_id=item.id,
            scheduled_time=time(8, 0),
            dose='1 tablet',
            frequency='BID',
            window_before=30,
            window_after=60,
            is_active=True
        )
        db.session.add(sched)
    
    # Create eMAR administration record
    emar = eMARAdministration.query.filter_by(patient_id=patient.id).first()
    if not emar:
        emar = eMARAdministration(
            patient_id=patient.id,
            prescription_id=presc.id,
            prescription_item_id=item.id,
            medication_id=med.id,
            scheduled_time=datetime.now(timezone.utc),
            status='SCHEDULED',
            dose_given='1 tablet',
            route='Oral'
        )
        db.session.add(emar)
    
    # 2. Clinical Pathway
    from models.clinical_pathway import ClinicalPathway, ClinicalPathwayStep, PatientCarePlan, CarePlanTask
    
    pathway = ClinicalPathway.query.filter_by(name='Diabetes Management').first()
    if not pathway:
        pathway = ClinicalPathway(
            name='Diabetes Management',
            description='Standard care pathway for Type 2 Diabetes',
            category='CHRONIC',
            is_active=True
        )
        db.session.add(pathway)
        db.session.commit()
    
    step = ClinicalPathwayStep.query.filter_by(pathway_id=pathway.id).first()
    if not step:
        step = ClinicalPathwayStep(
            pathway_id=pathway.id,
            step_number=1,
            title='Initial Assessment',
            description='HbA1c, fasting glucose, BMI',
            is_active=True
        )
        db.session.add(step)
    
    care_plan = PatientCarePlan.query.filter_by(patient_id=patient.id).first()
    if not care_plan:
        care_plan = PatientCarePlan(
            patient_id=patient.id,
            plan_name='Diabetes Care Plan',
            start_date=date.today(),
            status='ACTIVE',
            progress_percentage=25,
            is_active=True
        )
        db.session.add(care_plan)
        db.session.commit()
    
    task = CarePlanTask.query.filter_by(care_plan_id=care_plan.id).first()
    if not task:
        task = CarePlanTask(
            care_plan_id=care_plan.id,
            task_title='Check Blood Glucose',
            task_description='Fasting blood glucose check',
            due_date=date.today(),
            status='PENDING'
        )
        db.session.add(task)
    
    # 3. Data Warehouse
    from models.data_warehouse import DataWarehouseSync, DailyVisitSummary
    
    sync = DataWarehouseSync.query.filter_by(sync_name='daily_visits_summary').first()
    if not sync:
        sync = DataWarehouseSync(
            sync_name='daily_visits_summary',
            status='success',
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=12,
            source_rows=150,
            target_rows=150
        )
        db.session.add(sync)
    
    daily = DailyVisitSummary.query.filter_by(date=date.today()).first()
    if not daily:
        daily = DailyVisitSummary(
            date=date.today(),
            total_visits=45,
            new_patients=12,
            follow_up_visits=30,
            emergency_visits=3,
            revenue_total=12500.0
        )
        db.session.add(daily)
    
    # 4. DICOM
    from models.dicom_pacs import DICOMStudy, DICOMSeries, DICOMInstance
    
    study = DICOMStudy.query.filter_by(study_instance_uid='1.2.840.123456.1').first()
    if not study:
        study = DICOMStudy(
            study_instance_uid='1.2.840.123456.1',
            patient_id=patient.id,
            modality='CT',
            study_description='Chest CT without contrast',
            body_part='CHEST',
            status='RECEIVED',
            series_count=1,
            instance_count=3
        )
        db.session.add(study)
        db.session.commit()
    
    series = DICOMSeries.query.filter_by(study_id=study.id).first()
    if not series:
        series = DICOMSeries(
            study_id=study.id,
            series_instance_uid='1.2.840.123456.2',
            series_number=1,
            modality='CT',
            series_description='Chest axial',
            instance_count=3
        )
        db.session.add(series)
        db.session.commit()
    
    instance = DICOMInstance.query.filter_by(series_id=series.id).first()
    if not instance:
        instance = DICOMInstance(
            series_id=series.id,
            sop_instance_uid='1.2.840.123456.3',
            instance_number=1,
            file_path='/storage/dicom/demo.dcm',
            width=512,
            height=512
        )
        db.session.add(instance)
    
    # 5. Population Health
    from models.population_health import PopulationHealthIndicator, QualityMeasure, DiseaseRegistry
    
    indicator = PopulationHealthIndicator.query.filter_by(indicator_name='Diabetes Prevalence').first()
    if not indicator:
        indicator = PopulationHealthIndicator(
            indicator_name='Diabetes Prevalence',
            indicator_type='MORBIDITY',
            period_start=date(2026, 1, 1),
            period_end=date(2026, 12, 31),
            value=8.5,
            unit='PERCENT',
            numerator=850,
            denominator=10000
        )
        db.session.add(indicator)
    
    measure = QualityMeasure.query.filter_by(measure_code='DM001').first()
    if not measure:
        measure = QualityMeasure(
            measure_code='DM001',
            measure_name='HbA1c Control',
            measure_name_ar='التحكم بسكر الدم',
            description='Percentage of patients with HbA1c < 7%',
            measure_type='OUTCOME',
            target_value=70.0,
            current_value=65.0,
            is_active=True
        )
        db.session.add(measure)
    
    disease = DiseaseRegistry.query.filter_by(icd10_code='E11').first()
    if not disease:
        disease = DiseaseRegistry(
            icd10_code='E11',
            disease_name='Type 2 Diabetes Mellitus',
            disease_name_ar='سكري النوع الثاني',
            category='ENDOCRINE',
            prevalence_count=120,
            incidence_count=15,
            report_period_start=date(2026, 1, 1),
            report_period_end=date(2026, 6, 30)
        )
        db.session.add(disease)
    
    db.session.commit()
    print("Demo data seeded successfully for all advanced modules!")
