"""reports routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from services.lab_service import lab_service
from app_factory import db
import qrcode
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


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
        lab_request = db.session.get(LabRequest, request_id)
    if not lab_request:
        lab_request = LabRequest.query.order_by(LabRequest.created_at.desc()).first()
    recent_requests = LabRequest.query.order_by(LabRequest.created_at.desc()).limit(20).all()
    return render_template('lab/report.html', lab_request=lab_request, recent_requests=recent_requests, today=date.today().strftime('%Y-%m-%d'))

@lab_bp.route('/print_request/<int:id>')
@login_required
@role_required('lab', 'admin', 'manager')
def print_request(id: int):
    """طباعة تقرير طلب المختبر"""
    
    try:
        lab_request = db.session.get(LabRequest, id)
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
        payload = f"LAB|{lab_request.id}|{lab_request.patient_id}|{lab_request.created_at.isoformat()}"
        img = qrcode.make(payload)
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
        printed_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        html = render_template('print/lab_result.html', lab_request=lab_request, qr_data_uri=qr_data_uri, age_years=age_years, printed_at=printed_at)
        resp = make_response(html)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        return resp
    except Exception as e:
        logging.error(f"Error printing lab request {id}: {str(e)}")
        flash('حدث خطأ في طباعة تقرير المختبر', 'error')
        return redirect(url_for('lab.requests'))


@lab_bp.route('/print_request/<int:id>/pdf')
@login_required
@role_required('lab', 'admin', 'manager')
def print_request_pdf(id: int):
    """تنزيل تقرير طلب المختبر كـ PDF"""
    try:
        lab_request = db.session.get(LabRequest, id)
        if not lab_request:
            return jsonify({'success': False, 'message': 'طلب المختبر غير موجود'}), 404
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf_bytes = printer.generate_lab_report(lab_request)
        fname = f"lab_report_{lab_request.request_number or lab_request.id}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=fname
        )
    except Exception as e:
        logging.error(f"Error generating lab PDF {id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
