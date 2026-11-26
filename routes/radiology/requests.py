"""requests routes - extracted from monolithic radiology.py"""

import logging

# Imports
from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from models.radiology_request import RadiologyRequest
from routes.radiology import radiology_bp
from utils.decorators import role_required

# REQUESTS ROUTES


@radiology_bp.route('/requests')
@login_required
@role_required('radiology', 'manager')
def requests():
    """طلبات الأشعة"""
    try:
        stats = {
            'pending': db.session.execute(
                select(func.count()).select_from(RadiologyRequest).filter_by(status='REQUESTED')
            ).scalar(),
            'in_progress': db.session.execute(
                select(func.count()).select_from(RadiologyRequest).filter_by(status='IN_PROGRESS')
            ).scalar(),
            'completed': db.session.execute(
                select(func.count()).select_from(RadiologyRequest).filter_by(status='DONE')
            ).scalar(),
            'urgent': 0,
        }
        requests_list = (
            db.session.execute(
                select(RadiologyRequest).order_by(RadiologyRequest.created_at.desc()).limit(100)
            )
            .scalars()
            .all()
        )
        return render_template(
            'radiology/radiology_requests.html',
            stats=stats,
            requests=requests_list,
        )
    except Exception:
        logging.exception('Error loading radiology requests')
        flash('حدث خطأ في تحميل طلبات الأشعة', 'error')
        return redirect(url_for('radiology.dashboard'))


@radiology_bp.route('/tests')
@login_required
@role_required('radiology', 'manager')
def tests():
    """فحوصات الأشعة"""

    return render_template('radiology/add_scan.html')


@radiology_bp.route('/tests/add', methods=['POST'])
@login_required
@role_required('radiology', 'manager')
def add_scan_post():
    """إضافة فحص أشعة (نقطة إرسال الفورم)"""

    try:
        from models.radiology_request import RadiologyRequest
        from utils.db_safety import safe_commit

        patient_id = request.form.get('patient_id', type=int)
        visit_id = request.form.get('visit_id', type=int)
        if not patient_id:
            flash('المريض مطلوب', 'error')
            return redirect(url_for('radiology.tests'))
        rec = RadiologyRequest(
            tenant_id=getattr(current_user, 'tenant_id', None),
            patient_id=patient_id,
            visit_id=visit_id,
            requested_by=current_user.id,
            modality=(request.form.get('scan_type') or '').strip()[:20] or None,
            body_part=(request.form.get('technician') or '').strip()[:120] or None,
            notes=(request.form.get('notes') or '').strip() or None,
            status='REQUESTED',
        )
        db.session.add(rec)
        safe_commit(db.session, error_message='failed to save radiology scan', reraise=True)
        flash('تم استلام بيانات الفحص بنجاح', 'success')
        return redirect(url_for('radiology.tests'))
    except Exception:
        logging.exception('Error adding radiology scan')
        flash('حدث خطأ أثناء إضافة الفحص', 'error')
        return redirect(url_for('radiology.dashboard'))


@radiology_bp.route('/results')
@login_required
@role_required('radiology', 'manager')
def results():
    """نتائج الأشعة"""

    try:
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit
        from services.access_control_service import AccessControlService

        dept_ids = AccessControlService.get_accessible_department_ids(current_user)
        query = select(RadiologyRequest)
        if dept_ids is not None and dept_ids:
            query = query.join(Visit, Visit.id == RadiologyRequest.visit_id).filter(
                Visit.department_id.in_(dept_ids)
            )
        results = (
            db.session.execute(query.order_by(RadiologyRequest.created_at.desc())).scalars().all()
        )

        return render_template('radiology/results.html', results=results)
    except Exception:
        logging.exception('Error loading radiology results')
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('radiology.dashboard'))
