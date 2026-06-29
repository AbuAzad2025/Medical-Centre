"""Public SaaS onboarding API routes."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from app.core.rate_limiter import rate_limit
from app.core.saas.models import Package, PackageVersion, PackageVersionAvailability, PackageVersionAvailabilityStatus
from services.saas_registration_service import SaasRegistrationError, SaasRegistrationService

saas_bp = Blueprint('saas', __name__)


def _available_package_versions():
    return (
        PackageVersion.query.join(Package)
        .join(PackageVersionAvailability)
        .filter(
            Package.is_active == True,
            PackageVersionAvailability.availability_status == PackageVersionAvailabilityStatus.AVAILABLE,
        )
        .order_by(Package.name, PackageVersion.version)
        .all()
    )


@saas_bp.route('/saas/signup', methods=['GET', 'POST'])
@rate_limit(max_requests=20, window_seconds=300)
def signup_organization():
    """Public self-service signup for new healthcare organizations."""
    packages = _available_package_versions()
    if request.method == 'GET':
        return render_template('saas/signup.html', package_versions=packages)

    data = request.form
    pkg_raw = data.get('package_version_id')
    try:
        result = SaasRegistrationService.register_organization(
            slug=data.get('slug', ''),
            name=data.get('name', ''),
            contact_email=data.get('contact_email', ''),
            admin_username=data.get('admin_username', ''),
            admin_password=data.get('admin_password', ''),
            admin_full_name=data.get('admin_full_name', data.get('name', '')),
            package_version_id=int(pkg_raw) if pkg_raw else None,
            billing_type=(data.get('billing_type') or 'monthly').strip().lower(),
            product_profile_code=(data.get('product_profile_code') or '').strip() or None,
        )
        if result.checkout_url:
            return redirect(result.checkout_url)
        flash(f'تم إنشاء المنشأة {result.tenant.name} بنجاح. يمكنك تسجيل الدخول الآن.', 'success')
        return redirect(url_for('auth.login', tenant_slug=result.tenant.slug))
    except SaasRegistrationError as exc:
        flash(f'تعذر إكمال التسجيل: {exc}', 'error')
        return render_template('saas/signup.html', package_versions=packages), 400
    except Exception:
        flash('تعذر إكمال التسجيل حالياً. حاول لاحقاً.', 'error')
        return render_template('saas/signup.html', package_versions=packages), 500


@saas_bp.route('/api/saas/register', methods=['POST'])
@rate_limit(max_requests=10, window_seconds=300)
def register_organization():
    """Self-service tenant provisioning for new healthcare organizations."""
    data = request.get_json(silent=True) or {}
    try:
        result = SaasRegistrationService.register_organization(
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
        body = {
            'status': 'provisioned',
            'tenant': {
                'id': result.tenant.id,
                'slug': result.tenant.slug,
                'name': result.tenant.name,
                'status': getattr(result.tenant.status, 'value', result.tenant.status),
            },
            'admin': {
                'id': result.admin.id,
                'username': result.admin.username,
                'role': result.admin.role,
            },
            'login_path': f'/auth/login?tenant_slug={result.tenant.slug}',
            'signup_complete': True,
        }
        if result.checkout_url:
            body['checkout_url'] = result.checkout_url
            body['payment_required'] = True
        return jsonify(body), 201
    except SaasRegistrationError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'registration_failed'}), 500
