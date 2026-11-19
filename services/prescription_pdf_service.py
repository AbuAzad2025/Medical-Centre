"""Server-side PDF generation for printable clinical documents.

The in-app browser used by OpenCode cannot complete a native ``window.print()``
(no PDF / preview is produced), so clinical documents also get a real PDF
endpoint built with reportlab. Arabic text is reshaped + bidi-reordered so it
renders correctly with the bundled Tajawal TTF font.
"""

from __future__ import annotations

import io
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_FONT_DIR = Path(__file__).resolve().parents[1] / 'static' / 'vendor' / 'fonts'
_FONT_REGULAR = _FONT_DIR / 'Tajawal-Regular.ttf'
_FONT_BOLD = _FONT_DIR / 'Tajawal-Bold.ttf'
_FONT_NAME = 'Tajawal'
_FONT_NAME_BOLD = 'Tajawal-Bold'

_registered = False


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    if _FONT_REGULAR.exists():
        pdfmetrics.registerFont(TTFont(_FONT_NAME, str(_FONT_REGULAR)))
    if _FONT_BOLD.exists():
        pdfmetrics.registerFont(TTFont(_FONT_NAME_BOLD, str(_FONT_BOLD)))
    # Map the family so reportlab can resolve <b> and bold styles to the
    # registered TTF without trying to guess an installed system family.
    if _FONT_REGULAR.exists():
        from reportlab.pdfbase.pdfmetrics import registerFontFamily

        registerFontFamily(
            _FONT_NAME,
            normal=_FONT_NAME,
            bold=_FONT_NAME_BOLD if _FONT_BOLD.exists() else _FONT_NAME,
            italic=_FONT_NAME,
            boldItalic=_FONT_NAME_BOLD if _FONT_BOLD.exists() else _FONT_NAME,
        )
    _registered = True


def ar(text) -> str:
    """Reshape + bidi-reorder Arabic (and mixed) text for reportlab."""
    if text is None:
        return ''
    s = str(text)
    if not any('\u0600' <= ch <= '\u06ff' for ch in s):
        return s
    try:
        shaped = arabic_reshaper.reshape(s)
        return get_display(shaped)
    except Exception:
        return s


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'ArTitle',
            parent=base['Title'],
            fontName=_FONT_NAME_BOLD,
            fontSize=18,
            leading=26,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0f4c81'),
        ),
        'org': ParagraphStyle(
            'ArOrg',
            parent=base['Normal'],
            fontName=_FONT_NAME_BOLD,
            fontSize=11,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#334155'),
        ),
        'meta': ParagraphStyle(
            'ArMeta',
            parent=base['Normal'],
            fontName=_FONT_NAME,
            fontSize=9,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#475569'),
        ),
        'label': ParagraphStyle(
            'ArLabel',
            parent=base['Normal'],
            fontName=_FONT_NAME_BOLD,
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#0f4c81'),
        ),
        'value': ParagraphStyle(
            'ArValue',
            parent=base['Normal'],
            fontName=_FONT_NAME,
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#1e293b'),
        ),
        'th': ParagraphStyle(
            'ArTh',
            parent=base['Normal'],
            fontName=_FONT_NAME_BOLD,
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        'td': ParagraphStyle(
            'ArTd',
            parent=base['Normal'],
            fontName=_FONT_NAME,
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#1e293b'),
        ),
        'small': ParagraphStyle(
            'ArSmall',
            parent=base['Normal'],
            fontName=_FONT_NAME,
            fontSize=8,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#64748b'),
        ),
    }


def build_prescription_pdf(
    prescription, organization_name: str = '', qr_png_bytes: bytes | None = None
) -> bytes:
    """Return a PDF for a single prescription as bytes."""
    _register_fonts()
    s = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f'Prescription {prescription.prescription_number or prescription.id}',
    )
    story = []

    org = organization_name or 'AZAD Medical'
    story.append(Paragraph(ar(org), s['org']))
    story.append(Paragraph(ar('روشتة طبية'), s['title']))
    story.append(Spacer(1, 4))

    meta_parts = [
        f'رقم الروشتة: {prescription.prescription_number or prescription.id}',
        f'التاريخ: {prescription.created_at.strftime("%Y-%m-%d %H:%M") if prescription.created_at else "—"}',
        f'الحالة: {prescription.status or "—"}',
    ]
    story.append(Paragraph(ar('  |  '.join(meta_parts)), s['meta']))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#0f4c81')))
    story.append(Spacer(1, 8))

    patient = prescription.patient
    doctor = prescription.doctor
    info_rows = [
        [
            Paragraph(ar('المريض'), s['label']),
            Paragraph(ar(patient.full_name if patient else '—'), s['value']),
            Paragraph(ar('الهوية'), s['label']),
            Paragraph(ar(patient.national_id or '—') if patient else '—', s['value']),
        ],
        [
            Paragraph(ar('الهاتف'), s['label']),
            Paragraph(ar(patient.phone or '—') if patient else '—', s['value']),
            Paragraph(ar('الجنس'), s['label']),
            Paragraph(ar(patient.gender or '—') if patient else '—', s['value']),
        ],
        [
            Paragraph(ar('الطبيب'), s['label']),
            Paragraph(ar(doctor.full_name if doctor else '—'), s['value']),
            Paragraph(ar('الترخيص'), s['label']),
            Paragraph(
                ar(getattr(doctor, 'license_number', None) or '—') if doctor else '—', s['value']
            ),
        ],
    ]
    info = Table(info_rows, colWidths=[24 * mm, 58 * mm, 24 * mm, 58 * mm])
    info.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(info)
    story.append(Spacer(1, 10))

    if prescription.diagnosis:
        story.append(Paragraph(ar('التشخيص'), s['label']))
        story.append(Paragraph(ar(prescription.diagnosis), s['value']))
        story.append(Spacer(1, 8))

    data = [
        [
            Paragraph(ar('الدواء'), s['th']),
            Paragraph(ar('الجرعة'), s['th']),
            Paragraph(ar('التكرار'), s['th']),
            Paragraph(ar('المدة'), s['th']),
            Paragraph(ar('التعليمات'), s['th']),
        ]
    ]
    for item in prescription.items.all():
        med = item.medication
        med_txt = med.trade_name if med else '—'
        if med and med.strength:
            med_txt += f' {med.strength}'
        parts = (item.dosage or '').split(' | ', 1)
        data.append(
            [
                Paragraph(ar(med_txt), s['td']),
                Paragraph(ar(parts[0] if parts and parts[0] else '—'), s['td']),
                Paragraph(ar(parts[1] if len(parts) > 1 else '—'), s['td']),
                Paragraph(ar(item.duration_days or '—'), s['td']),
                Paragraph(ar(item.instructions or 'اتبع تعليمات الطبيب'), s['td']),
            ]
        )
    table = Table(data, colWidths=[46 * mm, 26 * mm, 30 * mm, 20 * mm, 42 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f4c81')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 10))

    if prescription.notes:
        story.append(Paragraph(ar('تعليمات إضافية'), s['label']))
        story.append(Paragraph(ar(prescription.notes), s['value']))
        story.append(Spacer(1, 12))

    # QR verification code (centred)
    if qr_png_bytes:
        try:
            from reportlab.lib.utils import ImageReader

            qr = ImageReader(io.BytesIO(qr_png_bytes))
            qr_table = Table([[qr]], colWidths=[26 * mm], rowHeights=[26 * mm])
            qr_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            story.append(qr_table)
            story.append(Paragraph(ar('رمز التحقق'), s['small']))
        except Exception:
            pass

    story.append(Spacer(1, 10))
    sig = Table(
        [
            [Paragraph(ar('توقيع الطبيب'), s['small']), Paragraph(ar('ختم المركز'), s['small'])],
        ],
        colWidths=[85 * mm, 85 * mm],
    )
    sig.setStyle(
        TableStyle(
            [
                ('LINEABOVE', (0, 0), (0, 0), 0.6, colors.HexColor('#94a3b8')),
                ('LINEABOVE', (1, 0), (1, 0), 0.6, colors.HexColor('#94a3b8')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(sig)
    story.append(Spacer(1, 8))
    story.append(Paragraph(ar('هذه الروشة صالحة لمدة 30 يوماً من تاريخ الإصدار'), s['small']))

    doc.build(story)
    return buf.getvalue()


def make_qr_png(payload: str) -> bytes | None:
    """Return a PNG QR code for the given payload, or None on error."""
    try:
        import qrcode

        img = qrcode.make(payload)
        out = io.BytesIO()
        img.save(out, format='PNG')
        return out.getvalue()
    except Exception:
        return None
