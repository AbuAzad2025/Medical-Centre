"""data routes - extracted from monolithic super_admin.py"""

import logging

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.super_admin import super_admin_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import super_admin_required

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
            data = request.get_json(silent=True) or {}
            items = data.get('items') or []
            cfg = (
                db.session.execute(select(SystemConfig).filter_by(config_key='branch_templates'))
                .scalars()
                .first()
            )
            if not cfg:
                cfg = SystemConfig(
                    config_key='branch_templates',
                    category='system',
                    is_system=True,
                    config_type='json',
                )
                db.session.add(cfg)
            cfg.set_value(items)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            return jsonify({'success': True, 'message': 'تم حفظ القوالب'}), 200
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='branch_templates'))
            .scalars()
            .first()
        )
        items = cfg.get_value() if cfg else []
        return render_template(
            'super_admin/branch_templates.html', items=items if isinstance(items, list) else []
        )
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception("Branch templates error: %s")
        return render_template('super_admin/branch_templates.html', items=[])


@super_admin_bp.route('/data-warehouse')
@login_required
@super_admin_required
def data_warehouse():
    try:
        from services.data_warehouse_service import DataWarehouseService

        snapshot = DataWarehouseService.export_snapshot(days=30)
        return render_template('super_admin/data_warehouse.html', snapshot=snapshot)
    except Exception:
        logging.exception("Data warehouse error: %s")
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
    except Exception:
        logging.exception("Data warehouse export error: %s")
        return jsonify({'success': False, 'message': 'تعذر تصدير المستودع'}), 500


@super_admin_bp.route('/export-data', methods=['POST'])
@login_required
@super_admin_required
def export_system_data():
    """تصدير بيانات النظام"""
    try:
        import json
        from datetime import datetime

        # جمع البيانات من جميع الجداول
        export_data = {
            'export_date': datetime.now().isoformat(),
            'system_info': {'version': '1.0.0', 'exported_by': current_user.username},
            'data': {},
        }

        # تصدير المستخدمين
        from models.user import User

        users = db.session.execute(select(User)).scalars().all()
        export_data['data']['users'] = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department_id': user.department_id,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ]

        # تصدير المرضى
        from models.patient import Patient

        patients = db.session.execute(select(Patient)).scalars().all()
        export_data['data']['patients'] = [
            {
                'id': patient.id,
                'name': patient.name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.isoformat() if patient.birth_date else None,
                'created_at': patient.created_at.isoformat() if patient.created_at else None,
            }
            for patient in patients
        ]

        # تصدير الزيارات
        from models.visit import Visit

        visits = db.session.execute(select(Visit)).scalars().all()
        export_data['data']['visits'] = [
            {
                'id': visit.id,
                'patient_id': visit.patient_id,
                'doctor_id': visit.doctor_id,
                'department_id': visit.department_id,
                'visit_type': visit.visit_type,
                'status': visit.status,
                'created_at': visit.created_at.isoformat() if visit.created_at else None,
            }
            for visit in visits
        ]

        # حفظ الملف
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'medical_system_export_{timestamp}.json'

        with open(f'instance/{filename}', 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        return jsonify(
            {
                'success': True,
                'message': 'تم تصدير البيانات بنجاح',
                'download_url': f'/super-admin/download-export/{filename}',
            }
        )

    except Exception:
        logging.exception("Error exporting data: %s")
        return jsonify({'success': False, 'message': 'تعذر تصدير البيانات حالياً'})


@super_admin_bp.route('/download-export/<filename>')
@login_required
@super_admin_required
def download_export(filename):
    """تحميل ملف التصدير"""
    try:
        import os

        from flask import send_file

        file_path = os.path.join('instance', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        flash('الملف غير موجود', 'error')
        return redirect(url_for('super_admin.dashboard'))

    except Exception:
        logging.exception("Error downloading export: %s")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('super_admin.dashboard'))
