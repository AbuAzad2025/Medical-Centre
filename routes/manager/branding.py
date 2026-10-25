"""Tenant-level branding routes — extracted from super_admin/branding.py.

Allows tenant managers/admins to edit their own BrandingSettings
(header/footer HTML, colors, logo, tax/license numbers).
"""

import logging
import os
import secrets

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from werkzeug.utils import secure_filename

from app.extensions import db
from models.branding import BrandingSettings
from routes.manager import manager_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

logger = logging.getLogger(__name__)

_DOC_LABELS = {
    'invoice': 'فاتورة',
    'receipt': 'إيصال',
    'prescription': 'روشتة',
    'report': 'تقرير',
    'lab_result': 'نتيجة مختبر',
    'radiology_report': 'تقرير أشعة',
    'emergency_report': 'تقرير طوارئ',
    'pharmacy_sale': 'بيع صيدلية',
    'queue_ticket': 'تذكرة طابور',
    'doctor_medical_report': 'تقرير طبي',
    'barcode': 'باركود',
    'label': 'ملصق',
}


def _get_or_create_tenant_branding():
    """Get or create BrandingSettings for the current tenant."""
    branding = BrandingSettings.get_active_settings()
    if not branding:
        branding = BrandingSettings.create_default(current_user.id)
    return branding


def _save_logo_file(branding):
    logo = request.files.get('logo_file')
    if not logo or not logo.filename:
        return
    upload_root = os.path.join(current_app.root_path, 'static', 'uploads', 'branding')
    os.makedirs(upload_root, exist_ok=True)
    safe = secure_filename(logo.filename) or 'logo.png'
    ext = os.path.splitext(safe)[1] or '.png'
    tenant_id = getattr(branding, 'tenant_id', None) or 'tenant'
    filename = f'logo_{tenant_id}_{secrets.token_hex(4)}{ext}'
    filepath = os.path.join(upload_root, filename)
    logo.save(filepath)
    branding.logo_path = f'uploads/branding/{filename}'


def _wants_json():
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )


@manager_bp.route('/branding', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def manager_branding():
    """Tenant-level branding settings — header/footer HTML, colors, logo, tax/license."""
    try:
        branding = _get_or_create_tenant_branding()

        if request.method == 'POST':
            try:
                validate_csrf(request.form.get('csrf_token'))

                branding.organization_name = request.form.get(
                    'organization_name', branding.organization_name
                )
                branding.organization_name_en = request.form.get(
                    'organization_name_en', branding.organization_name_en
                )
                branding.organization_address = request.form.get(
                    'organization_address', branding.organization_address
                )
                branding.organization_phone = request.form.get(
                    'organization_phone', branding.organization_phone
                )
                branding.organization_email = request.form.get(
                    'organization_email', branding.organization_email
                )
                branding.organization_website = request.form.get(
                    'organization_website', branding.organization_website
                )

                branding.primary_color = request.form.get('primary_color', branding.primary_color)
                branding.secondary_color = request.form.get(
                    'secondary_color', branding.secondary_color
                )
                branding.accent_color = request.form.get('accent_color', branding.accent_color)

                branding.report_header_html = request.form.get(
                    'report_header_html', branding.report_header_html
                )
                branding.report_footer_html = request.form.get(
                    'report_footer_html', branding.report_footer_html
                )
                branding.invoice_header_html = request.form.get(
                    'invoice_header_html', branding.invoice_header_html
                )
                branding.invoice_footer_html = request.form.get(
                    'invoice_footer_html', branding.invoice_footer_html
                )
                branding.receipt_header_html = request.form.get(
                    'receipt_header_html', branding.receipt_header_html
                )
                branding.prescription_header_html = request.form.get(
                    'prescription_header_html', branding.prescription_header_html
                )
                branding.prescription_footer_html = request.form.get(
                    'prescription_footer_html', branding.prescription_footer_html
                )
                branding.tax_number = request.form.get('tax_number', branding.tax_number)
                branding.license_number = request.form.get(
                    'license_number', branding.license_number
                )

                _save_logo_file(branding)
                branding.updated_by = current_user.id
                safe_commit(db.session, error_message='database commit failed', reraise=True)

                # Invalidate branding cache
                caches = getattr(current_app, '_branding_cache_v2', None)
                if caches is not None:
                    caches.clear()

                if _wants_json():
                    return jsonify({'success': True})

                flash('تم تحديث إعدادات العلامة التجارية بنجاح', 'success')
                return redirect(url_for('manager.manager_branding'))

            except Exception as e:
                safe_rollback(db.session, error_message='database rollback')
                logger.exception('Update tenant branding error')
                if _wants_json():
                    return jsonify({'success': False, 'error': str(e)}), 400
                flash(f'خطأ: {e}', 'error')
                return redirect(url_for('manager.manager_branding'))

        return render_template(
            'manager/branding.html',
            branding=branding,
            doc_labels=_DOC_LABELS,
        )
    except Exception as e:
        logger.exception('Branding page error')
        flash(f'خطأ: {e}', 'error')
        return redirect(url_for('manager.dashboard'))


@manager_bp.route('/branding/preview', methods=['GET'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def manager_branding_preview():
    """Preview print template with current tenant branding."""
    from app.shared.branding_context import resolve_branding_context
    from app.shared.print_context import resolve_print_slots

    doc_type = request.args.get('doc_type', 'invoice')
    if doc_type not in _DOC_LABELS:
        doc_type = 'invoice'

    branding = _get_or_create_tenant_branding()
    header_html, footer_html = resolve_print_slots(doc_type, branding)
    ui = resolve_branding_context().to_dict()

    return render_template(
        'manager/branding_preview.html',
        branding=branding,
        ui=ui,
        doc_type=doc_type,
        doc_type_label=_DOC_LABELS.get(doc_type, doc_type),
        print_header_html=header_html,
        print_footer_html=footer_html,
    )
