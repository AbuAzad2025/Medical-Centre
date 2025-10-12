"""
بذور البيانات المبسطة للنظام الصحي
Simple Seed Data for Medical System
نسخة محسّنة مع سيناريوهات واقعية للزيارات والمحاسبة
"""

from datetime import datetime, date, timedelta
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.department import Department
from models.visit import Visit
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.invoice import Invoice
from models.medication import Prescription, PrescriptionItem, Medication
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.emergency import EmergencyCase
from models.pricing import ServicePrice, DoctorPricing, PricingCatalog
from models.insurance import InsuranceCompany
from models.ai_analytics import AIRecommendation, DiseasePattern, PerformanceAnalytics
from models.audit_trail import AuditTrail, SystemLog
from models.notification import Notification
from models.queue_management import QueueManagement
from models.workflow import WorkflowStep
from models.system_config import SystemConfig
import random
import json

def create_additional_users():
    """إنشاء مستخدمين إضافيين"""
    # التحقق من المستخدمين الموجودين
    existing_users = User.query.all()
    if len(existing_users) > 1:  # إذا كان هناك أكثر من المستخدم الافتراضي
        print(f"✅ يوجد {len(existing_users)} مستخدم بالفعل")
        return existing_users
    
    users_data = [
        {
            'username': 'manager',
            'email': 'manager@medical-center.com',
            'full_name': 'سارة أحمد المدير',
            'role': 'manager',
            'department_id': None,
            'phone': '0599123457',
            'is_admin': True,
            'is_active': True
        },
        {
            'username': 'reception',
            'email': 'reception@medical-center.com',
            'full_name': 'فاطمة علي الاستقبال',
            'role': 'reception',
            'department_id': None,
            'phone': '0599123458',
            'is_active': True
        },
        {
            'username': 'dr_ahmed',
            'email': 'dr.ahmed@medical-center.com',
            'full_name': 'د. أحمد محمد الباطني',
            'role': 'doctor',
            'department_id': 1,  # الطب الباطني
            'phone': '0599123459',
            'is_active': True
        },
        {
            'username': 'emergency_doc',
            'email': 'emergency@medical-center.com',
            'full_name': 'د. محمد الطوارئ',
            'role': 'emergency',
            'department_id': 5,  # الطوارئ
            'phone': '0599123463',
            'is_active': True
        },
        {
            'username': 'lab_tech',
            'email': 'lab@medical-center.com',
            'full_name': 'أحمد المختبر',
            'role': 'lab',
            'department_id': 6,  # المختبر
            'phone': '0599123464',
            'is_active': True
        },
        {
            'username': 'radiology_tech',
            'email': 'radiology@medical-center.com',
            'full_name': 'سارة الأشعة',
            'role': 'radiology',
            'department_id': 7,  # الأشعة
            'phone': '0599123465',
            'is_active': True
        },
        {
            'username': 'nurse_1',
            'email': 'nurse1@medical-center.com',
            'full_name': 'مريم التمريض',
            'role': 'nurse',
            'department_id': 8,  # التمريض
            'phone': '0599123466',
            'is_active': True
        },
        {
            'username': 'accountant',
            'email': 'accountant@medical-center.com',
            'full_name': 'علي المحاسب',
            'role': 'accountant',
            'department_id': None,
            'phone': '0599123468',
            'is_active': True
        }
    ]
    
    created_users = []
    for user_data in users_data:
        # التحقق من وجود المستخدم
        existing_user = User.query.filter_by(username=user_data['username']).first()
        if not existing_user:
            user = User(**user_data)
            user.set_password('123456')
            db.session.add(user)
            created_users.append(user)
        else:
            created_users.append(existing_user)
    
    db.session.commit()
    print(f"✅ تم إنشاء/التحقق من {len(users_data)} مستخدم")
    return created_users

def create_sample_departments():
    """إنشاء أقسام عينة"""
    existing_depts = Department.query.count()
    if existing_depts > 0:
        print(f"✅ يوجد {existing_depts} قسم بالفعل")
        return Department.query.all()
    
    departments_data = [
        {
            'name': 'Emergency',
            'name_ar': 'الطوارئ',
            'description': 'قسم الطوارئ والحالات العاجلة',
            'is_active': True,
            'capacity': 20,
            'current_patients': 0
        },
        {
            'name': 'Internal Medicine',
            'name_ar': 'الباطنية',
            'description': 'قسم الطب الباطني',
            'is_active': True,
            'capacity': 15,
            'current_patients': 0
        },
        {
            'name': 'Pediatrics',
            'name_ar': 'الأطفال',
            'description': 'قسم طب الأطفال',
            'is_active': True,
            'capacity': 12,
            'current_patients': 0
        }
    ]
    
    departments = []
    for data in departments_data:
        dept = Department(**data)
        db.session.add(dept)
        departments.append(dept)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(departments)} قسم")
    return departments


def create_sample_patients():
    """إنشاء مرضى عينة"""
    existing_patients = Patient.query.count()
    if existing_patients > 0:
        print(f"✅ يوجد {existing_patients} مريض بالفعل")
        return Patient.query.all()
    
    patients_data = [
        {
            'national_id': '1234567890',
            'first_name': 'أحمد',
            'last_name': 'محمد',
            'first_name_ar': 'أحمد',
            'last_name_ar': 'محمد',
            'birth_date': date(1985, 5, 15),
            'gender': 'male',
            'phone': '0599123001',
            'address': 'رام الله - فلسطين',
            'notes': 'لا توجد حساسية - لا توجد أمراض مزمنة'
        },
        {
            'national_id': '1234567891',
            'first_name': 'فاطمة',
            'last_name': 'أحمد',
            'first_name_ar': 'فاطمة',
            'last_name_ar': 'أحمد',
            'birth_date': date(1990, 8, 22),
            'gender': 'female',
            'phone': '0599123003',
            'address': 'نابلس - فلسطين',
            'notes': 'حساسية من البنسلين - سكري من النوع الثاني'
        },
        {
            'national_id': '1234567892',
            'first_name': 'محمد',
            'last_name': 'علي',
            'first_name_ar': 'محمد',
            'last_name_ar': 'علي',
            'birth_date': date(1978, 3, 10),
            'gender': 'male',
            'phone': '0599123005',
            'address': 'الخليل - فلسطين',
            'notes': 'لا توجد حساسية - ضغط دم مرتفع'
        }
    ]
    
    created_patients = []
    for patient_data in patients_data:
        patient = Patient(**patient_data)
        db.session.add(patient)
        created_patients.append(patient)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(patients_data)} مريض")
    return created_patients

def create_sample_medications():
    """إنشاء أدوية عينة"""
    existing_medications = Medication.query.count()
    if existing_medications > 0:
        print(f"✅ يوجد {existing_medications} دواء بالفعل")
        return Medication.query.all()
    
    medications = [
        {
            'scientific_name': 'Paracetamol',
            'trade_name': 'باراسيتامول',
            'generic_name': 'Acetaminophen',
            'dosage_form': 'tablet',
            'strength': '500mg',
            'manufacturer': 'شركة الأدوية الفلسطينية',
            'description': 'مسكن للآلام وخافض للحرارة',
            'price': 5.0,
            'category': 'مسكن',
            'is_active': True
        },
        {
            'scientific_name': 'Amoxicillin',
            'trade_name': 'أموكسيسيلين',
            'generic_name': 'Amoxicillin',
            'dosage_form': 'capsule',
            'strength': '500mg',
            'manufacturer': 'شركة الأدوية العربية',
            'description': 'مضاد حيوي واسع الطيف',
            'price': 15.0,
            'category': 'مضاد حيوي',
            'is_active': True
        },
        {
            'scientific_name': 'Omeprazole',
            'trade_name': 'أوميبرازول',
            'generic_name': 'Omeprazole',
            'dosage_form': 'capsule',
            'strength': '20mg',
            'manufacturer': 'شركة الأدوية المتقدمة',
            'description': 'مثبط مضخة البروتون لعلاج القرحة',
            'price': 25.0,
            'category': 'مثبط مضخة البروتون',
            'is_active': True
        }
    ]
    
    created_medications = []
    for med_data in medications:
        medication = Medication(**med_data)
        db.session.add(medication)
        created_medications.append(medication)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(medications)} دواء")
    return created_medications

def create_sample_visits(patients, users):
    """إنشاء زيارات عينة"""
    existing_visits = Visit.query.count()
    if existing_visits > 0:
        print(f"✅ يوجد {existing_visits} زيارة بالفعل")
        return Visit.query.all()
    
    doctors = [user for user in users if user.role == 'doctor']
    reception_user = next((user for user in users if user.role == 'reception'), None)
    
    if not doctors or not reception_user:
        print("⚠️ لا توجد أطباء أو مستخدم استقبال")
        return []
    
    visits_data = []
    for i, patient in enumerate(patients):
        visit = Visit(
            patient_id=patient.id,
            department_id=1,  # الطب الباطني
            doctor_id=doctors[0].id,
            visit_number=f"V{1000 + i}",
            status='COMPLETED',
            payment_status='PAID',
            total_amount=80.00,
            paid_amount=80.00,
            currency='ILS',
            visit_type='REGULAR',
            payment_method='cash',
            symptoms='ألم في البطن',
            notes='مريض يشكو من ألم في البطن',
            diagnosis='التهاب معدة',
            treatment_plan='مضاد حيوي ومسكن',
            follow_up_required=True,
            follow_up_date=date.today() + timedelta(days=7),
            prescription_issued=True,
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        db.session.add(visit)
        visits_data.append(visit)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(visits_data)} زيارة")
    return visits_data

def create_sample_prescriptions(visits, medications):
    """إنشاء وصفات عينة"""
    existing_prescriptions = Prescription.query.count()
    if existing_prescriptions > 0:
        print(f"✅ يوجد {existing_prescriptions} وصفة بالفعل")
        return Prescription.query.all()
    
    prescriptions = []
    for i, visit in enumerate(visits):
        prescription = Prescription(
            patient_id=visit.patient_id,
            doctor_id=visit.doctor_id,
            visit_id=visit.id,
            prescription_number=f"RX{1000 + i}",
            status='active',
            notes='يتم تناول الدواء حسب التعليمات',
            created_at=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        db.session.add(prescription)
        db.session.flush()  # للحصول على ID
        
        # إضافة دواء للوصفة
        if medications:
            medication = medications[0]  # أول دواء
            item = PrescriptionItem(
                prescription_id=prescription.id,
                medication_id=medication.id,
                dosage='2 حبة 3 مرات يومياً',
                quantity=14,
                duration_days=7,
                instructions='يتم تناول الدواء مع الطعام',
                unit_price=medication.price,
                total_price=medication.price * 14
            )
            db.session.add(item)
        
        prescriptions.append(prescription)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(prescriptions)} وصفة طبية")
    return prescriptions

def create_sample_ai_data():
    """إنشاء بيانات الذكاء الاصطناعي العينة"""
    existing_recommendations = AIRecommendation.query.count()
    if existing_recommendations > 0:
        print(f"✅ يوجد {existing_recommendations} توصية ذكية بالفعل")
        return
    
    # التوصيات الذكية
    recommendations = [
        {
            'patient_id': 1,
            'visit_id': 1,
            'recommendation_type': 'diagnosis',
            'title': 'تشخيص محتمل: التهاب معدة',
            'description': 'بناءً على الأعراض المذكورة، يبدو أن المريض يعاني من التهاب في المعدة',
            'confidence_score': 0.85,
            'source_data': json.dumps({'symptoms': ['ألم في البطن', 'غثيان'], 'confidence': 0.85}),
            'is_accepted': True
        }
    ]
    
    for rec_data in recommendations:
        recommendation = AIRecommendation(**rec_data)
        db.session.add(recommendation)
    
    # أنماط الأمراض
    disease_patterns = [
        {
            'disease_name': 'التهاب المعدة',
            'icd_code': 'K29.7',
            'symptoms': json.dumps(['ألم في البطن', 'غثيان', 'قيء']),
            'risk_factors': json.dumps(['التوتر', 'التدخين', 'الكحول']),
            'age_group': 'جميع الأعمار',
            'gender_preference': 'غير محدد',
            'seasonality': 'طوال السنة',
            'prevalence_score': 0.7,
            'severity_level': 'moderate',
            'treatment_protocols': json.dumps(['مضاد حيوي', 'مسكنات', 'مضادات الحموضة']),
            'is_active': True
        }
    ]
    
    for pattern_data in disease_patterns:
        pattern = DiseasePattern(**pattern_data)
        db.session.add(pattern)
    
    # تحليلات الأداء
    performance_analytics = [
        {
            'metric_name': 'معدل الشفاء',
            'metric_type': 'monthly',
            'metric_value': 0.85,
            'target_value': 0.90,
            'unit': 'نسبة مئوية',
            'department': 'الطب الباطني',
            'period_start': datetime.now() - timedelta(days=30),
            'period_end': datetime.now(),
            'additional_data': json.dumps({'notes': 'معدل الشفاء الشهري'})
        }
    ]
    
    for analytics_data in performance_analytics:
        analytics = PerformanceAnalytics(**analytics_data)
        db.session.add(analytics)
    
    db.session.commit()
    print("✅ تم إنشاء بيانات الذكاء الاصطناعي")

def create_system_configs():
    """إنشاء إعدادات النظام"""
    existing_configs = SystemConfig.query.count()
    if existing_configs > 0:
        print(f"✅ يوجد {existing_configs} إعداد بالفعل")
        return
    
    configs = [
        {
            'config_key': 'clinic_name',
            'config_value': 'المركز الصحي المتخصص',
            'config_type': 'string',
            'description': 'اسم المركز الصحي',
            'category': 'general'
        },
        {
            'config_key': 'clinic_address',
            'config_value': 'رام الله - فلسطين',
            'config_type': 'string',
            'description': 'عنوان المركز',
            'category': 'general'
        },
        {
            'config_key': 'clinic_phone',
            'config_value': '0599123000',
            'config_type': 'string',
            'description': 'هاتف المركز',
            'category': 'general'
        },
        {
            'config_key': 'default_currency',
            'config_value': 'ILS',
            'config_type': 'string',
            'description': 'العملة الافتراضية',
            'category': 'financial'
        }
    ]
    
    for config_data in configs:
        config = SystemConfig(**config_data)
        db.session.add(config)
    
    db.session.commit()
    print(f"✅ تم إنشاء {len(configs)} إعداد للنظام")

def main():
    """الدالة الرئيسية لإنشاء البذور المبسطة"""
    print("🌱 بدء إنشاء البذور المبسطة...")
    
    # إنشاء التطبيق والسياق
    app = create_app()
    with app.app_context():
        try:
            # 1. إنشاء المستخدمين الإضافيين
            users = create_additional_users()
            
            # 2. إنشاء الأقسام (جديد)
            departments = create_sample_departments()
            
            # 3. إنشاء المرضى العينة
            patients = create_sample_patients()
            
            # 4. إنشاء الأدوية العينة
            medications = create_sample_medications()
            
            # 5. إنشاء الزيارات العينة
            visits = create_sample_visits(patients, users)
            
            # 6. إنشاء الوصفات العينة
            prescriptions = create_sample_prescriptions(visits, medications)
            
            # 7. إنشاء بيانات الذكاء الاصطناعي
            try:
                create_sample_ai_data()
            except Exception as e:
                print(f"⚠️ تخطي بيانات AI: {str(e)[:50]}")
            
            # 8. إنشاء إعدادات النظام
            try:
                create_system_configs()
            except Exception as e:
                print(f"⚠️ تخطي إعدادات النظام: {str(e)[:50]}")
            
            # 9. إنشاء سيناريوهات زيارات واقعية (جديد)
            print("\n💼 إنشاء سيناريوهات زيارات واقعية...")
            create_realistic_visit_scenarios(patients, users)
            
            print("\n🎉 تم إنشاء البذور المبسطة بنجاح!")
            print(f"📊 ملخص البيانات:")
            print(f"   - المستخدمين: {User.query.count()}")
            print(f"   - الأقسام: {Department.query.count()}")
            print(f"   - المرضى: {Patient.query.count()}")
            print(f"   - الأدوية: {Medication.query.count()}")
            print(f"   - الزيارات: {Visit.query.count()}")
            print(f"   - المدفوعات: {Payment.query.count()}")
            print(f"   - الوصفات: {Prescription.query.count()}")
            
            print("\n🔑 بيانات تسجيل الدخول:")
            print("   - السوبر أدمن: admin / admin123")
            print("   - المانجر: manager / 123456")
            print("   - الاستقبال: reception / 123456")
            print("   - الطبيب: dr_ahmed / 123456")
            print("   - الطوارئ: emergency_doc / 123456")
            print("   - المختبر: lab_tech / 123456")
            print("   - الأشعة: radiology_tech / 123456")
            print("   - التمريض: nurse_1 / 123456")
            print("   - المحاسب: accountant / 123456")
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء البذور: {str(e)}")
            db.session.rollback()
            raise

def create_realistic_visit_scenarios(patients, users):
    """
    إنشاء سيناريوهات زيارات واقعية لاختبار النظام
    يشمل جميع طرق الدفع والأقسام
    """
    print("  🏥 إنشاء سيناريوهات واقعية...")
    
    # إعادة تعيين session في حالة وجود أخطاء سابقة
    try:
        db.session.rollback()
    except:
        pass
    
    # الحصول على البيانات
    departments = Department.query.all()
    reception_user = User.query.filter_by(role='reception').first()
    accountant_user = User.query.filter_by(role='accountant').first()
    manager_user = User.query.filter_by(role='manager').first()
    doctors = User.query.filter_by(role='doctor').all()
    
    if not (reception_user and accountant_user and departments):
        print("  ⚠️ بيانات أساسية مفقودة - تخطي السيناريوهات")
        return
    
    scenarios = []
    
    # ===== السيناريو 1: دفع نقدي كامل =====
    if len(patients) > 0 and len(departments) > 0:
        visit1 = Visit(
            patient_id=patients[0].id,
            department_id=departments[0].id,
            doctor_id=doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-001",
            visit_type='REGULAR',
            symptoms='صداع وارتفاع حرارة',
            payment_method='cash',
            payment_status='PAID',
            total_amount=150.00,
            paid_amount=150.00,
            currency='ILS',
            status='COMPLETED',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(hours=3),
            completed_at=datetime.now() - timedelta(hours=1)
        )
        db.session.add(visit1)
        db.session.flush()
        
        # إنشاء سجل دفع
        payment1 = Payment(
            patient_id=patients[0].id,
            visit_id=visit1.id,
            method=PaymentMethod.CASH,
            amount=150.00,
            currency='ILS',
            status=PaymentStatus.CONFIRMED,
            receipt_number=f"RCP-{datetime.now().strftime('%Y%m%d')}-001",
            received_by=reception_user.id,
            payment_date=visit1.created_at
        )
        db.session.add(payment1)
        scenarios.append("✅ سيناريو 1: دفع نقدي كامل (150 شيكل)")
    
    # ===== السيناريو 2: دفع بالبطاقة =====
    if len(patients) > 1 and len(departments) > 0:
        visit2 = Visit(
            patient_id=patients[1].id,
            department_id=departments[0].id,
            doctor_id=doctors[1].id if len(doctors) > 1 else doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-002",
            visit_type='REGULAR',
            symptoms='ألم في الظهر',
            payment_method='visa',
            payment_status='PAID',
            total_amount=200.00,
            paid_amount=200.00,
            currency='ILS',
            card_number_last_digits='1234',
            card_holder_name='محمد أحمد',
            status='COMPLETED',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(hours=2),
            completed_at=datetime.now() - timedelta(minutes=30)
        )
        db.session.add(visit2)
        db.session.flush()
        
        payment2 = Payment(
            patient_id=patients[1].id,
            visit_id=visit2.id,
            method=PaymentMethod.CARD,
            amount=200.00,
            currency='ILS',
            status=PaymentStatus.CONFIRMED,
            receipt_number=f"RCP-{datetime.now().strftime('%Y%m%d')}-002",
            reference="CARD-****1234",
            received_by=reception_user.id,
            payment_date=visit2.created_at
        )
        db.session.add(payment2)
        scenarios.append("✅ سيناريو 2: دفع بالبطاقة (200 شيكل)")
    
    # ===== السيناريو 3: تأمين صحي =====
    if len(patients) > 2 and len(departments) > 0:
        visit3 = Visit(
            patient_id=patients[2].id,
            department_id=departments[0].id,
            doctor_id=doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-003",
            visit_type='REGULAR',
            symptoms='فحص دوري',
            payment_method='insurance',
            payment_status='PARTIAL',
            total_amount=400.00,
            insurance_provider='شركة التأمين الوطنية',
            insurance_policy_number='INS-12345-2025',
            insurance_coverage_percentage=80.00,
            insurance_amount=320.00,
            patient_share=80.00,
            paid_amount=80.00,  # دفع المريض حصته فقط
            currency='ILS',
            status='COMPLETED',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(hours=4),
            completed_at=datetime.now() - timedelta(hours=2)
        )
        db.session.add(visit3)
        db.session.flush()
        
        # دفع حصة المريض
        payment3 = Payment(
            patient_id=patients[2].id,
            visit_id=visit3.id,
            method=PaymentMethod.CASH,
            amount=80.00,
            currency='ILS',
            status=PaymentStatus.CONFIRMED,
            receipt_number=f"RCP-{datetime.now().strftime('%Y%m%d')}-003",
            notes="حصة المريض من التأمين - 20%",
            received_by=reception_user.id,
            payment_date=visit3.created_at
        )
        db.session.add(payment3)
        scenarios.append("✅ سيناريو 3: تأمين صحي (400 شيكل - دفع 80، معلق 320)")
    
    # ===== السيناريو 4: دفع قسري معتمد =====
    if len(patients) > 3 and len(departments) > 0 and manager_user:
        visit4 = Visit(
            patient_id=patients[3].id,
            department_id=departments[0].id,
            doctor_id=doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-004",
            visit_type='EMERGENCY',
            symptoms='حالة طوارئ - نزيف',
            payment_method='force',
            payment_status='DEBT',
            total_amount=500.00,
            paid_amount=0.00,
            currency='ILS',
            is_emergency=True,
            is_force_payment=True,
            force_payment_reason='حالة طوارئ حرجة - نزيف حاد - لا وقت للدفع',
            force_payment_approved_by=manager_user.id,
            force_payment_approved_at=datetime.now() - timedelta(hours=1),
            status='COMPLETED',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(hours=5),
            completed_at=datetime.now() - timedelta(hours=3)
        )
        db.session.add(visit4)
        scenarios.append("✅ سيناريو 4: دفع قسري معتمد (500 شيكل - دين)")
    
    # ===== السيناريو 5: دفع قسري معلق (بانتظار موافقة) =====
    if len(patients) > 4 and len(departments) > 1:
        visit5 = Visit(
            patient_id=patients[4].id,
            department_id=departments[1].id if len(departments) > 1 else departments[0].id,
            doctor_id=doctors[1].id if len(doctors) > 1 else doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-005",
            visit_type='REGULAR',
            symptoms='فحص عام',
            payment_method='force',
            payment_status='PENDING',
            total_amount=180.00,
            paid_amount=0.00,
            currency='ILS',
            is_force_payment=True,
            force_payment_reason='مريض معروف - سيدفع لاحقاً',
            status='IN_PROGRESS',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(minutes=30)
        )
        db.session.add(visit5)
        scenarios.append("⏳ سيناريو 5: دفع قسري معلق (بانتظار موافقة المدير)")
    
    # ===== السيناريو 6: دفع جزئي =====
    if len(patients) > 5 and len(departments) > 0:
        visit6 = Visit(
            patient_id=patients[5].id,
            department_id=departments[0].id,
            doctor_id=doctors[0].id if doctors else None,
            visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-006",
            visit_type='REGULAR',
            symptoms='كشف عام',
            payment_method='cash',
            payment_status='PARTIAL',
            total_amount=300.00,
            paid_amount=150.00,
            currency='ILS',
            status='COMPLETED',
            created_by=reception_user.id,
            created_at=datetime.now() - timedelta(hours=6),
            completed_at=datetime.now() - timedelta(hours=4)
        )
        db.session.add(visit6)
        db.session.flush()
        
        # الدفعة الأولى
        payment6a = Payment(
            patient_id=patients[5].id,
            visit_id=visit6.id,
            method=PaymentMethod.CASH,
            amount=150.00,
            currency='ILS',
            status=PaymentStatus.CONFIRMED,
            receipt_number=f"RCP-{datetime.now().strftime('%Y%m%d')}-006A",
            notes="دفعة أولى - متبقي 150 شيكل",
            received_by=reception_user.id,
            payment_date=visit6.created_at
        )
        db.session.add(payment6a)
        scenarios.append("⏳ سيناريو 6: دفع جزئي (300 شيكل - دُفع 150، متبقي 150)")
    
    # ===== السيناريو 7-10: زيارات لأقسام مختلفة =====
    visit_scenarios = [
        {'dept_idx': 0, 'symptoms': 'فحص دوري', 'amount': 120, 'method': 'cash'},
        {'dept_idx': 1, 'symptoms': 'ألم في المعدة', 'amount': 180, 'method': 'visa'},
        {'dept_idx': 0, 'symptoms': 'متابعة', 'amount': 100, 'method': 'cash'},
        {'dept_idx': 1, 'symptoms': 'فحص شامل', 'amount': 250, 'method': 'cash'},
    ]
    
    for i, scenario in enumerate(visit_scenarios):
        if len(patients) > (6 + i):
            dept_idx = min(scenario['dept_idx'], len(departments) - 1)
            doctor_idx = i % len(doctors) if doctors else None
            
            visit = Visit(
                patient_id=patients[6 + i].id,
                department_id=departments[dept_idx].id,
                doctor_id=doctors[doctor_idx].id if doctors and doctor_idx is not None else None,
                visit_number=f"V-{datetime.now().strftime('%Y%m%d')}-{7+i:03d}",
                visit_type='REGULAR',
                symptoms=scenario['symptoms'],
                payment_method=scenario['method'],
                payment_status='PAID',
                total_amount=scenario['amount'],
                paid_amount=scenario['amount'],
                currency='ILS',
                status='COMPLETED',
                created_by=reception_user.id,
                created_at=datetime.now() - timedelta(hours=(7+i)),
                completed_at=datetime.now() - timedelta(hours=(5+i))
            )
            db.session.add(visit)
            db.session.flush()
            
            # دفع
            payment = Payment(
                patient_id=patients[6 + i].id,
                visit_id=visit.id,
                method=PaymentMethod.CASH if scenario['method'] == 'cash' else PaymentMethod.CARD,
                amount=scenario['amount'],
                currency='ILS',
                status=PaymentStatus.CONFIRMED,
                receipt_number=f"RCP-{datetime.now().strftime('%Y%m%d')}-{7+i:03d}",
                received_by=reception_user.id,
                payment_date=visit.created_at
            )
            db.session.add(payment)
    
    db.session.commit()
    
    print(f"  ✅ تم إنشاء {len(scenarios) + len(visit_scenarios)} سيناريو واقعي:")
    for scenario in scenarios:
        print(f"     {scenario}")
    print(f"     ✅ + {len(visit_scenarios)} زيارة إضافية لأقسام مختلفة")


if __name__ == '__main__':
    main()
