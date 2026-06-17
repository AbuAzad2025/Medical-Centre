"""departments routes - extracted from monolithic super_admin.py"""

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
# DEPARTMENTS ROUTES
# =============================================

@super_admin_bp.route('/departments')
@login_required
@super_admin_required
def departments():
    """إدارة الأقسام"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        from models.department import Department
        from models.user import User
        query = Department.query.order_by(Department.name)
        
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        departments = query.offset((page - 1) * per_page).limit(per_page).all()
        total_doctors = User.query.filter_by(role='doctor').count()
        total_staff = User.query.count()
    except Exception as e:
        logging.error(f"Departments error: {str(e)}")
        departments = []
        total = 0
        pages = 0
        total_doctors = 0
        total_staff = 0

    return render_template('super_admin/departments.html', departments=departments, 
total_doctors=total_doctors, total_staff=total_staff,
                           page=page, pages=pages, total=total)
@super_admin_bp.route('/departments/create', methods=['POST'])
@login_required
@super_admin_required
def create_department():
    """إنشاء قسم جديد"""
    try:
        from models.department import Department
        from app_factory import db
        
        # التحقق من الحقول المطلوبة
        name = request.form.get('name')
        name_ar = request.form.get('name_ar')
        if not name or not name_ar:
            return jsonify({'success': False, 'message': 'الاسم الإنجليزي والاسم العربي مطلوبان'}), 400

        department = Department(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description'),
            location=request.form.get('location'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            is_active=bool(request.form.get('is_active', True))
        )
        
        db.session.add(department)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إنشاء القسم بنجاح', 'department_id': department.id}), 200
        
    except Exception as e:
        logging.error(f"Create department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إنشاء القسم حالياً'}), 500

@super_admin_bp.route('/department/<int:department_id>')
@login_required
@super_admin_required
def view_department(department_id):
    """عرض تفاصيل قسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        staff = User.query.filter_by(department_id=department_id).all()
        
        return render_template('super_admin/department_detail.html', 
                             department=department, 
                             staff=staff)
    except Exception as e:
        logging.error(f"View department error: {str(e)}")
        flash('حدث خطأ في عرض القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/edit-department/<int:department_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_department(department_id):
    """تعديل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        
        if request.method == 'POST':
            department.name_ar = request.form.get('name')
            department.name = request.form.get('name_en')
            department.description = request.form.get('description')
            department.location = request.form.get('location')
            department.phone = request.form.get('phone')
            department.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث القسم بنجاح', 'success')
            return redirect(url_for('super_admin.departments'))
        
        return render_template('super_admin/edit_department.html', department=department)
    except Exception as e:
        logging.error(f"Edit department error: {str(e)}")
        flash('حدث خطأ في تعديل القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>')
@login_required
@super_admin_required
def department_staff(department_id):
    """إدارة موظفي القسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        staff = User.query.filter_by(department_id=department_id).all()
        all_users = User.query.filter_by(is_active=True).all()
        
        return render_template('super_admin/department_staff.html', 
                             department=department, 
                             staff=staff,
                             all_users=all_users)
    except Exception as e:
        logging.error(f"Department staff error: {str(e)}")
        flash('حدث خطأ في إدارة موظفي القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>/add', methods=['POST'])
@login_required
@super_admin_required
def add_staff_to_department(department_id):
    """إضافة موظف للقسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        user.department_id = department_id
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إضافة الموظف للقسم'}), 200
    except Exception as e:
        logging.error(f"Add staff error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إضافة الموظف للقسم حالياً'}), 500

@super_admin_bp.route('/department-staff/<int:department_id>/remove', methods=['POST'])
@login_required
@super_admin_required
def remove_staff_from_department(department_id):
    """إزالة موظف من القسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        user.department_id = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إزالة الموظف من القسم'}), 200
    except Exception as e:
        logging.error(f"Remove staff error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إزالة الموظف من القسم حالياً'}), 500

@super_admin_bp.route('/activate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_department(department_id):
    """تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        department.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Activate department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تفعيل القسم حالياً'}), 500

@super_admin_bp.route('/deactivate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_department(department_id):
    """إلغاء تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        department.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Deactivate department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء تفعيل القسم حالياً'}), 500

@super_admin_bp.route('/export-departments')
@login_required
@super_admin_required
def export_departments():
    """تصدير الأقسام"""
    try:
        from models.department import Department
        import csv
        from io import StringIO
        from flask import make_response
        
        departments = Department.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم العربي', 'الاسم (إنجليزي)', 'الوصف', 'الموقع', 'الهاتف', 'نشط'])
        
        for dept in departments:
            writer.writerow([
                dept.id,
                dept.name_ar or '',
                dept.name or '',
                dept.description or '',
                dept.location or '',
                dept.phone or '',
                'نعم' if dept.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=departments_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export departments error: {str(e)}")
        flash('حدث خطأ في تصدير الأقسام', 'error')
        return redirect(url_for('super_admin.departments'))
