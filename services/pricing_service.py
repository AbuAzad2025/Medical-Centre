"""
خدمة إدارة الأسعار - Pricing Management Service
Medical System Pricing Management Service
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from app_factory import db
from models.pricing import ServicePrice, DoctorPricing, InsuranceProvider
from models.user import User
from models.department import Department
from models.lab_request import LabRequest
from models.radiology_test import RadiologyTest
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
                        ServicePrice.effective_to > datetime.utcnow()
                    )
                )
            )
            
            if department_id:
                query = query.filter(ServicePrice.department_id == department_id)
            
            service_price = query.first()
            
            if service_price:
                return service_price.get_price(payment_method)
            else:
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
    def get_doctor_price(doctor_id, visit_type='consultation', payment_method='cash'):
        """الحصول على سعر الطبيب"""
        try:
            doctor_pricing = DoctorPricing.query.filter(
                and_(
                    DoctorPricing.doctor_id == doctor_id,
                    DoctorPricing.is_active == True,
                    or_(
                        DoctorPricing.effective_to.is_(None),
                        DoctorPricing.effective_to > datetime.utcnow()
                    )
                )
            ).first()
            
            if doctor_pricing:
                return doctor_pricing.get_price(visit_type, payment_method)
            else:
                # البحث عن السعر الافتراضي للقسم
                doctor = User.query.get(doctor_id)
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
                effective_from=service_data.get('effective_from', datetime.utcnow()),
                effective_to=service_data.get('effective_to'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(service_price)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إنشاء سعر الخدمة بنجاح', 'service_price_id': service_price.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating service price: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إنشاء سعر الخدمة: {str(e)}'}
    
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
                effective_from=pricing_data.get('effective_from', datetime.utcnow()),
                effective_to=pricing_data.get('effective_to'),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(doctor_pricing)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إنشاء أسعار الطبيب بنجاح', 'pricing_id': doctor_pricing.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating doctor pricing: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إنشاء أسعار الطبيب: {str(e)}'}
    
    @staticmethod
    def update_service_price(service_price_id, update_data):
        """تحديث سعر الخدمة"""
        try:
            service_price = ServicePrice.query.get(service_price_id)
            if not service_price:
                return {'success': False, 'message': 'سعر الخدمة غير موجود'}
            
            # تحديث البيانات
            for key, value in update_data.items():
                if hasattr(service_price, key):
                    setattr(service_price, key, value)
            
            service_price.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'success': True, 'message': 'تم تحديث سعر الخدمة بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating service price: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحديث سعر الخدمة: {str(e)}'}
    
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
            return {'success': False, 'message': f'حدث خطأ في الحصول على ملخص الأسعار: {str(e)}'}
    
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
            return {'success': False, 'message': f'حدث خطأ في إنشاء الأسعار الافتراضية: {str(e)}'}
    
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
                if doctor_price > 0:
                    total_cost += doctor_price
                    services.append({
                        'name': 'استشارة طبية',
                        'type': 'consultation',
                        'price': doctor_price
                    })
            
            # تكلفة التحاليل
            if visit_data.get('lab_tests'):
                for lab_test_id in visit_data['lab_tests']:
                    lab_test = LabRequest.query.get(lab_test_id)
                    if lab_test:
                        lab_price = PricingService.get_service_price(
                            lab_test.name,
                            'lab_test',
                            visit_data.get('payment_method', 'cash')
                        )
                        if lab_price > 0:
                            total_cost += lab_price
                            services.append({
                                'name': f'فحص مختبر - {lab_test.name_ar}',
                                'type': 'lab_test',
                                'price': lab_price
                            })
            
            # تكلفة الأشعة
            if visit_data.get('radiology_tests'):
                for radiology_test_id in visit_data['radiology_tests']:
                    radiology_test = RadiologyResult.query.get(radiology_test_id)
                    if radiology_test:
                        radiology_price = PricingService.get_service_price(
                            radiology_test.name,
                            'radiology_scan',
                            visit_data.get('payment_method', 'cash')
                        )
                        if radiology_price > 0:
                            total_cost += radiology_price
                            services.append({
                                'name': f'فحص أشعة - {radiology_test.name_ar}',
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
            return {'success': False, 'message': f'حدث خطأ في حساب تكلفة الزيارة: {str(e)}'}