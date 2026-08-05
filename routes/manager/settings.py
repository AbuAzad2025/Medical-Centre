import logging

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app.core.platform_capabilities import require_platform_capability
from app.core.tenant.models import Tenant
from app.extensions import db
from routes.manager import manager_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

logger = logging.getLogger(__name__)


@manager_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def manager_settings():
    if request.method == 'POST':
        if not request.is_json:
            return jsonify({'success': False, 'message': 'طلب غير صالح'}), 400

        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'بيانات غير صالحة'}), 400
        tenant_id = getattr(current_user, 'tenant_id', None)
        if not tenant_id:
            return jsonify({'success': False, 'message': 'لا يوجد تينانت'}), 400

        tenant = db.session.get(Tenant, tenant_id)
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
        try:
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            logging.exception('Failed to save manager settings')
            return jsonify({'success': False, 'message': 'تعذر حفظ الإعدادات'}), 500

        return jsonify({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'})

    # GET: load current settings
    tenant_id = getattr(current_user, 'tenant_id', None)
    tenant = db.session.get(Tenant, tenant_id) if tenant_id else None
    settings = tenant.settings if tenant and tenant.settings else {}

    return render_template('manager/settings.html', settings=settings, tenant=tenant)


@manager_bp.route('/settings/test-sms', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
@require_platform_capability('sms_live')
def manager_test_sms():
    try:
        data = request.get_json(force=True, silent=True) or {}
        phone_number = data.get('phone_number', '')
        if not phone_number:
            return jsonify({'success': False, 'message': 'يرجى إدخال رقم الهاتف'}), 400

        tenant_id = getattr(current_user, 'tenant_id', None)
        tenant = db.session.get(Tenant, tenant_id) if tenant_id else None

        from services.sms_service import SMSService

        result = SMSService.send_sms(
            phone=phone_number, message='هذه رسالة تجريبية من إعدادات المركز', tenant=tenant
        )
        if result.get('success'):
            return jsonify({'success': True, 'message': 'تم إرسال الرسالة التجريبية بنجاح'}), 200
        return jsonify({'success': False, 'message': result.get('error', 'فشل الإرسال')}), 500
    except Exception as e:
        logging.exception("Manager test SMS error: %s")
        return jsonify({'success': False, 'message': f'خطأ: {e!s}'}), 500
