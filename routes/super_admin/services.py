"""services routes - extracted from monolithic super_admin.py"""

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
# SERVICES ROUTES
# =============================================

@super_admin_bp.route('/pricing')
@login_required
@super_admin_required
def pricing():
    """إدارة الأسعار المركزية (واجهة متطورة)"""
    try:
        from models.service import ServiceMaster
        from models.department import Department
        
        services = ServiceMaster.query.order_by(ServiceMaster.updated_at.desc()).all()
        departments = Department.query.filter_by(is_active=True).all()
        
        return render_template('manager/pricing.html', services=services, departments=departments)
    except Exception as e:
        logging.error(f"Error loading pricing for super admin: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأسعار', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/services')
@login_required
@super_admin_required
def services():
    """إدارة الخدمات"""
    try:
        from models.service import ServiceMaster
        from models.department import Department
        services = ServiceMaster.query.all()
        departments = Department.query.filter_by(is_active=True).all()
        return render_template('super_admin/services.html', services=services, departments=departments)
    except Exception as e:
        logging.error(f"Services error: {str(e)}")
        return render_template('super_admin/services.html', services=[], departments=[])

@super_admin_bp.route('/services/create', methods=['POST'])
@login_required
@super_admin_required
def create_service():
    """إنشاء خدمة جديدة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        import re, time
        
        # التوافق والتحقق من حقول النموذج
        name = request.form.get('name')
        name_ar = request.form.get('name_ar')
        if not name or not name_ar:
            return jsonify({'success': False, 'message': 'اسم الخدمة (إنجليزي) والاسم العربي مطلوبان'}), 400

        price_value_raw = request.form.get('base_price') or request.form.get('price') or '0'
        try:
            price_value = float(price_value_raw)
        except ValueError:
            return jsonify({'success': False, 'message': 'السعر يجب أن يكون رقمًا صالحًا'}), 400
        if price_value < 0:
            return jsonify({'success': False, 'message': 'السعر يجب أن يكون غير سالب'}), 400

        service_type = request.form.get('service_type') or 'general'
        category_map = {
            'LAB': 'lab',
            'RADIOLOGY': 'radiology',
        }
        category = category_map.get(service_type, 'general')
        if category not in ('general', 'doctor', 'lab', 'radiology'):
            category = 'general'
        department_id = request.form.get('department_id') or None
        currency = request.form.get('currency') or 'شيكل'
        allowed_currencies = {'شيكل', 'ILS', 'USD', 'EUR'}
        if currency not in allowed_currencies:
            currency = 'شيكل'

        # التحقق من المدة والحد اليومي إن تم إرسالها
        duration_val = request.form.get('duration')
        if duration_val:
            try:
                duration_int = int(duration_val)
                if duration_int < 1:
                    return jsonify({'success': False, 'message': 'المدة يجب أن تكون 1 دقيقة على الأقل'}), 400
            except ValueError:
                return jsonify({'success': False, 'message': 'المدة يجب أن تكون عددًا صحيحًا'}), 400
        else:
            duration_int = None

        max_daily_val = request.form.get('max_daily')
        if max_daily_val:
            try:
                max_daily_int = int(max_daily_val)
                if max_daily_int < 1:
                    return jsonify({'success': False, 'message': 'الحد اليومي يجب أن يكون 1 على الأقل'}), 400
            except ValueError:
                return jsonify({'success': False, 'message': 'الحد اليومي يجب أن يكون عددًا صحيحًا'}), 400
        else:
            max_daily_int = None

        # توليد رمز فريد للخدمة إذا لم يتم إرساله
        code = request.form.get('code')
        if not code:
            base = re.sub(r"[^A-Za-z0-9]+", "_", (name or "SERVICE").upper()).strip('_')
            code = f"{(category or 'GENERAL').upper()}_{base}_{int(time.time())}"

        service = ServiceMaster(
            code=code,
            name=name,
            name_ar=name_ar,
            description=request.form.get('description'),
            base_price=float(price_value or 0),
            category=category,
            department_id=int(department_id) if department_id else None,
            currency=currency,
            duration=duration_int,
            max_daily=max_daily_int,
            is_required=bool(request.form.get('is_required')),
            is_active=True
        )
        
        db.session.add(service)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إنشاء الخدمة بنجاح', 'service_id': service.id}), 200
        
    except Exception as e:
        logging.error(f"Create service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إنشاء الخدمة حالياً'}), 500

@super_admin_bp.route('/service/<int:service_id>')
@login_required
@super_admin_required
def view_service(service_id):
    """عرض تفاصيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        return render_template('super_admin/service_detail.html', service=service)
    except Exception as e:
        logging.error(f"View service error: {str(e)}")
        flash('حدث خطأ في عرض الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/edit-service/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_service(service_id):
    """تعديل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        
        if request.method == 'POST':
            service.name_ar = request.form.get('name')
            service.name = request.form.get('name_en')
            service.description = request.form.get('description')
            service.category = request.form.get('category') or service.category
            dep_id = request.form.get('department_id') or None
            service.department_id = int(dep_id) if dep_id else None
            service.currency = request.form.get('currency') or service.currency
            service.duration = int(request.form.get('duration')) if request.form.get('duration') else None
            service.max_daily = int(request.form.get('max_daily')) if request.form.get('max_daily') else None
            service.is_required = bool(request.form.get('is_required'))
            service.base_price = float(request.form.get('base_price', 0))
            service.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث الخدمة بنجاح', 'success')
            return redirect(url_for('super_admin.services'))
        
        from models.department import Department
        departments = Department.query.filter_by(is_active=True).all()
        return render_template('super_admin/edit_service.html', service=service, departments=departments)
    except Exception as e:
        logging.error(f"Edit service error: {str(e)}")
        flash('حدث خطأ في تعديل الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/service-pricing/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def service_pricing(service_id):
    """إدارة تسعير الخدمة"""
    try:
        from models.service import ServiceMaster
        from models.pricing_management import PricingManagement
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        pricing_records = PricingManagement.query.filter_by(service_id=service_id).all()
        pricing = []
        for rec in pricing_records:
            if rec.base_price:
                pricing.append({'id': rec.id, 'price_type': 'standard', 'price': float(rec.base_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.emergency_price:
                pricing.append({'id': rec.id, 'price_type': 'urgent', 'price': float(rec.emergency_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.private_price:
                pricing.append({'id': rec.id, 'price_type': 'vip', 'price': float(rec.private_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.insurance_price:
                pricing.append({'id': rec.id, 'price_type': 'insurance', 'price': float(rec.insurance_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
        
        if request.method == 'POST':
            price_type = request.form.get('price_type')
            price_value = float(request.form.get('price', 0))
            description = request.form.get('description')
            currency = request.form.get('currency') or 'ILS'
            discount_percentage_raw = request.form.get('discount_percentage')
            discount_amount_raw = request.form.get('discount_amount')
            try:
                discount_percentage = float(discount_percentage_raw) if discount_percentage_raw not in (None, '',) else 0.0
            except Exception:
                discount_percentage = 0.0
            try:
                discount_amount = float(discount_amount_raw) if discount_amount_raw not in (None, '',) else 0.0
            except Exception:
                discount_amount = 0.0

            new_pricing = PricingManagement(
                service_id=service_id,
                base_price=price_value if price_type in (None, '', 'base', 'standard') else 0,
                emergency_price=price_value if price_type in ('emergency', 'urgent') else None,
                insurance_price=price_value if price_type == 'insurance' else None,
                private_price=price_value if price_type == 'vip' else None,
                currency=currency,
                created_by=current_user.id,
                is_active=True
            )
            new_pricing.discount_percentage = discount_percentage
            new_pricing.discount_amount = discount_amount

            db.session.add(new_pricing)
            db.session.commit()
            flash('تم إضافة التسعير بنجاح', 'success')
            return redirect(url_for('super_admin.service_pricing', service_id=service_id))
        
        return render_template('super_admin/service_pricing.html', service=service, pricing=pricing)
    except Exception as e:
        logging.error(f"Service pricing error: {str(e)}")
        flash('حدث خطأ في إدارة التسعير', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/activate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_service(service_id):
    """تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        service.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Activate service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تفعيل الخدمة حالياً'}), 500

@super_admin_bp.route('/deactivate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_service(service_id):
    """إلغاء تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        service.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Deactivate service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء تفعيل الخدمة حالياً'}), 500

@super_admin_bp.route('/export-services')
@login_required
@super_admin_required
def export_services():
    """تصدير الخدمات"""
    try:
        from models.service import ServiceMaster
        import csv
        from io import StringIO
        from flask import make_response
        
        services = ServiceMaster.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم', 'الاسم بالإنجليزية', 'الوصف', 'السعر الأساسي', 'نشط'])
        
        for service in services:
            writer.writerow([
                service.id,
                service.name_ar or '',
                service.name or '',
                service.description or '',
                service.base_price or 0,
                'نعم' if service.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=services_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export services error: {str(e)}")
        flash('حدث خطأ في تصدير الخدمات', 'error')
        return redirect(url_for('super_admin.services'))
