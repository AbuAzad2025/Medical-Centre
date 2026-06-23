"""branding routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

import logging
import os
import secrets

from flask import (
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from werkzeug.utils import secure_filename

from utils.decorators import super_admin_required

_DOC_LABELS = {
    'invoice': 'فاتورة',
    'receipt': 'إيصال',
    'prescription': 'روشتة',
    'report': 'تقرير طبي',
}


def _invalidate_branding_cache():
    caches = getattr(current_app, '_branding_cache_v2', None)
    if caches is not None:
        caches.clear()


def _get_or_create_branding():
    from models.branding import BrandingSettings

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
    tenant_id = getattr(branding, 'tenant_id', None) or 'platform'
    filename = f'logo_{tenant_id}_{secrets.token_hex(4)}{ext}'
    filepath = os.path.join(upload_root, filename)
    logo.save(filepath)
    branding.logo_path = f'uploads/branding/{filename}'

    tenant = getattr(g, 'current_tenant', None)
    if tenant and hasattr(tenant, 'logo_url'):
        try:
            from app_factory import db
            rel = f'/static/uploads/branding/{filename}'
            if hasattr(tenant, 'settings') and isinstance(tenant.settings, dict):
                tenant.settings = {**(tenant.settings or {}), 'logo_path': rel}
            db.session.add(tenant)
        except Exception:
            pass


def _sync_tenant_colors(branding):
    tenant = getattr(g, 'current_tenant', None)
    if not tenant:
        return
    try:
        from app_factory import db
        if branding.primary_color:
            tenant.primary_color = branding.primary_color
        if branding.organization_name:
            tenant.name = branding.organization_name
        db.session.add(tenant)
    except Exception:
        pass


def _wants_json():
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.accept_mimetypes.best == 'application/json'
    )


# =============================================
# BRANDING ROUTES
# =============================================

@super_admin_bp.route('/branding')
@login_required
@super_admin_required
def branding():
    """إدارة العلامة التجارية والشعارات"""
    try:
        from models.branding import BrandingSettings, SystemTheme

        branding_settings = _get_or_create_branding()
        themes = SystemTheme.query.filter_by(is_active=True).all()

        return render_template(
            'super_admin/branding.html',
            branding=branding_settings,
            themes=themes,
            doc_labels=_DOC_LABELS,
        )
    except Exception as e:
        logging.error(f"Branding error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة العلامة التجارية', 'error')
        return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/branding/preview')
@login_required
@super_admin_required
def branding_print_preview():
    """iframe معاينة ترويسة المستندات (Gate 5)."""
    from app.shared.print_context import resolve_print_slots
    from app.shared.branding_context import resolve_branding_context

    doc_type = request.args.get('doc_type', 'invoice')
    if doc_type not in _DOC_LABELS:
        doc_type = 'invoice'

    branding_row = _get_or_create_branding()
    header_html, footer_html = resolve_print_slots(doc_type, branding_row)
    ui = resolve_branding_context().to_dict()

    return render_template(
        'super_admin/branding_preview.html',
        branding=branding_row,
        ui=ui,
        doc_type=doc_type,
        doc_type_label=_DOC_LABELS.get(doc_type, doc_type),
        print_header_html=header_html,
        print_footer_html=footer_html,
    )


@super_admin_bp.route('/branding/apply-theme/<int:theme_id>', methods=['POST'])
@login_required
@super_admin_required
def apply_branding_theme(theme_id):
    """تطبيق ألوان ثيم على إعدادات العلامة التجارية."""
    try:
        from models.branding import BrandingSettings, SystemTheme
        from app_factory import db

        validate_csrf(request.form.get('csrf_token') or request.headers.get('X-CSRFToken'))

        theme = SystemTheme.query.filter_by(id=theme_id, is_active=True).first()
        if not theme:
            return jsonify({'success': False, 'error': 'الثيم غير موجود'}), 404

        branding = _get_or_create_branding()
        branding.primary_color = theme.primary_color
        branding.secondary_color = theme.secondary_color
        branding.accent_color = theme.accent_color
        branding.updated_by = current_user.id
        _sync_tenant_colors(branding)
        db.session.commit()
        _invalidate_branding_cache()

        return jsonify({
            'success': True,
            'colors': {
                'primary_color': branding.primary_color,
                'secondary_color': branding.secondary_color,
                'accent_color': branding.accent_color,
            },
        })
    except Exception as e:
        logging.error(f"Apply theme error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400


@super_admin_bp.route('/branding/update', methods=['POST'])
@login_required
@super_admin_required
def update_branding():
    """تحديث إعدادات العلامة التجارية"""
    try:
        from app_factory import db

        validate_csrf(request.form.get('csrf_token'))

        branding = _get_or_create_branding()

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
        branding.secondary_color = request.form.get('secondary_color', branding.secondary_color)
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
        branding.license_number = request.form.get('license_number', branding.license_number)

        _save_logo_file(branding)
        _sync_tenant_colors(branding)
        branding.updated_by = current_user.id
        db.session.commit()
        _invalidate_branding_cache()

        if _wants_json():
            return jsonify({'success': True})

        flash('تم تحديث إعدادات العلامة التجارية بنجاح', 'success')
        return redirect(url_for('super_admin.branding'))

    except Exception as e:
        logging.error(f"Update branding error: {str(e)}")
        if _wants_json():
            return jsonify({'success': False, 'error': str(e)}), 400
        flash('حدث خطأ في تحديث إعدادات العلامة التجارية', 'error')
        return redirect(url_for('super_admin.branding'))
