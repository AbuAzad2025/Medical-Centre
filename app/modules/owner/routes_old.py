"""
Owner Blueprint — platform admin routes
"""
from flask import render_template_string, jsonify, request
from app.modules.owner import owner_bp
from app.core.tenant.models import Tenant, SubscriptionPlan
from app.core.tenant.service import TenantContextService
from app.core.module.validators import can_activate_module, get_active_modules_for_tenant
from app.extensions import db

DASHBOARD_HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="utf-8">
    <title>لوحة تحكم المالك</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-5">
    <h1 class="mb-4">لوحة تحكم المنصة (Owner)</h1>
    <div class="row g-4">
        <div class="col-md-4">
            <div class="card text-white bg-primary">
                <div class="card-body">
                    <h5 class="card-title">الشركات (Tenants)</h5>
                    <p class="card-text display-6">{{ tenant_count }}</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card text-white bg-success">
                <div class="card-body">
                    <h5 class="card-title">الخطط</h5>
                    <p class="card-text display-6">{{ plan_count }}</p>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card text-white bg-warning">
                <div class="card-body">
                    <h5 class="card-title">نشطة اليوم</h5>
                    <p class="card-text display-6">{{ active_today }}</p>
                </div>
            </div>
        </div>
    </div>
    <hr>
    <h3 class="mt-4">قائمة الشركات</h3>
    <table class="table table-striped">
        <thead><tr><th>الاسم</th><th>الرابط</th><th>الحالة</th><th>الخطة</th><th>ينتهي</th></tr></thead>
        <tbody>
        {% for t in tenants %}
        <tr>
            <td>{{ t.name }}</td>
            <td>{{ t.domain or t.subdomain or t.slug }}</td>
            <td>{{ t.status.value }}</td>
            <td>{{ t.plan.name if t.plan else '-' }}</td>
            <td>{{ t.subscription_end or '-' }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
</body>
</html>
"""


@owner_bp.route("/dashboard")
def owner_dashboard():
    tenants = Tenant.query.all()
    plans = SubscriptionPlan.query.all()
    return render_template_string(
        DASHBOARD_HTML,
        tenant_count=len(tenants),
        plan_count=len(plans),
        active_today=len([t for t in tenants if t.is_active_and_paid()]),
        tenants=tenants,
    )


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
    from app.core.module.models import TenantModule
    from datetime import datetime, timezone
    tm = TenantModule.query.filter_by(tenant_id=tenant_id, module_name=module_name).first()
    if not tm:
        tm = TenantModule(tenant_id=tenant_id, module_name=module_name)
        db.session.add(tm)
    tm.is_active = True
    tm.activated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"status": "activated", "module": module_name})
