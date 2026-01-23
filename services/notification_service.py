"""
خدمة إدارة الإشعارات - Notification Management Service
Medical System Notification Management Service
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, func, desc
from app_factory import db
from models.notification import Notification, NotificationTemplate, NotificationQueue, WhatsAppMessage, EmailMessage
from models.user import User
from models.department import Department
import logging
import json

class NotificationService:
    """خدمة إدارة الإشعارات"""
    
    @staticmethod
    def send_notification(recipient_id=None, recipient_role=None, recipient_department_id=None,
                         title=None, message=None, notification_type='info',
                         sender_id=None, related_entity_type=None, related_entity_id=None,
                         is_urgent=False, expires_at=None, template_name=None, template_variables=None):
        """إرسال إشعار"""
        try:
            # استخدام القالب إذا تم تحديده
            if template_name:
                template = NotificationTemplate.query.filter(
                    and_(
                        NotificationTemplate.name == template_name,
                        NotificationTemplate.is_active == True
                    )
                ).first()
                
                if template:
                    rendered = template.render(template_variables)
                    title = rendered.get('title') or rendered.get('subject')
                    message = rendered.get('message') or rendered.get('content')
                    notification_type = rendered['notification_type']
                else:
                    return {'success': False, 'message': 'قالب الإشعار غير موجود'}
            
            # إنشاء الإشعار (بدون حقول غير موجودة في النموذج)
            notification = Notification(
                title=title,
                message=message,
                notification_type=notification_type,
                recipient_id=recipient_id,
                recipient_role=recipient_role,
                recipient_department_id=recipient_department_id,
                sender_id=sender_id,
                is_urgent=is_urgent,
                expires_at=expires_at,
                sent_at=datetime.now(timezone.utc)
            )
            
            db.session.add(notification)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إرسال الإشعار بنجاح', 'notification_id': notification.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error sending notification: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال الإشعار حالياً'}
    
    @staticmethod
    def send_bulk_notification(recipient_ids=None, recipient_roles=None, recipient_department_ids=None,
                             title=None, message=None, notification_type='info',
                             sender_id=None, related_entity_type=None, related_entity_id=None,
                             is_urgent=False, expires_at=None, template_name=None, template_variables=None):
        """إرسال إشعار جماعي"""
        try:
            notifications = []
            
            # إرسال للمستخدمين المحددين
            if recipient_ids:
                for recipient_id in recipient_ids:
                    notification = Notification(
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        recipient_id=recipient_id,
                        sender_id=sender_id,
                        is_urgent=is_urgent,
                        expires_at=expires_at,
                        sent_at=datetime.now(timezone.utc)
                    )
                    notifications.append(notification)
            
            # إرسال للأدوار المحددة
            if recipient_roles:
                for role in recipient_roles:
                    notification = Notification(
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        recipient_role=role,
                        sender_id=sender_id,
                        is_urgent=is_urgent,
                        expires_at=expires_at,
                        sent_at=datetime.now(timezone.utc)
                    )
                    notifications.append(notification)
            
            # إرسال للأقسام المحددة
            if recipient_department_ids:
                for department_id in recipient_department_ids:
                    notification = Notification(
                        title=title,
                        message=message,
                        notification_type=notification_type,
                        recipient_department_id=department_id,
                        sender_id=sender_id,
                        is_urgent=is_urgent,
                        expires_at=expires_at,
                        sent_at=datetime.now(timezone.utc)
                    )
                    notifications.append(notification)
            
            # إضافة الإشعارات إلى قاعدة البيانات
            for notification in notifications:
                db.session.add(notification)
            
            db.session.commit()
            
            return {'success': True, 'message': f'تم إرسال {len(notifications)} إشعار بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error sending bulk notification: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال الإشعارات الجماعية حالياً'}
    
    @staticmethod
    def get_user_notifications(user_id, unread_only=False, urgent_only=False, limit=None):
        """الحصول على إشعارات المستخدم"""
        try:
            query = Notification.query.filter(
                and_(
                    Notification.recipient_id == user_id,
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > datetime.now(timezone.utc)
                    )
                )
            )
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            if urgent_only:
                query = query.filter(Notification.is_urgent == True)
            
            query = query.order_by(desc(Notification.sent_at))
            
            if limit:
                query = query.limit(limit)
            
            notifications = query.all()
            
            return {
                'success': True,
                'notifications': [notification.to_dict() for notification in notifications],
                'total_count': len(notifications)
            }
            
        except Exception as e:
            logging.error(f"Error getting user notifications: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب إشعارات المستخدم حالياً'}
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """تحديد الإشعار كمقروء"""
        try:
            notification = Notification.query.filter(
                and_(
                    Notification.id == notification_id,
                    Notification.recipient_id == user_id
                )
            ).first()
            
            if not notification:
                return {'success': False, 'message': 'الإشعار غير موجود'}
            
            notification.mark_as_read()
            
            return {'success': True, 'message': 'تم تحديد الإشعار كمقروء'}
            
        except Exception as e:
            logging.error(f"Error marking notification as read: {str(e)}")
            return {'success': False, 'message': 'تعذر تحديد الإشعار كمقروء حالياً'}
    
    @staticmethod
    def mark_all_as_read(user_id):
        """تحديد جميع الإشعارات كمقروءة"""
        try:
            notifications = Notification.query.filter(
                and_(
                    Notification.recipient_id == user_id,
                    Notification.is_read == False
                )
            ).all()
            
            for notification in notifications:
                notification.mark_as_read()
            
            return {'success': True, 'message': f'تم تحديد {len(notifications)} إشعار كمقروء'}
            
        except Exception as e:
            logging.error(f"Error marking all notifications as read: {str(e)}")
            return {'success': False, 'message': 'تعذر تحديد جميع الإشعارات كمقروءة حالياً'}
    
    @staticmethod
    def get_notification_count(user_id):
        """الحصول على عدد الإشعارات غير المقروءة"""
        try:
            unread_count = Notification.query.filter(
                and_(
                    Notification.recipient_id == user_id,
                    Notification.is_read == False,
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > datetime.now(timezone.utc)
                    )
                )
            ).count()
            
            urgent_count = Notification.query.filter(
                and_(
                    Notification.recipient_id == user_id,
                    Notification.is_read == False,
                    Notification.is_urgent == True,
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > datetime.now(timezone.utc)
                    )
                )
            ).count()
            
            return {
                'success': True,
                'unread_count': unread_count,
                'urgent_count': urgent_count
            }
            
        except Exception as e:
            logging.error(f"Error getting notification count: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب عدد الإشعارات حالياً'}
    
    @staticmethod
    def create_notification_template(name, title_template, message_template, notification_type,
                                    variables=None, is_system=False, created_by=None):
        """إنشاء قالب إشعار"""
        try:
            template = NotificationTemplate(
                name=name,
                template_type=notification_type,
                subject=title_template,
                content=message_template,
                variables=json.dumps(variables) if variables else None,
                is_system=is_system,
                created_by=created_by,
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(template)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إنشاء قالب الإشعار بنجاح', 'template_id': template.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating notification template: {str(e)}")
            return {'success': False, 'message': 'تعذر إنشاء قالب الإشعار حالياً'}
    
    @staticmethod
    def get_notification_templates():
        """الحصول على قوالب الإشعارات"""
        try:
            templates = NotificationTemplate.query.filter(
                NotificationTemplate.is_active == True
            ).all()
            
            return {
                'success': True,
                'templates': [template.to_dict() for template in templates]
            }
            
        except Exception as e:
            logging.error(f"Error getting notification templates: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب قوالب الإشعارات حالياً'}
    
    @staticmethod
    def create_default_templates():
        """إنشاء قوالب الإشعارات الافتراضية"""
        try:
            default_templates = [
                {
                    'name': 'new_visit',
                    'subject': 'زيارة جديدة - {patient_name}',
                    'content': 'تم تسجيل زيارة جديدة للمريض {patient_name} في قسم {department_name}',
                    'template_type': 'info',
                    'is_system': True
                },
                {
                    'name': 'appointment_reminder',
                    'subject': 'تذكير بالموعد - {patient_name}',
                    'content': 'موعد المريض {patient_name} مع الدكتور {doctor_name} في {appointment_time}',
                    'template_type': 'info',
                    'is_system': True
                },
                {
                    'name': 'payment_required',
                    'subject': 'دفع مطلوب - {patient_name}',
                    'content': 'يوجد مبلغ مستحق للمريض {patient_name} بقيمة {amount} شيكل',
                    'template_type': 'warning',
                    'is_system': True
                },
                {
                    'name': 'lab_result_ready',
                    'subject': 'نتائج المختبر جاهزة - {patient_name}',
                    'content': 'نتائج فحوصات المختبر للمريض {patient_name} جاهزة للمراجعة',
                    'template_type': 'success',
                    'is_system': True
                },
                {
                    'name': 'radiology_result_ready',
                    'subject': 'نتائج الأشعة جاهزة - {patient_name}',
                    'content': 'نتائج فحوصات الأشعة للمريض {patient_name} جاهزة للمراجعة',
                    'template_type': 'success',
                    'is_system': True
                },
                {
                    'name': 'emergency_alert',
                    'subject': 'تنبيه طوارئ - {patient_name}',
                    'content': 'حالة طوارئ للمريض {patient_name} - {emergency_type}',
                    'template_type': 'urgent',
                    'is_system': True
                }
            ]
            
            for template_data in default_templates:
                # التحقق من وجود القالب
                existing = NotificationTemplate.query.filter(
                    NotificationTemplate.name == template_data['name']
                ).first()
                
                if not existing:
                    template = NotificationTemplate(
                        name=template_data['name'],
                        template_type=template_data['template_type'],
                        subject=template_data['subject'],
                        content=template_data['content'],
                        is_system=template_data['is_system']
                    )
                    db.session.add(template)
            
            db.session.commit()
            return {'success': True, 'message': 'تم إنشاء قوالب الإشعارات الافتراضية بنجاح'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating default templates: {str(e)}")
            return {'success': False, 'message': 'تعذر إنشاء قوالب الإشعارات الافتراضية حالياً'}
    
    @staticmethod
    def cleanup_expired_notifications():
        """تنظيف الإشعارات المنتهية الصلاحية"""
        try:
            expired_notifications = Notification.query.filter(
                and_(
                    Notification.expires_at.isnot(None),
                    Notification.expires_at < datetime.now(timezone.utc)
                )
            ).all()
            
            for notification in expired_notifications:
                db.session.delete(notification)
            
            db.session.commit()
            
            return {'success': True, 'message': f'تم حذف {len(expired_notifications)} إشعار منتهي الصلاحية'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error cleaning up expired notifications: {str(e)}")
            return {'success': False, 'message': 'تعذر تنظيف الإشعارات المنتهية الصلاحية حالياً'}
    
    @staticmethod
    def send_whatsapp_message(phone_number, message_content, message_type='text', template_name=None, media_url=None):
        """إرسال رسالة واتساب"""
        try:
            whatsapp_message = WhatsAppMessage(
                phone_number=phone_number,
                message_content=message_content,
                message_type=message_type,
                template_name=template_name,
                media_url=media_url,
                status='pending'
            )
            
            db.session.add(whatsapp_message)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إضافة رسالة الواتساب إلى الطابور', 'message_id': whatsapp_message.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error sending WhatsApp message: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال رسالة الواتساب حالياً'}
    
    @staticmethod
    def send_email_message(recipient_email, subject, content, content_type='text/html', attachments=None):
        """إرسال رسالة بريد إلكتروني"""
        try:
            email_message = EmailMessage(
                recipient_email=recipient_email,
                subject=subject,
                content=content,
                content_type=content_type,
                attachments=json.dumps(attachments) if attachments else None,
                status='pending'
            )
            
            db.session.add(email_message)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إضافة رسالة البريد الإلكتروني إلى الطابور', 'message_id': email_message.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error sending email message: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال رسالة البريد الإلكتروني حالياً'}
    
    @staticmethod
    def add_to_notification_queue(user_id, notification_type, recipient, subject, content, 
                                template_id=None, variables=None, priority='normal', scheduled_at=None):
        """إضافة إشعار إلى طابور الإشعارات"""
        try:
            queue_item = NotificationQueue(
                user_id=user_id,
                template_id=template_id,
                notification_type=notification_type,
                recipient=recipient,
                subject=subject,
                content=content,
                variables=json.dumps(variables) if variables else None,
                priority=priority,
                scheduled_at=scheduled_at
            )
            
            db.session.add(queue_item)
            db.session.commit()
            
            return {'success': True, 'message': 'تم إضافة الإشعار إلى الطابور', 'queue_id': queue_item.id}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding to notification queue: {str(e)}")
            return {'success': False, 'message': 'تعذر إضافة الإشعار إلى الطابور حالياً'}
    
    @staticmethod
    def process_notification_queue():
        """معالجة طابور الإشعارات"""
        try:
            # جلب الإشعارات المعلقة
            pending_notifications = NotificationQueue.query.filter_by(status='pending').all()
            
            processed_count = 0
            for notification in pending_notifications:
                try:
                    # معالجة الإشعار حسب النوع
                    if notification.notification_type == 'whatsapp':
                        result = NotificationService.send_whatsapp_message(
                            phone_number=notification.recipient,
                            message_content=notification.content,
                            message_type='text'
                        )
                    elif notification.notification_type == 'email':
                        result = NotificationService.send_email_message(
                            recipient_email=notification.recipient,
                            subject=notification.subject or 'إشعار من النظام',
                            content=notification.content
                        )
                    else:
                        # إشعار عادي
                        result = NotificationService.send_notification(
                            recipient_id=notification.user_id,
                            title=notification.subject or 'إشعار',
                            message=notification.content,
                            notification_type='info'
                        )
                    
                    if result['success']:
                        notification.status = 'sent'
                        notification.sent_at = datetime.now(timezone.utc)
                        processed_count += 1
                    else:
                        notification.status = 'failed'
                        notification.failed_at = datetime.now(timezone.utc)
                        notification.error_message = result['message']
                        
                except Exception as e:
                    notification.status = 'failed'
                    notification.failed_at = datetime.now(timezone.utc)
                    notification.error_message = str(e)
                    logging.error(f"Error processing notification {notification.id}: {str(e)}")
            
            db.session.commit()
            
            return {'success': True, 'message': f'تم معالجة {processed_count} إشعار'}
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing notification queue: {str(e)}")
            return {'success': False, 'message': 'تعذر معالجة طابور الإشعارات حالياً'}
    
    @staticmethod
    def get_notification_queue_status():
        """الحصول على حالة طابور الإشعارات"""
        try:
            pending_count = NotificationQueue.query.filter_by(status='pending').count()
            sent_count = NotificationQueue.query.filter_by(status='sent').count()
            failed_count = NotificationQueue.query.filter_by(status='failed').count()
            
            return {
                'success': True,
                'pending_count': pending_count,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_count': pending_count + sent_count + failed_count
            }
            
        except Exception as e:
            logging.error(f"Error getting notification queue status: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب حالة طابور الإشعارات حالياً'}
    
    # ==================== تنبيهات الديون والتأمين (الأسبوع الثاني) ====================
    
    @staticmethod
    def send_debt_reminders():
        """
        إرسال تذكيرات بالديون المتأخرة
        يتم تشغيلها يومياً للديون > 7 أيام
        """
        try:
            from models.visit import Visit
            
            # الديون المتأخرة (> 7 أيام)
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            overdue_debts = Visit.query.filter(
                and_(
                    or_(
                        Visit.payment_status == 'DEBT',
                        Visit.payment_status == 'PENDING'
                    ),
                    Visit.created_at < seven_days_ago,
                    Visit.is_force_payment == True
                )
            ).all()
            
            sent_count = 0
            for debt in overdue_debts:
                age_days = (datetime.now() - debt.created_at).days
                remaining = float(debt.remaining_amount)
                
                # تحديد مستوى الإلحاح
                if age_days > 60:
                    urgency = 'urgent'
                    severity = 'عاجل جداً'
                elif age_days > 30:
                    urgency = 'warning'
                    severity = 'عاجل'
                else:
                    urgency = 'info'
                    severity = 'تذكير'
                
                # إرسال للمحاسب
                result = NotificationService.send_notification(
                    recipient_role='accountant',
                    title=f'{severity}: دين متأخر - {age_days} يوم',
                    message=f'المريض {debt.patient_id} - الزيارة {debt.id}\n'
                            f'المبلغ المتبقي: {remaining:.2f} شيكل\n'
                            f'العمر: {age_days} يوم\n'
                            f'السبب: {debt.force_payment_reason or "غير محدد"}',
                    notification_type=urgency,
                    is_urgent=(age_days > 30)
                )
                
                if result['success']:
                    sent_count += 1
                
                # إرسال للمدير للحالات الحرجة (> 60 يوم)
                if age_days > 60:
                    NotificationService.send_notification(
                        recipient_role='manager',
                        title=f'تنبيه دين حرج: {age_days} يوم',
                        message=f'دين متأخر جداً يتطلب التدخل\n'
                                f'الزيارة: {debt.id}\n'
                                f'المبلغ: {remaining:.2f} شيكل',
                        notification_type='urgent',
                        is_urgent=True
                    )
            
            return {
                'success': True,
                'message': f'تم إرسال {sent_count} تذكير بالديون',
                'debts_found': len(overdue_debts),
                'reminders_sent': sent_count
            }
            
        except Exception as e:
            logging.error(f"Error sending debt reminders: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر إرسال تذكيرات الديون حالياً'
            }
    
    @staticmethod
    def send_insurance_followup_alerts():
        """
        إرسال تنبيهات متابعة التأمين
        للزيارات التي لم يتم استلام دفعة التأمين بعد 14 يوم
        """
        try:
            from models.visit import Visit
            
            # زيارات التأمين القديمة (> 14 يوم)
            fourteen_days_ago = datetime.now() - timedelta(days=14)
            
            pending_insurance = Visit.query.filter(
                and_(
                    Visit.payment_method == 'insurance',
                    Visit.payment_status == 'PARTIAL',  # دفع المريض حصته فقط
                    Visit.created_at < fourteen_days_ago
                )
            ).all()
            
            sent_count = 0
            for visit in pending_insurance:
                age_days = (datetime.now() - visit.created_at).days
                insurance_pending = float(visit.insurance_amount or 0)
                
                # تحديد مستوى الإلحاح
                if age_days > 45:
                    urgency = 'urgent'
                    severity = 'عاجل جداً'
                elif age_days > 30:
                    urgency = 'warning'
                    severity = 'متابعة عاجلة'
                else:
                    urgency = 'info'
                    severity = 'متابعة'
                
                # إرسال للمحاسب
                result = NotificationService.send_notification(
                    recipient_role='accountant',
                    title=f'{severity}: تأمين معلق - {age_days} يوم',
                    message=f'شركة التأمين: {visit.insurance_provider}\n'
                            f'رقم البوليصة: {visit.insurance_policy_number}\n'
                            f'المبلغ المعلق: {insurance_pending:.2f} شيكل\n'
                            f'العمر: {age_days} يوم\n'
                            f'الزيارة: {visit.id}',
                    notification_type=urgency,
                    is_urgent=(age_days > 30)
                )
                
                if result['success']:
                    sent_count += 1
            
            return {
                'success': True,
                'message': f'تم إرسال {sent_count} تنبيه متابعة تأمين',
                'pending_claims': len(pending_insurance),
                'alerts_sent': sent_count
            }
            
        except Exception as e:
            logging.error(f"Error sending insurance followup alerts: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر إرسال تنبيهات متابعة التأمين حالياً'
            }
    
    @staticmethod
    def send_force_payment_approval_alerts():
        """
        إرسال تنبيهات للمدير بالدفعات القسرية المعلقة
        """
        try:
            from models.visit import Visit
            
            # دفعات قسرية بدون موافقة
            pending_force = Visit.query.filter(
                and_(
                    Visit.is_force_payment == True,
                    Visit.force_payment_approved_by == None
                )
            ).all()
            
            if not pending_force:
                return {
                    'success': True,
                    'message': 'لا توجد دفعات قسرية معلقة',
                    'pending_count': 0
                }
            
            # إرسال تنبيه واحد جماعي للمدير
            visits_list = '\n'.join([
                f'زيارة رقم {v.id}: {v.force_payment_reason[:50]}... ({float(v.total_amount):.2f} شيكل)'
                for v in pending_force[:10]  # أول 10 فقط
            ])
            
            result = NotificationService.send_notification(
                recipient_role='manager',
                title=f'تنبيه: {len(pending_force)} دفعة قسرية بانتظار الموافقة',
                message=f'يوجد {len(pending_force)} دفعة قسرية تحتاج موافقتك:\n\n{visits_list}\n\n'
                        f'{"...والمزيد" if len(pending_force) > 10 else ""}',
                notification_type='warning',
                is_urgent=True
            )
            
            return {
                'success': result['success'],
                'message': result['message'],
                'pending_count': len(pending_force)
            }
            
        except Exception as e:
            logging.error(f"Error sending force payment approval alerts: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر إرسال تنبيهات موافقات الدفع القسري حالياً'
            }
    
    @staticmethod
    def send_daily_summary_to_manager():
        """
        إرسال ملخص يومي للمدير
        يُشغل في نهاية كل يوم
        """
        try:
            from models.visit import Visit
            from services.report_service import ReportService
            
            # الحصول على تقرير التدقيق اليومي
            report = ReportService.get_daily_audit_report()
            
            if not report['success']:
                return report
            
            summary = report['summary']
            
            # بناء الرسالة
            message = (
                f"ملخص اليوم\n"
                f"الزيارات: {summary['total_visits']}\n"
                f"المحصل: {summary['total_collected']:.2f} شيكل\n"
                f"دفع قسري: {summary['force_payment_percentage']:.1f}%\n"
                f"تأمين: {summary['insurance_visits']} زيارة\n"
                f"{'تنبيهات: ' + str(summary['issues_count']) if summary['issues_count'] > 0 else 'لا توجد مشاكل'}"
            )
            
            # إضافة القضايا إن وجدت
            if report['audit_issues']:
                message += "\n\nالقضايا:\n"
                for issue in report['audit_issues']:
                    message += f"قضية: {issue['message']} ({issue['severity']})\n"
            
            # إرسال للمدير
            result = NotificationService.send_notification(
                recipient_role='manager',
                title=f'ملخص اليوم - {datetime.now().strftime("%Y-%m-%d")}',
                message=message,
                notification_type='info',
                is_urgent=False
            )
            
            return result
            
        except Exception as e:
            logging.error(f"Error sending daily summary to manager: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر إرسال الملخص اليومي حالياً'
            }
    
    @staticmethod
    def check_and_send_alerts():
        """
        فحص وإرسال جميع التنبيهات التلقائية
        يُشغل بشكل دوري (كل ساعة مثلاً)
        """
        try:
            results = {}
            
            # 1. تذكيرات الديون
            results['debt_reminders'] = NotificationService.send_debt_reminders()
            
            # 1-b. تذكيرات المواعيد القادمة خلال 24 ساعة
            results['appointment_reminders'] = NotificationService.send_appointment_reminders()

            results['online_booking_reminders'] = NotificationService.send_online_booking_reminders()

            # 2. متابعة التأمين
            results['insurance_followup'] = NotificationService.send_insurance_followup_alerts()
            
            # 3. موافقات الدفع القسري
            results['force_payment_approval'] = NotificationService.send_force_payment_approval_alerts()
            
            # 4. الملخص اليومي (فقط في نهاية اليوم)
            current_hour = datetime.now().hour
            if current_hour >= 18:  # بعد الساعة 6 مساءً
                results['daily_summary'] = NotificationService.send_daily_summary_to_manager()
            
            return {
                'success': True,
                'message': 'تم فحص وإرسال التنبيهات',
                'results': results
            }
            
        except Exception as e:
            logging.error(f"Error in check_and_send_alerts: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر فحص وإرسال التنبيهات حالياً'
            }

    @staticmethod
    def send_appointment_reminders():
        """
        إرسال تذكيرات بالمواعيد المجدولة خلال الـ 24 ساعة القادمة
        يعتمد على رقم هاتف المريض (SMS) إن وجد
        """
        try:
            from models.appointment import Appointment
            from models.patient import Patient
            from models.user import User
            from datetime import datetime, timedelta
            now = datetime.now()
            soon = now + timedelta(hours=24)

            appts = Appointment.query.filter(
                and_(
                    Appointment.status == 'SCHEDULED',
                    Appointment.starts_at >= now,
                    Appointment.starts_at <= soon
                )
            ).all()

            sent = 0
            fallback_notified = 0
            for ap in appts:
                patient = db.session.get(Patient, ap.patient_id)
                doctor = db.session.get(User, ap.doctor_id) if ap.doctor_id else None
                dept = db.session.get(Department, ap.department_id) if ap.department_id else None
                dt_str = ap.starts_at.strftime('%Y-%m-%d %H:%M')
                subject = 'تذكير بالموعد الطبي'
                if not patient or not patient.phone:
                    # إرسال إشعار لموظفي الاستقبال لمتابعة الاتصال
                    msg = (
                        f"موعد قادم للمريض ID={ap.patient_id}"
                        f" {('مع الدكتور ' + doctor.full_name) if doctor else ''}"
                        f" في {dept.name_ar or dept.name if dept else 'القسم'} بتاريخ {dt_str}."
                        f" المريض لا يملك رقم هاتف مسجل. يرجى المتابعة."
                    ).strip()
                    NotificationService.send_notification(
                        recipient_role='reception',
                        title=subject,
                        message=msg,
                        notification_type='warning',
                        is_urgent=True
                    )
                    fallback_notified += 1
                    continue
                content = (
                    f"عزيزي {patient.full_name}، لديك موعد "
                    f"{'مع الدكتور ' + doctor.full_name if doctor else ''} "
                    f"في {dept.name_ar or dept.name if dept else 'القسم'} بتاريخ {dt_str}."
                ).strip()

                NotificationService.add_to_notification_queue(
                    user_id=(doctor.id if doctor else (User.query.filter_by(role='reception').first().id if User.query.filter_by(role='reception').first() else User.query.first().id)),
                    notification_type='sms',
                    recipient=patient.phone,
                    subject=subject,
                    content=content,
                    variables={
                        'patient_id': patient.id,
                        'appointment_id': ap.id,
                        'starts_at': dt_str
                    },
                    priority='high',
                    scheduled_at=now
                )
                sent += 1

            return {'success': True, 'sent': sent, 'fallback_notified': fallback_notified}
        except Exception as e:
            logging.error(f"Error sending appointment reminders: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال تذكيرات المواعيد حالياً'}

    @staticmethod
    def send_online_booking_reminders():
        try:
            from models.online_booking import OnlineBooking
            from models.user import User
            from models.department import Department
            from datetime import datetime, timedelta

            now = datetime.now(timezone.utc)
            soon = now + timedelta(hours=24)

            q = OnlineBooking.query.filter(
                OnlineBooking.status.in_(['pending', 'confirmed']),
                OnlineBooking.appointment_date.isnot(None),
                OnlineBooking.appointment_time.isnot(None)
            ).all()

            sent = 0
            fallback_notified = 0
            for b in q:
                try:
                    dt = datetime.combine(b.appointment_date, b.appointment_time, tzinfo=timezone.utc)
                except Exception:
                    continue
                if not (dt >= now and dt <= soon):
                    continue
                dept = db.session.get(Department, b.department_id) if b.department_id else None
                doctor = db.session.get(User, b.doctor_id) if b.doctor_id else None
                dt_str = dt.strftime('%Y-%m-%d %H:%M')
                subject = 'تذكير بموعد الحجز'

                if not b.email:
                    msg = f"حجز {b.booking_reference} للمريض {b.get_full_name()} بتاريخ {dt_str} بدون بريد للتواصل."
                    NotificationService.send_notification(
                        recipient_role='reception',
                        title=subject,
                        message=msg,
                        notification_type='warning',
                        is_urgent=True
                    )
                    fallback_notified += 1
                    continue

                content = (
                    f"عزيزي {b.get_full_name()}، تذكير بموعدك بتاريخ {dt_str} "
                    f"في {dept.name_ar or dept.name if dept else 'القسم'} "
                    f"{('مع ' + doctor.full_name) if doctor else ''}. "
                    f"رقم الحجز: {b.booking_reference}."
                ).strip()

                queue_user_id = None
                if doctor:
                    queue_user_id = doctor.id
                if not queue_user_id:
                    any_user = User.query.filter(User.role.in_(['reception', 'manager', 'super_admin'])).first()
                    queue_user_id = any_user.id if any_user else 1

                NotificationService.add_to_notification_queue(
                    user_id=queue_user_id,
                    notification_type='email',
                    recipient=b.email,
                    subject=subject,
                    content=content,
                    priority='normal',
                    scheduled_at=now
                )
                sent += 1

            return {'success': True, 'sent': sent, 'fallback_notified': fallback_notified}
        except Exception as e:
            logging.error(f"Error sending online booking reminders: {str(e)}")
            return {'success': False, 'message': 'تعذر إرسال تذكيرات الحجز حالياً'}
