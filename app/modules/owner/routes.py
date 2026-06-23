"""
Owner Blueprint — platform admin routes (SaaS control plane)
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from flask import current_app, render_template, render_template_string, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.modules.owner import owner_bp
from app.extensions import db
from app.core.tenant.models import (
    Tenant, SubscriptionPlan, TenantSubscriptionHistory,
    SupportTicket, PlatformAuditLog, ResourceUsage, NotificationRule,
    ProductBundle, get_bundle_for_profile, check_tenant_limits
)
from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module, get_active_modules_for_tenant
from app.core.module.registry import MODULE_REGISTRY, get_all_module_names
from app.shared.enums import TenantStatus, SubscriptionType, StorageMode, ProductProfile
from app.core.rate_limiter import rate_limit
from app.modules.owner.decorators import owner_required
from services.webhook_service import dispatch_webhook, EVENT_TENANT_CREATED, EVENT_TENANT_SUSPENDED, EVENT_TENANT_ACTIVATED, EVENT_MODULE_ACTIVATED, EVENT_MODULE_DEACTIVATED, EVENT_BUNDLE_CHANGED
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionEntitlement,
    PackageVersionLimit,
    PackageVersionPricing,
    SubscriptionLine,
    SubscriptionLineStatus,
    SubscriptionLineType,
)
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.projection import EntitlementProjectionService


def _log_action(action, entity_type, entity_id=None, details=None):
    try:
        log = PlatformAuditLog(
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string[:255] if request.user_agent else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _compute_platform_revenue():
    """MRR/ARR snapshot for owner billing dashboard."""
    all_tenants = Tenant.query.all()
    mrr = 0.0
    for t in all_tenants:
        if t.is_active_and_paid() and t.plan:
            price = float(t.plan.base_price or 0)
            if t.subscription_type == SubscriptionType.YEARLY:
                price = price / 12.0
            elif t.subscription_type == SubscriptionType.PERPETUAL:
                price = 0
            mrr += price
    return {
        'tenant_count': len(all_tenants),
        'active_paid': sum(1 for t in all_tenants if t.is_active_and_paid()),
        'mrr': mrr,
        'arr': mrr * 12,
        'currency': 'SAR',
    }


@owner_bp.route("/dashboard")
@login_required
@owner_required
def owner_dashboard():
    """لوحة تحكم المنصة — SaaS metrics"""


    all_tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    plans = SubscriptionPlan.query.all()

    tenant_count = len(all_tenants)
    active_today = sum(1 for t in all_tenants if t.is_active_and_paid())
    expired_count = sum(1 for t in all_tenants if t.status == TenantStatus.EXPIRED)
    suspended_count = sum(1 for t in all_tenants if t.status == TenantStatus.SUSPENDED)
    trial_count = sum(1 for t in all_tenants if t.status == TenantStatus.PENDING)

    # MRR/ARR
    mrr = 0.0
    for t in all_tenants:
        if t.is_active_and_paid() and t.plan:
            price = float(t.plan.base_price or 0)
            if t.subscription_type == SubscriptionType.YEARLY:
                price = price / 12.0
            elif t.subscription_type == SubscriptionType.PERPETUAL:
                price = 0
            mrr += price
    arr = mrr * 12

    churn_rate = round((expired_count / max(tenant_count, 1)) * 100, 1)
    total_users_all = sum(len(t.users) for t in all_tenants)
    avg_users_per_tenant = total_users_all / max(tenant_count, 1)

    # Trial conversion rate (mock: those who have plan and were created > 30 days ago vs trial)
    conversion_rate = 0.0
    expiring_trials = 0
    if trial_count > 0:
        thirty_days_ago = date.today() - timedelta(days=30)
        old_trials = [t for t in all_tenants if t.status == TenantStatus.PENDING and t.created_at and t.created_at.date() < thirty_days_ago]
        converted = [t for t in old_trials if t.plan_id]
        conversion_rate = round((len(converted) / max(len(old_trials), 1)) * 100, 1)
        # Expiring this week
        next_week = date.today() + timedelta(days=7)
        expiring_trials = sum(1 for t in all_tenants if t.status == TenantStatus.PENDING and t.subscription_end and t.subscription_end <= next_week)

    # Filter
    filter_status = request.args.get('status', '')
    tenants = all_tenants
    if filter_status:
        tenants = [t for t in all_tenants if t.status.value == filter_status]

    # Alerts
    alerts = []
    for t in all_tenants:
        if t.status == TenantStatus.EXPIRED:
            alerts.append({'type': 'اشتراك', 'color': 'danger', 'message': f'انتهى اشتراك {t.name}', 'tenant': t.name})
        elif t.grace_period_end and date.today() > t.grace_period_end and t.status == TenantStatus.ACTIVE:
            alerts.append({'type': 'سماح', 'color': 'warning', 'message': f'انتهت فترة سماح {t.name}', 'tenant': t.name})
    if suspended_count:
        alerts.append({'type': 'عميل', 'color': 'secondary', 'message': f'{suspended_count} عميل موقوف', 'tenant': None})

    # Chart data: last 6 months
    months = []
    tenant_growth = []
    mrr_trend = []
    churn_spark = []
    user_spark = []
    for i in range(5, -1, -1):
            month_start = (date.today().replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=31)).replace(day=1)
            months.append(month_start.strftime('%Y-%m'))
            # Count tenants created up to this month
            count = sum(1 for t in all_tenants if t.created_at and t.created_at.date() <= month_start)
            tenant_growth.append(count)
            # MRR at that month
            monthly_mrr = 0.0
            for t in all_tenants:
                if t.is_active_and_paid() and t.plan and t.created_at and t.created_at.date() <= month_start:
                    price = float(t.plan.base_price or 0)
                    if t.subscription_type == SubscriptionType.YEARLY:
                        price = price / 12.0
                    elif t.subscription_type == SubscriptionType.PERPETUAL:
                        price = 0
                    monthly_mrr += price
            mrr_trend.append(round(monthly_mrr, 2))
            # Real churn: tenants that expired in this month
            churn_count = sum(1 for t in all_tenants if t.status == TenantStatus.EXPIRED and t.subscription_end and month_start <= t.subscription_end < month_end)
            churn_spark.append(churn_count)
            # Real user growth: users created in this month
            user_count = sum(1 for t in all_tenants for u in (t.users or []) if u.created_at and month_start <= u.created_at.date() < month_end)
            user_spark.append(user_count)

    # Status distribution for chart
    status_labels = ['نشط', 'معلق', 'منتهي', 'موقوف']
    status_data = [
        sum(1 for t in all_tenants if t.status == TenantStatus.ACTIVE),
        sum(1 for t in all_tenants if t.status == TenantStatus.PENDING),
        sum(1 for t in all_tenants if t.status == TenantStatus.EXPIRED),
        sum(1 for t in all_tenants if t.status == TenantStatus.SUSPENDED),
    ]

    # Support tickets summary for chart
    ticket_counts = {
        'open': SupportTicket.query.filter_by(status='open').count(),
        'in_progress': SupportTicket.query.filter_by(status='in_progress').count(),
        'resolved': SupportTicket.query.filter_by(status='resolved').count(),
        'closed': SupportTicket.query.filter_by(status='closed').count(),
    }
    ticket_labels = ['مفتوحة', 'قيد المعالجة', 'محلولة', 'مغلقة']
    ticket_data = [ticket_counts['open'], ticket_counts['in_progress'], ticket_counts['resolved'], ticket_counts['closed']]

    # Recent audit logs
    recent_logs = PlatformAuditLog.query.order_by(PlatformAuditLog.created_at.desc()).limit(5).all()

    # Top resource consumers
    top_resources = ResourceUsage.query.order_by(ResourceUsage.db_size_mb.desc()).limit(5).all()

    return render_template('owner/dashboard.html',
                           tenant_count=tenant_count,
                           active_today=active_today,
                           expired_count=expired_count,
                           suspended_count=suspended_count,
                           mrr=mrr,
                           arr=arr,
                           churn_rate=churn_rate,
                           total_users_all=total_users_all,
                           avg_users_per_tenant=avg_users_per_tenant,
                           trial_count=trial_count,
                           conversion_rate=conversion_rate,
                           expiring_trials=expiring_trials,
                           tenants=tenants,
                           plans=plans,
                           alerts=alerts,
                           filter_status=filter_status,
                           chart_months=months,
                           chart_tenant_growth=tenant_growth,
                           chart_mrr_trend=mrr_trend,
                           chart_churn_spark=churn_spark,
                           chart_user_spark=user_spark,
                           chart_status_labels=status_labels,
                           chart_status_data=status_data,
                           chart_ticket_labels=ticket_labels,
                           chart_ticket_data=ticket_data,
                           recent_logs=recent_logs,
                           top_resources=top_resources,
                           currency='SAR')


@owner_bp.route("/tenants/create", methods=["GET", "POST"])
@login_required
@owner_required
def owner_create_tenant():


    plans = SubscriptionPlan.query.all()
    if request.method == 'POST':
        try:
            profile_code = request.form.get('product_profile', '').strip() or None
            t = Tenant(
                slug=request.form.get('slug', '').strip(),
                name=request.form.get('name', '').strip(),
                name_ar=request.form.get('name_ar', '').strip() or None,
                domain=request.form.get('domain', '').strip() or None,
                subdomain=request.form.get('subdomain', '').strip() or None,
                contact_email=request.form.get('contact_email', '').strip(),
                contact_phone=request.form.get('contact_phone', '').strip() or None,
                tax_number=request.form.get('tax_number', '').strip() or None,
                product_profile_code=profile_code if profile_code else None,
                plan_id=int(request.form.get('plan_id')) if request.form.get('plan_id') else None,
                subscription_type=SubscriptionType(request.form.get('subscription_type', 'monthly')),
                subscription_start=date.today(),
                subscription_end=datetime.strptime(request.form.get('subscription_end'), '%Y-%m-%d').date() if request.form.get('subscription_end') else None,
                grace_period_end=datetime.strptime(request.form.get('grace_period_end'), '%Y-%m-%d').date() if request.form.get('grace_period_end') else None,
                storage_mode=StorageMode(request.form.get('storage_mode', 'local')),
                status=TenantStatus.ACTIVE
            )
            db.session.add(t)
            db.session.flush()

            # Auto-activate default modules for the profile
            if profile_code:
                from app.core.tenant.models import get_default_modules_for_profile
                default_modules = get_default_modules_for_profile(profile_code)
                for mod_name in default_modules:
                    from app.core.module.models import TenantModule
                    tm = TenantModule(tenant_id=t.id, module_name=mod_name, is_active=True)
                    db.session.add(tm)

            db.session.commit()
            _log_action('CREATE_TENANT', 'tenant', t.id, f"Created tenant {t.name} ({t.slug}) profile={profile_code}")
            dispatch_webhook(EVENT_TENANT_CREATED, {"tenant_id": t.id, "name": t.name, "slug": t.slug})
            flash('تم إنشاء العميل بنجاح', 'success')
            return redirect(url_for('owner.owner_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    from app.shared.enums import ProductProfile
    return render_template('owner/create_tenant.html', plans=plans, profiles=list(ProductProfile))


@owner_bp.route("/tenants/<int:tenant_id>")
@login_required
@owner_required
def owner_tenant_detail(tenant_id):


    tenant = Tenant.query.get_or_404(tenant_id)
    active_modules = get_active_modules_for_tenant(tenant_id)
    from app.core.tenant.models import TenantFeatureFlag, get_bundle_for_profile, check_tenant_limits
    feature_flags = TenantFeatureFlag.query.filter_by(tenant_id=tenant_id, is_enabled=True).all()
    from app.core.module.registry import MODULE_REGISTRY, get_all_module_names
    all_modules = get_all_module_names()
    bundle = get_bundle_for_profile(tenant.product_profile_code.value) if tenant.product_profile_code else None
    bundle_limits = None
    bundle_name = None
    if bundle:
        bundle_limits = {
            'max_users': bundle.max_users,
            'max_patients': bundle.max_patients,
            'storage_gb': bundle.storage_gb,
            'api_calls_per_month': bundle.api_calls_per_month,
        }
        bundle_name = bundle.name_ar or bundle.name
    user_count = len(tenant.users)
    from models.patient import Patient
    patient_count = Patient.query.filter_by(tenant_id=tenant_id).count()
    return render_template('owner/tenant_detail.html',
                           tenant=tenant,
                           active_modules=list(active_modules),
                           feature_flags=feature_flags,
                           all_modules=all_modules,
                           bundle_limits=bundle_limits,
                           bundle_name=bundle_name,
                           user_count=user_count,
                           patient_count=patient_count)


@owner_bp.route("/tenants/<int:tenant_id>/renew")
@login_required
@owner_required
def owner_renew_tenant(tenant_id):


    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        old_plan = tenant.plan_id
        if tenant.plan and tenant.subscription_type == SubscriptionType.MONTHLY:
            tenant.subscription_end = date.today().replace(month=tenant.subscription_end.month + 1 if tenant.subscription_end and tenant.subscription_end.month < 12 else 1)
        elif tenant.plan and tenant.subscription_type == SubscriptionType.YEARLY:
            tenant.subscription_end = date(tenant.subscription_end.year + 1, tenant.subscription_end.month, tenant.subscription_end.day) if tenant.subscription_end else date.today()
        elif tenant.plan and tenant.subscription_type == SubscriptionType.PERPETUAL:
            tenant.subscription_end = None

        tenant.status = TenantStatus.ACTIVE
        db.session.commit()

        h = TenantSubscriptionHistory(
            tenant_id=tenant_id,
            action='RENEW',
            old_plan_id=old_plan,
            new_plan_id=tenant.plan_id,
            performed_by=current_user.id,
            notes='تجديد الاشتراك من لوحة المنصة'
        )
        db.session.add(h)
        db.session.commit()
        _log_action('RENEW_SUBSCRIPTION', 'tenant', tenant_id, f"Renewed tenant {tenant.name}")
        flash('تم تجديد الاشتراك', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_tenant_detail', tenant_id=tenant_id))


@owner_bp.route("/tenants/<int:tenant_id>/suspend")
@login_required
@owner_required
def owner_suspend_tenant(tenant_id):


    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()
        _log_action('SUSPEND_TENANT', 'tenant', tenant_id, f"Suspended tenant {tenant.name}")
        dispatch_webhook(EVENT_TENANT_SUSPENDED, {"tenant_id": tenant_id, "name": tenant.name})
        flash('تم إيقاف العميل', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/tenants/<int:tenant_id>/activate")
@login_required
@owner_required
def owner_activate_tenant(tenant_id):


    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.ACTIVE
        db.session.commit()
        _log_action('ACTIVATE_TENANT', 'tenant', tenant_id, f"Activated tenant {tenant.name}")
        dispatch_webhook(EVENT_TENANT_ACTIVATED, {"tenant_id": tenant_id, "name": tenant.name})
        flash('تم تفعيل العميل', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/plans")
@login_required
@owner_required
def owner_plans():


    plans = SubscriptionPlan.query.all()
    return render_template('owner/plans.html', plans=plans)


@owner_bp.route("/announcements", methods=["GET", "POST"])
@login_required
@owner_required
def owner_announcements():


    announcements = []
    try:
        from models.system_config import SystemConfig
        cfg = SystemConfig.query.filter_by(config_key='owner_announcements').first()
        if cfg and cfg.config_value:
            import json
            announcements = json.loads(cfg.config_value)
    except Exception:
        announcements = []

    if request.method == 'POST':
        try:
            new_announcement = {
                'id': int(datetime.now(timezone.utc).timestamp()),
                'title': request.form.get('title', '').strip(),
                'content': request.form.get('content', '').strip(),
                'priority': request.form.get('priority', 'info'),
                'target_audience': request.form.get('target_audience', 'all'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'created_by': current_user.id
            }
            announcements.insert(0, new_announcement)
            announcements = announcements[:50]

            from models.system_config import SystemConfig
            cfg = SystemConfig.query.filter_by(config_key='owner_announcements').first()
            import json
            if cfg:
                cfg.config_value = json.dumps(announcements)
                cfg.updated_by = current_user.id
                cfg.updated_at = datetime.now(timezone.utc)
            else:
                cfg = SystemConfig(
                    config_key='owner_announcements',
                    config_value=json.dumps(announcements),
                    config_type='json',
                    category='owner',
                    created_by=current_user.id,
                    updated_by=current_user.id
                )
                db.session.add(cfg)
            db.session.commit()
            _log_action('CREATE_ANNOUNCEMENT', 'system', None, new_announcement['title'])
            flash('تم إرسال الإعلان', 'success')
            return redirect(url_for('owner.owner_announcements'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    return render_template('owner/announcements.html', announcements=announcements)


# ─────────────────────────────────────────────
# Support Tickets
# ─────────────────────────────────────────────
@owner_bp.route("/support-tickets")
@login_required
@owner_required
def owner_support_tickets():


    status_filter = request.args.get('status', '')
    q = SupportTicket.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    tickets = q.order_by(SupportTicket.created_at.desc()).limit(50).all()
    return render_template('owner/support_tickets.html', tickets=tickets, status_filter=status_filter)


@owner_bp.route("/support-tickets/<int:ticket_id>/update", methods=["POST"])
@login_required
@owner_required
def owner_update_ticket(ticket_id):


    ticket = SupportTicket.query.get_or_404(ticket_id)
    try:
        ticket.status = request.form.get('status', ticket.status)
        ticket.priority = request.form.get('priority', ticket.priority)
        ticket.assigned_to = int(request.form.get('assigned_to')) if request.form.get('assigned_to') else ticket.assigned_to
        if ticket.status == 'resolved':
            ticket.resolved_at = datetime.now(timezone.utc)
        db.session.commit()
        _log_action('UPDATE_TICKET', 'ticket', ticket_id, f"Status: {ticket.status}")
        flash('تم تحديث التذكرة', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_support_tickets'))


# ─────────────────────────────────────────────
# Audit Logs
# ─────────────────────────────────────────────
@owner_bp.route("/audit-logs")
@login_required
@owner_required
def owner_audit_logs():


    entity_type = request.args.get('entity_type', '')
    q = PlatformAuditLog.query
    if entity_type:
        q = q.filter_by(entity_type=entity_type)
    logs = q.order_by(PlatformAuditLog.created_at.desc()).limit(100).all()
    return render_template('owner/audit_logs.html', logs=logs, entity_type=entity_type)


# ─────────────────────────────────────────────
# Resource Usage
# ─────────────────────────────────────────────
@owner_bp.route("/resource-usage")
@login_required
@owner_required
def owner_resource_usage():


    usages = ResourceUsage.query.order_by(ResourceUsage.recorded_at.desc()).limit(100).all()
    return render_template('owner/resource_usage.html', usages=usages)


# ─────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────
@owner_bp.route("/notifications")
@login_required
@owner_required
def owner_notifications():


    rules = NotificationRule.query.order_by(NotificationRule.created_at.desc()).all()
    return render_template('owner/notifications.html', rules=rules)


@owner_bp.route("/notifications/create", methods=["POST"])
@login_required
@owner_required
def owner_create_notification():


    try:
        r = NotificationRule(
            event_type=request.form.get('event_type', 'subscription_expiry'),
            channel=request.form.get('channel', 'email'),
            target=request.form.get('target', '').strip(),
            template_subject=request.form.get('template_subject', '').strip() or None,
            template_body=request.form.get('template_body', '').strip() or None,
            is_active=bool(request.form.get('is_active'))
        )
        db.session.add(r)
        db.session.commit()
        _log_action('CREATE_NOTIFICATION', 'notification', r.id)
        flash('تم إنشاء قاعدة الإشعار', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_notifications'))


# ─────────────────────────────────────────────
# Platform Branding (White-label)
# ─────────────────────────────────────────────
@owner_bp.route("/branding", methods=["GET", "POST"])
@login_required
@owner_required
def owner_branding():


    branding = {}
    try:
        from models.system_config import SystemConfig
        cfg = SystemConfig.query.filter_by(config_key='owner_platform_branding').first()
        if cfg and cfg.config_value:
            import json
            branding = json.loads(cfg.config_value)
    except Exception:
        branding = {}

    if request.method == 'POST':
        try:
            branding = {
                'platform_name': request.form.get('platform_name', '').strip(),
                'platform_name_en': request.form.get('platform_name_en', '').strip(),
                'primary_color': request.form.get('primary_color', '#1a1f3a').strip(),
                'secondary_color': request.form.get('secondary_color', '#D4AF37').strip(),
                'logo_url': request.form.get('logo_url', '').strip() or None,
                'favicon_url': request.form.get('favicon_url', '').strip() or None,
                'meta_description': request.form.get('meta_description', '').strip() or None,
            }
            from models.system_config import SystemConfig
            cfg = SystemConfig.query.filter_by(config_key='owner_platform_branding').first()
            import json
            if cfg:
                cfg.config_value = json.dumps(branding)
                cfg.updated_by = current_user.id
                cfg.updated_at = datetime.now(timezone.utc)
            else:
                cfg = SystemConfig(
                    config_key='owner_platform_branding',
                    config_value=json.dumps(branding),
                    config_type='json',
                    category='owner',
                    created_by=current_user.id,
                    updated_by=current_user.id
                )
                db.session.add(cfg)
            db.session.commit()
            _log_action('UPDATE_BRANDING', 'system', None, 'Updated platform branding')
            flash('تم حفظ التخصيص', 'success')
            return redirect(url_for('owner.owner_branding'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    return render_template('owner/branding.html', branding=branding)


# ─────────────────────────────────────────────
# Webhooks & API Keys
# ─────────────────────────────────────────────
@owner_bp.route("/webhooks", methods=["GET", "POST"])
@login_required
@owner_required
def owner_webhooks():


    webhooks = []
    try:
        from models.system_config import SystemConfig
        cfg_wh = SystemConfig.query.filter_by(config_key='owner_webhooks').first()
        if cfg_wh and cfg_wh.config_value:
            webhooks = json.loads(cfg_wh.config_value)
    except Exception:
        pass

    if request.method == 'POST':
        try:
            if request.form.get('name') and request.form.get('url'):
                # Webhook
                webhooks.insert(0, {
                    'id': int(datetime.now(timezone.utc).timestamp()),
                    'name': request.form.get('name', '').strip(),
                    'url': request.form.get('url', '').strip(),
                    'events': request.form.get('events', '').strip(),
                    'secret': request.form.get('secret', '').strip(),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                })
                webhooks = webhooks[:50]
                from models.system_config import SystemConfig
                cfg = SystemConfig.query.filter_by(config_key='owner_webhooks').first()
                import json
                if cfg:
                    cfg.config_value = json.dumps(webhooks)
                    cfg.updated_by = current_user.id
                else:
                    cfg = SystemConfig(config_key='owner_webhooks', config_value=json.dumps(webhooks), config_type='json', category='owner', created_by=current_user.id, updated_by=current_user.id)
                    db.session.add(cfg)
                db.session.commit()
                _log_action('CREATE_WEBHOOK', 'system', None, request.form.get('name'))
                flash('تم إضافة الـ Webhook', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')
        return redirect(url_for('owner.owner_webhooks'))

    return render_template('owner/webhooks.html', webhooks=webhooks)


@owner_bp.route("/api-keys", methods=["GET", "POST"])
@login_required
@owner_required
def owner_api_keys_page():
    """إدارة API Keys — صفحة مستقلة (G-141)."""
    api_keys = []
    tenants = Tenant.query.all()
    try:
        from models.system_config import SystemConfig
        cfg_key = SystemConfig.query.filter_by(config_key='owner_api_keys').first()
        if cfg_key and cfg_key.config_value:
            api_keys_raw = json.loads(cfg_key.config_value)
            for k in api_keys_raw:
                tenant = Tenant.query.get(k.get('tenant_id'))
                api_keys.append({
                    'name': k.get('name'),
                    'scopes': k.get('scopes'),
                    'key': k.get('key'),
                    'created_at': k.get('created_at'),
                    'tenant': tenant,
                })
    except Exception:
        pass

    if request.method == 'POST':
        try:
            import secrets as _secrets
            new_key = {
                'id': int(datetime.now(timezone.utc).timestamp()),
                'tenant_id': int(request.form.get('tenant_id', 0)),
                'name': request.form.get('name', '').strip(),
                'key': 'ak_' + _secrets.token_urlsafe(32),
                'scopes': request.form.get('scopes', 'read').strip(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'created_by': current_user.id,
            }
            from models.system_config import SystemConfig
            cfg = SystemConfig.query.filter_by(config_key='owner_api_keys').first()
            keys = []
            if cfg and cfg.config_value:
                keys = json.loads(cfg.config_value)
            keys.insert(0, new_key)
            keys = keys[:100]
            if cfg:
                cfg.config_value = json.dumps(keys)
                cfg.updated_by = current_user.id
            else:
                cfg = SystemConfig(
                    config_key='owner_api_keys',
                    config_value=json.dumps(keys),
                    config_type='json',
                    category='owner',
                    created_by=current_user.id,
                    updated_by=current_user.id,
                )
                db.session.add(cfg)
            db.session.commit()
            _log_action('CREATE_API_KEY', 'system', new_key['tenant_id'], new_key['name'])
            flash(f"تم إنشاء API Key: {new_key['key'][:20]}...", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')
        return redirect(url_for('owner.owner_api_keys_page'))

    return render_template('owner/api_keys.html', api_keys=api_keys, tenants=tenants)


@owner_bp.route("/themes", methods=["GET", "POST"])
@login_required
@owner_required
def owner_themes():
    """إدارة ثيمات النظام (SystemTheme)."""
    from models.branding import SystemTheme

    if request.method == 'POST':
        try:
            theme = SystemTheme(
                name=request.form.get('name', '').strip(),
                name_ar=request.form.get('name_ar', '').strip(),
                description=request.form.get('description', '').strip() or None,
                primary_color=request.form.get('primary_color', '#2563eb'),
                secondary_color=request.form.get('secondary_color', '#10b981'),
                accent_color=request.form.get('accent_color', '#f59e0b'),
                background_color=request.form.get('background_color', '#f8fafc'),
                text_color=request.form.get('text_color', '#1f2937'),
                is_active=True,
            )
            db.session.add(theme)
            db.session.commit()
            _log_action('CREATE_THEME', 'theme', theme.id, theme.name_ar)
            flash('تم إنشاء الثيم', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')
        return redirect(url_for('owner.owner_themes'))

    themes = SystemTheme.query.order_by(SystemTheme.is_default.desc(), SystemTheme.name_ar).all()
    return render_template('owner/themes.html', themes=themes)


@owner_bp.route("/billing")
@login_required
@owner_required
def owner_billing():
    """ملخص الفوترة والإيرادات المتكررة."""
    stats = _compute_platform_revenue()
    plans = SubscriptionPlan.query.all()
    plan_rows = []
    for plan in plans:
        count = sum(1 for t in Tenant.query.all() if t.plan_id == plan.id and t.is_active_and_paid())
        plan_rows.append({'plan': plan, 'active_count': count})
    return render_template('owner/billing.html', stats=stats, plan_rows=plan_rows)


# ─────────────────────────────────────────────
# Existing API routes preserved
# ─────────────────────────────────────────────
@owner_bp.route("/api/tenants", methods=["GET"])
@login_required
@owner_required
def api_tenants():

    tenants = Tenant.query.all()
    return jsonify([{"id": t.id, "name": t.name, "slug": t.slug, "status": str(t.status)} for t in tenants])


@owner_bp.route("/api/tenants/<int:tenant_id>/modules", methods=["GET"])
@login_required
@owner_required
def api_tenant_modules(tenant_id):

    active = get_active_modules_for_tenant(tenant_id)
    return jsonify({"tenant_id": tenant_id, "active_modules": list(active)})


@owner_bp.route("/api/tenants/<int:tenant_id>/modules/<module_name>/activate", methods=["POST"])
@login_required
@owner_required
def api_activate_module(tenant_id, module_name):

    ok, err = can_activate_module(tenant_id, module_name)
    if not ok:
        return jsonify({"error": err}), 400
    tm = TenantModule.query.filter_by(tenant_id=tenant_id, module_name=module_name).first()
    if not tm:
        tm = TenantModule(tenant_id=tenant_id, module_name=module_name)
        db.session.add(tm)
    tm.is_active = True
    tm.activated_at = datetime.now(timezone.utc)
    db.session.commit()
    dispatch_webhook(EVENT_MODULE_ACTIVATED, {"tenant_id": tenant_id, "module": module_name})
    return jsonify({"status": "activated", "module": module_name})


@owner_bp.route("/api/tenants/<int:tenant_id>/modules/<module_name>/deactivate", methods=["POST"])
@login_required
@owner_required
def api_deactivate_module(tenant_id, module_name):

    tm = TenantModule.query.filter_by(tenant_id=tenant_id, module_name=module_name).first()
    if tm:
        tm.is_active = False
        tm.deactivated_at = datetime.now(timezone.utc)
        db.session.commit()
        _log_action('DEACTIVATE_MODULE', 'module', tenant_id, f"Deactivated {module_name}")
        dispatch_webhook(EVENT_MODULE_DEACTIVATED, {"tenant_id": tenant_id, "module": module_name})
    return jsonify({"status": "deactivated", "module": module_name})


@owner_bp.route("/api/tenants/<int:tenant_id>/profile", methods=["POST"])
@login_required
@owner_required
def api_update_profile(tenant_id):

    tenant = Tenant.query.get_or_404(tenant_id)
    profile_code = request.json.get("product_profile") or request.form.get("product_profile")
    from app.core.tenant.models import _PRODUCT_PROFILE_SEED
    if profile_code and profile_code not in _PRODUCT_PROFILE_SEED:
        return jsonify({"error": "Invalid profile"}), 400
    try:
        tenant.product_profile_code = profile_code
        db.session.commit()
        _log_action('UPDATE_PROFILE', 'tenant', tenant_id, f"Profile -> {profile_code}")
        return jsonify({"status": "updated", "profile": profile_code})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@owner_bp.route("/api/tenants/<int:tenant_id>/features/<feature_key>/toggle", methods=["POST"])
@login_required
@owner_required
def api_toggle_feature(tenant_id, feature_key):

    from app.core.tenant.models import TenantFeatureFlag
    flag = TenantFeatureFlag.query.filter_by(tenant_id=tenant_id, feature_key=feature_key).first()
    if not flag:
        flag = TenantFeatureFlag(tenant_id=tenant_id, feature_key=feature_key, is_enabled=True)
        db.session.add(flag)
    else:
        flag.is_enabled = not flag.is_enabled
    try:
        db.session.commit()
        _log_action('TOGGLE_FEATURE', 'feature', tenant_id, f"{feature_key}={flag.is_enabled}")
        return jsonify({"status": "toggled", "feature": feature_key, "is_enabled": flag.is_enabled})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ─────────────────────────────────────────────
# ProductBundle HTML page
# ─────────────────────────────────────────────
@owner_bp.route("/bundles")
@login_required
@owner_required
def owner_bundles():
    """إدارة الباقات (HTML)"""
    bundles = ProductBundle.query.order_by(ProductBundle.monthly_price).all()
    return render_template('owner/bundles.html', bundles=bundles)


# ─────────────────────────────────────────────
# ProductBundle CRUD API
# ─────────────────────────────────────────────
@owner_bp.route("/api/bundles", methods=["GET"])
@login_required
@rate_limit(max_requests=30, window_seconds=60)
def api_list_bundles():
    """List all product bundles."""

    bundles = ProductBundle.query.filter_by(is_active=True).order_by(ProductBundle.monthly_price).all()
    return jsonify([{
        "id": b.id,
        "slug": b.slug,
        "name": b.name,
        "name_ar": b.name_ar,
        "description_ar": b.description_ar,
        "monthly_price": float(b.monthly_price),
        "yearly_price": float(b.yearly_price),
        "setup_fee": float(b.setup_fee),
        "currency": b.currency,
        "modules": b.get_modules(),
        "max_users": b.max_users,
        "max_patients": b.max_patients,
        "storage_gb": b.storage_gb,
        "api_calls_per_month": b.api_calls_per_month,
        "is_public": b.is_public,
        "is_active": b.is_active,
        "profile_code": b.profile_code,
    } for b in bundles])


@owner_bp.route("/api/bundles/<int:bundle_id>", methods=["GET"])
@login_required
@rate_limit(max_requests=60, window_seconds=60)
def api_get_bundle(bundle_id):
    """Get a single bundle detail."""

    b = ProductBundle.query.get_or_404(bundle_id)
    return jsonify({
        "id": b.id,
        "slug": b.slug,
        "name": b.name,
        "name_ar": b.name_ar,
        "description_ar": b.description_ar,
        "monthly_price": float(b.monthly_price),
        "yearly_price": float(b.yearly_price),
        "setup_fee": float(b.setup_fee),
        "currency": b.currency,
        "modules": b.get_modules(),
        "max_users": b.max_users,
        "max_patients": b.max_patients,
        "storage_gb": b.storage_gb,
        "api_calls_per_month": b.api_calls_per_month,
        "is_public": b.is_public,
        "is_active": b.is_active,
        "profile_code": b.profile_code,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    })


@owner_bp.route("/api/bundles", methods=["POST"])
@login_required
@rate_limit(max_requests=20, window_seconds=60)
def api_create_bundle():
    """Create a new product bundle."""

    try:
        data = request.get_json() or request.form
        b = ProductBundle(
            slug=data.get("slug", "").strip(),
            name=data.get("name", "").strip(),
            name_ar=data.get("name_ar", "").strip(),
            description_ar=data.get("description_ar", "").strip() or None,
            monthly_price=Decimal(str(data.get("monthly_price", 0))),
            yearly_price=Decimal(str(data.get("yearly_price", 0))),
            setup_fee=Decimal(str(data.get("setup_fee", 0))),
            currency=data.get("currency", "SAR"),
            modules=json.dumps(data.get("modules", [])),
            max_users=int(data.get("max_users")) if data.get("max_users") else None,
            max_patients=int(data.get("max_patients")) if data.get("max_patients") else None,
            storage_gb=int(data.get("storage_gb")) if data.get("storage_gb") else None,
            api_calls_per_month=int(data.get("api_calls_per_month")) if data.get("api_calls_per_month") else None,
            is_public=bool(data.get("is_public", True)),
            is_active=bool(data.get("is_active", True)),
            profile_code=data.get("profile_code", "").strip() or None,
        )
        db.session.add(b)
        db.session.commit()
        _log_action('CREATE_BUNDLE', 'bundle', b.id, f"Created bundle {b.name_ar}")
        dispatch_webhook(EVENT_BUNDLE_CHANGED, {"action": "created", "bundle_id": b.id, "slug": b.slug, "name": b.name_ar})
        return jsonify({"status": "created", "id": b.id, "slug": b.slug})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@owner_bp.route("/api/bundles/<int:bundle_id>", methods=["PUT"])
@login_required
@rate_limit(max_requests=20, window_seconds=60)
def api_update_bundle(bundle_id):
    """Update a product bundle."""

    b = ProductBundle.query.get_or_404(bundle_id)
    try:
        data = request.get_json() or request.form
        b.name = data.get("name", b.name)
        b.name_ar = data.get("name_ar", b.name_ar)
        b.description_ar = data.get("description_ar", b.description_ar)
        b.monthly_price = Decimal(str(data.get("monthly_price", b.monthly_price)))
        b.yearly_price = Decimal(str(data.get("yearly_price", b.yearly_price)))
        b.setup_fee = Decimal(str(data.get("setup_fee", b.setup_fee)))
        b.currency = data.get("currency", b.currency)
        if "modules" in data:
            b.set_modules(data.get("modules"))
        b.max_users = int(data.get("max_users")) if data.get("max_users") else None
        b.max_patients = int(data.get("max_patients")) if data.get("max_patients") else None
        b.storage_gb = int(data.get("storage_gb")) if data.get("storage_gb") else None
        b.api_calls_per_month = int(data.get("api_calls_per_month")) if data.get("api_calls_per_month") else None
        b.is_public = bool(data.get("is_public", b.is_public))
        b.is_active = bool(data.get("is_active", b.is_active))
        b.profile_code = data.get("profile_code", b.profile_code) or None
        db.session.commit()
        _log_action('UPDATE_BUNDLE', 'bundle', bundle_id, f"Updated bundle {b.name_ar}")
        dispatch_webhook(EVENT_BUNDLE_CHANGED, {"action": "updated", "bundle_id": bundle_id, "slug": b.slug, "name": b.name_ar})
        return jsonify({"status": "updated", "id": b.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@owner_bp.route("/api/bundles/<int:bundle_id>", methods=["DELETE"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def api_delete_bundle(bundle_id):
    """Delete (deactivate) a product bundle."""

    b = ProductBundle.query.get_or_404(bundle_id)
    try:
        b.is_active = False
        db.session.commit()
        _log_action('DELETE_BUNDLE', 'bundle', bundle_id, f"Deactivated bundle {b.name_ar}")
        dispatch_webhook(EVENT_BUNDLE_CHANGED, {"action": "deleted", "bundle_id": bundle_id, "slug": b.slug, "name": b.name_ar})
        return jsonify({"status": "deleted", "id": bundle_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ─────────────────────────────────────────────
# Tenant Provisioning with Bundle
# ─────────────────────────────────────────────
@owner_bp.route("/api/tenants/provision", methods=["POST"])
@login_required
@rate_limit(max_requests=10, window_seconds=60)
def api_provision_tenant():
    """Create a new tenant with bundle-based provisioning."""

    try:
        data = request.get_json() or request.form
        slug = data.get("slug", "").strip()
        name = data.get("name", "").strip()
        name_ar = data.get("name_ar", "").strip() or None
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip() or None
        bundle_slug = data.get("bundle_slug", "").strip()
        domain = data.get("domain", "").strip() or None
        subdomain = data.get("subdomain", "").strip() or None
        
        if not all([slug, name, email, bundle_slug]):
            return jsonify({"error": "Missing required fields: slug, name, email, bundle_slug"}), 400
        
        if Tenant.query.filter_by(slug=slug).first():
            return jsonify({"error": "Slug already exists"}), 400
        
        bundle = ProductBundle.query.filter_by(slug=bundle_slug, is_active=True).first()
        if not bundle:
            return jsonify({"error": "Invalid or inactive bundle"}), 400
        
        # Check bundle limits for trial
        if not bundle.is_unlimited("max_users") and bundle.max_users and bundle.max_users < 1:
            return jsonify({"error": "Bundle has zero user limit"}), 400
        
        tenant = Tenant(
            slug=slug,
            name=name,
            name_ar=name_ar,
            domain=domain,
            subdomain=subdomain,
            contact_email=email,
            contact_phone=phone,
            product_profile_code=bundle.profile_code,
            status=TenantStatus.ACTIVE,
            storage_mode=StorageMode.LOCAL,
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Activate bundle modules
        for mod_name in bundle.get_modules():
            tm = TenantModule(tenant_id=tenant.id, module_name=mod_name, is_active=True)
            db.session.add(tm)
        
        # Record initial resource snapshot
        from app.core.tenant.models import ResourceUsage
        ResourceUsage.record_snapshot(tenant.id)
        
        db.session.commit()
        _log_action('PROVISION_TENANT', 'tenant', tenant.id, f"Provisioned {tenant.name} with bundle {bundle_slug}")
        dispatch_webhook(EVENT_TENANT_CREATED, {"tenant_id": tenant.id, "name": tenant.name, "slug": tenant.slug, "bundle": bundle_slug})
        
        return jsonify({
            "status": "provisioned",
            "tenant": {
                "id": tenant.id,
                "slug": tenant.slug,
                "name": tenant.name,
                "bundle": bundle.slug,
                "modules": bundle.get_modules(),
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@owner_bp.route("/api/tenants/<int:tenant_id>/limits", methods=["GET"])
@login_required
@owner_required
def api_tenant_limits(tenant_id):
    """Get tenant's current resource usage vs bundle limits."""

    tenant = Tenant.query.get_or_404(tenant_id)
    limits = check_tenant_limits(tenant_id)
    bundle = get_bundle_for_profile(tenant.product_profile_code or "")
    latest_usage = ResourceUsage.query.filter_by(tenant_id=tenant_id).order_by(ResourceUsage.recorded_at.desc()).first()
    
    return jsonify({
        "tenant_id": tenant_id,
        "bundle": bundle.slug if bundle else None,
        "limits": limits,
        "usage": latest_usage.to_dict() if latest_usage else None,
    })


@owner_bp.route("/api/tenants/<int:tenant_id>/record-usage", methods=["POST"])
@login_required
@rate_limit(max_requests=30, window_seconds=60)
def api_record_usage(tenant_id):
    """Manually trigger a resource usage snapshot for a tenant."""

    snapshot = ResourceUsage.record_snapshot(tenant_id)
    return jsonify({"status": "recorded", "snapshot": snapshot.to_dict()})


# ---------------------------------------------------------------------------
# UX0 — SaaS Owner Console
# ---------------------------------------------------------------------------

@owner_bp.route("/packages")
@login_required
@owner_required
def owner_packages():
    """Package Manager UI (UX0-001)."""
    packages = Package.query.order_by(Package.category, Package.name).all()
    return render_template("owner/packages.html", packages=packages)


@owner_bp.route("/packages/create", methods=["POST"])
@login_required
@owner_required
def owner_create_package():
    """Create a new Package + initial PackageVersion."""
    name = request.form.get("name", "").strip()
    name_ar = request.form.get("name_ar", "").strip()
    slug = request.form.get("slug", "").strip()
    category = request.form.get("category", "bundle").strip()
    version = request.form.get("version", "1.0.0").strip()

    if not name or not slug:
        flash("اسم Package وSlug مطلوبان", "error")
        return redirect(url_for("owner.owner_packages"))

    if Package.query.filter_by(slug=slug).first():
        flash("Slug مستخدم مسبقاً", "error")
        return redirect(url_for("owner.owner_packages"))

    package = Package(name=name, name_ar=name_ar or None, slug=slug, category=category, is_active=True)
    db.session.add(package)
    db.session.flush()

    pv = PackageVersion(
        package_id=package.id,
        version=version,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(pv)
    db.session.commit()
    _log_action("CREATE_PACKAGE", "package", package.id, f"slug={slug}")
    flash("تم إنشاء Package بنجاح", "success")
    return redirect(url_for("owner.owner_packages"))


@owner_bp.route("/packages/<int:package_id>/versions/create", methods=["POST"])
@login_required
@owner_required
def owner_create_package_version(package_id):
    """Create a new version of an existing package."""
    package = Package.query.get_or_404(package_id)
    version = request.form.get("version", "").strip()
    changelog = request.form.get("changelog", "").strip()
    copy_from_latest = request.form.get("copy_from_latest") == "on"

    if not version:
        flash("رقم الإصدار مطلوب", "error")
        return redirect(url_for("owner.owner_packages"))

    if PackageVersion.query.filter_by(package_id=package.id, version=version).first():
        flash("هذا الإصدار موجود مسبقاً", "error")
        return redirect(url_for("owner.owner_packages"))

    new_pv = PackageVersion(
        package_id=package.id,
        version=version,
        changelog=changelog or None,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(new_pv)
    db.session.flush()

    if copy_from_latest:
        latest = (
            PackageVersion.query.filter_by(package_id=package.id)
            .filter(PackageVersion.id != new_pv.id)
            .order_by(PackageVersion.published_at.desc())
            .first()
        )
        if latest:
            for ent in latest.entitlements:
                db.session.add(PackageVersionEntitlement(
                    package_version_id=new_pv.id,
                    module_name=ent.module_name,
                    capability_key=ent.capability_key,
                ))
            for lim in latest.limits:
                db.session.add(PackageVersionLimit(
                    package_version_id=new_pv.id,
                    limit_key=lim.limit_key,
                    limit_value=lim.limit_value,
                ))
            for prc in latest.pricing:
                db.session.add(PackageVersionPricing(
                    package_version_id=new_pv.id,
                    billing_type=prc.billing_type,
                    price=prc.price,
                    setup_fee=prc.setup_fee,
                    currency=prc.currency,
                ))

    db.session.commit()
    _log_action("CREATE_PACKAGE_VERSION", "package_version", new_pv.id, f"package={package.slug}, version={version}")
    flash("تم إنشاء الإصدار بنجاح", "success")
    return redirect(url_for("owner.owner_packages"))


@owner_bp.route("/packages/versions/<int:version_id>/deprecate", methods=["POST"])
@login_required
@owner_required
def owner_deprecate_package_version(version_id):
    """Deprecate a package version."""
    pv = PackageVersion.query.get_or_404(version_id)
    pv.is_deprecated = True
    db.session.commit()
    _log_action("DEPRECATE_PACKAGE_VERSION", "package_version", pv.id,
                f"package={pv.package.slug}, version={pv.version}")
    flash("تم تعطيل الإصدار", "warning")
    return redirect(url_for("owner.owner_packages"))


@owner_bp.route("/subscriptions")
@login_required
@owner_required
def owner_subscriptions():
    """Subscription Manager UI (UX0-002)."""
    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    package_versions = PackageVersion.query.join(Package).order_by(Package.name, PackageVersion.version).all()
    return render_template(
        "owner/subscriptions.html",
        tenants=tenants,
        package_versions=package_versions,
        SubscriptionLineType=SubscriptionLineType,
        SubscriptionLineStatus=SubscriptionLineStatus,
    )


@owner_bp.route("/subscriptions/<int:tenant_id>/upgrade", methods=["POST"])
@login_required
@owner_required
def owner_upgrade_subscription(tenant_id):
    """Upgrade tenant to a new base package version."""
    version_id = request.form.get("package_version_id", type=int)
    billing_type = request.form.get("billing_type", "monthly").strip()
    if not version_id:
        flash("يجب اختيار Package Version", "error")
        return redirect(url_for("owner.owner_subscriptions"))
    try:
        TenantProvisioningService.upgrade_tenant(
            tenant_id, version_id, billing_type, performed_by_user_id=current_user.id
        )
        flash("تم ترقية الاشتراك بنجاح", "success")
    except Exception as e:
        flash(f"فشل الترقية: {e}", "error")
    return redirect(url_for("owner.owner_subscriptions"))


@owner_bp.route("/subscriptions/<int:tenant_id>/addon", methods=["POST"])
@login_required
@owner_required
def owner_add_addon(tenant_id):
    """Add an add-on subscription line to a tenant."""
    version_id = request.form.get("package_version_id", type=int)
    billing_type = request.form.get("billing_type", "monthly").strip()
    if not version_id:
        flash("يجب اختيار Package Version", "error")
        return redirect(url_for("owner.owner_subscriptions"))
    try:
        TenantProvisioningService.add_addon(
            tenant_id, version_id, billing_type, performed_by_user_id=current_user.id
        )
        flash("تمت إضافة الإضافة بنجاح", "success")
    except Exception as e:
        flash(f"فشل إضافة الإضافة: {e}", "error")
    return redirect(url_for("owner.owner_subscriptions"))


@owner_bp.route("/subscriptions/<int:tenant_id>/renew", methods=["POST"])
@login_required
@owner_required
def owner_renew_subscription(tenant_id):
    """Renew the active base line for a tenant."""
    line = (
        SubscriptionLine.query.filter_by(
            tenant_id=tenant_id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
        )
        .order_by(SubscriptionLine.effective_from.desc())
        .first()
    )
    if not line:
        flash("لا يوجد اشتراك أساسي نشط للتجديد", "error")
        return redirect(url_for("owner.owner_subscriptions"))
    try:
        TenantProvisioningService.renew_base_line(line.id, periods=1, performed_by_user_id=current_user.id)
        flash("تم تجديد الاشتراك بنجاح", "success")
    except Exception as e:
        flash(f"فشل التجديد: {e}", "error")
    return redirect(url_for("owner.owner_subscriptions"))


@owner_bp.route("/subscriptions/<int:tenant_id>/cancel", methods=["POST"])
@login_required
@owner_required
def owner_cancel_subscription(tenant_id):
    """Cancel a tenant subscription."""
    try:
        TenantProvisioningService.cancel_tenant(tenant_id, performed_by_user_id=current_user.id)
        flash("تم إلغاء الاشتراك بنجاح", "warning")
    except Exception as e:
        flash(f"فشل الإلغاء: {e}", "error")
    return redirect(url_for("owner.owner_subscriptions"))


@owner_bp.route("/provision", methods=["GET", "POST"])
@login_required
@owner_required
def owner_provision():
    """Tenant Provisioning UI (UX0-003)."""
    package_versions = PackageVersion.query.join(Package).filter(Package.is_active == True).order_by(Package.name).all()

    if request.method == "POST":
        slug = request.form.get("slug", "").strip()
        name = request.form.get("name", "").strip()
        contact_email = request.form.get("contact_email", "").strip()
        package_version_id = request.form.get("package_version_id", type=int)
        billing_type = request.form.get("billing_type", "monthly").strip()
        product_profile_code = request.form.get("product_profile_code", "").strip() or None

        if not all([slug, name, contact_email, package_version_id]):
            flash("جميع الحقول الأساسية مطلوبة", "error")
            return redirect(url_for("owner.owner_provision"))

        try:
            tenant = TenantProvisioningService.provision_tenant(
                slug=slug,
                name=name,
                contact_email=contact_email,
                package_version_id=package_version_id,
                billing_type=billing_type,
                product_profile_code=product_profile_code,
                performed_by_user_id=current_user.id,
            )
            _log_action("PROVISION_TENANT", "tenant", tenant.id, f"slug={slug}")
            flash(f"تم إنشاء العميل {tenant.name} بنجاح", "success")
            return redirect(url_for("owner.owner_tenant_detail", tenant_id=tenant.id))
        except Exception as e:
            flash(f"فشل إنشاء العميل: {e}", "error")
            return redirect(url_for("owner.owner_provision"))

    return render_template(
        "owner/provision.html",
        package_versions=package_versions,
        profiles=list(ProductProfile),
    )


@owner_bp.route("/tenant-usage/<int:tenant_id>")
@login_required
@owner_required
def owner_tenant_usage(tenant_id):
    """UX0-006: owner view of a tenant's resource usage dashboard."""
    tenant = Tenant.query.get_or_404(tenant_id)
    latest = (
        ResourceUsage.query.filter_by(tenant_id=tenant_id)
        .order_by(ResourceUsage.recorded_at.desc())
        .first()
    )
    if not latest:
        latest = ResourceUsage.record_snapshot(tenant_id)

    base_line = (
        SubscriptionLine.query.filter_by(
            tenant_id=tenant_id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
        )
        .order_by(SubscriptionLine.effective_from.desc())
        .first()
    )

    limits = {}
    if base_line:
        for lim in base_line.package_version.limits:
            limits[lim.limit_key] = lim.limit_value
    else:
        bundle = get_bundle_for_profile(tenant.product_profile_code or "")
        if bundle:
            limits = {
                "max_users": bundle.max_users,
                "max_patients": bundle.max_patients,
                "storage_gb": bundle.storage_gb,
                "api_calls_per_month": bundle.api_calls_per_month,
            }

    snapshots = (
        ResourceUsage.query.filter_by(tenant_id=tenant_id)
        .order_by(ResourceUsage.recorded_at.desc())
        .limit(30)
        .all()
    )

    return render_template(
        "owner/tenant_usage.html",
        tenant=tenant,
        latest=latest,
        limits=limits,
        snapshots=snapshots,
    )

