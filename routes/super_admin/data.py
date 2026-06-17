"""data routes - extracted from monolithic super_admin.py"""

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
# DATA ROUTES
# =============================================

@super_admin_bp.route('/branch-templates', methods=['GET', 'POST'])
@login_required
@super_admin_required
def branch_templates():
    try:
        from models.system_config import SystemConfig
        if request.method == 'POST':
            data = request.get_json() or {}
            items = data.get('items') or []
            cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
            if not cfg:
                cfg = SystemConfig(config_key='branch_templates', category='system', is_system=True, config_type='json')
                db.session.add(cfg)
            cfg.set_value(items)
            db.session.commit()
            return jsonify({'success': True, 'message': 'تم حفظ القوالب'}), 200
        cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
        items = cfg.get_value() if cfg else []
        return render_template('super_admin/branch_templates.html', items=items if isinstance(items, list) else [])
    except Exception as e:
        logging.error(f"Branch templates error: {str(e)}")
        return render_template('super_admin/branch_templates.html', items=[])

@super_admin_bp.route('/data-warehouse')
@login_required
@super_admin_required
def data_warehouse():
    try:
        from services.data_warehouse_service import DataWarehouseService
        snapshot = DataWarehouseService.export_snapshot(days=30)
        return render_template('super_admin/data_warehouse.html', snapshot=snapshot)
    except Exception as e:
        logging.error(f"Data warehouse error: {str(e)}")
        return render_template('super_admin/data_warehouse.html', snapshot={})

@super_admin_bp.route('/data-warehouse/export')
@login_required
@super_admin_required
def data_warehouse_export():
    try:
        from services.data_warehouse_service import DataWarehouseService
        days = request.args.get('days', type=int) or 30
        days = max(7, min(days, 365))
        snapshot = DataWarehouseService.export_snapshot(days=days)
        return jsonify({'success': True, 'snapshot': snapshot}), 200
    except Exception as e:
        logging.error(f"Data warehouse export error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تصدير المستودع'}), 500

@super_admin_bp.route('/export-data', methods=['POST'])
@login_required
@super_admin_required
def export_system_data():
    """تصدير بيانات النظام"""
    try:
        from datetime import datetime
        import json
        
        # جمع البيانات من جميع الجداول
        export_data = {
            'export_date': datetime.now().isoformat(),
            'system_info': {
                'version': '1.0.0',
                'exported_by': current_user.username
            },
            'data': {}
        }
        
        # تصدير المستخدمين
        from models.user import User
        users = User.query.all()
        export_data['data']['users'] = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department_id': user.department_id,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
        
        # تصدير المرضى
        from models.patient import Patient
        patients = Patient.query.all()
        export_data['data']['patients'] = [
            {
                'id': patient.id,
                'name': patient.name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.isoformat() if patient.birth_date else None,
                'created_at': patient.created_at.isoformat() if patient.created_at else None
            }
            for patient in patients
        ]
        
        # تصدير الزيارات
        from models.visit import Visit
        visits = Visit.query.all()
        export_data['data']['visits'] = [
            {
                'id': visit.id,
                'patient_id': visit.patient_id,
                'doctor_id': visit.doctor_id,
                'department_id': visit.department_id,
                'visit_type': visit.visit_type,
                'status': visit.status,
                'created_at': visit.created_at.isoformat() if visit.created_at else None
            }
            for visit in visits
        ]
        
        # حفظ الملف
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'medical_system_export_{timestamp}.json'
        
        with open(f'instance/{filename}', 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'تم تصدير البيانات بنجاح',
            'download_url': f'/super-admin/download-export/{filename}'
        })
        
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'تعذر تصدير البيانات حالياً'
        })

@super_admin_bp.route('/download-export/<filename>')
@login_required
@super_admin_required
def download_export(filename):
    """تحميل ملف التصدير"""
    try:
        from flask import send_file
        import os
        
        file_path = os.path.join('instance', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            flash('الملف غير موجود', 'error')
            return redirect(url_for('super_admin.dashboard'))
            
    except Exception as e:
        logging.error(f"Error downloading export: {str(e)}")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('super_admin.dashboard'))
