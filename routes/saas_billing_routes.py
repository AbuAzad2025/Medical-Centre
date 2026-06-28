"""Stripe billing webhook and self-service outbound billing routes."""

from flask import Blueprint, g, jsonify, request
from flask_login import current_user, login_required

from services.stripe_billing_service import StripeBillingError, StripeBillingService
from services.stripe_subscription_service import StripeSubscriptionService, StripeWebhookError

saas_billing_bp = Blueprint('saas_billing', __name__)


def _tenant_id_from_context() -> int:
    tenant = getattr(g, 'current_tenant', None)
    if tenant is None:
        raise StripeBillingError('tenant_context_required')
    return tenant.id


@saas_billing_bp.route('/api/billing/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """Ingest Stripe subscription lifecycle events."""
    signature = request.headers.get('Stripe-Signature', '')
    try:
        result = StripeSubscriptionService.ingest_webhook(request.get_data(), signature)
        return jsonify({'received': True, **result}), 200
    except StripeWebhookError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'webhook_processing_failed'}), 500


@saas_billing_bp.route('/api/billing/checkout', methods=['POST'])
@login_required
def create_checkout():
    """Start a Stripe Checkout session for subscription purchase."""
    data = request.get_json(silent=True) or {}
    try:
        tenant_id = _tenant_id_from_context()
        result = StripeBillingService.create_checkout_session(
            tenant_id,
            int(data.get('package_version_id')),
            (data.get('billing_type') or 'monthly').strip().lower(),
            success_url=data.get('success_url') or request.host_url.rstrip('/') + '/finance/dashboard',
            cancel_url=data.get('cancel_url') or request.host_url.rstrip('/') + '/finance/dashboard',
        )
        return jsonify(result), 201
    except (StripeBillingError, ValueError, TypeError) as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'checkout_failed'}), 500


@saas_billing_bp.route('/api/billing/portal', methods=['POST'])
@login_required
def billing_portal():
    """Open Stripe customer portal for card updates."""
    data = request.get_json(silent=True) or {}
    try:
        tenant_id = _tenant_id_from_context()
        result = StripeBillingService.create_billing_portal_session(
            tenant_id,
            return_url=data.get('return_url') or request.host_url.rstrip('/') + '/finance/dashboard',
        )
        return jsonify(result), 200
    except StripeBillingError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'portal_failed'}), 500


@saas_billing_bp.route('/api/billing/subscription/cancel', methods=['POST'])
@login_required
def cancel_subscription():
    """Cancel the tenant's Stripe subscription."""
    data = request.get_json(silent=True) or {}
    try:
        tenant_id = _tenant_id_from_context()
        result = StripeBillingService.cancel_subscription(
            tenant_id,
            at_period_end=data.get('at_period_end', True),
        )
        return jsonify(result), 200
    except StripeBillingError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'cancel_failed'}), 500


@saas_billing_bp.route('/api/billing/subscription/change-plan', methods=['POST'])
@login_required
def change_plan():
    """Upgrade or downgrade the active subscription package."""
    data = request.get_json(silent=True) or {}
    try:
        tenant_id = _tenant_id_from_context()
        result = StripeBillingService.change_plan(
            tenant_id,
            int(data.get('package_version_id')),
            (data.get('billing_type') or 'monthly').strip().lower(),
            performed_by_user_id=getattr(current_user, 'id', None),
        )
        return jsonify(result), 200
    except (StripeBillingError, ValueError, TypeError) as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception:
        return jsonify({'error': 'change_plan_failed'}), 500
