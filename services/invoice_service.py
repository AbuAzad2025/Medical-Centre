"""
خدمة إدارة الفواتير - Invoice Management Service
Medical System Invoice Management Service
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from app_factory import db
from models.invoice import Invoice, InvoiceService
from models.visit import Visit
from models.patient import Patient
from models.user import User
from models.department import Department
from models.lab_request import LabRequest
from models.radiology_test import RadiologyTest
from models.payment import Payment
import logging
import secrets
import string

class InvoiceService:
    """خدمة إدارة الفواتير الموحدة"""
    
    @staticmethod
    def generate_invoice_number():
        """توليد رقم فاتورة فريد"""
        try:
            # الحصول على آخر رقم فاتورة
            last_invoice = Invoice.query.order_by(Invoice.id.desc()).first()
            if last_invoice:
                last_number = int(last_invoice.invoice_number.split('-')[-1]) if '-' in last_invoice.invoice_number else 0
                new_number = last_number + 1
            else:
                new_number = 1
            
            # تنسيق رقم الفاتورة: INV-YYYY-MM-DD-XXXX
            today = datetime.now()
            invoice_number = f"INV-{today.year:04d}-{today.month:02d}-{today.day:02d}-{new_number:04d}"
            
            return invoice_number
            
        except Exception as e:
            logging.error(f"Error generating invoice number: {str(e)}")
            # رقم احتياطي
            return f"INV-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4)}"
    
    @staticmethod
    def create_invoice(patient_id, visit_id=None, services_data=None, created_by=None, **kwargs):
        """إنشاء فاتورة جديدة"""
        try:
            # التحقق من وجود المريض
            patient = Patient.query.get(patient_id)
            if not patient:
                return {'success': False, 'message': 'المريض غير موجود'}
            
            # إنشاء الفاتورة
            invoice = Invoice(
                invoice_number=InvoiceService.generate_invoice_number(),
                patient_id=patient_id,
                visit_id=visit_id,
                issue_date=datetime.utcnow(),
                due_date=kwargs.get('due_date', datetime.utcnow() + timedelta(days=30)),
                total_amount=0.0,
                discount_amount=kwargs.get('discount_amount', 0.0),
                tax_amount=kwargs.get('tax_amount', 0.0),
                net_amount=0.0,
                paid_amount=0.0,
                balance_due=0.0,
                status='PENDING',
                payment_method=kwargs.get('payment_method'),
                force_payment=kwargs.get('force_payment', False),
                force_payment_reason=kwargs.get('force_payment_reason'),
                force_payment_approved_by=kwargs.get('force_payment_approved_by'),
                force_payment_approved_at=kwargs.get('force_payment_approved_at'),
                notes=kwargs.get('notes'),
                created_by=created_by,
                updated_by=created_by
            )
            
            db.session.add(invoice)
            db.session.flush()  # للحصول على ID
            
            # إضافة الخدمات
            if services_data:
                for service_data in services_data:
                    service = InvoiceService(
                        invoice_id=invoice.id,
                        service_name=service_data.get('service_name', ''),
                        service_type=service_data.get('service_type', ''),
                        service_id=service_data.get('service_id'),
                        quantity=service_data.get('quantity', 1),
                        unit_price=service_data.get('unit_price', 0.0),
                        total_price=service_data.get('total_price', 0.0),
                        notes=service_data.get('notes'),
                        department_id=service_data.get('department_id'),
                        provider_id=service_data.get('provider_id')
                    )
                    db.session.add(service)
            
            # حساب المبالغ
            invoice.calculate_amounts()
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'تم إنشاء الفاتورة بنجاح',
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating invoice: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إنشاء الفاتورة: {str(e)}'}
    
    @staticmethod
    def add_service_to_invoice(invoice_id, service_data):
        """إضافة خدمة إلى الفاتورة"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            # إنشاء الخدمة
            service = InvoiceService(
                invoice_id=invoice_id,
                service_name=service_data.get('service_name', ''),
                service_type=service_data.get('service_type', ''),
                service_id=service_data.get('service_id'),
                quantity=service_data.get('quantity', 1),
                unit_price=service_data.get('unit_price', 0.0),
                total_price=service_data.get('total_price', 0.0),
                notes=service_data.get('notes'),
                department_id=service_data.get('department_id'),
                provider_id=service_data.get('provider_id')
            )
            
            db.session.add(service)
            
            # إعادة حساب المبالغ
            invoice.calculate_amounts()
            
            db.session.commit()
            
            return {'success': True, 'message': 'تم إضافة الخدمة بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding service to invoice: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إضافة الخدمة: {str(e)}'}
    
    @staticmethod
    def process_payment(invoice_id, payment_data, processed_by=None):
        """معالجة الدفع للفاتورة"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            payment_method = payment_data.get('payment_method')
            paid_amount = float(payment_data.get('paid_amount', 0))
            
            if not payment_method or paid_amount <= 0:
                return {'success': False, 'message': 'بيانات الدفع مطلوبة'}
            
            # تحديث حالة الدفع
            invoice.paid_amount += paid_amount
            invoice.payment_method = payment_method
            invoice.updated_by = processed_by
            invoice.updated_at = datetime.utcnow()
            
            # إعادة حساب المبالغ
            invoice.calculate_amounts()
            
            # إنشاء سجل دفع
            payment = Payment(
                invoice_id=invoice_id,
                amount=paid_amount,
                payment_method=payment_method,
                payment_date=datetime.utcnow(),
                notes=payment_data.get('notes'),
                created_by=processed_by
            )
            
            db.session.add(payment)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'تم معالجة الدفع بنجاح',
                'invoice_status': invoice.status,
                'balance_due': invoice.balance_due
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing payment: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في معالجة الدفع: {str(e)}'}
    
    @staticmethod
    def force_payment(invoice_id, reason, approved_by=None):
        """تفعيل الدفع القوي للفاتورة"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            # تفعيل الدفع القوي
            invoice.force_payment = True
            invoice.force_payment_reason = reason
            invoice.force_payment_approved_by = approved_by
            invoice.force_payment_approved_at = datetime.utcnow()
            invoice.status = 'FORCE_PAYMENT'
            invoice.payment_status = 'FORCE_ENTRY'
            invoice.updated_by = approved_by
            invoice.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return {'success': True, 'message': 'تم تفعيل الدفع القوي بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error forcing payment: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تفعيل الدفع القوي: {str(e)}'}
    
    @staticmethod
    def get_invoice_summary(invoice_id):
        """الحصول على ملخص الفاتورة"""
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            return {
                'success': True,
                'invoice': invoice.to_dict(),
                'services': [service.to_dict() for service in invoice.services],
                'payments': [payment.to_dict() for payment in invoice.payments]
            }
            
        except Exception as e:
            logging.error(f"Error getting invoice summary: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في الحصول على ملخص الفاتورة: {str(e)}'}
    
    @staticmethod
    def get_patient_invoices(patient_id, status=None):
        """الحصول على فواتير المريض"""
        try:
            query = Invoice.query.filter(Invoice.patient_id == patient_id)
            
            if status:
                query = query.filter(Invoice.status == status)
            
            invoices = query.order_by(Invoice.created_at.desc()).all()
            
            return {
                'success': True,
                'invoices': [invoice.to_dict() for invoice in invoices],
                'total_count': len(invoices)
            }
            
        except Exception as e:
            logging.error(f"Error getting patient invoices: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في الحصول على فواتير المريض: {str(e)}'}
    
    @staticmethod
    def get_financial_summary(start_date=None, end_date=None, department_id=None):
        """الحصول على الملخص المالي"""
        try:
            query = Invoice.query
            
            if start_date:
                query = query.filter(Invoice.created_at >= start_date)
            if end_date:
                query = query.filter(Invoice.created_at <= end_date)
            if department_id:
                query = query.join(InvoiceService).filter(InvoiceService.department_id == department_id)
            
            invoices = query.all()
            
            # حساب الإحصائيات
            total_invoices = len(invoices)
            total_amount = sum(invoice.total_amount for invoice in invoices)
            paid_amount = sum(invoice.paid_amount for invoice in invoices)
            pending_amount = total_amount - paid_amount
            
            # حسب الحالة
            status_summary = {}
            for invoice in invoices:
                status = invoice.status
                if status not in status_summary:
                    status_summary[status] = {'count': 0, 'amount': 0}
                status_summary[status]['count'] += 1
                status_summary[status]['amount'] += invoice.total_amount
            
            return {
                'success': True,
                'summary': {
                    'total_invoices': total_invoices,
                    'total_amount': total_amount,
                    'paid_amount': paid_amount,
                    'pending_amount': pending_amount,
                    'status_summary': status_summary
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting financial summary: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في الحصول على الملخص المالي: {str(e)}'}
    
    @staticmethod
    def create_visit_invoice(visit_id, created_by=None):
        """إنشاء فاتورة للزيارة"""
        try:
            visit = Visit.query.get(visit_id)
            if not visit:
                return {'success': False, 'message': 'الزيارة غير موجودة'}
            
            # إعداد بيانات الخدمات
            services_data = []
            
            # خدمة الاستشارة
            if visit.doctor_id:
                services_data.append({
                    'service_name': f'استشارة طبية - {visit.doctor.full_name if visit.doctor else "طبيب"}',
                    'service_type': 'consultation',
                    'service_id': visit.doctor_id,
                    'quantity': 1,
                    'unit_price': visit.doctor_pricing or 0.0,
                    'total_price': visit.doctor_pricing or 0.0,
                    'department_id': visit.department_id,
                    'provider_id': visit.doctor_id
                })
            
            # خدمات المختبر
            if visit.lab_requests:
                for lab_request in visit.lab_requests:
                    services_data.append({
                        'service_name': f'فحص مختبر - {lab_request.lab_test.name if lab_request.lab_test else "فحص"}',
                        'service_type': 'lab_test',
                        'service_id': lab_request.lab_test_id,
                        'quantity': 1,
                        'unit_price': lab_request.lab_test.pricing or 0.0,
                        'total_price': lab_request.lab_test.pricing or 0.0,
                        'department_id': visit.department_id,
                        'provider_id': visit.doctor_id
                    })
            
            # خدمات الأشعة
            if visit.radiology_requests:
                for radiology_request in visit.radiology_requests:
                    services_data.append({
                        'service_name': f'فحص أشعة - {radiology_request.radiology_test.name if radiology_request.radiology_test else "فحص"}',
                        'service_type': 'radiology_scan',
                        'service_id': radiology_request.radiology_test_id,
                        'quantity': 1,
                        'unit_price': radiology_request.radiology_test.pricing or 0.0,
                        'total_price': radiology_request.radiology_test.pricing or 0.0,
                        'department_id': visit.department_id,
                        'provider_id': visit.doctor_id
                    })
            
            # إنشاء الفاتورة
            result = InvoiceService.create_invoice(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                services_data=services_data,
                created_by=created_by
            )
            
            if result['success']:
                # تحديث حالة الزيارة
                visit.invoice_id = result['invoice_id']
                visit.status = 'PENDING_PAYMENT'
                visit.payment_status = 'PENDING'
                db.session.commit()
            
            return result
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating visit invoice: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إنشاء فاتورة الزيارة: {str(e)}'}
    
    # ==================== تحسينات الأسبوع الثاني ====================
    
    @staticmethod
    def cancel_invoice(invoice_id, user_id, reason):
        """
        إلغاء فاتورة
        ملاحظة: لا يتم الحذف، بل يتم التعليم كملغية فقط
        """
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            # التحقق من أنها لم تُدفع
            if invoice.status == 'PAID':
                return {'success': False, 'message': 'لا يمكن إلغاء فاتورة مدفوعة'}
            
            # التحقق من أنها لم تُلغى مسبقاً
            if invoice.status == 'CANCELLED':
                return {'success': False, 'message': 'الفاتورة ملغاة مسبقاً'}
            
            # التحقق من السبب
            if not reason or len(reason.strip()) < 5:
                return {'success': False, 'message': 'يجب تقديم سبب الإلغاء'}
            
            # الإلغاء
            old_status = invoice.status
            invoice.status = 'CANCELLED'
            invoice.cancelled_by = user_id
            invoice.cancelled_at = datetime.utcnow()
            invoice.cancellation_reason = reason
            invoice.updated_by = user_id
            invoice.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            # تسجيل في التدقيق
            from models.audit_trail import AuditTrail
            audit = AuditTrail(
                user_id=user_id,
                action='CANCEL',
                entity_type='invoice',
                entity_id=invoice_id,
                old_values=f'{{"status": "{old_status}"}}',
                new_values=f'{{"status": "CANCELLED", "reason": "{reason}"}}',
                description=f'إلغاء فاتورة - {reason}'
            )
            db.session.add(audit)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'تم إلغاء الفاتورة بنجاح',
                'invoice_number': invoice.invoice_number
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cancelling invoice: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إلغاء الفاتورة: {str(e)}'}
    
    @staticmethod
    def link_payment_to_invoice(invoice_id, payment_id):
        """
        ربط دفعة بفاتورة
        """
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            payment = Payment.query.get(payment_id)
            if not payment:
                return {'success': False, 'message': 'الدفعة غير موجودة'}
            
            # ربط الدفعة بالفاتورة
            payment.invoice_id = invoice_id
            
            # تحديث المبلغ المدفوع في الفاتورة
            invoice.paid_amount = float(invoice.paid_amount or 0) + float(payment.amount)
            invoice.balance_due = float(invoice.net_amount) - float(invoice.paid_amount)
            
            # تحديث حالة الفاتورة
            if invoice.balance_due <= 0:
                invoice.status = 'PAID'
                invoice.paid_at = datetime.utcnow()
            elif invoice.paid_amount > 0:
                invoice.status = 'PARTIALLY_PAID'
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'تم ربط الدفعة بالفاتورة',
                'balance_due': float(invoice.balance_due)
            }
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error linking payment to invoice: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في ربط الدفعة: {str(e)}'}
    
    @staticmethod
    def get_invoice_with_details(invoice_id):
        """
        الحصول على فاتورة مع جميع التفاصيل
        """
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return {'success': False, 'message': 'الفاتورة غير موجودة'}
            
            # جلب الخدمات
            services = InvoiceService.query.filter_by(invoice_id=invoice_id).all()
            
            # جلب المدفوعات المرتبطة
            payments = Payment.query.filter_by(invoice_id=invoice_id).all()
            
            return {
                'success': True,
                'invoice': {
                    'id': invoice.id,
                    'invoice_number': invoice.invoice_number,
                    'patient_id': invoice.patient_id,
                    'visit_id': invoice.visit_id,
                    'total_amount': float(invoice.total_amount),
                    'discount_amount': float(invoice.discount_amount or 0),
                    'tax_amount': float(invoice.tax_amount or 0),
                    'net_amount': float(invoice.net_amount),
                    'paid_amount': float(invoice.paid_amount or 0),
                    'balance_due': float(invoice.balance_due or 0),
                    'status': invoice.status,
                    'payment_method': invoice.payment_method,
                    'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                    'paid_at': invoice.paid_at.isoformat() if invoice.paid_at else None
                },
                'services': [
                    {
                        'service_name': s.service_name,
                        'quantity': s.quantity,
                        'unit_price': float(s.unit_price),
                        'total_price': float(s.total_price)
                    } for s in services
                ],
                'payments': [
                    {
                        'id': p.id,
                        'amount': float(p.amount),
                        'method': p.method,
                        'payment_date': p.payment_date.isoformat() if p.payment_date else None
                    } for p in payments
                ]
            }
            
        except Exception as e:
            logging.error(f"Error getting invoice details: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ: {str(e)}'}
