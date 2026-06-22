"""
Tenant subscription self-service — UX0-004 / UX0-005
"""
from datetime import date

from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from app.extensions import db
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import Package, PackageVersion, SubscriptionLine, SubscriptionLineStatus, SubscriptionLineType
from app.core.tenant.models import Tenant
from utils.decorators import super_admin_required

from . import super_admin_bp


def _current_tenant() -> Tenant:
    return Tenant.query.get_or_404(current_user.tenant_id)


def _active_base_line(tenant: Tenant) -> SubscriptionLine | None:
    return (
        SubscriptionLine.query.filter_by(
            tenant_id=tenant.id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
        )
        .order_by(SubscriptionLine.effective_from.desc())
        .first()
    )


@super_admin_bp.route("/subscription-status")
@login_required
@super_admin_required
def subscription_status():
    """UX0-004: widget showing subscription status for tenant users."""
    tenant = _current_tenant()
    base_line = _active_base_line(tenant)

    status_label = tenant.status.value
    status_class = "secondary"
    if tenant.status.value in ("active", "trial"):
        status_class = "success"
    elif tenant.status.value == "suspended":
        status_class = "warning"
    elif tenant.status.value in ("expired", "cancelled"):
        status_class = "danger"

    in_grace = bool(
        tenant.grace_period_end and date.today() <= tenant.grace_period_end
    )

    return render_template(
        "tenant/subscription_status.html",
        tenant=tenant,
        base_line=base_line,
        status_label=status_label,
        status_class=status_class,
        in_grace=in_grace,
    )


@super_admin_bp.route("/change-plan", methods=["GET", "POST"])
@login_required
@super_admin_required
def change_plan():
    """UX0-005: self-service upgrade/downgrade for tenant admin."""
    tenant = _current_tenant()
    base_line = _active_base_line(tenant)

    if request.method == "POST":
        version_id = request.form.get("package_version_id", type=int)
        action = request.form.get("action", "upgrade").strip()
        billing_type = request.form.get("billing_type", "monthly").strip()
        if not version_id:
            flash("يجب اختيار خطة", "error")
            return redirect(url_for("super_admin.change_plan"))

        try:
            if action == "downgrade":
                TenantProvisioningService.downgrade_tenant(
                    tenant.id,
                    version_id,
                    billing_type,
                    performed_by_user_id=current_user.id,
                )
                flash("تم تخفيض الخطة بنجاح", "success")
            else:
                TenantProvisioningService.upgrade_tenant(
                    tenant.id,
                    version_id,
                    billing_type,
                    performed_by_user_id=current_user.id,
                )
                flash("تم ترقية الخطة بنجاح", "success")
        except Exception as e:
            flash(f"فشل تغيير الخطة: {e}", "error")
        return redirect(url_for("super_admin.change_plan"))

    available = (
        PackageVersion.query.join(PackageVersion.package)
        .filter(Package.is_active == True)
        .filter(PackageVersion.is_deprecated == False)
        .order_by(Package.name, PackageVersion.version)
        .all()
    )

    return render_template(
        "tenant/change_plan.html",
        tenant=tenant,
        base_line=base_line,
        available_versions=available,
    )
