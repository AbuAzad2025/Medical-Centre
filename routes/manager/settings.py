from routes.manager import manager_bp

from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from app.core.platform_capabilities import require_platform_capability
from app_factory import db
from app.core.tenant.models import Tenant
import logging
import json

logger = logging.getLogger(__name__)


@manager_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def manager_settings():
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({'success': False, 'message': 'طلب غير صالح'}), 400

        data = request.get_json(force=True)
        tenant_id = getattr(current_user, 'tenant_id', None)
        if not tenant_id:
            return jsonify({'success': False, 'message': 'لا يوجد تينانت'}), 400

        tenant = Tenant.query.get(tenant_id)
        if not tenant:
            return jsonify({'success': False, 'message': 'التينانت غير موجود'}), 404

        settings = dict(tenant.settings or {})

        # General settings
        if 'general' in data:
            settings['general'] = data['general']

        # SMS settings
        if 'sms' in data:
            settings['sms'] = data['sms']

        # Lab settings
        if 'lab' in data:
            settings['lab'] = data['lab']

        # Radiology settings
        if 'radiology' in data:
            settings['radiology'] = data['radiology']

        tenant.settings = settings
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'})

    # GET: load current settings
    tenant_id = getattr(current_user, 'tenant_id', None)
    tenant = Tenant.query.get(tenant_id) if tenant_id else None
    settings = tenant.settings if tenant and tenant.settings else {}

    return render_template('manager/settings.html', settings=settings, tenant=tenant)


@manager_bp.route('/settings/test-sms', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
@require_platform_capability('sms_live')
def manager_test_sms():
    try:
        data = request.get_json(force=True) or {}
        phone_number = data.get('phone_number', '')
        if not phone_number:
            return jsonify({'success': False, 'message': 'يرجى إدخال رقم الهاتف'}), 400

        tenant_id = getattr(current_user, 'tenant_id', None)
        tenant = Tenant.query.get(tenant_id) if tenant_id else None

        from services.sms_service import SMSService
        result = SMSService.send_sms(
            phone=phone_number,
            message='هذه رسالة تجريبية من إعدادات المركز',
            tenant=tenant
        )
        if result.get('success'):
            return jsonify({'success': True, 'message': 'تم إرسال الرسالة التجريبية بنجاح'}), 200
        else:
            return jsonify({'success': False, 'message': result.get('error', 'فشل الإرسال')}), 500
    except Exception as e:
        logging.error(f"Manager test SMS error: {str(e)}")
        return jsonify({'success': False, 'message': f'خطأ: {str(e)}'}), 500
