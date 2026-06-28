"""
خدمة إدارة الطابور - Queue Management Service
Medical System Queue Management Service
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, desc, asc, case
from app.shared.enums import QueueState, VisitState, PaymentStatus
from services.visit_state_machine_service import VisitStateMachineService
from app_factory import db
import logging

class QueueManagementService:
    """خدمة إدارة الطابور المتقدمة"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _priority_rank_expr(self, QueueManagement):
        return case(
            (QueueManagement.priority_level == 'urgent', 0),
            (QueueManagement.priority_level == 'high', 1),
            (QueueManagement.priority_level == 'normal', 2),
            (QueueManagement.priority_level == 'low', 3),
            else_=4
        )

    def _visit_kind_rank_expr(self, QueueManagement, Visit):
        is_appt = case(
            (Visit.notes.ilike('%[APPOINTMENT:%'), 1),
            (Visit.notes.ilike('%[ONLINE_BOOKING:%'), 1),
            (Visit.visit_type == 'FOLLOW_UP', 1),
            else_=0
        )
        is_em = case(
            (QueueManagement.is_emergency == True, 1),
            (Visit.is_emergency == True, 1),
            (Visit.visit_type == 'EMERGENCY', 1),
            else_=0
        )
        return case(
            (is_em == 1, 0),
            (is_appt == 1, 1),
            else_=2
        )

    def _status_rank_expr(self, QueueManagement):
        return case(
            (QueueManagement.status == QueueState.WAITING, 0),
            (QueueManagement.status == QueueState.CALLED, 1),
            (QueueManagement.status == QueueState.IN_PROGRESS, 2),
            else_=9
        )
    
    def _is_user_allowed_for_department(self, user_id, department_id):
        try:
            from models.user import User
            from models.department import Department
            from models.user_department_access import UserDepartmentAccess
            user = db.session.get(User, user_id)
            dept = db.session.get(Department, department_id)
            if not user or not dept:
                return False
            if user.role in ['super_admin', 'admin', 'manager']:
                return True
            if user.department_id != dept.id:
                extra = UserDepartmentAccess.query.filter_by(user_id=user.id, department_id=dept.id, can_access=True).first()
                if not extra:
                    return False
            dept_type = getattr(dept, 'get_type', lambda: 'general')()
            allowed_roles = {
                'general': {'doctor'},
                'lab': {'lab'},
                'radiology': {'radiology'},
                'emergency': {'emergency'}
            }
            roles = allowed_roles.get(dept_type, {'doctor'})
            return user.role in roles
        except Exception:
            return False
    
    def add_patient_to_queue(self, patient_id, department_id, doctor_id=None, 
                           visit_id=None, appointment_id=None, queue_type='normal',
                           is_emergency=False, emergency_reason=None,
                           force_entry=False, force_entry_reason=None,
                           payment_status=PaymentStatus.PENDING, created_by=None):
        """إضافة مريض إلى الطابور"""
        try:
            from models.queue_management import QueueManagement, QueueSettings
            from models.visit import Visit
            from models.department import Department
            
            # التحقق من إعدادات الطابور
            settings = QueueSettings.query.filter_by(department_id=department_id).first()
            if not settings:
                # إنشاء إعدادات افتراضية
                settings = QueueSettings(
                    department_id=department_id,
                    payment_required=True,
                    emergency_payment_waived=True,
                    force_entry_allowed=True,
                    allow_partial_payment=True,
                    allow_debt=False
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

            dept_obj = db.session.get(Department, int(department_id)) if department_id else None
            if dept_obj and getattr(dept_obj, 'get_type', lambda: 'general')() == 'general':
                if not doctor_id:
                    if visit_id:
                        v = db.session.get(Visit, int(visit_id))
                        if not v or not v.doctor_id:
                            return False, "يجب اختيار طبيب للقسم التخصصي"
                    else:
                        return False, "يجب اختيار طبيب للقسم التخصصي"

            # إنشاء زيارة بسيطة للطبيب إن وُجد طبيب ولم تُحدّد زيارة
            if doctor_id and not visit_id:
                v = Visit(
                    patient_id=int(patient_id),
                    department_id=int(department_id),
                    doctor_id=int(doctor_id),
                    status=VisitState.OPEN,
                    created_by=created_by
                )
                db.session.add(v)
                db.session.flush()
                visit_id = v.id

            # إنشاء تذكرة الطابور
            ticket = QueueManagement(
                queue_number=f"Q{int(datetime.now(timezone.utc).timestamp())}",
                patient_id=patient_id,
                visit_id=visit_id,
                department_id=department_id,
                is_emergency=is_emergency,
                emergency_reason=emergency_reason,
                force_entry=force_entry,
                force_entry_reason=force_entry_reason,
                payment_status=payment_status,
                created_at=datetime.now(timezone.utc)
            )
            
            # تحديد مستوى الأولوية
            if is_emergency:
                ticket.priority_level = 'urgent'
            elif force_entry or queue_type in {'vip', 'priority'}:
                ticket.priority_level = 'high'
            else:
                ticket.priority_level = 'normal'
            
            db.session.add(ticket)
            db.session.commit()
            self._emit_queue_updates()
            
            self.logger.info(f"Patient {patient_id} added to queue with queue number {ticket.queue_number}")
            return True, f"تم إضافة المريض إلى الطابور - الرقم {ticket.queue_number}"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error adding patient to queue: {str(e)}")
            return False, f"حدث خطأ في إضافة المريض إلى الطابور: {str(e)}"

    def transfer_visit(self, visit_id, new_department_id, new_doctor_id=None, transferred_by=None, source='reception'):
        try:
            from models.visit import Visit
            from models.department import Department
            from models.queue_management import QueueManagement
            from models.visit_transfer import VisitTransferLog

            visit = db.session.get(Visit, int(visit_id))
            if not visit:
                return False, "visit_not_found"

            try:
                new_department_id = int(new_department_id)
            except Exception:
                return False, "invalid_department"

            new_doctor_id_int = None
            if new_doctor_id:
                try:
                    new_doctor_id_int = int(new_doctor_id)
                except Exception:
                    new_doctor_id_int = None

            dept = db.session.get(Department, new_department_id)
            if not dept:
                return False, "department_not_found"

            if getattr(dept, "get_type", lambda: "general")() == "general" and not new_doctor_id_int:
                return False, "doctor_required"

            qm = QueueManagement.query.filter_by(visit_id=visit.id).order_by(QueueManagement.created_at.desc()).first()
            if qm and qm.status in ["called", "in_progress"]:
                return False, "cannot_transfer_active_treatment"

            old_department_id = visit.department_id
            old_doctor_id = visit.doctor_id
            visit.department_id = new_department_id
            visit.doctor_id = new_doctor_id_int
            db.session.flush()

            if qm and qm.status == "waiting":
                qm.department_id = new_department_id

            db.session.add(VisitTransferLog(
                visit_id=visit.id,
                from_department_id=old_department_id,
                to_department_id=new_department_id,
                from_doctor_id=old_doctor_id,
                to_doctor_id=new_doctor_id_int,
                transferred_by=transferred_by,
                source=source or 'reception'
            ))

            db.session.commit()
            self._emit_queue_updates()
            self._emit_queue_updates()
            return True, "ok"
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Transfer visit error: {str(e)}")
            return False, "transfer_failed"
    
    def _check_queue_entry_conditions(self, patient_id, department_id, payment_status, 
                                   is_emergency, force_entry, settings):
        """التحقق من شروط دخول الطابور"""
        
        # الطوارئ دائماً يمكنها الدخول
        if is_emergency:
            return True, "طوارئ - دخول مباشر"
        
        # الدخول القوي
        if force_entry and settings.force_entry_allowed:
            return True, "دخول قوي - معتمد"
        
        # التحقق من حالة الدفع
        if settings.payment_required:
            if payment_status == PaymentStatus.PAID:
                return True, "تم الدفع - يمكن الدخول"
            elif payment_status == PaymentStatus.PARTIAL and getattr(settings, 'allow_partial_payment', True):
                return True, "دفع جزئي - يمكن الدخول"
            elif payment_status == PaymentStatus.DEBT and getattr(settings, 'allow_debt', False):
                return True, "دين معتمد - يمكن الدخول"
            elif payment_status == PaymentStatus.EMERGENCY_DEBT and settings.emergency_payment_waived:
                return True, "دين طوارئ - يمكن الدخول"
            else:
                return False, "يجب الدفع أولاً أو الحصول على موافقة للدين"
        
        return True, "لا يتطلب دفع"
    
    def get_queue_status(self, department_id, doctor_id=None):
        """الحصول على حالة الطابور"""
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit
            from models.patient import Patient
            from models.user import User
            from models.department import Department
            
            query = QueueManagement.query.filter_by(department_id=department_id).outerjoin(Visit, Visit.id == QueueManagement.visit_id)
            if doctor_id:
                # فلترة حسب الطبيب عبر الربط على الزيارة
                query = query.filter(Visit.doctor_id == doctor_id)
            
            # جلب المرضى في الطابور
            priority_rank = self._priority_rank_expr(QueueManagement)
            kind_rank = self._visit_kind_rank_expr(QueueManagement, Visit)
            # Use explicit column criteria: after the outerjoin, filter_by() would
            # bind to the joined Visit entity instead of QueueManagement.
            waiting_patients = query.filter(QueueManagement.status == QueueState.WAITING).order_by(
                kind_rank.asc(),
                priority_rank.asc(),
                QueueManagement.queued_at.asc()
            ).all()
            
            # جلب المريض الحالي
            current_patient = query.filter(QueueManagement.status == QueueState.IN_PROGRESS).first()
            
            # جلب المرضى المستدعين
            called_patients = query.filter(QueueManagement.status == QueueState.CALLED).all()

            def enrich(ticket: QueueManagement):
                d = ticket.to_dict()
                try:
                    now = datetime.now(timezone.utc)
                    qa = ticket.queued_at
                    if qa and qa.tzinfo is None:
                        qa = qa.replace(tzinfo=timezone.utc)
                    wait_minutes = None
                    if qa:
                        wait_minutes = int(max(0, (now - qa).total_seconds()) // 60)
                    d['ticket_id'] = ticket.id
                    d['ticket_number'] = ticket.queue_number
                    d['patient_name'] = ticket.patient.full_name if getattr(ticket, 'patient', None) else None
                    d['department_name'] = (ticket.department.name_ar or ticket.department.name) if getattr(ticket, 'department', None) else None
                    d['status_display'] = ticket.get_status_display()
                    d['priority_display'] = ticket.get_priority_display()
                    d['queued_at_display'] = ticket.queued_at.strftime('%Y-%m-%d %H:%M') if ticket.queued_at else None
                    d['called_at_display'] = ticket.called_at.strftime('%Y-%m-%d %H:%M') if ticket.called_at else None
                    d['wait_minutes'] = wait_minutes
                    d['doctor_name'] = None
                    if ticket.visit_id:
                        v = db.session.get(Visit, ticket.visit_id)
                        if v and v.doctor_id:
                            doc = db.session.get(User, v.doctor_id)
                    d['queued_at_display'] = ticket.queued_at.strftime('%Y-%m-%d %H:%M') if ticket.queued_at else None
                    d['called_at_display'] = ticket.called_at.strftime('%Y-%m-%d %H:%M') if ticket.called_at else None
                    d['wait_minutes'] = wait_minutes
                    d['doctor_name'] = None
                    if ticket.visit_id:
                        v = db.session.get(Visit, ticket.visit_id)
                        if v and v.doctor_id:
                            doc = db.session.get(User, v.doctor_id)
                            d['doctor_name'] = doc.full_name if doc else None
                    return d
                except Exception:
                    return d
            
            return {
                'waiting_count': len(waiting_patients),
                'current_patient': enrich(current_patient) if current_patient else None,
                'called_patients': [enrich(p) for p in called_patients],
                'waiting_patients': [enrich(p) for p in waiting_patients[:50]],
                'estimated_wait_time': self._calculate_estimated_wait_time(department_id)
            }
        except Exception as e:
            self.logger.error(f"Error getting queue status: {str(e)}")
            return None

    def get_queue_status_all(self, department_ids, doctor_id=None, status=None, priority=None, search=None, is_emergency=None, force_entry=None):
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit
            from models.user import User
            from models.department import Department
            from models.patient import Patient

            q = QueueManagement.query.filter(QueueManagement.department_id.in_(department_ids)).outerjoin(Visit, Visit.id == QueueManagement.visit_id)
            if doctor_id:
                q = q.filter(Visit.doctor_id == doctor_id)

            if status:
                q = q.filter(QueueManagement.status == status)
            else:
                q = q.filter(QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS]))
            if priority:
                q = q.filter(QueueManagement.priority_level == priority)
            if is_emergency is not None:
                q = q.filter(QueueManagement.is_emergency == bool(is_emergency))
            if force_entry is not None:
                q = q.filter(QueueManagement.force_entry == bool(force_entry))
            if search:
                q = q.join(Patient, Patient.id == QueueManagement.patient_id).filter(
                    db.or_(Patient.full_name.ilike(f"%{search}%"), QueueManagement.queue_number.ilike(f"%{search}%"))
                )

            status_rank = self._status_rank_expr(QueueManagement)
            priority_rank = self._priority_rank_expr(QueueManagement)
            kind_rank = self._visit_kind_rank_expr(QueueManagement, Visit)
            tickets = q.order_by(status_rank.asc(), kind_rank.asc(), priority_rank.asc(), QueueManagement.queued_at.asc()).all()

            def enrich(ticket: QueueManagement):
                d = ticket.to_dict()
                try:
                    now = datetime.now(timezone.utc)
                    qa = ticket.queued_at
                    if qa and qa.tzinfo is None:
                        qa = qa.replace(tzinfo=timezone.utc)
                    wait_minutes = None
                    if qa:
                        wait_minutes = int(max(0, (now - qa).total_seconds()) // 60)
                    d['ticket_id'] = ticket.id
                    d['ticket_number'] = ticket.queue_number
                    d['patient_name'] = ticket.patient.full_name if getattr(ticket, 'patient', None) else None
                    d['department_name'] = (ticket.department.name_ar or ticket.department.name) if getattr(ticket, 'department', None) else None
                    d['status_display'] = ticket.get_status_display()
                    d['priority_display'] = ticket.get_priority_display()
                    d['queued_at_display'] = ticket.queued_at.strftime('%Y-%m-%d %H:%M') if ticket.queued_at else None
                    d['called_at_display'] = ticket.called_at.strftime('%Y-%m-%d %H:%M') if ticket.called_at else None
                    d['wait_minutes'] = wait_minutes
                    d['doctor_name'] = None
                    if ticket.visit_id:
                        v = db.session.get(Visit, ticket.visit_id)
                        if v and v.doctor_id:
                            doc = db.session.get(User, v.doctor_id)
                            d['doctor_name'] = doc.full_name if doc else None
                    return d
                except Exception:
                    return d

            enriched = [enrich(t) for t in tickets]
            waiting = sum(1 for t in tickets if t.status == QueueState.WAITING)
            called = sum(1 for t in tickets if t.status == QueueState.CALLED)
            in_progress = sum(1 for t in tickets if t.status == QueueState.IN_PROGRESS)
            return {
                'tickets': enriched,
                'waiting_count': waiting,
                'called_count': called,
                'in_progress_count': in_progress
            }
        except Exception as e:
            self.logger.error(f"Error getting all queue status: {str(e)}")
            return None
    
    def call_next_patient(self, department_id, doctor_id=None, called_by=None):
        """استدعاء المريض التالي"""
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit
            
            # البحث عن المريض التالي
            query = QueueManagement.query.filter_by(
                department_id=department_id,
                status=QueueState.WAITING
            )
            query = query.outerjoin(Visit, Visit.id == QueueManagement.visit_id)
            if doctor_id:
                query = query.filter(Visit.doctor_id == doctor_id)
            
            priority_rank = self._priority_rank_expr(QueueManagement)
            kind_rank = self._visit_kind_rank_expr(QueueManagement, Visit)
            next_patient = query.order_by(
                kind_rank.asc(),
                priority_rank.asc(),
                QueueManagement.queued_at.asc()
            ).first()
            
            if not next_patient:
                return False, "لا يوجد مرضى في الطابور"
            
            # تحديث حالة المريض
            next_patient.status = QueueState.CALLED
            next_patient.called_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            self.logger.info(f"Patient {next_patient.patient_id} called from queue")
            return True, f"تم استدعاء المريض - التذكرة رقم {next_patient.queue_number}"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error calling next patient: {str(e)}")
            return False, f"حدث خطأ في استدعاء المريض: {str(e)}"

    def get_wait_metrics_today(self, department_ids):
        try:
            from models.queue_management import QueueManagement
            from models.department import Department

            now = datetime.now(timezone.utc)
            start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)

            rows = QueueManagement.query.filter(
                QueueManagement.department_id.in_(department_ids),
                QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS, QueueState.COMPLETED]),
                QueueManagement.queued_at >= start
            ).all()

            dept_minutes = {}
            dept_counts = {}
            all_minutes = []
            for t in rows:
                qa = t.queued_at
                ca = t.called_at or now
                if qa and qa.tzinfo is None:
                    qa = qa.replace(tzinfo=timezone.utc)
                if ca and ca.tzinfo is None:
                    ca = ca.replace(tzinfo=timezone.utc)
                if not qa or not ca:
                    continue
                mins = int(max(0, (ca - qa).total_seconds()) // 60)
                all_minutes.append(mins)
                dept_minutes[t.department_id] = dept_minutes.get(t.department_id, 0) + mins
                dept_counts[t.department_id] = dept_counts.get(t.department_id, 0) + 1

            departments = Department.query.filter(Department.id.in_(department_ids)).all() if department_ids else []
            dept_names = {d.id: (d.name_ar or d.name) for d in departments}

            per_dept = {}
            for dep_id in department_ids:
                cnt = dept_counts.get(dep_id, 0)
                if cnt <= 0:
                    per_dept[dep_id] = None
                else:
                    per_dept[dep_id] = int(round(dept_minutes.get(dep_id, 0) / cnt))

            overall = int(round(sum(all_minutes) / len(all_minutes))) if all_minutes else None

            return {
                'overall_avg_wait_minutes': overall,
                'by_department': [
                    {'department_id': dep_id, 'department_name': dept_names.get(dep_id, str(dep_id)), 'avg_wait_minutes': per_dept.get(dep_id)}
                    for dep_id in department_ids
                ]
            }
        except Exception as e:
            self.logger.error(f"Error computing wait metrics: {str(e)}")
            return {'overall_avg_wait_minutes': None, 'by_department': []}
    
    def start_treatment(self, ticket_id, started_by=None):
        """بدء العلاج"""
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            if ticket.status != QueueState.CALLED:
                return False, "يجب استدعاء المريض أولاً"
            
            if started_by:
                allowed = self._is_user_allowed_for_department(started_by, ticket.department_id)
                if not allowed:
                    v = None
                    if ticket.visit_id:
                        try:
                            v = db.session.get(Visit, ticket.visit_id)
                        except Exception:
                            v = None
                    if not (v and v.doctor_id == started_by):
                        return False, "ليس لديك صلاحية لبدء علاج هذه التذكرة"
            
            # تحديث حالة التذكرة
            ticket.status = QueueState.IN_PROGRESS
            ticket.started_at = datetime.now(timezone.utc)
            
            # مزامنة حالة الزيارة إلى IN_PROGRESS إذا وجدت
            if ticket.visit_id:
                try:
                    visit = db.session.get(Visit, ticket.visit_id)
                    if visit:
                        VisitStateMachineService.ensure_in_progress(visit, actor=started_by)
                except Exception:
                    pass
            
            # حساب وقت الانتظار الفعلي
            # يمكن حساب وقت الانتظار الفعلي لاحقاً إذا توفر الحقل
            
            db.session.commit()
            
            try:
                self.logger.info(f"Treatment started for ticket {ticket.queue_number}")
            except Exception:
                self.logger.info("Treatment started for ticket")
            return True, "تم بدء العلاج"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error starting treatment: {str(e)}")
            return False, f"حدث خطأ في بدء العلاج: {str(e)}"
    
    def complete_treatment(self, ticket_id, completed_by=None):
        """إكمال العلاج"""
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            if ticket.status != QueueState.IN_PROGRESS:
                return False, "يجب بدء العلاج أولاً"
            
            if completed_by:
                allowed = self._is_user_allowed_for_department(completed_by, ticket.department_id)
                if not allowed:
                    v = None
                    if ticket.visit_id:
                        try:
                            v = db.session.get(Visit, ticket.visit_id)
                        except Exception:
                            v = None
                    if not (v and v.doctor_id == completed_by):
                        return False, "ليس لديك صلاحية لإنهاء علاج هذه التذكرة"
            
            # تحديث حالة التذكرة
            ticket.status = QueueState.COMPLETED
            ticket.completed_at = datetime.now(timezone.utc)
            
            # مزامنة حالة الزيارة إلى COMPLETED إذا وجدت
            if ticket.visit_id:
                try:
                    visit = db.session.get(Visit, ticket.visit_id)
                    if visit:
                        VisitStateMachineService.ensure_completed(visit, actor=completed_by)
                        visit.completed_at = datetime.now(timezone.utc)
                        visit.completed_by = completed_by
                        self._ensure_survey_for_visit(visit)
                except Exception:
                    pass
            
            db.session.commit()
            
            try:
                self.logger.info(f"Treatment completed for ticket {ticket.queue_number}")
            except Exception:
                self.logger.info("Treatment completed for ticket")
            return True, "تم إكمال العلاج"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error completing treatment: {str(e)}")
            return False, f"حدث خطأ في إكمال العلاج: {str(e)}"
    
    def skip_patient(self, ticket_id, reason=None, skipped_by=None):
        """تخطي المريض"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة التذكرة
            ticket.status = QueueState.SKIPPED
            ticket.notes = f"تم التخطي - السبب: {reason}" if reason else "تم التخطي"
            
            db.session.commit()
            self._emit_queue_updates()
            
            self.logger.info(f"Patient skipped for ticket {ticket.queue_number}")
            return True, "تم تخطي المريض"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error skipping patient: {str(e)}")
            return False, f"حدث خطأ في تخطي المريض: {str(e)}"

    def return_to_queue(self, ticket_id, reason=None, returned_by=None):
        try:
            from models.queue_management import QueueManagement
            from models.visit import Visit

            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"

            old_status = ticket.status
            if old_status not in {QueueState.CALLED, QueueState.IN_PROGRESS, QueueState.SKIPPED}:
                return False, "لا يمكن إعادة هذه التذكرة للطابور"

            ticket.status = QueueState.WAITING
            ticket.queued_at = datetime.now(timezone.utc)
            ticket.called_at = None
            ticket.started_at = None

            note = "تم إرجاع للطابور"
            if reason:
                note = f"{note} - السبب: {reason}"
            ticket.notes = f"{ticket.notes} | {note}" if ticket.notes else note

            if ticket.visit_id and old_status == QueueState.IN_PROGRESS:
                try:
                    v = db.session.get(Visit, ticket.visit_id)
                    if v and VisitStateMachineService.get_status(v) == VisitState.IN_PROGRESS:
                        VisitStateMachineService.transition(v, VisitState.CHECKED_IN, actor=returned_by)
                except Exception:
                    pass

            db.session.commit()
            self._emit_queue_updates()
            self._emit_queue_updates()
            return True, "تم إرجاع المريض للطابور"
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error returning patient to queue: {str(e)}")
            return False, f"حدث خطأ في إرجاع المريض للطابور: {str(e)}"
    
    def cancel_ticket(self, ticket_id, reason=None, cancelled_by=None):
        """إلغاء التذكرة"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة التذكرة
            ticket.status = QueueState.CANCELLED
            ticket.notes = f"تم الإلغاء - السبب: {reason}" if reason else "تم الإلغاء"
            
            db.session.commit()
            self._emit_queue_updates()
            self._emit_queue_updates()
            
            self.logger.info(f"Ticket cancelled: {ticket.queue_number}")
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
                status=QueueState.WAITING
            ).count()
            
            # متوسط وقت الخدمة من إعدادات القسم إن وُجد
            try:
                from models.queue_management import QueueSettings
                qs = QueueSettings.query.filter_by(department_id=department_id).first()
                avg_service_time = int(qs.average_wait_time) if qs and qs.average_wait_time else 30
            except Exception:
                avg_service_time = 30
            
            # حساب الوقت المتوقع
            estimated_time = waiting_count * avg_service_time
            
            return estimated_time
            
        except Exception as e:
            self.logger.error(f"Error calculating wait time: {str(e)}")
            return 0

    def _build_queue_snapshot(self):
        from models.queue_management import QueueManagement
        items = QueueManagement.query.filter(
            QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS])
        ).order_by(QueueManagement.queued_at.asc()).limit(80).all()
        result = []
        for item in items:
            result.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'status': item.get_status_display(),
                'priority': item.get_priority_display(),
                'payment': item.get_payment_status_display()
            })
        return result

    def _build_display_waiting(self):
        from models.queue_management import QueueManagement
        waiting = QueueManagement.query.filter(
            QueueManagement.status == QueueState.WAITING
        ).order_by(QueueManagement.queued_at.asc()).limit(60).all()
        called = QueueManagement.query.filter(
            QueueManagement.status == QueueState.CALLED
        ).order_by(QueueManagement.called_at.desc()).limit(12).all()
        current = QueueManagement.query.filter(
            QueueManagement.status == QueueState.IN_PROGRESS
        ).order_by(QueueManagement.started_at.desc()).limit(6).all()

        def _pack(item):
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            return {
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            }

        return {
            QueueState.WAITING: [_pack(i) for i in waiting],
            QueueState.CALLED: [_pack(i) for i in called],
            'current': [_pack(i) for i in current]
        }

    def _build_display_calls(self):
        from models.queue_management import QueueManagement
        called = QueueManagement.query.filter(
            QueueManagement.status.in_([QueueState.CALLED, QueueState.IN_PROGRESS])
        ).order_by(QueueManagement.called_at.desc()).limit(24).all()
        items = []
        for item in called:
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            items.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            })
        return items

    def _emit_queue_updates(self):
        try:
            from app_factory import socketio
            socketio.emit('queue_snapshot', {'items': self._build_queue_snapshot()}, namespace='/queue')
            socketio.emit('queue_display_waiting', self._build_display_waiting(), namespace='/queue')
            socketio.emit('queue_display_calls', {'items': self._build_display_calls()}, namespace='/queue')
        except Exception as e:
            self.logger.error(f"Error emitting queue updates: {str(e)}")

    def _ensure_survey_for_visit(self, visit):
        try:
            from models.patient_satisfaction import PatientSatisfactionSurvey
            import secrets
            existing = PatientSatisfactionSurvey.query.filter_by(visit_id=visit.id).first()
            if existing:
                return existing
            token = secrets.token_urlsafe(24)
            survey = PatientSatisfactionSurvey(
                visit_id=visit.id,
                patient_id=getattr(visit, 'patient_id', None),
                token=token
            )
            db.session.add(survey)
            return survey
        except Exception:
            return None
    
    def get_patient_queue_position(self, patient_id, department_id):
        """الحصول على موقع المريض في الطابور"""
        try:
            from models.queue_management import QueueManagement
            
            # البحث عن تذكرة المريض
            ticket = QueueManagement.query.filter_by(
                patient_id=patient_id,
                department_id=department_id,
                status=QueueState.WAITING
            ).first()
            
            if not ticket:
                return None, "المريض غير موجود في الطابور"
            
            # حساب الموقع
            rank_map = {'urgent': 0, 'high': 1, 'normal': 2, 'low': 3}
            ticket_rank = rank_map.get((ticket.priority_level or '').lower(), 4)
            priority_rank = self._priority_rank_expr(QueueManagement)
            position = QueueManagement.query.filter(
                QueueManagement.department_id == department_id,
                QueueManagement.status == QueueState.WAITING,
                db.or_(
                    priority_rank < ticket_rank,
                    db.and_(priority_rank == ticket_rank, QueueManagement.queued_at < ticket.queued_at)
                )
            ).count() + 1
            
            return position, f"موقع المريض في الطابور: {position}"
            
        except Exception as e:
            self.logger.error(f"Error getting queue position: {str(e)}")
            return None, f"حدث خطأ في حساب موقع المريض: {str(e)}"
    
    def approve_emergency_debt(self, ticket_id, approved_by, max_amount=None):
        """الموافقة على دين الطوارئ"""
        try:
            from models.queue_management import QueueManagement, QueueSettings
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # التحقق من إعدادات الطوارئ
            # يمكن لاحقاً ضبط حدود دين الطوارئ عبر إعدادات إضافية
            
            # تحديث حالة الدفع
            ticket.payment_status = 'waived'
            ticket.emergency_approved_by = approved_by
            
            db.session.commit()
            
            self.logger.info(f"Emergency debt approved for ticket {ticket.queue_number}")
            return True, "تم الموافقة على دين الطوارئ"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error approving emergency debt: {str(e)}")
            return False, f"حدث خطأ في الموافقة على دين الطوارئ: {str(e)}"
    
    def approve_force_entry(self, ticket_id, approved_by, reason=None):
        """الموافقة على الدخول القوي"""
        try:
            from models.queue_management import QueueManagement
            
            ticket = db.session.get(QueueManagement, ticket_id)
            if not ticket:
                return False, "التذكرة غير موجودة"
            
            # تحديث حالة الدخول القوي
            ticket.force_entry = True
            ticket.force_entry_reason = reason
            ticket.force_entry_approved_by = approved_by
            
            # رفع مستوى الأولوية
            ticket.priority_level = 'high'
            
            db.session.commit()
            
            self.logger.info(f"Force entry approved for ticket {ticket.queue_number}")
            return True, "تم الموافقة على الدخول القوي"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error approving force entry: {str(e)}")
            return False, f"حدث خطأ في الموافقة على الدخول القوي: {str(e)}"
