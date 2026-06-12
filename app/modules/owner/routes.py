"""
Owner Blueprint — platform admin routes (SaaS control plane)
"""
from datetime import date, datetime, timezone
from flask import render_template, render_template_string, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.modules.owner import owner_bp
from app.extensions import db
from app.core.tenant.models import Tenant, SubscriptionPlan, TenantSubscriptionHistory
from app.core.module.models import TenantModule
from app.core.module.validators import can_activate_module, get_active_modules_for_tenant
from app.shared.enums import TenantStatus, SubscriptionType, StorageMode


@owner_bp.route("/dashboard")
@login_required
def owner_dashboard():
    """لوحة تحكم المنصة — SaaS metrics"""
    # Only super_admin can access owner dashboard
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    tenants = Tenant.query.order_by(Tenant.created_at.desc()).all()
    plans = SubscriptionPlan.query.all()

    tenant_count = len(tenants)
    active_today = sum(1 for t in tenants if t.is_active_and_paid())
    expired_count = sum(1 for t in tenants if t.status == TenantStatus.EXPIRED)
    suspended_count = sum(1 for t in tenants if t.status == TenantStatus.SUSPENDED)

    # MRR/ARR calculation (simplified)
    mrr = 0.0
    for t in tenants:
        if t.is_active_and_paid() and t.plan:
            price = float(t.plan.base_price or 0)
            if t.subscription_type == SubscriptionType.YEARLY:
                price = price / 12.0
            elif t.subscription_type == SubscriptionType.PERPETUAL:
                price = 0  # Perpetual = one-time
            mrr += price
    arr = mrr * 12

    # Churn rate (expired / total)
    churn_rate = round((expired_count / max(tenant_count, 1)) * 100, 1)

    # Users across all tenants
    total_users_all = sum(len(t.users) for t in tenants)
    avg_users_per_tenant = total_users_all / max(tenant_count, 1)

    # Filter by status
    filter_status = request.args.get('status', '')
    if filter_status:
        tenants = [t for t in tenants if t.status.value == filter_status]

    # Alerts
    alerts = []
    for t in tenants:
        if t.status == TenantStatus.EXPIRED:
            alerts.append({'type': 'اشتراك', 'color': 'danger', 'message': f'انتهى اشتراك {t.name}', 'tenant': t.name})
        elif t.grace_period_end and date.today() > t.grace_period_end and t.status == TenantStatus.ACTIVE:
            alerts.append({'type': 'سماح', 'color': 'warning', 'message': f'انتهت فترة سماح {t.name}', 'tenant': t.name})
    if suspended_count:
        alerts.append({'type': 'عميل', 'color': 'secondary', 'message': f'{suspended_count} عميل موقوف', 'tenant': None})

    # Announcements (mock model for now, using a simple list in memory or from config)
    # We will render from a simple in-memory list if model doesn't exist
    announcements = []
    try:
        from models.system_config import SystemConfig
        cfg = SystemConfig.query.filter_by(config_key='owner_announcements').first()
        if cfg and cfg.config_value:
            import json
            announcements = json.loads(cfg.config_value)
    except Exception:
        announcements = []

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
                           tenants=tenants,
                           plans=plans,
                           alerts=alerts,
                           filter_status=filter_status,
                           announcements=announcements,
                           currency='SAR')


@owner_bp.route("/tenants/create", methods=["GET", "POST"])
@login_required
def owner_create_tenant():
    """إنشاء عميل جديد"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    plans = SubscriptionPlan.query.all()
    if request.method == 'POST':
        try:
            t = Tenant(
                slug=request.form.get('slug', '').strip(),
                name=request.form.get('name', '').strip(),
                name_ar=request.form.get('name_ar', '').strip() or None,
                domain=request.form.get('domain', '').strip() or None,
                subdomain=request.form.get('subdomain', '').strip() or None,
                contact_email=request.form.get('contact_email', '').strip(),
                contact_phone=request.form.get('contact_phone', '').strip() or None,
                tax_number=request.form.get('tax_number', '').strip() or None,
                plan_id=int(request.form.get('plan_id')) if request.form.get('plan_id') else None,
                subscription_type=SubscriptionType(request.form.get('subscription_type', 'monthly')),
                subscription_start=date.today(),
                subscription_end=datetime.strptime(request.form.get('subscription_end'), '%Y-%m-%d').date() if request.form.get('subscription_end') else None,
                grace_period_end=datetime.strptime(request.form.get('grace_period_end'), '%Y-%m-%d').date() if request.form.get('grace_period_end') else None,
                storage_mode=StorageMode(request.form.get('storage_mode', 'local')),
                status=TenantStatus.ACTIVE
            )
            db.session.add(t)
            db.session.commit()
            flash('تم إنشاء العميل بنجاح', 'success')
            return redirect(url_for('owner.owner_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    return render_template('owner/create_tenant.html', plans=plans)


@owner_bp.route("/tenants/<int:tenant_id>")
@login_required
def owner_tenant_detail(tenant_id):
    """تفاصيل العميل"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    tenant = Tenant.query.get_or_404(tenant_id)
    active_modules = get_active_modules_for_tenant(tenant_id)
    return render_template('owner/tenant_detail.html',
                           tenant=tenant,
                           active_modules=list(active_modules))


@owner_bp.route("/tenants/<int:tenant_id>/renew")
@login_required
def owner_renew_tenant(tenant_id):
    """تجديد اشتراك العميل"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

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

        # Log history
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
        flash('تم تجديد الاشتراك', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_tenant_detail', tenant_id=tenant_id))


@owner_bp.route("/tenants/<int:tenant_id>/suspend")
@login_required
def owner_suspend_tenant(tenant_id):
    """إيقاف عميل"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.SUSPENDED
        db.session.commit()
        flash('تم إيقاف العميل', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/tenants/<int:tenant_id>/activate")
@login_required
def owner_activate_tenant(tenant_id):
    """تفعيل عميل موقوف"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    tenant = Tenant.query.get_or_404(tenant_id)
    try:
        tenant.status = TenantStatus.ACTIVE
        db.session.commit()
        flash('تم تفعيل العميل', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'خطأ: {e}', 'error')
    return redirect(url_for('owner.owner_dashboard'))


@owner_bp.route("/plans")
@login_required
def owner_plans():
    """إدارة خطط الاشتراك"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

    plans = SubscriptionPlan.query.all()
    return render_template('owner/plans.html', plans=plans)


@owner_bp.route("/announcements", methods=["GET", "POST"])
@login_required
def owner_announcements():
    """إعلانات المنصة"""
    if current_user.role not in ('super_admin', 'admin', 'owner'):
        flash('غير مصرح', 'error')
        return redirect(url_for('main.dashboard'))

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
            # Keep only last 50
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
            flash('تم إرسال الإعلان', 'success')
            return redirect(url_for('owner.owner_announcements'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {e}', 'error')

    return render_template('owner/announcements.html', announcements=announcements)


# Existing API routes preserved
@owner_bp.route("/api/tenants", methods=["GET"])
def api_tenants():
    tenants = Tenant.query.all()
    return jsonify([{"id": t.id, "name": t.name, "slug": t.slug, "status": str(t.status)} for t in tenants])


@owner_bp.route("/api/tenants/<int:tenant_id>/modules", methods=["GET"])
def api_tenant_modules(tenant_id):
    active = get_active_modules_for_tenant(tenant_id)
    return jsonify({"tenant_id": tenant_id, "active_modules": list(active)})


@owner_bp.route("/api/tenants/<int:tenant_id>/modules/<module_name>/activate", methods=["POST"])
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
    return jsonify({"status": "activated", "module": module_name})
