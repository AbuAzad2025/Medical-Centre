"""Stripe billing webhook routes."""

from flask import Blueprint, jsonify, request

from services.stripe_subscription_service import StripeSubscriptionService, StripeWebhookError

saas_billing_bp = Blueprint('saas_billing', __name__)


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
