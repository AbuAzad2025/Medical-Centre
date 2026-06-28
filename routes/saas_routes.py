"""Public SaaS onboarding API routes."""

from flask import Blueprint, jsonify, request

from app.core.rate_limiter import rate_limit
from services.saas_registration_service import SaasRegistrationError, SaasRegistrationService

saas_bp = Blueprint('saas', __name__)


@saas_bp.route('/api/saas/register', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=300)
def register_organization():
  """Self-service tenant provisioning for new healthcare organizations."""
  data = request.get_json(silent=True) or {}
  try:
    tenant, admin = SaasRegistrationService.register_organization(
      slug=data.get('slug', ''),
      name=data.get('name', ''),
      contact_email=data.get('contact_email', ''),
      admin_username=data.get('admin_username', ''),
      admin_password=data.get('admin_password', ''),
      admin_full_name=data.get('admin_full_name', data.get('name', '')),
      package_version_id=data.get('package_version_id'),
      billing_type=(data.get('billing_type') or 'monthly').strip().lower(),
      product_profile_code=(data.get('product_profile_code') or '').strip() or None,
    )
    return jsonify({
      'status': 'provisioned',
      'tenant': {
        'id': tenant.id,
        'slug': tenant.slug,
        'name': tenant.name,
        'status': getattr(tenant.status, 'value', tenant.status),
      },
      'admin': {
        'id': admin.id,
        'username': admin.username,
        'role': admin.role,
      },
      'login_path': f'/auth/login?tenant_slug={tenant.slug}',
    }), 201
  except SaasRegistrationError as exc:
    return jsonify({'error': str(exc)}), 400
  except Exception:
    return jsonify({'error': 'registration_failed'}), 500
