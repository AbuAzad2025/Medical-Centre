"""reports routes - extracted from monolithic lab.py"""

import logging
from datetime import UTC, date, datetime
from io import BytesIO

# Imports
from flask import (
    flash,
    g,
    jsonify,
    make_response,
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
from models.lab_request import LabRequest
from routes.lab import lab_bp
from utils.decorators import role_required

# =============================================
# REPORTS ROUTES
# =============================================


@lab_bp.route('/reports')
@login_required
@role_required('lab', 'admin', 'manager')
def reports():
    """تقارير المختبر"""

    request_id = request.args.get('request_id', type=int)
    lab_request = None
    if request_id:
        lab_request = (
            db.session.execute(
                select(LabRequest).filter(
                    LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )
    if not lab_request:
        lab_request = (
            db.session.execute(select(LabRequest).order_by(LabRequest.created_at.desc()))
            .scalars()
            .first()
        )
    recent_requests = (
        db.session.execute(select(LabRequest).order_by(LabRequest.created_at.desc()).limit(20))
        .scalars()
        .all()
    )
    return render_template(
        'lab/report.html',
        lab_request=lab_request,
        recent_requests=recent_requests,
        today=date.today().strftime('%Y-%m-%d'),
    )


@lab_bp.route('/print_request/<int:id>')
@login_required
@role_required('lab', 'admin', 'manager')
def print_request(id: int):
    """طباعة تقرير طلب المختبر"""

    try:
        lab_request = (
            db.session.execute(
                select(LabRequest).filter(LabRequest.id == id, LabRequest.tenant_id == g.tenant_id)
            )
            .scalars()
            .first()
        )
        if not lab_request:
            flash('طلب المختبر غير موجود', 'error')
            return redirect(url_for('lab.requests'))
        age_years = None
        try:
            if lab_request.patient and lab_request.patient.birth_date:
                b = lab_request.patient.birth_date
                today = date.today()
                age_years = today.year - b.year - ((today.month, today.day) < (b.month, b.day))
        except Exception:
            age_years = None
        qr_data_uri = generate_qr_data_uri(
            f'LAB|{lab_request.id}|{lab_request.patient_id}|{lab_request.created_at.isoformat()}'
        )
        printed_at = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
        html = render_template(
            'print/lab_result.html',
            lab_request=lab_request,
            qr_data_uri=qr_data_uri,
            age_years=age_years,
            printed_at=printed_at,
        )
        resp = make_response(html)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    except Exception:
        logging.exception('Error printing lab request {id}: %s')
        flash('حدث خطأ في طباعة تقرير المختبر', 'error')
        return redirect(url_for('lab.requests'))


@lab_bp.route('/print_request/<int:id>/pdf')
@login_required
@role_required('lab', 'admin', 'manager')
def print_request_pdf(id: int):
    """تنزيل تقرير طلب المختبر كـ PDF"""
    try:
        lab_request = (
            db.session.execute(
                select(LabRequest).filter(LabRequest.id == id, LabRequest.tenant_id == g.tenant_id)
            )
            .scalars()
            .first()
        )
        if not lab_request:
            return jsonify({'success': False, 'message': 'طلب المختبر غير موجود'}), 404
        from app.integrations.printing.pdf import PDFReportPrinter

        printer = PDFReportPrinter()
        pdf_bytes = printer.generate_lab_report(lab_request)
        fname = f'lab_report_{lab_request.request_number or lab_request.id}.pdf'
        return send_file(
            BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=fname
        )
    except Exception as e:
        logging.exception('Error generating lab PDF {id}: %s')
        return jsonify({'success': False, 'message': str(e)}), 500
