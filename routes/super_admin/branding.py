"""branding routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
import logging
from sqlalchemy import func


# =============================================
# BRANDING ROUTES
# =============================================

# إدارة العلامة التجارية
@super_admin_bp.route('/branding')
@login_required
@super_admin_required
def branding():
    """إدارة العلامة التجارية والشعارات"""
    try:
        from models.branding import BrandingSettings, SystemTheme
        
        branding_settings = BrandingSettings.get_active_settings()
        themes = SystemTheme.query.filter_by(is_active=True).all()
        
        if not branding_settings:
            branding_settings = BrandingSettings.create_default(current_user.id)
        
        return render_template('super_admin/branding.html', 
                             branding=branding_settings, 
                             themes=themes)
    except Exception as e:
        logging.error(f"Branding error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة العلامة التجارية', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/branding/update', methods=['POST'])
@login_required
@super_admin_required
def update_branding():
    """تحديث إعدادات العلامة التجارية"""
    try:
        from models.branding import BrandingSettings
        from app_factory import db
        from flask_wtf.csrf import validate_csrf
        
        # التحقق من CSRF token
        validate_csrf(request.form.get('csrf_token'))
        
        branding = BrandingSettings.get_active_settings()
        if not branding:
            branding = BrandingSettings.create_default(current_user.id)
        
        # تحديث البيانات الأساسية
        branding.organization_name = request.form.get('organization_name', branding.organization_name)
        branding.organization_name_en = request.form.get('organization_name_en', branding.organization_name_en)
        branding.organization_address = request.form.get('organization_address', branding.organization_address)
        branding.organization_phone = request.form.get('organization_phone', branding.organization_phone)
        branding.organization_email = request.form.get('organization_email', branding.organization_email)
        branding.organization_website = request.form.get('organization_website', branding.organization_website)
        
        # تحديث الألوان
        branding.primary_color = request.form.get('primary_color', branding.primary_color)
        branding.secondary_color = request.form.get('secondary_color', branding.secondary_color)
        branding.accent_color = request.form.get('accent_color', branding.accent_color)
        
        # تحديث ترويسة التقارير
        branding.report_header_html = request.form.get('report_header_html', branding.report_header_html)
        branding.report_footer_html = request.form.get('report_footer_html', branding.report_footer_html)
        
        branding.updated_by = current_user.id
        db.session.commit()
        
        flash('تم تحديث إعدادات العلامة التجارية بنجاح', 'success')
        return redirect(url_for('super_admin.branding'))
        
    except Exception as e:
        logging.error(f"Update branding error: {str(e)}")
        flash('حدث خطأ في تحديث إعدادات العلامة التجارية', 'error')
        return redirect(url_for('super_admin.branding'))

# إدارة المستخدمين المتقدمة
