"""reports routes - extracted from monolithic radiology.py"""

import logging
from datetime import date
from io import BytesIO

# Imports
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.print_context import generate_qr_data_uri
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from routes.radiology import radiology_bp
from utils.decorators import role_required

# =============================================
# REPORTS ROUTES
# =============================================


@radiology_bp.route('/reports')
@login_required
@role_required('radiology', 'manager')
def reports():
    """تقارير الأشعة"""

    request_id = request.args.get('request_id', type=int)
    radiology_request = None
    if request_id:
        radiology_request = (
            db.session.execute(
                select(RadiologyRequest).filter(
                    RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )
    if not radiology_request:
        radiology_request = (
            db.session.execute(
                select(RadiologyRequest).order_by(RadiologyRequest.created_at.desc())
            )
            .scalars()
            .first()
        )
    radiology_result = (
        radiology_request.results[0] if radiology_request and radiology_request.results else None
    )
    recent_requests = (
        db.session.execute(
            select(RadiologyRequest).order_by(RadiologyRequest.created_at.desc()).limit(20)
        )
        .scalars()
        .all()
    )
    return render_template(
        'radiology/radiology_report_form.html',
        radiology_request=radiology_request,
        radiology_result=radiology_result,
        recent_requests=recent_requests,
        today=date.today().strftime('%Y-%m-%d'),
    )


@radiology_bp.route('/print_report/<int:radiology_scan_id>', methods=['GET'])
@login_required
@role_required('radiology', 'manager')
def print_report(radiology_scan_id=None):
    """طباعة تقرير الأشعة"""

    try:
        if radiology_scan_id is None:
            flash('المعرف غير محدد', 'error')
            return redirect(url_for('radiology.reports'))
        result = (
            db.session.execute(
                select(RadiologyResult).filter(
                    RadiologyResult.id == radiology_scan_id,
                    RadiologyResult.tenant_id == g.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not result:
            req = (
                db.session.execute(
                    select(RadiologyRequest).filter(
                        RadiologyRequest.id == radiology_scan_id,
                        RadiologyRequest.tenant_id == g.tenant_id,
                    )
                )
                .scalars()
                .first()
            )
            if not req or not req.results:
                flash('نتيجة الأشعة غير موجودة', 'error')
                return redirect(url_for('radiology.reports'))
            result = req.results[0]
        qr_data_uri = generate_qr_data_uri(
            f'RAD|{result.id}|{result.patient_id}|{result.created_at.isoformat()}'
        )
        return render_template(
            'print/radiology_report.html', radiology_result=result, qr_data_uri=qr_data_uri
        )
    except Exception:
        logging.exception("Error printing radiology report {radiology_scan_id}: %s")
        flash('حدث خطأ في طباعة تقرير الأشعة', 'error')
        return redirect(url_for('radiology.reports'))


@radiology_bp.route('/print_report/<int:radiology_scan_id>/pdf', methods=['GET'])
@login_required
@role_required('radiology', 'manager')
def print_report_pdf(radiology_scan_id=None):
    """تنزيل تقرير الأشعة كـ PDF"""
    try:
        if radiology_scan_id is None:
            return jsonify({'success': False, 'message': 'المعرف غير محدد'}), 400
        result = (
            db.session.execute(
                select(RadiologyResult).filter(
                    RadiologyResult.id == radiology_scan_id,
                    RadiologyResult.tenant_id == g.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not result:
            req = (
                db.session.execute(
                    select(RadiologyRequest).filter(
                        RadiologyRequest.id == radiology_scan_id,
                        RadiologyRequest.tenant_id == g.tenant_id,
                    )
                )
                .scalars()
                .first()
            )
            if not req or not req.results:
                return jsonify({'success': False, 'message': 'نتيجة الأشعة غير موجودة'}), 404
            result = req.results[0]
        from app.integrations.printing.pdf import PDFReportPrinter

        printer = PDFReportPrinter()
        pdf_bytes = printer.generate_radiology_report(result)
        fname = f'radiology_report_{result.id}.pdf'
        return send_file(
            BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=fname
        )
    except Exception as e:
        logging.exception("Error generating radiology PDF {radiology_scan_id}: %s")
        return jsonify({'success': False, 'message': str(e)}), 500
