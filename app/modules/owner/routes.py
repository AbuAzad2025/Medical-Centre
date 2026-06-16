"""
Owner Blueprint — platform admin routes (SaaS control plane)
"""
from datetime import date, datetime, timedelta, timezone
from flask import current_app, render_template, render_template_string, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.modules.owner import owner_bp
from app.extensions import db
from app.core.tenant.models import (
    Tenant, SubscriptionPlan, TenantSubscriptionHistory,
    SupportTicket, PlatformAuditLog, ResourceUsage, NotificationRule
)
from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module, get_active_modules_for_tenant
from app.shared.enums import TenantStatus, SubscriptionType, StorageMode, ProductProfile


def _owner_guard():
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))
    return None


def _owner_api_guard():
    if not current_user.is_authenticated:
        return jsonify({"error": "authentication_required"}), 401
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        return jsonify({"error": "owner_access_required"}), 403
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        return jsonify({"error": "saas_mode_disabled"}), 404
    return None


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


@owner_bp.route("/dashboard")
@login_required
def owner_dashboard():
    """لوحة تحكم المنصة — SaaS metrics"""
    guard = _owner_guard()
    if guard:
        return guard

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
        months.append(month_start.strftime('%Y-%m'))
        # Count tenants created up to this month
        count = sum(1 for t in all_tenants if t.created_at and t.created_at.date() <= month_start)
        tenant_growth.append(count)
        # MRR at that month (simplified: current active with created before)
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
        churn_spark.append(max(0, expired_count - i))  # synthetic sparkline
        user_spark.append(max(0, total_users_all - i * 2))

    # Status distribution for chart
    status_labels = ['نشط', 'معلق', 'منتهي', 'موقوف', 'تجريبي']
    status_data = [
        sum(1 for t in all_tenants if t.status == TenantStatus.ACTIVE),
        sum(1 for t in all_tenants if t.status == TenantStatus.PENDING),
        sum(1 for t in all_tenants if t.status == TenantStatus.EXPIRED),
        sum(1 for t in all_tenants if t.status == TenantStatus.SUSPENDED),
        sum(1 for t in all_tenants if t.status == TenantStatus.PENDING),
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
def owner_create_tenant():
    guard = _owner_guard()
    if guard:
        return guard

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
                product_profile_code=ProductProfile(profile_code) if profile_code else None,
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
            flash('تم إنشاء العميل بنجاح', 'success')
            return redirect(url_for('owner.owner_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    from app.shared.enums import ProductProfile
    return render_template('owner/create_tenant.html', plans=plans, profiles=list(ProductProfile))


@owner_bp.route("/tenants/<int:tenant_id>")
@login_required
def owner_tenant_detail(tenant_id):
    guard = _owner_guard()
    if guard:
        return guard

    tenant = Tenant.query.get_or_404(tenant_id)
    active_modules = get_active_modules_for_tenant(tenant_id)
    from app.core.tenant.models import TenantFeatureFlag
    feature_flags = TenantFeatureFlag.query.filter_by(tenant_id=tenant_id, is_enabled=True).all()
    from app.core.module.registry import MODULE_REGISTRY, get_all_module_names
    all_modules = get_all_module_names()
    return render_template('owner/tenant_detail.html',
                           tenant=tenant,
                           active_modules=list(active_modules),
                           feature_flags=feature_flags,
                           all_modules=all_modules)


@owner_bp.route("/tenants/<int:tenant_id>/renew")
@login_required
def owner_renew_tenant(tenant_id):
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_suspend_tenant(tenant_id):
    guard = _owner_guard()
    if guard:
        return guard

    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()
        _log_action('SUSPEND_TENANT', 'tenant', tenant_id, f"Suspended tenant {tenant.name}")
        flash('تم إيقاف العميل', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/tenants/<int:tenant_id>/activate")
@login_required
def owner_activate_tenant(tenant_id):
    guard = _owner_guard()
    if guard:
        return guard

    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.ACTIVE
        db.session.commit()
        _log_action('ACTIVATE_TENANT', 'tenant', tenant_id, f"Activated tenant {tenant.name}")
        flash('تم تفعيل العميل', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/plans")
@login_required
def owner_plans():
    guard = _owner_guard()
    if guard:
        return guard

    plans = SubscriptionPlan.query.all()
    return render_template('owner/plans.html', plans=plans)


@owner_bp.route("/announcements", methods=["GET", "POST"])
@login_required
def owner_announcements():
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_support_tickets():
    guard = _owner_guard()
    if guard:
        return guard

    status_filter = request.args.get('status', '')
    q = SupportTicket.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    tickets = q.order_by(SupportTicket.created_at.desc()).limit(50).all()
    return render_template('owner/support_tickets.html', tickets=tickets, status_filter=status_filter)


@owner_bp.route("/support-tickets/<int:ticket_id>/update", methods=["POST"])
@login_required
def owner_update_ticket(ticket_id):
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_audit_logs():
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_resource_usage():
    guard = _owner_guard()
    if guard:
        return guard

    usages = ResourceUsage.query.order_by(ResourceUsage.recorded_at.desc()).limit(100).all()
    return render_template('owner/resource_usage.html', usages=usages)


# ─────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────
@owner_bp.route("/notifications")
@login_required
def owner_notifications():
    guard = _owner_guard()
    if guard:
        return guard

    rules = NotificationRule.query.order_by(NotificationRule.created_at.desc()).all()
    return render_template('owner/notifications.html', rules=rules)


@owner_bp.route("/notifications/create", methods=["POST"])
@login_required
def owner_create_notification():
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_branding():
    guard = _owner_guard()
    if guard:
        return guard

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
def owner_webhooks():
    guard = _owner_guard()
    if guard:
        return guard

    webhooks = []
    api_keys = []
    tenants = Tenant.query.all()
    try:
        from models.system_config import SystemConfig
        cfg_wh = SystemConfig.query.filter_by(config_key='owner_webhooks').first()
        if cfg_wh and cfg_wh.config_value:
            import json
            webhooks = json.loads(cfg_wh.config_value)
        cfg_key = SystemConfig.query.filter_by(config_key='owner_api_keys').first()
        if cfg_key and cfg_key.config_value:
            import json
            api_keys_raw = json.loads(cfg_key.config_value)
            api_keys = []
            for k in api_keys_raw:
                tenant = Tenant.query.get(k.get('tenant_id'))
                api_keys.append({'name': k.get('name'), 'scopes': k.get('scopes'), 'tenant': tenant})
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

    return render_template('owner/webhooks.html', webhooks=webhooks, api_keys=api_keys, tenants=tenants)


@owner_bp.route("/api-keys", methods=["POST"])
@login_required
def owner_api_keys():
    guard = _owner_guard()
    if guard:
        return guard

    try:
        import secrets
        new_key = {
            'id': int(datetime.now(timezone.utc).timestamp()),
            'tenant_id': int(request.form.get('tenant_id', 0)),
            'name': request.form.get('name', '').strip(),
            'key': 'ak_' + secrets.token_urlsafe(32),
            'scopes': request.form.get('scopes', 'read').strip(),
            'created_at': datetime.now(timezone.utc).isoformat(),
            'created_by': current_user.id,
        }
        from models.system_config import SystemConfig
        cfg = SystemConfig.query.filter_by(config_key='owner_api_keys').first()
        import json
        keys = []
        if cfg and cfg.config_value:
            keys = json.loads(cfg.config_value)
        keys.insert(0, new_key)
        keys = keys[:100]
        if cfg:
            cfg.config_value = json.dumps(keys)
            cfg.updated_by = current_user.id
        else:
            cfg = SystemConfig(config_key='owner_api_keys', config_value=json.dumps(keys), config_type='json', category='owner', created_by=current_user.id, updated_by=current_user.id)
            db.session.add(cfg)
        db.session.commit()
        _log_action('CREATE_API_KEY', 'system', new_key['tenant_id'], new_key['name'])
        flash(f"تم إنشاء API Key: {new_key['key'][:20]}...", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_webhooks'))


# ─────────────────────────────────────────────
# Existing API routes preserved
# ─────────────────────────────────────────────
@owner_bp.route("/api/tenants", methods=["GET"])
@login_required
def api_tenants():
    guard = _owner_api_guard()
    if guard:
        return guard
    tenants = Tenant.query.all()
    return jsonify([{"id": t.id, "name": t.name, "slug": t.slug, "status": str(t.status)} for t in tenants])


@owner_bp.route("/api/tenants/<int:tenant_id>/modules", methods=["GET"])
@login_required
def api_tenant_modules(tenant_id):
    guard = _owner_api_guard()
    if guard:
        return guard
    active = get_active_modules_for_tenant(tenant_id)
    return jsonify({"tenant_id": tenant_id, "active_modules": list(active)})


@owner_bp.route("/api/tenants/<int:tenant_id>/modules/<module_name>/activate", methods=["POST"])
@login_required
def api_activate_module(tenant_id, module_name):
    guard = _owner_api_guard()
    if guard:
        return guard
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
    return jsonify({"status": "activated", "module": module_name})


@owner_bp.route("/api/tenants/<int:tenant_id>/modules/<module_name>/deactivate", methods=["POST"])
@login_required
def api_deactivate_module(tenant_id, module_name):
    guard = _owner_api_guard()
    if guard:
        return guard
    tm = TenantModule.query.filter_by(tenant_id=tenant_id, module_name=module_name).first()
    if tm:
        tm.is_active = False
        tm.deactivated_at = datetime.now(timezone.utc)
        db.session.commit()
        _log_action('DEACTIVATE_MODULE', 'module', tenant_id, f"Deactivated {module_name}")
    return jsonify({"status": "deactivated", "module": module_name})


@owner_bp.route("/api/tenants/<int:tenant_id>/profile", methods=["POST"])
@login_required
def api_update_profile(tenant_id):
    guard = _owner_api_guard()
    if guard:
        return guard
    tenant = Tenant.query.get_or_404(tenant_id)
    profile_code = request.json.get("product_profile") or request.form.get("product_profile")
    from app.shared.enums import ProductProfile
    if profile_code and profile_code not in ProductProfile.__members__.values() and profile_code not in [e.value for e in ProductProfile]:
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
def api_toggle_feature(tenant_id, feature_key):
    guard = _owner_api_guard()
    if guard:
        return guard
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
