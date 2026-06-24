"""reports routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app_factory import db
import qrcode
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


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
        radiology_request = db.session.get(RadiologyRequest, request_id)
    if not radiology_request:
        radiology_request = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).first()
    radiology_result = radiology_request.results[0] if radiology_request and radiology_request.results else None
    recent_requests = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).limit(20).all()
    return render_template(
        'radiology/radiology_report_form.html',
        radiology_request=radiology_request,
        radiology_result=radiology_result,
        recent_requests=recent_requests,
        today=date.today().strftime('%Y-%m-%d')
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
        result = db.session.get(RadiologyResult, radiology_scan_id)
        if not result:
            req = db.session.get(RadiologyRequest, radiology_scan_id)
            if not req or not req.results:
                flash('نتيجة الأشعة غير موجودة', 'error')
                return redirect(url_for('radiology.reports'))
            result = req.results[0]
        payload = f"RAD|{result.id}|{result.patient_id}|{result.created_at.isoformat()}"
        img = qrcode.make(payload)
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
        return render_template('print/radiology_report.html', radiology_result=result, qr_data_uri=qr_data_uri)
    except Exception as e:
        logging.error(f"Error printing radiology report {radiology_scan_id}: {str(e)}")
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
        result = db.session.get(RadiologyResult, radiology_scan_id)
        if not result:
            req = db.session.get(RadiologyRequest, radiology_scan_id)
            if not req or not req.results:
                return jsonify({'success': False, 'message': 'نتيجة الأشعة غير موجودة'}), 404
            result = req.results[0]
        from app.integrations.printing.pdf import PDFReportPrinter
        printer = PDFReportPrinter()
        pdf_bytes = printer.generate_radiology_report(result)
        fname = f"radiology_report_{result.id}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=fname
        )
    except Exception as e:
        logging.error(f"Error generating radiology PDF {radiology_scan_id}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
