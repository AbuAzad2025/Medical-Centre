"""
خدمة إدارة الطابور - Queue Management Service
Medical System Queue Management Service
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, desc, asc
from app_factory import db
import logging

class QueueManagementService:
    """خدمة إدارة الطابور المتقدمة"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def add_patient_to_queue(self, patient_id, department_id, doctor_id=None, 
                           visit_id=None, appointment_id=None, queue_type='normal',
                           is_emergency=False, emergency_reason=None,
                           force_entry=False, force_entry_reason=None,
                           payment_status='PENDING', created_by=None):
        """إضافة مريض إلى الطابور"""
        try:
            from models.queue_management import QueueManagement, QueueSettings
            
            # التحقق من إعدادات الطابور
            settings = QueueSettings.query.filter_by(department_id=department_id).first()
            if not settings:
                # إنشاء إعدادات افتراضية
                settings = QueueSettings(
                    department_id=department_id,
                    require_payment_before_queue=True,
                    allow_emergency_debt=True,
                    allow_force_entry=True
                )
                db.session.add(settings)
                db.session.flush()
            
            # التحقق من شروط الدخول
            can_enter, reason = self._check_queue_entry_conditions(
                patient_id, department_id, payment_status, is_emergency, 
                force_entry, settings
            )
            
            if not can_enter:
                return False, reason
            
            # إنشاء تذكرة الطابور
            ticket = QueueManagement(
                ticket_number=QueueManagement.generate_ticket_number(),
                patient_id=patient_id,
                visit_id=visit_id,
                appointment_id=appointment_id,
                department_id=department_id,
                doctor_id=doctor_id,
                queue_type=queue_type,
                is_emergency=is_emergency,
                emergency_reason=emergency_reason,
                force_entry=force_entry,
                force_entry_reason=force_entry_reason,
                payment_status=payment_status,
                payment_required=settings.require_payment_before_queue,
                created_by=created_by
            )
            
            # تحديد مستوى الأولوية
            if is_emergency:
                ticket.priority_level = 1
            elif force_entry:
                ticket.priority_level = 2
            elif queue_type == 'vip':
                ticket.priority_level = 3
            elif queue_type == 'priority':
                ticket.priority_level = 4
            else:
                ticket.priority_level = 5
            
            db.session.add(ticket)
            db.session.commit()
            
            self.logger.info(f"Patient {patient_id} added to queue with ticket {ticket.ticket_number}")
            return True, f"تم إضافة المريض إلى الطابور - التذكرة رقم {ticket.ticket_number}"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error adding patient to queue: {str(e)}")
            return False, f"حدث خطأ في إضافة المريض إلى الطابور: {str(e)}"
    
    def _check_queue_entry_conditions(self, patient_id, department_id, payment_status, 
                                   is_emergency, force_entry, settings):
        """التحقق من شروط دخول الطابور"""
        
        # الطوارئ دائماً يمكنها الدخول
        if is_emergency:
            return True, "طوارئ - دخول مباشر"
        
        # الدخول القوي
        if force_entry and settings.allow_force_entry:
            return True, "دخول قوي - معتمد"
        
        # التحقق من حالة الدفع
        if settings.require_payment_before_queue:
            if payment_status == 'PAID':
                return True, "تم الدفع - يمكن الدخول"
            elif payment_status == 'DEBT' and settings.allow_emergency_debt:
                return True, "دين معتمد - يمكن الدخول"
            elif payment_status == 'EMERGENCY_DEBT':
                return True, "دين طوارئ - يمكن الدخول"
            else:
                return False, "يجب الدفع أولاً أو الحصول على موافقة للدين"
        
        return True, "لا يتطلب دفع"
    
    def get_queue_status(self, department_id, doctor_id=None):
        """الحصول على حالة الطابور"""
        try:
            from models.queue_management import QueueManagement
            
            query = QueueManagement.query.filter_by(department_id=department_id)
            if doctor_id:
                query = query.filter_by(doctor_id=doctor_id)
            
            # جلب المرضى في الطابور
            waiting_patients = query.filter_by(status='WAITING').order_by(
                QueueManagement.priority_level.asc(),
                QueueManagement.queued_at.asc()
            ).all()
            
            # جلب المريض الحالي
            current_patient = query.filter_by(status='IN_PROGRESS').first()
            
            # جلب المرضى المستدعين
            called_patients = query.filter_by(status='CALLING').all()
            
            return {
                'waiting_count': len(waiting_patients),
                'current_patient': current_patient.to_dict() if current_patient else None,
                'called_patients': [p.to_dict() for p in called_patients],
                'waiting_patients': [p.to_dict() for p in waiting_patients[:10]],  # أول 10 مرضى
                'estimated_wait_time': self._calculate_estimated_wait_time(department_id)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            return None
    
    def call_next_patient(self, department_id, doctor_id=None, called_by=None):
        """استدعاء المريض التالي"""
        try:
            from models.queue_management import QueueManagement
            
            # البحث عن المريض التالي
            query = QueueManagement.query.filter_by(
                department_id=department_id,
                status='WAITING'
            )
            if doctor_id:
                query = query.filter_by(doctor_id=doctor_id)
            
            next_patient = query.order_by(
                QueueManagement.priority_level.asc(),
                QueueManagement.queued_at.asc()
            ).first()
            
            if not next_patient:
                return False, "لا يوجد مرضى في الطابور"
            
            # تحديث حالة المريض
            next_patient.status = 'CALLING'
            next_patient.called_at = datetime.utcnow()
            
            db.session.commit()
            
            self.logger.info(f"Patient {next_patient.patient_id} called from queue")
            return True, f"تم استدعاء المريض - التذكرة رقم {next_patient.ticket_number}"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error calling next patient: {str(e)}")
            return False, f"حدث خطأ في استدعاء المريض: {str(e)}"
    
    def start_treatment(self, ticket_id, started_by=None):
        """بدء العلاج"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            if ticket.status != 'CALLING':
                return False, "يجب استدعاء المريض أولاً"
            
            # تحديث حالة التذكرة
            ticket.status = 'IN_PROGRESS'
            ticket.started_at = datetime.utcnow()
            
            # حساب وقت الانتظار الفعلي
            if ticket.called_at:
                wait_time = (datetime.utcnow() - ticket.called_at).total_seconds() / 60
                ticket.actual_wait_time = int(wait_time)
            
            db.session.commit()
            
            self.logger.info(f"Treatment started for ticket {ticket.ticket_number}")
            return True, "تم بدء العلاج"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error starting treatment: {str(e)}")
            return False, f"حدث خطأ في بدء العلاج: {str(e)}"
    
    def complete_treatment(self, ticket_id, completed_by=None):
        """إكمال العلاج"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            if ticket.status != 'IN_PROGRESS':
                return False, "يجب بدء العلاج أولاً"
            
            # تحديث حالة التذكرة
            ticket.status = 'COMPLETED'
            ticket.completed_at = datetime.utcnow()
            
            db.session.commit()
            
            self.logger.info(f"Treatment completed for ticket {ticket.ticket_number}")
            return True, "تم إكمال العلاج"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error completing treatment: {str(e)}")
            return False, f"حدث خطأ في إكمال العلاج: {str(e)}"
    
    def skip_patient(self, ticket_id, reason=None, skipped_by=None):
        """تخطي المريض"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة التذكرة
            ticket.status = 'SKIPPED'
            ticket.notes = f"تم التخطي - السبب: {reason}" if reason else "تم التخطي"
            
            db.session.commit()
            
            self.logger.info(f"Patient skipped for ticket {ticket.ticket_number}")
            return True, "تم تخطي المريض"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error skipping patient: {str(e)}")
            return False, f"حدث خطأ في تخطي المريض: {str(e)}"
    
    def cancel_ticket(self, ticket_id, reason=None, cancelled_by=None):
        """إلغاء التذكرة"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة التذكرة
            ticket.status = 'CANCELLED'
            ticket.notes = f"تم الإلغاء - السبب: {reason}" if reason else "تم الإلغاء"
            
            db.session.commit()
            
            self.logger.info(f"Ticket cancelled: {ticket.ticket_number}")
            return True, "تم إلغاء التذكرة"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error cancelling ticket: {str(e)}")
            return False, f"حدث خطأ في إلغاء التذكرة: {str(e)}"
    
    def _calculate_estimated_wait_time(self, department_id):
        """حساب وقت الانتظار المتوقع"""
        try:
            from models.queue_management import QueueManagement
            
            # عدد المرضى في الطابور
            waiting_count = QueueManagement.query.filter_by(
                department_id=department_id,
                status='WAITING'
            ).count()
            
            # متوسط وقت الخدمة (30 دقيقة)
            avg_service_time = 30
            
            # حساب الوقت المتوقع
            estimated_time = waiting_count * avg_service_time
            
            return estimated_time
            
        except Exception as e:
            self.logger.error(f"Error calculating wait time: {str(e)}")
            return 0
    
    def get_patient_queue_position(self, patient_id, department_id):
        """الحصول على موقع المريض في الطابور"""
        try:
            from models.queue_management import QueueManagement
            
            # البحث عن تذكرة المريض
            ticket = QueueManagement.query.filter_by(
                patient_id=patient_id,
                department_id=department_id,
                status='WAITING'
            ).first()
            
            if not ticket:
                return None, "المريض غير موجود في الطابور"
            
            # حساب الموقع
            position = QueueManagement.query.filter(
                QueueManagement.department_id == department_id,
                QueueManagement.status == 'WAITING',
                QueueManagement.priority_level < ticket.priority_level,
                QueueManagement.queued_at < ticket.queued_at
            ).count() + 1
            
            return position, f"موقع المريض في الطابور: {position}"
            
        except Exception as e:
            self.logger.error(f"Error getting queue position: {str(e)}")
            return None, f"حدث خطأ في حساب موقع المريض: {str(e)}"
    
    def approve_emergency_debt(self, ticket_id, approved_by, max_amount=None):
        """الموافقة على دين الطوارئ"""
        try:
            from models.queue_management import QueueManagement, QueueSettings
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # التحقق من إعدادات الطوارئ
            settings = QueueSettings.query.filter_by(department_id=ticket.department_id).first()
            if settings and max_amount and max_amount > settings.emergency_max_amount:
                return False, f"المبلغ يتجاوز الحد الأقصى المسموح ({settings.emergency_max_amount})"
            
            # تحديث حالة الدفع
            ticket.payment_status = 'EMERGENCY_DEBT'
            ticket.emergency_approved_by = approved_by
            ticket.emergency_approved_at = datetime.utcnow()
            
            db.session.commit()
            
            self.logger.info(f"Emergency debt approved for ticket {ticket.ticket_number}")
            return True, "تم الموافقة على دين الطوارئ"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error approving emergency debt: {str(e)}")
            return False, f"حدث خطأ في الموافقة على دين الطوارئ: {str(e)}"
    
    def approve_force_entry(self, ticket_id, approved_by, reason=None):
        """الموافقة على الدخول القوي"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = QueueManagement.query.get(ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة الدخول القوي
            ticket.force_entry = True
            ticket.force_entry_reason = reason
            ticket.force_entry_approved_by = approved_by
            ticket.force_entry_approved_at = datetime.utcnow()
            
            # رفع مستوى الأولوية
            ticket.priority_level = 2
            
            db.session.commit()
            
            self.logger.info(f"Force entry approved for ticket {ticket.ticket_number}")
            return True, "تم الموافقة على الدخول القوي"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error approving force entry: {str(e)}")
            return False, f"حدث خطأ في الموافقة على الدخول القوي: {str(e)}"
