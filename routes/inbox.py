"""Unified work inbox — UX1-003."""

from flask import Blueprint, g, render_template, request
from flask_login import login_required, current_user

from services.work_inbox_service import WorkInboxService

inbox_bp = Blueprint('inbox', __name__)


def _resolve_is_entitled():
    from app.core.saas.resolver import EntitlementResolver
    tenant = getattr(g, 'current_tenant', None)
    if tenant is None:
        return lambda _k: True
    return lambda cap: EntitlementResolver.is_entitled(tenant.id, cap)


@inbox_bp.route('/inbox')
@login_required
def dashboard():
    """لوحة العمل الموحدة — تجمع المهام المعلّقة حسب الدور وحالة الزيارة."""
    is_entitled = _resolve_is_entitled()
    filter_type = (request.args.get('type') or '').strip().lower()
    items = WorkInboxService.get_inbox_items(current_user, is_entitled=is_entitled)
    if filter_type:
        items = [i for i in items if i.get('item_type') == filter_type]
    type_counts = WorkInboxService.get_type_counts(items)
    return render_template(
        'inbox/dashboard.html',
        items=items,
        user_role=current_user.role,
        filter_type=filter_type,
        type_counts=type_counts,
    )
