"""
Tenant resource usage dashboard — UX0-006 (tenant view)
"""
from flask import render_template
from flask_login import login_required, current_user

from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus, SubscriptionLineType
from app.core.tenant.models import Tenant, ResourceUsage
from utils.decorators import super_admin_required

from . import super_admin_bp


def _tenant_usage_context(tenant_id: int):
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

    # Resolve limits from active subscription line first, then legacy bundle.
    limits = {}
    if base_line:
        for lim in base_line.package_version.limits:
            limits[lim.limit_key] = lim.limit_value
    else:
        from app.core.tenant.models import get_bundle_for_profile
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

    return {
        "tenant": tenant,
        "latest": latest,
        "limits": limits,
        "snapshots": snapshots,
    }


@super_admin_bp.route("/usage")
@login_required
@super_admin_required
def tenant_usage():
    """UX0-006: tenant admin view of resource usage."""
    ctx = _tenant_usage_context(current_user.tenant_id)
    return render_template("tenant/usage.html", **ctx)
