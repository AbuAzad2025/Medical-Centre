"""
خدمة حراسة النظام - Gatekeeper Service
Medical System Gatekeeper Service
نسخة محسّنة مع دعم كامل للتحقق من قواعد الدفع
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import func, select

from app.extensions import db
from models.audit_trail import AuditTrail
from models.invoice import InvoiceService
from models.payment import Payment
from models.user import User
from models.visit import Visit
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record

logger = logging.getLogger(__name__)


class GatekeeperService:
    """خدمة حراسة النظام - تتحكم في الدفع والأرشفة والتحقق من قواعد العمل"""

    # القواعد الثابتة
    MAX_FORCE_PAYMENT_PERCENTAGE = 5  # 5% حد أقصى للدفع القسري
    MAX_CASH_AMOUNT = 5000  # الحد الأقصى للدفع النقدي (ILS)
    MIN_INSURANCE_COVERAGE = 50  # الحد الأدنى لتغطية التأمين (%)
    MAX_INSURANCE_COVERAGE = 100  # الحد الأقصى لتغطية التأمين (%)

    @staticmethod
    def can_enqueue_visit(visit_id, user_id):
        """
        التحقق من إمكانية إدراج الزيارة في الطابور
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # للطوارئ أو الدفع القوي: يتطلب إقرار المسؤولية
            if visit.is_emergency or visit.is_strong_pay:
                if not visit.liability_acknowledged_at:
                    return False, 'يتطلب إقرار المسؤولية للطوارئ/الدفع القوي'
                # يبقى القفل المالي مفعل
                visit.financial_locked = True
                safe_commit(
                    db.session, error_message='فشل تحديث القفل المالي للزيارة', reraise=True
                )
                return True, 'تم الإدراج مع القفل المالي'

            # للزيارات العادية: يتطلب سند قبض نظامي
            if not visit.receipt_printed:
                return False, 'يتطلب سند قبض نظامي للزيارات العادية'

            return True, 'تم الإدراج بنجاح'

        except Exception as e:
            current_app.logger.exception('خطأ في التحقق من إمكانية الإدراج: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def can_post_gl(visit_id, user_id):
        """
        التحقق من إمكانية الترحيل المالي
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # التحقق من القفل المالي
            if visit.financial_locked:
                return False, 'الزيارة مقفلة مالياً'

            # التحقق من وجود سند قبض
            if not visit.receipt_printed:
                return False, 'يتطلب سند قبض نظامي'

            # التحقق من اكتمال الدفع
            if visit.paid_amount < visit.total_amount:
                return False, 'المبلغ المدفوع أقل من المطلوب'

            return True, 'يمكن الترحيل المالي'

        except Exception as e:
            current_app.logger.exception('خطأ في التحقق من الترحيل المالي: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def can_archive_visit(visit_id, user_id):
        """
        التحقق من إمكانية أرشفة الزيارة.

        Ticket 4: Archive, settlement, and financial mutation lockdown.
        - Visit must be clinically COMPLETED before administrative archive.
        - Already archived visits cannot be re-archived.
        - Financial preconditions (gl_posted_at, financial_locked, financial_completed_at)
          remain enforced.
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # Ticket 4: must be clinically completed before administrative archive
            if visit.status != 'COMPLETED':
                return False, 'يجب إنهاء العلاج أولاً قبل الأرشفة'

            # Ticket 4: already archived visits cannot be re-archived
            if visit.archive_status == 'ARCHIVED':
                return False, 'الزيارة مؤرشفة مسبقاً'

            # التحقق من الترحيل المالي
            if not visit.gl_posted_at:
                return False, 'يتطلب الترحيل المالي أولاً'

            # التحقق من القفل المالي
            if visit.financial_locked:
                return False, 'الزيارة مقفلة مالياً'

            # Ticket 1: outstanding balance blocks final settlement/archive
            if Decimal(visit.paid_amount or 0) < Decimal(visit.total_amount or 0):
                return False, 'المبلغ المدفوع أقل من المطلوب — لا يمكن الأرشفة'

            # للطوارئ أو الدفع القوي: التحقق من اكتمال الدفع
            if visit.is_emergency or visit.is_strong_pay:
                if not visit.financial_completed_at:
                    return False, 'يتطلب اكتمال الدفع للطوارئ/الدفع القوي'

            # Ticket 8: service-line reconciliation — when itemized lines exist, aggregate total must match
            has_lines = (
                db.session.execute(
                    select(db.func.count(InvoiceService.id)).filter(
                        InvoiceService.visit_id == visit.id
                    )
                ).scalar()
                > 0
            )

            if has_lines:
                itemized_total = db.session.execute(
                    select(
                        db.func.coalesce(db.func.sum(InvoiceService.total_price), Decimal(0))
                    ).filter(InvoiceService.visit_id == visit.id)
                ).scalar()

                if Decimal(visit.total_amount or 0) != Decimal(itemized_total or 0):
                    return False, 'مبلغ الزيارة لا يتوافق مع مجموع الخدمات — يتطلب تسوية الخدمات'

            return True, 'يمكن الأرشفة'

        except Exception as e:
            current_app.logger.exception('خطأ في التحقق من الأرشفة: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def create_system_receipt(visit_id, user_id, amount, payment_method='cash'):
        """
        إنشاء سند قبض نظامي.

        Ticket 4: Block ordinary financial mutations on archived visits.
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # Ticket 4: archived visits cannot receive ordinary financial mutations
            if visit.archive_status == 'ARCHIVED':
                return False, 'الزيارة مؤرشفة ولا يمكن إضافة سند قبض'

            # إنشاء رقم سند فريد
            receipt_number = f'RCP-{datetime.now().strftime("%Y%m%d%H%M%S")}-{visit_id}'

            # إنشاء الدفع
            payment = Payment(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                amount=amount,
                method=(payment_method or 'CASH').upper(),
                receipt_number=receipt_number,
                is_provisional=False,
                received_by=user_id,
            )

            db.session.add(payment)

            # تحديث الزيارة
            visit.receipt_printed = True
            visit.receipt_number = receipt_number
            visit.paid_amount = amount

            # إذا كان المبلغ المدفوع يساوي المطلوب، إزالة القفل المالي
            if visit.paid_amount >= visit.total_amount:
                visit.financial_locked = False
                visit.financial_completed_at = datetime.now(UTC)

            safe_commit(db.session, error_message='فشل إنشاء سند القبض النظامي', reraise=True)

            # تسجيل التدقيق
            audit = AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=user_id,
                old_values='{"receipt_printed": false}',
                new_values=f'{{"receipt_printed": true, "receipt_number": "{receipt_number}"}}',
                description='تم إنشاء سند قبض نظامي',
            )
            db.session.add(audit)

            return True, f'تم إنشاء السند رقم {receipt_number}'

        except Exception as e:
            current_app.logger.exception('خطأ في إنشاء السند: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def create_provisional_receipt(
        visit_id, user_id, amount, payment_method='cash', reason='EMERGENCY'
    ):
        """
        إنشاء سند قبض مؤقت (للطوارئ/الدفع القوي)
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # التحقق من أن الزيارة طوارئ أو دفع قوي
            if not (visit.is_emergency or visit.is_strong_pay):
                return False, 'السند المؤقت للطوارئ/الدفع القوي فقط'

            # إنشاء رقم سند فريد
            receipt_number = f'PRV-{datetime.now().strftime("%Y%m%d%H%M%S")}-{visit_id}'

            # إنشاء الدفع
            payment = Payment(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                amount=amount,
                method=(payment_method or 'CASH').upper(),
                receipt_number=receipt_number,
                is_provisional=True,
                provisional_reason=reason,
                received_by=user_id,
            )

            db.session.add(payment)

            # تحديث الزيارة (بدون تغيير receipt_printed)
            visit.paid_amount = amount
            visit.financial_locked = True  # يبقى مقفل حتى السند النظامي

            safe_commit(db.session, error_message='فشل إنشاء السند المؤقت', reraise=True)

            # تسجيل التدقيق
            audit = AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=user_id,
                old_values='{"is_provisional": false}',
                new_values=f'{{"is_provisional": true, "provisional_reason": "{reason}"}}',
                description='تم إنشاء سند قبض مؤقت',
            )
            db.session.add(audit)

            return True, f'تم إنشاء السند المؤقت رقم {receipt_number}'

        except Exception as e:
            current_app.logger.exception('خطأ في إنشاء السند المؤقت: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def acknowledge_liability(visit_id, user_id):
        """
        إقرار المسؤولية للطوارئ/الدفع القوي
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # التحقق من أن الزيارة طوارئ أو دفع قوي
            if not (visit.is_emergency or visit.is_strong_pay):
                return False, 'إقرار المسؤولية للطوارئ/الدفع القوي فقط'

            # تحديث الزيارة
            visit.liability_acknowledged_at = datetime.now(UTC)
            visit.financial_locked = True

            safe_commit(db.session, error_message='فشل إقرار المسؤولية', reraise=True)

            # تسجيل التدقيق
            audit = AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=user_id,
                old_values='{"liability_acknowledged_at": null}',
                new_values=f'{{"liability_acknowledged_at": "{visit.liability_acknowledged_at}"}}',
                description='تم إقرار المسؤولية',
            )
            db.session.add(audit)

            return True, 'تم إقرار المسؤولية'

        except Exception as e:
            current_app.logger.exception('خطأ في إقرار المسؤولية: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def post_gl(visit_id, user_id):
        """
        الترحيل المالي
        """
        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # التحقق من إمكانية الترحيل
            can_post, message = GatekeeperService.can_post_gl(visit_id, user_id)
            if not can_post:
                return False, message

            # تحديث الزيارة
            visit.gl_posted_at = datetime.now(UTC)

            safe_commit(db.session, error_message='فشل الترحيل المالي', reraise=True)

            # تسجيل التدقيق
            audit = AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=user_id,
                old_values='{"gl_posted_at": null}',
                new_values=f'{{"gl_posted_at": "{visit.gl_posted_at}"}}',
                description='تم الترحيل المالي',
            )
            db.session.add(audit)

            return True, 'تم الترحيل المالي'

        except Exception as e:
            current_app.logger.exception('خطأ في الترحيل المالي: %s')
            return False, f'خطأ في النظام: {e!s}'

    @staticmethod
    def archive_visit(visit_id, user_id):
        """
        أرشفة الزيارة.

        P1-002: This is the single owner of writes to Visit.archive_status.
        Archival is an administrative/financial closure action; it is NOT a
        clinical state transition and must remain separate from Visit.status.

        Ticket 1: Reception is the only ordinary tenant role that may initiate
        archive.  super_admin may also archive as platform support.
        """
        try:
            user = db.session.get(User, user_id)
            if not user or user.role not in ('reception', 'super_admin'):
                return False, 'ليس لديك الصلاحية لأرشفة الزيارة'

            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # التحقق من إمكانية الأرشفة
            can_archive, message = GatekeeperService.can_archive_visit(visit_id, user_id)
            if not can_archive:
                return False, message

            # تحديث الزيارة
            visit.archive_status = 'ARCHIVED'
            visit.archived_by = user_id
            visit.archived_at = datetime.now(UTC)

            safe_commit(db.session, error_message='فشل أرشفة الزيارة', reraise=True)

            # تسجيل التدقيق
            audit = AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=user_id,
                old_values='{"archive_status": "ACTIVE"}',
                new_values='{"archive_status": "ARCHIVED"}',
                description='تم الأرشفة',
            )
            db.session.add(audit)

            return True, 'تم الأرشفة'

        except Exception as e:
            current_app.logger.exception('خطأ في الأرشفة: %s')
            return False, f'خطأ في النظام: {e!s}'

    # ========== وظائف التحقق من قواعد الدفع الجديدة ==========

    @staticmethod
    def validate_payment_method(payment_method, amount=None):
        """
        التحقق من صلاحية طريقة الدفع
        """
        valid_methods = ['cash', 'visa', 'card', 'insurance', 'force', 'wire']

        if not payment_method:
            return False, 'يجب تحديد طريقة الدفع'

        if payment_method.lower() not in valid_methods:
            return False, f'طريقة دفع غير صالحة: {payment_method}'

        # التحقق من المبلغ للدفع النقدي
        if payment_method.lower() == 'cash' and amount:
            if Decimal(str(amount)) > Decimal(str(GatekeeperService.MAX_CASH_AMOUNT)):
                return (
                    False,
                    f'المبلغ النقدي يتجاوز الحد المسموح ({GatekeeperService.MAX_CASH_AMOUNT} شيكل)',
                )

        return True, 'طريقة الدفع صالحة'

    @staticmethod
    def validate_force_payment(visit_id, user_id, reason):
        """
        التحقق من صلاحية الدفع القسري
        """
        try:
            # 1. التحقق من السبب
            if not reason or len(reason.strip()) < 10:
                return False, 'يجب تقديم سبب واضح للدفع القسري (10 أحرف على الأقل)'

            # 2. التحقق من صلاحية المستخدم
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return False, 'المستخدم غير موجود'

            if user.role not in ['manager', 'super_admin']:
                return False, 'فقط المدير أو super_admin يمكنه الموافقة على الدفع القسري'

            # 3. التحقق من الزيارة
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False, 'الزيارة غير موجودة'

            # 4. التحقق من نسبة الدفع القسري في النظام
            thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
            total_visits = db.session.execute(
                select(func.count()).select_from(Visit).filter(Visit.created_at >= thirty_days_ago)
            ).scalar()

            force_visits = db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(Visit.created_at >= thirty_days_ago, Visit.is_force_payment)
            ).scalar()

            if total_visits > 0:
                force_percentage = (force_visits / total_visits) * 100
                if force_percentage >= GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE:
                    return (
                        False,
                        f'تجاوزت نسبة الدفع القسري الحد المسموح ({GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE}%)',
                    )

            # 5. التحقق من أن المستخدم ليس هو من أنشأ الزيارة (فصل المهام)
            if visit.created_by == user_id:
                return (
                    False,
                    'لا يمكن للمستخدم الذي أنشأ الزيارة الموافقة على الدفع القسري (فصل المهام)',
                )

            return True, 'يمكن الموافقة على الدفع القسري'

        except Exception as e:
            logger.exception('Error validating force payment: %s')
            return False, f'خطأ في التحقق: {e!s}'

    @staticmethod
    def validate_insurance(insurance_provider, policy_number, coverage_percentage):
        """
        التحقق من صلاحية التأمين
        """
        # 1. التحقق من مزود التأمين
        if not insurance_provider or len(insurance_provider.strip()) < 3:
            return False, 'يجب تحديد مزود التأمين'

        # 2. التحقق من رقم البوليصة
        if not policy_number or len(policy_number.strip()) < 3:
            return False, 'يجب تحديد رقم البوليصة'

        # 3. التحقق من نسبة التغطية
        try:
            coverage = float(coverage_percentage)
            if coverage < GatekeeperService.MIN_INSURANCE_COVERAGE:
                return (
                    False,
                    f'نسبة التغطية منخفضة جداً (الحد الأدنى {GatekeeperService.MIN_INSURANCE_COVERAGE}%)',
                )

            if coverage > GatekeeperService.MAX_INSURANCE_COVERAGE:
                return (
                    False,
                    f'نسبة التغطية غير صالحة (الحد الأقصى {GatekeeperService.MAX_INSURANCE_COVERAGE}%)',
                )

        except (ValueError, TypeError):
            return False, 'نسبة التغطية يجب أن تكون رقماً'

        return True, 'بيانات التأمين صالحة'

    @staticmethod
    def validate_card_payment(card_last_digits, card_holder_name):
        """
        التحقق من صلاحية الدفع بالبطاقة
        """
        # 1. التحقق من آخر 4 أرقام
        if not card_last_digits:
            return False, 'يجب إدخال آخر 4 أرقام من البطاقة'

        if not card_last_digits.isdigit() or len(card_last_digits) != 4:
            return False, 'آخر 4 أرقام من البطاقة يجب أن تكون أرقاماً فقط'

        # 2. التحقق من اسم حامل البطاقة
        if not card_holder_name or len(card_holder_name.strip()) < 3:
            return False, 'يجب إدخال اسم حامل البطاقة'

        return True, 'بيانات البطاقة صالحة'

    @staticmethod
    def check_payment_rules(visit):
        """
        التحقق من جميع قواعد الدفع للزيارة
        """
        issues = []

        # 1. التحقق من أن المبلغ الإجمالي محدد
        if not visit.total_amount or visit.total_amount <= 0:
            issues.append('المبلغ الإجمالي غير محدد أو صفر')

        # 2. التحقق من أن المبلغ المدفوع لا يتجاوز الإجمالي
        if visit.paid_amount > visit.total_amount:
            issues.append('المبلغ المدفوع يتجاوز المبلغ الإجمالي')

        # 3. التحقق حسب طريقة الدفع
        pm = (getattr(visit, 'payment_method', '') or '').lower()
        if pm == 'insurance':
            if not visit.insurance_provider:
                issues.append('مزود التأمين غير محدد')
            if not visit.insurance_policy_number:
                issues.append('رقم البوليصة غير محدد')
            if not visit.insurance_coverage_percentage:
                issues.append('نسبة التغطية غير محددة')
            if visit.patient_share and visit.patient_share > 0:
                if visit.paid_amount < visit.patient_share:
                    issues.append('حصة المريض غير مدفوعة بالكامل')

        elif pm == 'force':
            if not visit.is_force_payment:
                issues.append('الدفع القسري غير مفعل')
            if not visit.force_payment_reason:
                issues.append('سبب الدفع القسري غير محدد')
            if not visit.force_payment_approved_by:
                issues.append('لا توجد موافقة على الدفع القسري')

        elif pm in ['visa', 'card']:
            if not visit.card_number_last_digits:
                issues.append('آخر 4 أرقام من البطاقة غير محددة')
            if not visit.card_holder_name:
                issues.append('اسم حامل البطاقة غير محدد')

        is_valid = len(issues) == 0
        return is_valid, issues

    @staticmethod
    def get_force_payment_statistics(days=30):
        """
        الحصول على إحصائيات الدفع القسري
        """
        try:
            start_date = datetime.now(UTC) - timedelta(days=days)

            total_visits = db.session.execute(
                select(func.count()).select_from(Visit).filter(Visit.created_at >= start_date)
            ).scalar()

            force_visits = db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(Visit.created_at >= start_date, Visit.is_force_payment)
            ).scalar()

            approved_force_visits = db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(
                    Visit.created_at >= start_date,
                    Visit.is_force_payment,
                    Visit.force_payment_approved_by is not None,
                )
            ).scalar()

            pending_force_visits = force_visits - approved_force_visits

            force_percentage = 0
            if total_visits > 0:
                force_percentage = (force_visits / total_visits) * 100

            return {
                'total_visits': total_visits,
                'force_visits': force_visits,
                'approved_force_visits': approved_force_visits,
                'pending_force_visits': pending_force_visits,
                'force_percentage': round(force_percentage, 2),
                'is_within_limit': force_percentage
                <= GatekeeperService.MAX_FORCE_PAYMENT_PERCENTAGE,
                'days': days,
            }

        except Exception as e:
            logger.exception('Error getting force payment statistics: %s')
            return {'error': str(e)}
