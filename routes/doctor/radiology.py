"""radiology routes - extracted from monolithic doctor.py"""

import logging

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.extensions import db
from app.shared.enums import VisitState
from models.audit_trail import AuditTrail
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from routes.doctor import doctor_bp
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# RADIOLOGY ROUTES
# =============================================


@doctor_bp.route('/radiology-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def radiology_request(visit_id):
    try:
        if 'radiology' not in getattr(g, 'enabled_modules', set()):
            flash('وحدة الأشعة غير مفعلة لهذه المنشأة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        visit = (
            db.session.execute(
                select(Visit).filter(
                    Visit.id == visit_id,
                    Visit.tenant_id == g.tenant_id,
                    Visit.doctor_id == current_user.id,
                )
            )
            .scalars()
            .first()
        )
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != VisitState.IN_PROGRESS:
            flash('لا يمكن طلب تصوير أشعة إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        if request.method == 'POST':
            test_name = (request.form.get('test_name') or '').strip()
            notes = (
                request.form.get('notes') or request.form.get('test_description') or ''
            ).strip()
            if len(test_name) > 200:
                flash('اسم التصوير طويل جداً', 'warning')
                return redirect(url_for('doctor.patient_details', visit_id=visit_id))
            if len(notes) > 2000:
                flash('الوصف طويل جداً', 'warning')
                return redirect(url_for('doctor.patient_details', visit_id=visit_id))
            modality = (request.form.get('modality') or '').strip()
            body_part = (request.form.get('body_part') or '').strip()
            if len(modality) > 50:
                flash('الآلية طويلة جداً', 'warning')
                return redirect(url_for('doctor.patient_details', visit_id=visit_id))
            if len(body_part) > 200:
                flash('المنطقة طويلة جداً', 'warning')
                return redirect(url_for('doctor.patient_details', visit_id=visit_id))
            memo_parts = []
            if test_name:
                memo_parts.append(f'نوع التصوير: {test_name}')
            if modality:
                memo_parts.append(f'المنظار/الآلية: {modality}')
            if body_part:
                memo_parts.append(f'المنطقة: {body_part}')
            if notes:
                memo_parts.append(f'الوصف: {notes}')
            memo_text = '[مذكرة تصوير]\n' + (
                '\n'.join(memo_parts) if memo_parts else 'يرجى إجراء التصوير لدى مركز مناسب.'
            )

            # P2-003: Create structured RadiologyRequest when modality/body_part supplied.
            structured_ok = False
            if modality or body_part:
                from services.radiology_service import radiology_service

                ok, result = radiology_service.create_request(
                    visit_id=visit.id,
                    requested_by=current_user.id,
                    modality=modality,
                    body_part=body_part,
                    notes=notes,
                    tenant_id=getattr(current_user, 'tenant_id', None),
                )
                if ok:
                    structured_ok = True
                    memo_parts.append(f'رقم الطلب المهيكل: {result["request_number"]}')
                else:
                    flash(f'تعذر إنشاء طلب الأشعة المهيكل: {result.get("error")}', 'warning')

            visit.notes = visit.notes or ''
            visit.notes += ('\n\n' if visit.notes else '') + memo_text
            visit.radiology_ordered = True
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            try:
                db.session.add(
                    AuditTrail(
                        tenant_id=g.tenant_id,
                        entity_type='radiology_test',
                        entity_id=visit.id,
                        action='create',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='إضافة مذكرة تصوير'
                        + (' + RadiologyRequest' if structured_ok else ''),
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            flash(
                'تم تدوين مذكرة التصوير. '
                + (
                    'تم إنشاء طلب أشعة مهيكل.'
                    if structured_ok
                    else 'يتوجه المريض للاستقبال لإنشاء زيارة لقسم الأشعة عند رغبة التنفيذ داخل المركز.'
                ),
                'info',
            )
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception:
        logging.exception('Error in radiology_request: %s')
        flash('حدث خطأ أثناء إنشاء طلب الأشعة', 'error')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))


@doctor_bp.route('/radiology-results/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def radiology_results(patient_id):
    """عرض نتائج الأشعة للطبيب — للإطلاع فقط"""
    try:
        patient = (
            db.session.execute(
                select(Patient).filter(Patient.id == patient_id, Patient.tenant_id == g.tenant_id)
            )
            .scalars()
            .first()
        )
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))

        rad_requests = (
            db.session.execute(
                select(RadiologyRequest)
                .filter(
                    RadiologyRequest.patient_id == patient_id,
                    RadiologyRequest.tenant_id == g.tenant_id,
                )
                .order_by(desc(RadiologyRequest.created_at))
            )
            .scalars()
            .all()
        )

        results = []
        if rad_requests:
            try:
                from models.radiology_result import RadiologyResult

                req_ids = [r.id for r in rad_requests]
                req_map = {r.id: r for r in rad_requests}
                all_results = (
                    db.session.execute(
                        select(RadiologyResult)
                        .filter(
                            RadiologyResult.request_id.in_(req_ids),
                            RadiologyResult.tenant_id == g.tenant_id,
                        )
                        .order_by(desc(RadiologyResult.created_at))
                    )
                    .scalars()
                    .all()
                )
                for r in all_results:
                    req = req_map.get(r.request_id)
                    results.append(
                        {
                            'modality': getattr(req, 'modality', 'غير محدد') if req else 'غير محدد',
                            'body_part': getattr(req, 'body_part', 'غير محدد')
                            if req
                            else 'غير محدد',
                            'findings': getattr(r, 'findings', None),
                            'impression': getattr(r, 'impression', None),
                            'status': getattr(r, 'status', 'PENDING'),
                            'is_critical': getattr(r, 'is_critical', False),
                            'recorded_at': getattr(r, 'created_at', None),
                            'radiologist': getattr(r, 'recorded_by', None),
                        }
                    )
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
        return render_template(
            'doctor/radiology_results.html',
            patient=patient,
            rad_requests=rad_requests,
            results=results,
        )
    except Exception:
        logging.exception('Error loading radiology results: %s')
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/radiology-requests')
@login_required
def radiology_requests():
    flash(
        'تم فصل طلبات الأشعة عن الطبيب. للاستعلام، يرجى مراجعة قسم الأشعة أو الاستقبال.', 'warning'
    )
    return redirect(url_for('doctor.patient_queue'))
