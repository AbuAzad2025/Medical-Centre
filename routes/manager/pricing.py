"""pricing routes - extracted from monolithic manager.py"""

import logging

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.manager import manager_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import (
    role_required,
    role_required_json,
)

# =============================================
# PRICING ROUTES
# =============================================


@manager_bp.route('/pricing')
@login_required
@role_required('manager', 'admin', 'super_admin')
def pricing():
    """إدارة الأسعار"""

    try:
        # جلب خدمات التسعير
        from models.department import Department
        from models.service import ServiceMaster

        services = (
            db.session.execute(
                select(ServiceMaster)
                .filter(ServiceMaster.tenant_id == current_user.tenant_id)
                .order_by(ServiceMaster.updated_at.desc())
            )
            .scalars()
            .all()
        )
        departments = (
            db.session.execute(
                select(Department)
                .filter_by(is_active=True)
                .filter(Department.tenant_id == current_user.tenant_id)
            )
            .scalars()
            .all()
        )

        return render_template('manager/pricing.html', services=services, departments=departments)
    except Exception:
        logging.exception("Error loading pricing: %s")
        flash('حدث خطأ في تحميل إدارة الأسعار', 'error')
        return redirect(url_for('manager.dashboard'))


# --- API Endpoints for Pricing Management ---


@manager_bp.route('/api/pricing/services', methods=['GET'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def get_services_api():
    """API لجلب كافة الخدمات"""
    try:
        from models.service import ServiceMaster

        services = (
            db.session.execute(
                select(ServiceMaster)
                .filter(ServiceMaster.tenant_id == current_user.tenant_id)
                .order_by(ServiceMaster.updated_at.desc())
            )
            .scalars()
            .all()
        )
        return jsonify(
            {
                'success': True,
                'data': [
                    {
                        'id': s.id,
                        'code': s.code,
                        'name': s.name,
                        'name_ar': s.name_ar,
                        'category': s.category,
                        'base_price': float(s.base_price),
                        'emergency_price': float(s.emergency_price)
                        if s.emergency_price is not None
                        else None,
                        'insurance_price': float(s.insurance_price)
                        if s.insurance_price is not None
                        else None,
                        'currency': s.currency,
                        'department_id': s.department_id,
                        'department_name': s.department.name_ar if s.department else None,
                        'duration': s.duration,
                        'max_daily': s.max_daily,
                        'is_active': s.is_active,
                        'description': s.description,
                        'updated_at': s.updated_at.strftime('%Y-%m-%d'),
                    }
                    for s in services
                ],
            }
        )
    except Exception:
        return jsonify({'success': False, 'message': 'تعذر جلب البيانات حالياً'}), 500


@manager_bp.route('/api/pricing/services', methods=['POST'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def add_service_api():
    """API لإضافة خدمة جديدة"""
    try:
        from models.service import ServiceMaster

        data = request.get_json(silent=True) or {}

        # Validation
        if not data.get('name') or not data.get('code'):
            return jsonify({'success': False, 'message': 'الاسم وكود الخدمة مطلوبان'}), 400

        existing = (
            db.session.execute(
                select(ServiceMaster)
                .filter_by(code=data['code'])
                .filter(ServiceMaster.tenant_id == current_user.tenant_id)
            )
            .scalars()
            .first()
        )
        if existing:
            return jsonify({'success': False, 'message': 'كود الخدمة موجود مسبقاً'}), 400

        new_service = ServiceMaster(
            code=data['code'],
            name=data['name'],
            name_ar=data.get('name_ar'),
            description=data.get('description'),
            category=data.get('category', 'general'),
            base_price=data.get('base_price', 0),
            emergency_price=data.get('emergency_price'),
            insurance_price=data.get('insurance_price'),
            currency=data.get('currency', 'شيكل'),
            department_id=data.get('department_id'),
            duration=data.get('duration'),
            max_daily=data.get('max_daily'),
            is_active=data.get('is_active', True),
        )
        db.session.add(new_service)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        return jsonify({'success': True, 'message': 'تم إضافة الخدمة بنجاح', 'id': new_service.id})
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        return jsonify({'success': False, 'message': 'تعذر إضافة الخدمة حالياً'}), 500


@manager_bp.route('/api/pricing/services/<int:id>', methods=['PUT'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def update_service_api(id):
    """API لتحديث خدمة"""
    try:
        from models.service import ServiceMaster

        service = db.session.get(ServiceMaster, id)
        if not service:
            return jsonify({'success': False, 'message': 'الخدمة غير موجودة'}), 404

        data = request.get_json(silent=True) or {}

        if 'name' in data:
            service.name = data['name']
        if 'name_ar' in data:
            service.name_ar = data['name_ar']
        if 'description' in data:
            service.description = data['description']
        if 'category' in data:
            service.category = data['category']
        if 'base_price' in data:
            service.base_price = data['base_price']
        if 'emergency_price' in data:
            service.emergency_price = data['emergency_price']
        if 'insurance_price' in data:
            service.insurance_price = data['insurance_price']
        if 'currency' in data:
            service.currency = data['currency']
        if 'department_id' in data:
            service.department_id = data['department_id']
        if 'duration' in data:
            service.duration = data['duration']
        if 'max_daily' in data:
            service.max_daily = data['max_daily']
        if 'is_active' in data:
            service.is_active = data['is_active']

        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'message': 'تم تحديث الخدمة بنجاح'})
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        return jsonify({'success': False, 'message': 'تعذر تحديث الخدمة حالياً'}), 500


@manager_bp.route('/api/pricing/services/<int:id>', methods=['DELETE'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def delete_service_api(id):
    """API لحذف خدمة"""
    try:
        from models.service import ServiceMaster

        service = db.session.get(ServiceMaster, id)
        if not service:
            return jsonify({'success': False, 'message': 'الخدمة غير موجودة'}), 404

        db.session.delete(service)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'message': 'تم حذف الخدمة بنجاح'})
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        return jsonify({'success': False, 'message': 'تعذر حذف الخدمة حالياً'}), 500


@manager_bp.route('/seed-pricing', methods=['POST'])
@login_required
@role_required_json('manager', 'admin', 'super_admin')
def seed_pricing():
    """إضافة مجموعة أسعار مقترحة"""

    try:
        from services.pricing_service import PricingService

        res = PricingService.seed_all()
        status = 200 if res.get('success') else 400
        return jsonify(
            {'success': res.get('success', False), 'message': res.get('message', '')}
        ), status
    except Exception:
        logging.exception("Error seeding pricing: %s")
        return jsonify({'success': False, 'message': 'حدث خطأ في إضافة الأسعار المقترحة'}), 500
