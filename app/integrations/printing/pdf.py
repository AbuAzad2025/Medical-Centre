"""
PDF Report Printer — A4 medical reports with Arabic support
"""
import logging
import os
from io import BytesIO
from typing import Optional
from datetime import datetime, timezone, date

logger = logging.getLogger(__name__)

_FONT_PATH = r'C:\Windows\Fonts\trado.ttf'
_FONT_NAME = 'TraditionalArabic'


class PDFReportPrinter:
    """Generates A4 PDF reports using ReportLab with Arabic support."""

    def __init__(self):
        self._font_registered = False
        self._register_font()

    def _register_font(self):
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            if os.path.exists(_FONT_PATH):
                pdfmetrics.registerFont(TTFont(_FONT_NAME, _FONT_PATH))
                self._font_registered = True
        except Exception as e:
            logger.warning("Could not register Arabic font: %s", e)

    def _arabic(self, text: str) -> str:
        if not text or not self._font_registered:
            return text
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

    def _draw_header(self, c, width, title: str, subtitle: str = '', logo_path: str = ''):
        from reportlab.lib.units import mm
        y_top = 297 * mm - 15 * mm
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(logo_path, 15 * mm, y_top - 15 * mm, width=20 * mm, height=20 * mm, preserveAspectRatio=True)
            except Exception:
                pass
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 16)
        c.drawString(40 * mm if not logo_path else 42 * mm, y_top, self._arabic(title))
        if subtitle:
            c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 10)
            c.drawString(40 * mm, y_top - 6 * mm, self._arabic(subtitle))
        c.line(15 * mm, y_top - 13 * mm, width - 15 * mm, y_top - 13 * mm)

    def _draw_patient_info(self, c, x, y, patient, request=None):
        from reportlab.lib.units import mm
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 10)
        c.drawString(x, y, self._arabic('معلومات المريض:'))
        y -= 5 * mm
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 9)
        lines = []
        p = patient
        lines.append(f"الاسم: {getattr(p, 'full_name', '') or getattr(p, 'first_name_ar', '') or getattr(p, 'first_name', '')}")
        if hasattr(p, 'birth_date') and p.birth_date:
            b = p.birth_date
            if isinstance(b, str):
                from datetime import datetime as dt
                b = dt.strptime(b, '%Y-%m-%d').date()
            age = date.today().year - b.year - ((date.today().month, date.today().day) < (b.month, b.day))
            lines.append(f"العمر: {age} سنة")
        if hasattr(p, 'gender') and p.gender:
            g = 'ذكر' if str(p.gender).lower() in ('male', 'm', 'ذكر') else 'أنثى'
            lines.append(f"الجنس: {g}")
        if hasattr(p, 'id_number') and p.id_number:
            lines.append(f"رقم الهوية: {p.id_number}")
        elif hasattr(p, 'national_id') and p.national_id:
            lines.append(f"رقم الهوية: {p.national_id}")
        if hasattr(p, 'phone') and p.phone:
            lines.append(f"الهاتف: {p.phone}")
        col_x = x
        for line in lines:
            c.drawString(col_x, y, self._arabic(line))
            col_x += 45 * mm
            if col_x > 170 * mm:
                col_x = x
                y -= 4.5 * mm
        y -= 7 * mm
        if request:
            c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 9)
            req_lines = []
            if hasattr(request, 'request_number') and request.request_number:
                req_lines.append(f"رقم الطلب: {request.request_number}")
            elif hasattr(request, 'id'):
                req_lines.append(f"رقم الطلب: #{request.id}")
            if hasattr(request, 'created_at') and request.created_at:
                ts = request.created_at
                if hasattr(ts, 'strftime'):
                    req_lines.append(f"التاريخ: {ts.strftime('%Y-%m-%d')}")
            if hasattr(request, 'status') and request.status:
                req_lines.append(f"الحالة: {request.status}")
            col_x = x
            for line in req_lines:
                c.drawString(col_x, y, self._arabic(line))
                col_x += 50 * mm
        return y - 5 * mm

    def _draw_lab_results(self, c, x, y, results, width):
        from reportlab.lib.units import mm
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 10)
        c.drawString(x, y, self._arabic('نتائج التحاليل:'))
        y -= 6 * mm
        cols = [x, x + 50 * mm, x + 100 * mm, x + 130 * mm]
        col_widths = [48 * mm, 48 * mm, 28 * mm, 35 * mm]
        headers = ['اسم التحليل', 'النتيجة', 'الوحدة', 'النطاق الطبيعي']
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 8)
        for i, h in enumerate(headers):
            c.drawString(cols[i], y, self._arabic(h))
        y -= 4 * mm
        c.line(x, y, x + 155 * mm, y)
        y -= 3 * mm
        if not results:
            c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 9)
            c.drawString(x, y, self._arabic('لا توجد نتائج'))
            return y - 5 * mm
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 8)
        for r in results:
            if y < 30 * mm:
                c.showPage()
                y = 297 * mm - 25 * mm
                self._draw_header(c, width, 'نتائج التحاليل - تابع')
                c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 8)
            vals = [
                getattr(r, 'test_name', '') or '',
                getattr(r, 'value', '') or '',
                getattr(r, 'unit', '') or '',
                getattr(r, 'reference_range', '') or '',
            ]
            for i, v in enumerate(vals):
                c.drawString(cols[i], y, self._arabic(v))
            y -= 5 * mm
        return y - 3 * mm

    def _draw_radiology_section(self, c, x, y, label: str, text: str):
        from reportlab.lib.units import mm
        if not text:
            return y
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 10)
        c.drawString(x, y, self._arabic(f'{label}:'))
        y -= 5 * mm
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 9)
        import textwrap
        max_chars = 90
        wrapped = textwrap.wrap(text, width=max_chars)
        for line in wrapped:
            if y < 25 * mm:
                c.showPage()
                y = 297 * mm - 25 * mm
            c.drawString(x + 5 * mm, y, self._arabic(line))
            y -= 4.5 * mm
        return y - 4 * mm

    def _draw_qr(self, c, x, y, data: str, size=20):
        from reportlab.lib.units import mm
        try:
            import qrcode
            from io import BytesIO as _Bio
            img = qrcode.make(data)
            buf = _Bio()
            img.save(buf, format='PNG')
            buf.seek(0)
            c.drawImage(buf, x, y - size * mm, width=size * mm, height=size * mm)
        except Exception:
            pass

    def _draw_footer(self, c, width, y_pos=None):
        from reportlab.lib.units import mm
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 7)
        text = self._arabic(f'تم الإنشاء: {ts}')
        c.drawString(15 * mm, 10 * mm, text)
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 7)
        c.drawRightString(width - 15 * mm, 10 * mm, self._arabic('تقرير طبي - نظام الإدارة الطبية'))

    def generate_lab_report(self, lab_request) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError:
            return b"%PDF-1.4 placeholder"
        width, height = A4
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        y = self._initial_y(c, width, height, 'تقرير نتائج التحاليل', lab_request)
        y = self._draw_patient_info(c, 15 * mm, y, getattr(lab_request, 'patient', None), lab_request)
        y = self._draw_lab_results(c, 15 * mm, y, getattr(lab_request, 'results', []) or [], width)
        if getattr(lab_request, 'notes', ''):
            y = self._draw_radiology_section(c, 15 * mm, y, 'ملاحظات', lab_request.notes)
        payload = f"LAB|{lab_request.id}|{getattr(lab_request, 'patient_id', '')}|{getattr(lab_request, 'created_at', '')}"
        self._draw_qr(c, width - 30 * mm, y, payload)
        self._draw_footer(c, width)
        c.save()
        buffer.seek(0)
        return buffer.read()

    def generate_radiology_report(self, radiology_result) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError:
            return b"%PDF-1.4 placeholder"
        width, height = A4
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        req = getattr(radiology_result, 'request', None)
        y = self._initial_y(c, width, height, 'تقرير الأشعة', req)
        y = self._draw_patient_info(c, 15 * mm, y, getattr(radiology_result, 'patient', None), req)
        if req:
            modality_text = ''
            if getattr(req, 'modality', ''):
                modality_text += f"نوع الفحص: {req.modality}"
            if getattr(req, 'body_part', ''):
                if modality_text:
                    modality_text += ' | '
                modality_text += f"المنطقة: {req.body_part}"
            if modality_text:
                c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 9)
                c.drawString(15 * mm, y, self._arabic(modality_text))
                y -= 6 * mm
        y = self._draw_radiology_section(c, 15 * mm, y, 'النتائج', getattr(radiology_result, 'findings', ''))
        y = self._draw_radiology_section(c, 15 * mm, y, 'الانطباع', getattr(radiology_result, 'impression', ''))
        y = self._draw_radiology_section(c, 15 * mm, y, 'التوصيات', getattr(radiology_result, 'notes', ''))
        payload = f"RAD|{radiology_result.id}|{getattr(radiology_result, 'patient_id', '')}|{getattr(radiology_result, 'created_at', '')}"
        self._draw_qr(c, width - 30 * mm, y, payload)
        self._draw_footer(c, width)
        c.save()
        buffer.seek(0)
        return buffer.read()

    def _initial_y(self, c, width, height, title: str, request_obj=None):
        from reportlab.lib.units import mm
        tenant_name = ''
        tenant_logo = ''
        if request_obj and hasattr(request_obj, 'tenant_id') and request_obj.tenant_id:
            try:
                from app.core.tenant.models import Tenant
                t = Tenant.query.get(request_obj.tenant_id)
                if t:
                    tenant_name = t.name or t.name_ar or ''
                    tenant_logo = t.logo_url or ''
            except Exception:
                pass
        self._draw_header(c, width, title, tenant_name, tenant_logo)
        return 297 * mm - 32 * mm

    def generate_report(self, title: str, patient_info: dict, sections: list[dict]) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError:
            logger.warning("reportlab not installed; returning empty PDF placeholder")
            return b"%PDF-1.4 placeholder"

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 16)
        c.drawString(20 * mm, height - 20 * mm, self._arabic(title))
        c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 10)
        y = height - 30 * mm
        for k, v in patient_info.items():
            c.drawString(20 * mm, y, f"{k}: {self._arabic(str(v))}")
            y -= 5 * mm

        for section in sections:
            y -= 5 * mm
            c.setFont(_FONT_NAME if self._font_registered else 'Helvetica-Bold', 12)
            c.drawString(20 * mm, y, self._arabic(section.get("heading", "")))
            y -= 5 * mm
            c.setFont(_FONT_NAME if self._font_registered else 'Helvetica', 10)
            for line in section.get("lines", []):
                c.drawString(25 * mm, y, self._arabic(line))
                y -= 4 * mm
                if y < 30 * mm:
                    c.showPage()
                    y = height - 20 * mm

        self._draw_footer(c, width)
        c.save()
        buffer.seek(0)
        return buffer.read()
