"""
خدمة إدارة الأسعار - Pricing Management Service
Medical System Pricing Management Service
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, func
from app_factory import db
from models.pricing import ServicePrice, DoctorPricing, InsuranceProvider, PricingCatalog
from models.user import User
from models.department import Department
from models.lab_request import LabRequest
from models.radiology_result import RadiologyResult
from models.service import ServiceMaster
import logging

class PricingService:
    """خدمة إدارة الأسعار والخدمات"""
    
    @staticmethod
    def get_service_price(service_name, service_type, payment_method='cash', department_id=None):
        """الحصول على سعر الخدمة"""
        try:
            # البحث عن السعر
            query = ServicePrice.query.filter(
                and_(
                    ServicePrice.service_name == service_name,
                    ServicePrice.service_type == service_type,
                    ServicePrice.is_active == True,
                    or_(
                        ServicePrice.effective_to.is_(None),
                        ServicePrice.effective_to > datetime.now(timezone.utc)
                    )
                )
            )
            
            if department_id:
                query = query.filter(ServicePrice.department_id == department_id)
            
            service_price = query.first()
            
            if service_price:
                return service_price.get_price(payment_method)
            else:
                # محاولة مطابقة أسماء شائعة (aliases)
                for alt in PricingService._normalize_service_aliases(service_name, service_type):
                    alt_q = ServicePrice.query.filter(
                        and_(
                            ServicePrice.service_name == alt,
                            ServicePrice.service_type == service_type,
                            ServicePrice.is_active == True
                        )
                    ).first()
                    if alt_q:
                        return alt_q.get_price(payment_method)
                
                # البحث عن السعر الافتراضي
                default_price = ServicePrice.query.filter(
                    and_(
                        ServicePrice.service_name == service_name,
                        ServicePrice.service_type == service_type,
                        ServicePrice.is_active == True,
                        ServicePrice.department_id.is_(None)
                    )
                ).first()
                
                if default_price:
                    return default_price.get_price(payment_method)
                else:
                    return 0.0
                    
        except Exception as e:
            logging.error(f"Error getting service price: {str(e)}")
            return 0.0
    
    @staticmethod
    def _normalize_service_aliases(service_name, service_type):
        """تطبيع أسماء الخدمات الشائعة لأسماء قياسية"""
        name = (service_name or '').strip().lower()
        aliases = {
            'lab_test': {
                'cbc': ['CBC', 'صورة دم كاملة', 'complete blood count'],
                'esr': ['ESR', 'erythrocyte sedimentation rate', 'سرعة الترسيب'],
                'crp': ['CRP', 'سي آر بي', 'c-reactive protein'],
                'urinalysis': ['Urinalysis', 'تحليل بول'],
                'stool analysis': ['Stool Analysis', 'تحليل براز'],
                'lft': ['Liver Function Tests', 'وظائف الكبد', 'lft'],
                'rft': ['Renal Function Tests', 'وظائف الكلى', 'rft'],
                'tsh': ['TSH', 'tsh'],
                'free t3': ['Free T3', 'free t3'],
                'free t4': ['Free T4', 'free t4'],
                'ferritin': ['Ferritin', 'فيريتين'],
                'iron studies': ['Iron Studies', 'دراسات الحديد'],
                'vitamin d': ['Vitamin D', 'فيتامين D'],
                'd-dimer': ['D-Dimer', 'دي دايمر'],
                'psa': ['PSA', 'psa'],
                'prolactin': ['Prolactin', 'برولاكتين'],
                'afp': ['AFP', 'afp'],
                'ca-125': ['CA-125', 'ca-125'],
                'ca 19-9': ['CA 19-9', 'ca 19-9'],
            },
            'radiology_scan': {
                'chest x-ray': ['Chest X-Ray', 'أشعة سينية صدر', 'cxr', 'xray chest', 'pa chest', 'chest pa', 'ap chest', 'chest ap', 'cxr pa'],
                'abdomen x-ray': ['Abdomen X-Ray', 'أشعة سينية بطن', 'abdominal x-ray', 'xray abdomen'],
                'pelvis x-ray': ['Pelvis X-Ray', 'أشعة سينية حوض', 'xray pelvis'],
                'pa chest': ['PA Chest', 'Chest X-Ray', 'أشعة سينية صدر'],
                'ultrasound abdomen': ['سونار البطن', 'Ultrasound Abdomen', 'US Abdomen'],
                'us abdomen': ['سونار البطن', 'Ultrasound Abdomen', 'US Abdomen'],
                'ultrasound pelvis': ['سونار الحوض', 'Ultrasound Pelvis', 'US Pelvis'],
                'us pelvis': ['سونار الحوض', 'Ultrasound Pelvis', 'US Pelvis'],
                'ultrasound thyroid': ['سونار الغدة الدرقية', 'Ultrasound Thyroid', 'US Thyroid'],
                'us thyroid': ['سونار الغدة الدرقية', 'Ultrasound Thyroid', 'US Thyroid'],
                'obstetric ultrasound': ['سونار الحمل', 'Obstetric Ultrasound', 'Pregnancy Ultrasound', 'US Obstetric'],
                'doppler ultrasound': ['سونار دوبلر', 'Doppler Ultrasound', 'US Doppler'],
                'ct head': ['طبقي محوري للرأس', 'CT Head', 'Head CT', 'CT Brain', 'Brain CT'],
                'ct brain': ['طبقي محوري للرأس', 'CT Head', 'Head CT', 'CT Brain', 'Brain CT'],
                'ct chest': ['طبقي محوري للصدر', 'CT Chest', 'Chest CT'],
                'ct abdomen pelvis': ['طبقي محوري للبطن والحوض', 'CT Abdomen Pelvis', 'CT Abdomen and Pelvis', 'CT A/P'],
                'ct angio': ['طبقي محوري شرياني', 'CT Angio', 'CT Angiography'],
                'mri brain': ['رنين مغناطيسي للدماغ', 'MRI Brain', 'Brain MRI'],
                'mri spine': ['رنين مغناطيسي للعمود الفقري', 'MRI Spine', 'Spine MRI'],
                'mri knee': ['رنين مغناطيسي للركبة', 'MRI Knee', 'Knee MRI'],
                'mri shoulder': ['رنين مغناطيسي للكتف', 'MRI Shoulder', 'Shoulder MRI'],
                'mri abdomen': ['رنين مغناطيسي للبطن', 'MRI Abdomen', 'Abdomen MRI']
            }
        }
        out = []
        group = aliases.get(service_type, {})
        # ابحث في القاموس عن مفاتيح/قيم تطابق الاسم المدخل
        for key, vals in group.items():
            if name == key or name in [v.lower() for v in vals]:
                out.extend(vals)
        # دائماً ضمّن الاسم الأصلي كخيار أخير
        if service_name and service_name not in out:
            out.append(service_name)
        return out
    
    @staticmethod
    def get_doctor_price(doctor_id, visit_type='consultation', payment_method='cash'):
        """الحصول على سعر الطبيب"""
        try:
            doctor_pricing = DoctorPricing.query.filter(
                and_(
                    DoctorPricing.doctor_id == doctor_id,
                    DoctorPricing.is_active == True,
                    or_(
                        DoctorPricing.effective_to.is_(None),
                        DoctorPricing.effective_to > datetime.now(timezone.utc)
                    )
                )
            ).first()
            
            if doctor_pricing:
                return doctor_pricing.get_price(visit_type, payment_method)
            else:
                # البحث عن السعر الافتراضي للقسم
                doctor = db.session.get(User, doctor_id)
                if doctor and doctor.department_id:
                    department_pricing = DoctorPricing.query.filter(
                        and_(
                            DoctorPricing.department_id == doctor.department_id,
                            DoctorPricing.doctor_id.is_(None),
                            DoctorPricing.is_active == True
                        )
                    ).first()
                    
                    if department_pricing:
                        return department_pricing.get_price(visit_type, payment_method)
                
                return 0.0
                
        except Exception as e:
            logging.error(f"Error getting doctor price: {str(e)}")
            return 0.0
    
    @staticmethod
    def create_service_price(service_data, created_by=None):
        """إنشاء سعر خدمة جديد"""
        try:
            service_price = ServicePrice(
                service_name=service_data.get('service_name'),
                service_type=service_data.get('service_type'),
                service_code=service_data.get('service_code'),
                base_price=service_data.get('base_price', 0.0),
                insurance_price=service_data.get('insurance_price'),
                cash_price=service_data.get('cash_price'),
                vip_price=service_data.get('vip_price'),
                description=service_data.get('description'),
                is_active=service_data.get('is_active', True),
                requires_doctor=service_data.get('requires_doctor', False),
                requires_department=service_data.get('requires_department', False),
                effective_from=service_data.get('effective_from', datetime.now(timezone.utc)),
                effective_to=service_data.get('effective_to'),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            db.session.add(service_price)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إنشاء سعر الخدمة بنجاح', 'service_price_id': service_price.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating service price: {str(e)}")
            return {'success': False, 'message': 'تعذر إنشاء سعر الخدمة حالياً'}
    
    @staticmethod
    def create_doctor_pricing(doctor_id, pricing_data, created_by=None):
        """إنشاء أسعار الطبيب"""
        try:
            doctor_pricing = DoctorPricing(
                doctor_id=doctor_id,
                department_id=pricing_data.get('department_id'),
                consultation_price=pricing_data.get('consultation_price', 0.0),
                follow_up_price=pricing_data.get('follow_up_price'),
                emergency_price=pricing_data.get('emergency_price'),
                vip_price=pricing_data.get('vip_price'),
                is_active=pricing_data.get('is_active', True),
                notes=pricing_data.get('notes'),
                effective_from=pricing_data.get('effective_from', datetime.now(timezone.utc)),
                effective_to=pricing_data.get('effective_to'),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            db.session.add(doctor_pricing)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إنشاء أسعار الطبيب بنجاح', 'pricing_id': doctor_pricing.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating doctor pricing: {str(e)}")
            return {'success': False, 'message': 'تعذر إنشاء أسعار الطبيب حالياً'}
    
    @staticmethod
    def update_service_price(service_price_id, update_data):
        """تحديث سعر الخدمة"""
        try:
            service_price = db.session.get(ServicePrice, service_price_id)
            if not service_price:
                return {'success': False, 'message': 'سعر الخدمة غير موجود'}
            
            # تحديث البيانات
            for key, value in update_data.items():
                if hasattr(service_price, key):
                    setattr(service_price, key, value)
            
            service_price.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return {'success': True, 'message': 'تم تحديث سعر الخدمة بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating service price: {str(e)}")
            return {'success': False, 'message': 'تعذر تحديث سعر الخدمة حالياً'}
    
    @staticmethod
    def get_pricing_summary(department_id=None, start_date=None, end_date=None):
        """الحصول على ملخص الأسعار"""
        try:
            # أسعار الخدمات
            service_prices_query = ServicePrice.query.filter(ServicePrice.is_active == True)
            if department_id:
                service_prices_query = service_prices_query.filter(ServicePrice.department_id == department_id)
            
            service_prices = service_prices_query.all()
            
            # أسعار الأطباء
            doctor_pricing_query = DoctorPricing.query.filter(DoctorPricing.is_active == True)
            if department_id:
                doctor_pricing_query = doctor_pricing_query.filter(DoctorPricing.department_id == department_id)
            
            doctor_pricing = doctor_pricing_query.all()
            
            # إحصائيات
            total_services = len(service_prices)
            total_doctors = len(doctor_pricing)
            
            # متوسط الأسعار
            avg_service_price = sum(sp.base_price for sp in service_prices) / total_services if total_services > 0 else 0
            avg_consultation_price = sum(dp.consultation_price for dp in doctor_pricing) / total_doctors if total_doctors > 0 else 0
            
            return {
                'success': True,
                'summary': {
                    'total_services': total_services,
                    'total_doctors': total_doctors,
                    'avg_service_price': avg_service_price,
                    'avg_consultation_price': avg_consultation_price,
                    'service_prices': [sp.to_dict() for sp in service_prices],
                    'doctor_pricing': [dp.to_dict() for dp in doctor_pricing]
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting pricing summary: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب ملخص الأسعار حالياً'}
    
    @staticmethod
    def create_default_pricing():
        """إنشاء الأسعار الافتراضية"""
        try:
            # أسعار الخدمات الافتراضية
            default_services = [
                {
                    'service_name': 'استشارة طبية',
                    'service_type': 'consultation',
                    'base_price': 50.0,
                    'insurance_price': 40.0,
                    'cash_price': 50.0,
                    'vip_price': 100.0,
                    'requires_doctor': True,
                    'requires_department': True
                },
                {
                    'service_name': 'فحص مختبر',
                    'service_type': 'lab_test',
                    'base_price': 30.0,
                    'insurance_price': 25.0,
                    'cash_price': 30.0,
                    'vip_price': 60.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'فحص أشعة',
                    'service_type': 'radiology_scan',
                    'base_price': 80.0,
                    'insurance_price': 60.0,
                    'cash_price': 80.0,
                    'vip_price': 150.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'CBC',
                    'service_type': 'lab_test',
                    'base_price': 30.0,
                    'insurance_price': 25.0,
                    'cash_price': 30.0,
                    'vip_price': 60.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'ESR',
                    'service_type': 'lab_test',
                    'base_price': 20.0,
                    'insurance_price': 16.0,
                    'cash_price': 20.0,
                    'vip_price': 40.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'CRP',
                    'service_type': 'lab_test',
                    'base_price': 30.0,
                    'insurance_price': 24.0,
                    'cash_price': 30.0,
                    'vip_price': 60.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'Urinalysis',
                    'service_type': 'lab_test',
                    'base_price': 20.0,
                    'insurance_price': 16.0,
                    'cash_price': 20.0,
                    'vip_price': 40.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'Stool Analysis',
                    'service_type': 'lab_test',
                    'base_price': 20.0,
                    'insurance_price': 16.0,
                    'cash_price': 20.0,
                    'vip_price': 40.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'Chest X-Ray',
                    'service_type': 'radiology_scan',
                    'base_price': 80.0,
                    'insurance_price': 60.0,
                    'cash_price': 80.0,
                    'vip_price': 150.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'Abdomen X-Ray',
                    'service_type': 'radiology_scan',
                    'base_price': 80.0,
                    'insurance_price': 60.0,
                    'cash_price': 80.0,
                    'vip_price': 150.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'Pelvis X-Ray',
                    'service_type': 'radiology_scan',
                    'base_price': 80.0,
                    'insurance_price': 60.0,
                    'cash_price': 80.0,
                    'vip_price': 150.0,
                    'requires_doctor': False,
                    'requires_department': True
                },
                {
                    'service_name': 'علاج إسعافي',
                    'service_type': 'emergency',
                    'base_price': 100.0,
                    'insurance_price': 80.0,
                    'cash_price': 100.0,
                    'vip_price': 200.0,
                    'requires_doctor': True,
                    'requires_department': True
                }
            ]
            
            for service_data in default_services:
                # التحقق من وجود السعر
                existing = ServicePrice.query.filter(
                    and_(
                        ServicePrice.service_name == service_data['service_name'],
                        ServicePrice.service_type == service_data['service_type']
                    )
                ).first()
                
                if not existing:
                    service_price = ServicePrice(**service_data)
                    db.session.add(service_price)
            
            db.session.commit()
            return {'success': True, 'message': 'تم إنشاء الأسعار الافتراضية بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating default pricing: {str(e)}")
            return {'success': False, 'message': 'تعذر إنشاء الأسعار الافتراضية حالياً'}
    
    @staticmethod
    def calculate_visit_cost(visit_data):
        """حساب تكلفة الزيارة"""
        try:
            total_cost = 0.0
            services = []
            
            # تكلفة الطبيب
            if visit_data.get('doctor_id'):
                doctor_price = PricingService.get_doctor_price(
                    visit_data['doctor_id'],
                    visit_data.get('visit_type', 'consultation'),
                    visit_data.get('payment_method', 'cash')
                )
                doctor_price_float = float(doctor_price or 0.0)
                if doctor_price_float > 0:
                    total_cost += doctor_price_float
                    services.append({
                        'name': 'استشارة طبية',
                        'type': 'consultation',
                        'price': doctor_price_float
                    })
            
            # تكلفة التحاليل
            if visit_data.get('lab_tests'):
                for lab_test_id in visit_data['lab_tests']:
                    lab_test = db.session.get(LabRequest, lab_test_id)
                    if lab_test:
                        # محاولة الحصول على اسم الفحص إن وجد، وإلا استخدام أول سعر خدمة نشط لنوع lab_test
                        service_name = getattr(lab_test, 'name', None) or getattr(lab_test, 'name_ar', None) or getattr(lab_test, 'test_name', None)
                        payment_method = visit_data.get('payment_method', 'cash')
                        lab_price = 0.0
                        if service_name:
                            lab_price = float(PricingService.get_service_price(service_name, 'lab_test', payment_method) or 0.0)
                        else:
                            sp = ServicePrice.query.filter(ServicePrice.service_type == 'lab_test', ServicePrice.is_active == True).first()
                            if sp:
                                lab_price = float(sp.get_price(payment_method) or 0.0)
                        if lab_price > 0:
                            total_cost += lab_price
                            services.append({
                                'name': f"فحص مختبر - {getattr(lab_test, 'name_ar', None) or getattr(lab_test, 'test_name', None) or 'غير محدد'}",
                                'type': 'lab_test',
                                'price': lab_price
                            })
            
            # تكلفة الأشعة
            if visit_data.get('radiology_tests'):
                for radiology_test_id in visit_data['radiology_tests']:
                    radiology_test = db.session.get(RadiologyResult, radiology_test_id)
                    if radiology_test:
                        service_name = getattr(radiology_test, 'name', None) or getattr(radiology_test, 'name_ar', None) or getattr(radiology_test, 'study_uid', None)
                        payment_method = visit_data.get('payment_method', 'cash')
                        radiology_price = 0.0
                        if service_name:
                            radiology_price = float(PricingService.get_service_price(service_name, 'radiology_scan', payment_method) or 0.0)
                        else:
                            sp = ServicePrice.query.filter(ServicePrice.service_type == 'radiology_scan', ServicePrice.is_active == True).first()
                            if sp:
                                radiology_price = float(sp.get_price(payment_method) or 0.0)
                        if radiology_price > 0:
                            total_cost += radiology_price
                            services.append({
                                'name': f"فحص أشعة - {getattr(radiology_test, 'name_ar', None) or 'غير محدد'}",
                                'type': 'radiology_scan',
                                'price': radiology_price
                            })
            
            return {
                'success': True,
                'total_cost': total_cost,
                'services': services,
                'payment_method': visit_data.get('payment_method', 'cash')
            }
            
        except Exception as e:
            logging.error(f"Error calculating visit cost: {str(e)}")
            return {'success': False, 'message': 'تعذر حساب تكلفة الزيارة حالياً'}

    @staticmethod
    def seed_departments():
        try:
            created = 0
            items = [
                {'name': 'Radiology', 'name_ar': 'الأشعة'},
                {'name': 'Lab', 'name_ar': 'المختبر'},
                {'name': 'General Clinic', 'name_ar': 'العيادة العامة'},
                {'name': 'Emergency', 'name_ar': 'الطوارئ'},
                {'name': 'Internal Medicine', 'name_ar': 'الباطنية'},
                {'name': 'Gynecology', 'name_ar': 'النسائية'},
                {'name': 'Pediatrics', 'name_ar': 'الأطفال'},
                {'name': 'General Surgery', 'name_ar': 'الجراحة العامة'},
                {'name': 'Orthopedics', 'name_ar': 'العظام'},
                {'name': 'Cardiology', 'name_ar': 'القلبية'},
                {'name': 'ENT', 'name_ar': 'أنف وأذن وحنجرة'},
                {'name': 'Ophthalmology', 'name_ar': 'العيون'},
                {'name': 'Dermatology', 'name_ar': 'الجلدية'},
                {'name': 'Urology', 'name_ar': 'المسالك البولية'},
                {'name': 'Neurology', 'name_ar': 'الأعصاب'}
            ]
            result = {}
            for item in items:
                dept = Department.query.filter_by(name=item['name']).first()
                if not dept:
                    dept = Department(name=item['name'], name_ar=item['name_ar'], is_active=True)
                    db.session.add(dept)
                    created += 1
                result[item['name']] = dept
            db.session.commit()
            return {'success': True, 'created': created, 'departments': {k: v.id for k, v in result.items()}}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding departments: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة الأقسام حالياً'}

    @staticmethod
    def seed_doctors(departments):
        try:
            created = 0
            all_depts = Department.query.all()
            result = []
            for dept in all_depts:
                if dept.name in ('Lab', 'Radiology'):
                    continue
                existing = User.query.filter_by(role='doctor', department_id=dept.id, is_active=True).order_by(User.id.asc()).first()
                if existing:
                    result.append(existing)
                    continue
                base = 'doctor_' + ''.join(c.lower() for c in dept.name if c.isalnum() or c == '_')
                while '__' in base:
                    base = base.replace('__', '_')
                username = base
                i = 1
                while User.query.filter_by(username=username).first():
                    i += 1
                    username = f"{base}{i}"
                email = f"{username}@example.com"
                if User.query.filter_by(email=email).first():
                    email = f"{username}+{dept.id}@example.com"
                full_name = dept.name_ar or dept.name
                user = User(username=username, email=email, full_name=full_name, role='doctor', department_id=dept.id, is_active=True)
                user.set_password('p')
                db.session.add(user)
                created += 1
                result.append(user)
            db.session.commit()
            return {'success': True, 'created': created, 'doctors': [u.id for u in result]}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding doctors: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة الأطباء حالياً'}

    @staticmethod
    def seed_technicians():
        try:
            created = 0
            lab_dept = Department.query.filter_by(name='Lab').first()
            rad_dept = Department.query.filter_by(name='Radiology').first()
            lab_user = User.query.filter_by(username='lab_tech').first()
            if not lab_user:
                lab_user = User(username='lab_tech', email='lab_tech@example.com', full_name='فني مختبر', role='lab', department_id=lab_dept.id if lab_dept else None, is_active=True)
                lab_user.set_password('p')
                db.session.add(lab_user)
                created += 1
            else:
                if lab_dept and lab_user.department_id != lab_dept.id:
                    lab_user.department_id = lab_dept.id
            rad_user = User.query.filter_by(username='radiology_tech').first()
            if not rad_user:
                rad_user = User(username='radiology_tech', email='radiology_tech@example.com', full_name='فني أشعة', role='radiology', department_id=rad_dept.id if rad_dept else None, is_active=True)
                rad_user.set_password('p')
                db.session.add(rad_user)
                created += 1
            else:
                if rad_dept and rad_user.department_id != rad_dept.id:
                    rad_user.department_id = rad_dept.id
            db.session.commit()
            return {'success': True, 'created': created, 'technicians': [u.id for u in [lab_user, rad_user] if u]}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding technicians: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة الفنيين حالياً'}

    @staticmethod
    def seed_service_master():
        try:
            created = 0
            defs = [
                {'code': 'CONSULT_GEN', 'name': 'استشارة عامة', 'name_ar': 'استشارة عامة', 'category': 'doctor', 'base_price': 50, 'insurance_price': 40},
                {'code': 'LAB_CBC', 'name': 'تحليل CBC', 'name_ar': 'تحليل CBC', 'category': 'lab', 'base_price': 30, 'insurance_price': 25},
                {'code': 'RAD_XRAY_CHEST', 'name': 'أشعة سينية صدر', 'name_ar': 'أشعة صدر', 'category': 'radiology', 'base_price': 80, 'insurance_price': 60},
                {'code': 'EMERGENCY_VISIT', 'name': 'زيارة طوارئ', 'name_ar': 'زيارة طوارئ', 'category': 'general', 'base_price': 100, 'insurance_price': 80, 'emergency_price': 100}
            ]
            for d in defs:
                svc = ServiceMaster.query.filter_by(code=d['code']).first()
                if not svc:
                    svc = ServiceMaster(code=d['code'], name=d['name'], name_ar=d['name_ar'], category=d['category'], base_price=d.get('base_price', 0), insurance_price=d.get('insurance_price'), emergency_price=d.get('emergency_price'), is_active=True)
                    db.session.add(svc)
                    created += 1
            db.session.commit()
            return {'success': True, 'created': created}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding service master: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة الخدمات الرئيسية حالياً'}

    @staticmethod
    def seed_service_prices():
        try:
            created = 0
            items = [
                {'service_name': 'تحليل CBC', 'service_type': 'lab_test', 'base_price': 30.0, 'insurance_price': 24.0, 'cash_price': 30.0, 'vip_price': 60.0},
                {'service_name': 'سكر صائم', 'service_type': 'lab_test', 'base_price': 25.0, 'insurance_price': 20.0, 'cash_price': 25.0, 'vip_price': 50.0},
                {'service_name': 'سكر عشوائي', 'service_type': 'lab_test', 'base_price': 20.0, 'insurance_price': 16.0, 'cash_price': 20.0, 'vip_price': 40.0},
                {'service_name': 'HbA1c', 'service_type': 'lab_test', 'base_price': 45.0, 'insurance_price': 36.0, 'cash_price': 45.0, 'vip_price': 90.0},
                {'service_name': 'دهون شاملة', 'service_type': 'lab_test', 'base_price': 40.0, 'insurance_price': 32.0, 'cash_price': 40.0, 'vip_price': 80.0},
                {'service_name': 'وظائف الكبد', 'service_type': 'lab_test', 'base_price': 45.0, 'insurance_price': 36.0, 'cash_price': 45.0, 'vip_price': 90.0},
                {'service_name': 'وظائف الكلى', 'service_type': 'lab_test', 'base_price': 45.0, 'insurance_price': 36.0, 'cash_price': 45.0, 'vip_price': 90.0},
                {'service_name': 'TSH', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'Free T3', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'Free T4', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'فيريتين', 'service_type': 'lab_test', 'base_price': 50.0, 'insurance_price': 40.0, 'cash_price': 50.0, 'vip_price': 100.0},
                {'service_name': 'دراسات الحديد', 'service_type': 'lab_test', 'base_price': 55.0, 'insurance_price': 44.0, 'cash_price': 55.0, 'vip_price': 110.0},
                {'service_name': 'فيتامين D', 'service_type': 'lab_test', 'base_price': 70.0, 'insurance_price': 56.0, 'cash_price': 70.0, 'vip_price': 140.0},
                {'service_name': 'PT/INR', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'PTT', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'CRP', 'service_type': 'lab_test', 'base_price': 30.0, 'insurance_price': 24.0, 'cash_price': 30.0, 'vip_price': 60.0},
                {'service_name': 'ESR', 'service_type': 'lab_test', 'base_price': 20.0, 'insurance_price': 16.0, 'cash_price': 20.0, 'vip_price': 40.0},
                {'service_name': 'عامل روماتويدي', 'service_type': 'lab_test', 'base_price': 40.0, 'insurance_price': 32.0, 'cash_price': 40.0, 'vip_price': 80.0},
                {'service_name': 'ANA', 'service_type': 'lab_test', 'base_price': 60.0, 'insurance_price': 48.0, 'cash_price': 60.0, 'vip_price': 120.0},
                {'service_name': 'HBsAg', 'service_type': 'lab_test', 'base_price': 40.0, 'insurance_price': 32.0, 'cash_price': 40.0, 'vip_price': 80.0},
                {'service_name': 'Anti-HCV', 'service_type': 'lab_test', 'base_price': 50.0, 'insurance_price': 40.0, 'cash_price': 50.0, 'vip_price': 100.0},
                {'service_name': 'HIV Ab', 'service_type': 'lab_test', 'base_price': 60.0, 'insurance_price': 48.0, 'cash_price': 60.0, 'vip_price': 120.0},
                {'service_name': 'Beta-hCG', 'service_type': 'lab_test', 'base_price': 35.0, 'insurance_price': 28.0, 'cash_price': 35.0, 'vip_price': 70.0},
                {'service_name': 'فصيلة الدم وRh', 'service_type': 'lab_test', 'base_price': 20.0, 'insurance_price': 16.0, 'cash_price': 20.0, 'vip_price': 40.0},
                {'service_name': 'الكتروليتات', 'service_type': 'lab_test', 'base_price': 30.0, 'insurance_price': 24.0, 'cash_price': 30.0, 'vip_price': 60.0},
                {'service_name': 'كالسيوم', 'service_type': 'lab_test', 'base_price': 25.0, 'insurance_price': 20.0, 'cash_price': 25.0, 'vip_price': 50.0},
                {'service_name': 'مغنيسيوم', 'service_type': 'lab_test', 'base_price': 25.0, 'insurance_price': 20.0, 'cash_price': 25.0, 'vip_price': 50.0},
                {'service_name': 'فوسفات', 'service_type': 'lab_test', 'base_price': 25.0, 'insurance_price': 20.0, 'cash_price': 25.0, 'vip_price': 50.0},
                {'service_name': 'تروبونين', 'service_type': 'lab_test', 'base_price': 80.0, 'insurance_price': 64.0, 'cash_price': 80.0, 'vip_price': 160.0},
                {'service_name': 'دي دايمر', 'service_type': 'lab_test', 'base_price': 60.0, 'insurance_price': 48.0, 'cash_price': 60.0, 'vip_price': 120.0},
                {'service_name': 'PSA', 'service_type': 'lab_test', 'base_price': 55.0, 'insurance_price': 44.0, 'cash_price': 55.0, 'vip_price': 110.0},
                {'service_name': 'برولاكتين', 'service_type': 'lab_test', 'base_price': 45.0, 'insurance_price': 36.0, 'cash_price': 45.0, 'vip_price': 90.0},
                {'service_name': 'AFP', 'service_type': 'lab_test', 'base_price': 55.0, 'insurance_price': 44.0, 'cash_price': 55.0, 'vip_price': 110.0},
                {'service_name': 'CA-125', 'service_type': 'lab_test', 'base_price': 65.0, 'insurance_price': 52.0, 'cash_price': 65.0, 'vip_price': 130.0},
                {'service_name': 'CA 19-9', 'service_type': 'lab_test', 'base_price': 65.0, 'insurance_price': 52.0, 'cash_price': 65.0, 'vip_price': 130.0},
                {'service_name': 'تحليل بول', 'service_type': 'lab_test', 'base_price': 20.0, 'insurance_price': 16.0, 'cash_price': 20.0, 'vip_price': 40.0},
                {'service_name': 'تحليل براز', 'service_type': 'lab_test', 'base_price': 20.0, 'insurance_price': 16.0, 'cash_price': 20.0, 'vip_price': 40.0},
                {'service_name': 'زرع بول', 'service_type': 'lab_test', 'base_price': 60.0, 'insurance_price': 48.0, 'cash_price': 60.0, 'vip_price': 120.0},
                {'service_name': 'زرع دم', 'service_type': 'lab_test', 'base_price': 80.0, 'insurance_price': 64.0, 'cash_price': 80.0, 'vip_price': 160.0},
                {'service_name': 'زرع بلغم', 'service_type': 'lab_test', 'base_price': 60.0, 'insurance_price': 48.0, 'cash_price': 60.0, 'vip_price': 120.0},
                {'service_name': 'أشعة سينية صدر', 'service_type': 'radiology_scan', 'base_price': 80.0, 'insurance_price': 60.0, 'cash_price': 80.0, 'vip_price': 150.0},
                {'service_name': 'أشعة سينية بطن', 'service_type': 'radiology_scan', 'base_price': 80.0, 'insurance_price': 60.0, 'cash_price': 80.0, 'vip_price': 150.0},
                {'service_name': 'أشعة سينية حوض', 'service_type': 'radiology_scan', 'base_price': 80.0, 'insurance_price': 60.0, 'cash_price': 80.0, 'vip_price': 150.0},
                {'service_name': 'أشعة سينية عمود فقري', 'service_type': 'radiology_scan', 'base_price': 90.0, 'insurance_price': 67.5, 'cash_price': 90.0, 'vip_price': 170.0},
                {'service_name': 'أشعة طرف', 'service_type': 'radiology_scan', 'base_price': 70.0, 'insurance_price': 52.5, 'cash_price': 70.0, 'vip_price': 130.0},
                {'service_name': 'سونار البطن', 'service_type': 'radiology_scan', 'base_price': 100.0, 'insurance_price': 75.0, 'cash_price': 100.0, 'vip_price': 200.0},
                {'service_name': 'سونار الحوض', 'service_type': 'radiology_scan', 'base_price': 90.0, 'insurance_price': 67.5, 'cash_price': 90.0, 'vip_price': 180.0},
                {'service_name': 'سونار الحمل', 'service_type': 'radiology_scan', 'base_price': 120.0, 'insurance_price': 90.0, 'cash_price': 120.0, 'vip_price': 240.0},
                {'service_name': 'سونار الغدة الدرقية', 'service_type': 'radiology_scan', 'base_price': 90.0, 'insurance_price': 67.5, 'cash_price': 90.0, 'vip_price': 180.0},
                {'service_name': 'سونار دوبلر', 'service_type': 'radiology_scan', 'base_price': 140.0, 'insurance_price': 105.0, 'cash_price': 140.0, 'vip_price': 260.0},
                {'service_name': 'طبقي محوري للرأس', 'service_type': 'radiology_scan', 'base_price': 250.0, 'insurance_price': 187.5, 'cash_price': 250.0, 'vip_price': 400.0},
                {'service_name': 'طبقي محوري للصدر', 'service_type': 'radiology_scan', 'base_price': 280.0, 'insurance_price': 210.0, 'cash_price': 280.0, 'vip_price': 420.0},
                {'service_name': 'طبقي محوري للبطن والحوض', 'service_type': 'radiology_scan', 'base_price': 300.0, 'insurance_price': 225.0, 'cash_price': 300.0, 'vip_price': 450.0},
                {'service_name': 'طبقي محوري شرياني', 'service_type': 'radiology_scan', 'base_price': 350.0, 'insurance_price': 262.5, 'cash_price': 350.0, 'vip_price': 500.0},
                {'service_name': 'رنين مغناطيسي للدماغ', 'service_type': 'radiology_scan', 'base_price': 350.0, 'insurance_price': 262.5, 'cash_price': 350.0, 'vip_price': 500.0},
                {'service_name': 'رنين مغناطيسي للعمود الفقري', 'service_type': 'radiology_scan', 'base_price': 400.0, 'insurance_price': 300.0, 'cash_price': 400.0, 'vip_price': 560.0},
                {'service_name': 'رنين مغناطيسي للركبة', 'service_type': 'radiology_scan', 'base_price': 350.0, 'insurance_price': 262.5, 'cash_price': 350.0, 'vip_price': 500.0},
                {'service_name': 'رنين مغناطيسي للكتف', 'service_type': 'radiology_scan', 'base_price': 350.0, 'insurance_price': 262.5, 'cash_price': 350.0, 'vip_price': 500.0},
                {'service_name': 'رنين مغناطيسي للبطن', 'service_type': 'radiology_scan', 'base_price': 450.0, 'insurance_price': 337.5, 'cash_price': 450.0, 'vip_price': 600.0},
                {'service_name': 'ماموغرام', 'service_type': 'radiology_scan', 'base_price': 200.0, 'insurance_price': 150.0, 'cash_price': 200.0, 'vip_price': 320.0},
                {'service_name': 'صورة بانورامية للأسنان', 'service_type': 'radiology_scan', 'base_price': 150.0, 'insurance_price': 112.5, 'cash_price': 150.0, 'vip_price': 250.0},
                {'service_name': 'إيكو قلب', 'service_type': 'radiology_scan', 'base_price': 200.0, 'insurance_price': 150.0, 'cash_price': 200.0, 'vip_price': 320.0},
                {'service_name': 'فلوروسكوبي', 'service_type': 'radiology_scan', 'base_price': 220.0, 'insurance_price': 165.0, 'cash_price': 220.0, 'vip_price': 350.0},
                {'service_name': 'استشارة طبية', 'service_type': 'consultation', 'base_price': 50.0, 'insurance_price': 40.0, 'cash_price': 50.0, 'vip_price': 100.0}
            ]
            for i in items:
                existing = ServicePrice.query.filter(and_(ServicePrice.service_name == i['service_name'], ServicePrice.service_type == i['service_type'])).first()
                if not existing:
                    sp = ServicePrice(**i)
                    db.session.add(sp)
                    created += 1
            db.session.commit()
            return {'success': True, 'created': created}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding service prices: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة أسعار الخدمات حالياً'}

    @staticmethod
    def seed_doctor_pricing():
        try:
            created = 0
            docs = User.query.filter_by(role='doctor', is_active=True).all()
            for doc in docs:
                exists = DoctorPricing.query.filter(DoctorPricing.doctor_id == doc.id, DoctorPricing.is_active == True).first()
                if not exists:
                    dp = DoctorPricing(doctor_id=doc.id, department_id=doc.department_id, consultation_price=50.0, follow_up_price=35.0, emergency_price=100.0, vip_price=120.0, is_active=True, effective_from=datetime.now(timezone.utc))
                    db.session.add(dp)
                    created += 1
            db.session.commit()
            return {'success': True, 'created': created}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding doctor pricing: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة أسعار الأطباء حالياً'}

    @staticmethod
    def seed_pricing_catalog():
        try:
            creator = User.query.filter(User.role.in_(['admin', 'manager', 'super_admin']), User.is_active == True).first()
            if not creator:
                return {'success': False, 'message': 'تعذر العثور على مستخدم مسؤول'}
            created = 0
            items = [
                {'service_type': 'consultation', 'service_name': 'Consultation', 'service_name_ar': 'استشارة', 'base_price': 50.0, 'insurance_coverage': 20.0, 'patient_share': 40.0},
                {'service_type': 'lab', 'service_name': 'CBC', 'service_name_ar': 'تحليل CBC', 'base_price': 30.0, 'insurance_coverage': 20.0, 'patient_share': 24.0},
                {'service_type': 'lab', 'service_name': 'Fasting Blood Glucose', 'service_name_ar': 'سكر صائم', 'base_price': 25.0, 'insurance_coverage': 20.0, 'patient_share': 20.0},
                {'service_type': 'lab', 'service_name': 'Random Blood Glucose', 'service_name_ar': 'سكر عشوائي', 'base_price': 20.0, 'insurance_coverage': 20.0, 'patient_share': 16.0},
                {'service_type': 'lab', 'service_name': 'HbA1c', 'service_name_ar': 'HbA1c', 'base_price': 45.0, 'insurance_coverage': 20.0, 'patient_share': 36.0},
                {'service_type': 'lab', 'service_name': 'Lipid Profile', 'service_name_ar': 'دهون شاملة', 'base_price': 40.0, 'insurance_coverage': 20.0, 'patient_share': 32.0},
                {'service_type': 'lab', 'service_name': 'Liver Function Tests', 'service_name_ar': 'وظائف الكبد', 'base_price': 45.0, 'insurance_coverage': 20.0, 'patient_share': 36.0},
                {'service_type': 'lab', 'service_name': 'Renal Function Tests', 'service_name_ar': 'وظائف الكلى', 'base_price': 45.0, 'insurance_coverage': 20.0, 'patient_share': 36.0},
                {'service_type': 'lab', 'service_name': 'TSH', 'service_name_ar': 'TSH', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'Free T3', 'service_name_ar': 'Free T3', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'Free T4', 'service_name_ar': 'Free T4', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'Ferritin', 'service_name_ar': 'فيريتين', 'base_price': 50.0, 'insurance_coverage': 20.0, 'patient_share': 40.0},
                {'service_type': 'lab', 'service_name': 'Iron Studies', 'service_name_ar': 'دراسات الحديد', 'base_price': 55.0, 'insurance_coverage': 20.0, 'patient_share': 44.0},
                {'service_type': 'lab', 'service_name': 'Vitamin D', 'service_name_ar': 'فيتامين D', 'base_price': 70.0, 'insurance_coverage': 20.0, 'patient_share': 56.0},
                {'service_type': 'lab', 'service_name': 'PT/INR', 'service_name_ar': 'PT/INR', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'PTT', 'service_name_ar': 'PTT', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'CRP', 'service_name_ar': 'CRP', 'base_price': 30.0, 'insurance_coverage': 20.0, 'patient_share': 24.0},
                {'service_type': 'lab', 'service_name': 'ESR', 'service_name_ar': 'ESR', 'base_price': 20.0, 'insurance_coverage': 20.0, 'patient_share': 16.0},
                {'service_type': 'lab', 'service_name': 'Rheumatoid Factor', 'service_name_ar': 'عامل روماتويدي', 'base_price': 40.0, 'insurance_coverage': 20.0, 'patient_share': 32.0},
                {'service_type': 'lab', 'service_name': 'ANA', 'service_name_ar': 'ANA', 'base_price': 60.0, 'insurance_coverage': 20.0, 'patient_share': 48.0},
                {'service_type': 'lab', 'service_name': 'HBsAg', 'service_name_ar': 'HBsAg', 'base_price': 40.0, 'insurance_coverage': 20.0, 'patient_share': 32.0},
                {'service_type': 'lab', 'service_name': 'Anti-HCV', 'service_name_ar': 'Anti-HCV', 'base_price': 50.0, 'insurance_coverage': 20.0, 'patient_share': 40.0},
                {'service_type': 'lab', 'service_name': 'HIV Antibody', 'service_name_ar': 'HIV Ab', 'base_price': 60.0, 'insurance_coverage': 20.0, 'patient_share': 48.0},
                {'service_type': 'lab', 'service_name': 'Beta-hCG', 'service_name_ar': 'Beta-hCG', 'base_price': 35.0, 'insurance_coverage': 20.0, 'patient_share': 28.0},
                {'service_type': 'lab', 'service_name': 'Blood Group and Rh', 'service_name_ar': 'فصيلة الدم وRh', 'base_price': 20.0, 'insurance_coverage': 20.0, 'patient_share': 16.0},
                {'service_type': 'lab', 'service_name': 'Electrolytes', 'service_name_ar': 'الكتروليتات', 'base_price': 30.0, 'insurance_coverage': 20.0, 'patient_share': 24.0},
                {'service_type': 'lab', 'service_name': 'Calcium', 'service_name_ar': 'كالسيوم', 'base_price': 25.0, 'insurance_coverage': 20.0, 'patient_share': 20.0},
                {'service_type': 'lab', 'service_name': 'Magnesium', 'service_name_ar': 'مغنيسيوم', 'base_price': 25.0, 'insurance_coverage': 20.0, 'patient_share': 20.0},
                {'service_type': 'lab', 'service_name': 'Phosphate', 'service_name_ar': 'فوسفات', 'base_price': 25.0, 'insurance_coverage': 20.0, 'patient_share': 20.0},
                {'service_type': 'lab', 'service_name': 'Troponin', 'service_name_ar': 'تروبونين', 'base_price': 80.0, 'insurance_coverage': 20.0, 'patient_share': 64.0},
                {'service_type': 'lab', 'service_name': 'D-Dimer', 'service_name_ar': 'دي دايمر', 'base_price': 60.0, 'insurance_coverage': 20.0, 'patient_share': 48.0},
                {'service_type': 'lab', 'service_name': 'PSA', 'service_name_ar': 'PSA', 'base_price': 55.0, 'insurance_coverage': 20.0, 'patient_share': 44.0},
                {'service_type': 'lab', 'service_name': 'Prolactin', 'service_name_ar': 'برولاكتين', 'base_price': 45.0, 'insurance_coverage': 20.0, 'patient_share': 36.0},
                {'service_type': 'lab', 'service_name': 'AFP', 'service_name_ar': 'AFP', 'base_price': 55.0, 'insurance_coverage': 20.0, 'patient_share': 44.0},
                {'service_type': 'lab', 'service_name': 'CA-125', 'service_name_ar': 'CA-125', 'base_price': 65.0, 'insurance_coverage': 20.0, 'patient_share': 52.0},
                {'service_type': 'lab', 'service_name': 'CA 19-9', 'service_name_ar': 'CA 19-9', 'base_price': 65.0, 'insurance_coverage': 20.0, 'patient_share': 52.0},
                {'service_type': 'lab', 'service_name': 'Urinalysis', 'service_name_ar': 'تحليل بول', 'base_price': 20.0, 'insurance_coverage': 20.0, 'patient_share': 16.0},
                {'service_type': 'lab', 'service_name': 'Stool Analysis', 'service_name_ar': 'تحليل براز', 'base_price': 20.0, 'insurance_coverage': 20.0, 'patient_share': 16.0},
                {'service_type': 'lab', 'service_name': 'Urine Culture', 'service_name_ar': 'زرع بول', 'base_price': 60.0, 'insurance_coverage': 20.0, 'patient_share': 48.0},
                {'service_type': 'lab', 'service_name': 'Blood Culture', 'service_name_ar': 'زرع دم', 'base_price': 80.0, 'insurance_coverage': 20.0, 'patient_share': 64.0},
                {'service_type': 'lab', 'service_name': 'Sputum Culture', 'service_name_ar': 'زرع بلغم', 'base_price': 60.0, 'insurance_coverage': 20.0, 'patient_share': 48.0},
                {'service_type': 'radiology', 'service_name': 'Chest X-ray', 'service_name_ar': 'أشعة سينية صدر', 'base_price': 80.0, 'insurance_coverage': 25.0, 'patient_share': 60.0},
                {'service_type': 'radiology', 'service_name': 'Abdomen X-ray', 'service_name_ar': 'أشعة سينية بطن', 'base_price': 80.0, 'insurance_coverage': 25.0, 'patient_share': 60.0},
                {'service_type': 'radiology', 'service_name': 'Pelvis X-ray', 'service_name_ar': 'أشعة سينية حوض', 'base_price': 80.0, 'insurance_coverage': 25.0, 'patient_share': 60.0},
                {'service_type': 'radiology', 'service_name': 'Spine X-ray', 'service_name_ar': 'أشعة سينية عمود فقري', 'base_price': 90.0, 'insurance_coverage': 25.0, 'patient_share': 67.5},
                {'service_type': 'radiology', 'service_name': 'Extremity X-ray', 'service_name_ar': 'أشعة طرف', 'base_price': 70.0, 'insurance_coverage': 25.0, 'patient_share': 52.5},
                {'service_type': 'radiology', 'service_name': 'Abdominal Ultrasound', 'service_name_ar': 'سونار البطن', 'base_price': 100.0, 'insurance_coverage': 25.0, 'patient_share': 75.0},
                {'service_type': 'radiology', 'service_name': 'Pelvic Ultrasound', 'service_name_ar': 'سونار الحوض', 'base_price': 90.0, 'insurance_coverage': 25.0, 'patient_share': 67.5},
                {'service_type': 'radiology', 'service_name': 'Obstetric Ultrasound', 'service_name_ar': 'سونار الحمل', 'base_price': 120.0, 'insurance_coverage': 25.0, 'patient_share': 90.0},
                {'service_type': 'radiology', 'service_name': 'Thyroid Ultrasound', 'service_name_ar': 'سونار الغدة الدرقية', 'base_price': 90.0, 'insurance_coverage': 25.0, 'patient_share': 67.5},
                {'service_type': 'radiology', 'service_name': 'Doppler Ultrasound', 'service_name_ar': 'سونار دوبلر', 'base_price': 140.0, 'insurance_coverage': 25.0, 'patient_share': 105.0},
                {'service_type': 'radiology', 'service_name': 'CT Head', 'service_name_ar': 'طبقي محوري للرأس', 'base_price': 250.0, 'insurance_coverage': 25.0, 'patient_share': 187.5},
                {'service_type': 'radiology', 'service_name': 'CT Chest', 'service_name_ar': 'طبقي محوري للصدر', 'base_price': 280.0, 'insurance_coverage': 25.0, 'patient_share': 210.0},
                {'service_type': 'radiology', 'service_name': 'CT Abdomen/Pelvis', 'service_name_ar': 'طبقي محوري للبطن والحوض', 'base_price': 300.0, 'insurance_coverage': 25.0, 'patient_share': 225.0},
                {'service_type': 'radiology', 'service_name': 'CT Angiography', 'service_name_ar': 'طبقي محوري شرياني', 'base_price': 350.0, 'insurance_coverage': 25.0, 'patient_share': 262.5},
                {'service_type': 'radiology', 'service_name': 'MRI Brain', 'service_name_ar': 'رنين مغناطيسي للدماغ', 'base_price': 350.0, 'insurance_coverage': 25.0, 'patient_share': 262.5},
                {'service_type': 'radiology', 'service_name': 'MRI Spine', 'service_name_ar': 'رنين مغناطيسي للعمود الفقري', 'base_price': 400.0, 'insurance_coverage': 25.0, 'patient_share': 300.0},
                {'service_type': 'radiology', 'service_name': 'MRI Knee', 'service_name_ar': 'رنين مغناطيسي للركبة', 'base_price': 350.0, 'insurance_coverage': 25.0, 'patient_share': 262.5},
                {'service_type': 'radiology', 'service_name': 'MRI Shoulder', 'service_name_ar': 'رنين مغناطيسي للكتف', 'base_price': 350.0, 'insurance_coverage': 25.0, 'patient_share': 262.5},
                {'service_type': 'radiology', 'service_name': 'MRI Abdomen', 'service_name_ar': 'رنين مغناطيسي للبطن', 'base_price': 450.0, 'insurance_coverage': 25.0, 'patient_share': 337.5},
                {'service_type': 'radiology', 'service_name': 'Mammography', 'service_name_ar': 'ماموغرام', 'base_price': 200.0, 'insurance_coverage': 25.0, 'patient_share': 150.0},
                {'service_type': 'radiology', 'service_name': 'Dental Panoramic', 'service_name_ar': 'صورة بانورامية للأسنان', 'base_price': 150.0, 'insurance_coverage': 25.0, 'patient_share': 112.5},
                {'service_type': 'radiology', 'service_name': 'Echocardiography', 'service_name_ar': 'إيكو قلب', 'base_price': 200.0, 'insurance_coverage': 25.0, 'patient_share': 150.0},
                {'service_type': 'radiology', 'service_name': 'Fluoroscopy', 'service_name_ar': 'فلوروسكوبي', 'base_price': 220.0, 'insurance_coverage': 25.0, 'patient_share': 165.0}
            ]
            for i in items:
                existing = PricingCatalog.query.filter(PricingCatalog.service_type == i['service_type'], PricingCatalog.service_name == i['service_name']).first()
                if not existing:
                    pc = PricingCatalog(**i, is_active=True, is_temporary=False, created_by=creator.id)
                    db.session.add(pc)
                    created += 1
            db.session.commit()
            return {'success': True, 'created': created}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error seeding pricing catalog: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة كتالوج الأسعار حالياً'}

    @staticmethod
    def seed_all():
        try:
            depts = PricingService.seed_departments()
            PricingService.seed_service_master()
            PricingService.seed_doctors(depts.get('departments', {}))
            PricingService.seed_technicians()
            PricingService.seed_service_prices()
            PricingService.seed_doctor_pricing()
            PricingService.seed_pricing_catalog()
            return {'success': True}
        except Exception as e:
            logging.error(f"Error seeding all: {str(e)}")
            return {'success': False, 'message': 'تعذر تهيئة البيانات الأساسية حالياً'}

    # ===================== تنظيف التكرارات =====================
    @staticmethod
    def cleanup_service_prices():
        try:
            all_prices = ServicePrice.query.order_by(ServicePrice.service_name, ServicePrice.service_type, ServicePrice.created_at.asc()).all()
            groups = {}
            for sp in all_prices:
                key = (sp.service_name.strip(), sp.service_type.strip())
                groups.setdefault(key, []).append(sp)
            removed = 0
            for key, items in groups.items():
                if len(items) > 1:
                    keep = items[0]
                    for extra in items[1:]:
                        db.session.delete(extra)
                        removed += 1
            db.session.commit()
            return {'success': True, 'removed': removed}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning service prices: {str(e)}")
            return {'success': False, 'message': 'تعذر تنظيف أسعار الخدمات حالياً'}

    @staticmethod
    def cleanup_pricing_catalog():
        try:
            all_items = PricingCatalog.query.order_by(PricingCatalog.service_type, PricingCatalog.service_name, PricingCatalog.created_at.asc()).all()
            groups = {}
            for pc in all_items:
                key = (pc.service_type.strip(), pc.service_name.strip())
                groups.setdefault(key, []).append(pc)
            removed = 0
            for key, items in groups.items():
                if len(items) > 1:
                    keep = items[0]
                    for extra in items[1:]:
                        db.session.delete(extra)
                        removed += 1
            db.session.commit()
            return {'success': True, 'removed': removed}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning pricing catalog: {str(e)}")
            return {'success': False, 'message': 'تعذر تنظيف كتالوج الأسعار حالياً'}

    @staticmethod
    def cleanup_doctor_pricing():
        try:
            all_dp = DoctorPricing.query.order_by(DoctorPricing.doctor_id, DoctorPricing.effective_from.asc(), DoctorPricing.created_at.asc()).all()
            groups = {}
            for dp in all_dp:
                key = dp.doctor_id
                groups.setdefault(key, []).append(dp)
            removed = 0
            for doc_id, items in groups.items():
                if len(items) > 1:
                    keep = items[0]
                    for extra in items[1:]:
                        db.session.delete(extra)
                        removed += 1
            db.session.commit()
            return {'success': True, 'removed': removed}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning doctor pricing: {str(e)}")
            return {'success': False, 'message': 'تعذر تنظيف أسعار الأطباء حالياً'}

    @staticmethod
    def cleanup_users_by_role(max_keep_per_role: int = 2):
        try:
            roles = ['super_admin','admin','manager','reception','doctor','lab','radiology','nurse','emergency','accountant','pharmacist']
            deactivated = 0
            for role in roles:
                users = User.query.filter_by(role=role).order_by(User.id.asc()).all()
                if len(users) > max_keep_per_role:
                    to_deactivate = users[max_keep_per_role:]
                    for u in to_deactivate:
                        u.is_active = False
                        if role == 'doctor':
                            dps = DoctorPricing.query.filter_by(doctor_id=u.id).all()
                            for dp in dps:
                                db.session.delete(dp)
                        deactivated += 1
            db.session.commit()
            return {'success': True, 'deactivated': deactivated}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning users: {str(e)}")
            return {'success': False, 'message': 'تعذر تنظيف المستخدمين حالياً'}

    @staticmethod
    def cleanup_all(max_keep_per_role: int = 2):
        try:
            r1 = PricingService.cleanup_service_prices()
            r2 = PricingService.cleanup_pricing_catalog()
            r3 = PricingService.cleanup_doctor_pricing()
            r4 = PricingService.cleanup_users_by_role(max_keep_per_role)
            return {'success': True, 'service_prices_removed': r1.get('removed', 0), 'catalog_removed': r2.get('removed', 0), 'doctor_pricing_removed': r3.get('removed', 0), 'users_deactivated': r4.get('deactivated', 0)}
        except Exception as e:
            logging.error(f"Error cleaning all: {str(e)}")
            return {'success': False, 'message': 'تعذر تنفيذ عملية التنظيف حالياً'}

    @staticmethod
    def purge_users_keep_policy():
        try:
            kept_ids = set()
            dept_map = {d.name: d.id for d in Department.query.all()}

            def _keep_first(role):
                u = User.query.filter_by(role=role, is_active=True).order_by(User.id.asc()).first()
                if u:
                    kept_ids.add(u.id)
                return u

            def _ensure_doctor_in(dept_name, username, email, full_name):
                dept_id = dept_map.get(dept_name)
                u = User.query.filter_by(role='doctor', department_id=dept_id).order_by(User.id.asc()).first()
                if not u:
                    u = User(username=username, email=email, full_name=full_name, role='doctor', department_id=dept_id, is_active=True)
                    u.set_password('p')
                    db.session.add(u)
                    db.session.flush()
                kept_ids.add(u.id)

            def _ensure_staff(role, dept_name, username, email, full_name):
                dept_id = dept_map.get(dept_name)
                u = User.query.filter_by(role=role, department_id=dept_id).order_by(User.id.asc()).first()
                if not u:
                    u = User(username=username, email=email, full_name=full_name, role=role, department_id=dept_id, is_active=True)
                    u.set_password('p')
                    db.session.add(u)
                    db.session.flush()
                kept_ids.add(u.id)

            su = _keep_first('super_admin')
            _keep_first('manager')
            _keep_first('reception')

            specialties = [
                ('Internal Medicine', 'dr_internal', 'dr_internal@example.com', 'طبيب الباطنية'),
                ('Gynecology', 'dr_gyne', 'dr_gyne@example.com', 'طبيب النسائية'),
                ('Pediatrics', 'dr_pediatrics', 'dr_pediatrics@example.com', 'طبيب الأطفال'),
                ('General Surgery', 'dr_surgery', 'dr_surgery@example.com', 'طبيب الجراحة العامة'),
                ('Orthopedics', 'dr_orthopedics', 'dr_orthopedics@example.com', 'طبيب العظام'),
                ('Cardiology', 'dr_cardiology', 'dr_cardiology@example.com', 'طبيب القلبية'),
                ('ENT', 'dr_ent', 'dr_ent@example.com', 'طبيب الأنف والأذن والحنجرة'),
                ('Ophthalmology', 'dr_ophthalmology', 'dr_ophthalmology@example.com', 'طبيب العيون'),
                ('Dermatology', 'dr_dermatology', 'dr_dermatology@example.com', 'طبيب الجلدية'),
                ('Urology', 'dr_urology', 'dr_urology@example.com', 'طبيب المسالك البولية'),
                ('Neurology', 'dr_neurology', 'dr_neurology@example.com', 'طبيب الأعصاب')
            ]
            for dept_name, uname, email, fname in specialties:
                _ensure_doctor_in(dept_name, uname, email, fname)

            _ensure_staff('lab', 'Lab', 'lab_tech', 'lab_tech@example.com', 'فني مختبر')
            _ensure_staff('radiology', 'Radiology', 'radiology_tech', 'radiology_tech@example.com', 'فني أشعة')
            _ensure_doctor_in('Emergency', 'dr_emergency', 'dr_emergency@example.com', 'طبيب الطوارئ')

            gc_doc = User.query.filter_by(role='doctor').join(Department, User.department_id == Department.id).filter(Department.name == 'General Clinic').order_by(User.id.asc()).first()
            if gc_doc:
                kept_ids.add(gc_doc.id)

            to_delete = User.query.filter(User.id.notin_(kept_ids)).all()
            deleted = 0
            for u in to_delete:
                if su and u.id == su.id:
                    continue
                if u.role == 'doctor':
                    for dp in DoctorPricing.query.filter_by(doctor_id=u.id).all():
                        db.session.delete(dp)
                db.session.delete(u)
                deleted += 1
            db.session.commit()
            return {'success': True, 'deleted': deleted, 'kept': len(kept_ids)}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error purging users: {str(e)}")
            return {'success': False, 'message': 'تعذر تنفيذ عملية الحذف حالياً'}
