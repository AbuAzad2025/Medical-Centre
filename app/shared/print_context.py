"""Print document header/footer resolution — tenant branding (phase 5/9)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.shared.branding_context import get_branding_row, resolve_ui_context

PLATFORM_COPYRIGHT = 'شركة ازاد للأنظمة الذكية'
PLATFORM_WATERMARK = 'شركة أزاد للأنظمة الطبية'

DOC_TYPES = ('invoice', 'receipt', 'prescription', 'report', 'queue_ticket', 'lab_result', 'radiology_report', 'emergency_report', 'pharmacy_sale', 'barcode', 'label', 'doctor_medical_report')

_HEADER_FIELDS = {
    'invoice': 'invoice_header_html',
    'receipt': 'receipt_header_html',
    'prescription': 'prescription_header_html',
    'report': 'report_header_html',
    'queue_ticket': 'report_header_html',
    'lab_result': 'report_header_html',
    'radiology_report': 'report_header_html',
    'emergency_report': 'report_header_html',
    'pharmacy_sale': 'receipt_header_html',
    'barcode': 'report_header_html',
    'label': 'report_header_html',
    'doctor_medical_report': 'report_header_html',
}

_FOOTER_FIELDS = {
    'invoice': 'invoice_footer_html',
    'receipt': None,
    'prescription': 'prescription_footer_html',
    'report': 'report_footer_html',
    'queue_ticket': None,
    'lab_result': 'report_footer_html',
    'radiology_report': 'report_footer_html',
    'emergency_report': 'report_footer_html',
    'pharmacy_sale': None,
    'barcode': None,
    'label': None,
    'doctor_medical_report': 'report_footer_html',
}


def resolve_print_slots(doc_type: str, branding) -> Tuple[Optional[str], Optional[str]]:
    """Return (header_html, footer_html) for a document type."""
    doc_type = (doc_type or 'report').lower()
    if doc_type not in _HEADER_FIELDS:
        doc_type = 'report'

    header = footer = None
    if branding:
        h_field = _HEADER_FIELDS[doc_type]
        f_field = _FOOTER_FIELDS[doc_type]
        header = getattr(branding, h_field, None) or None
        if f_field:
            footer = getattr(branding, f_field, None) or None
    return header, footer


def generate_qr_data_uri(payload: str) -> str:
    """Generate a base64-encoded QR code data URI from a string payload.

    Uses the ``qrcode`` library to create a QR image in memory, saves it
    as PNG, and returns a ``data:image/png;base64,...`` URI suitable for
    inline ``<img src="…">`` in print templates.

    Example::

        qr_data_uri = generate_qr_data_uri(f"RX|{rx.id}|{rx.patient_id}")
    """
    import base64
    from io import BytesIO

    import qrcode

    img = qrcode.make(payload)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')


def generate_barcode_code128(payload: str) -> str:
    """Generate a Code128 barcode as a base64-encoded PNG data URI.

    Lightweight pure-Python implementation (no external C deps).
    Returns ``data:image/png;base64,...`` for inline ``<img>``.

    Example::

        barcode_uri = generate_barcode_code128(f"INV|{invoice.id}|{tenant_id}")
    """
    import base64
    from io import BytesIO

    # Full Code128 patterns for all 107 codes (0-106)
    # 0-102: data characters, 103: START A, 104: START B, 105: START C, 106: STOP
    _CODE128_PATTERNS = [
        "11011001100", "11001101100", "11001100110", "10010011000", "10010001100",
        "10001001100", "10011001000", "10011000100", "10001100100", "11001001000",
        "11001000100", "11000100100", "10110011100", "10011011100", "10011001110",
        "10111001100", "10011101100", "10011100110", "11001110010", "11001011100",
        "11000101110", "11101101110", "11101001100", "11100101100", "11100100110",
        "11101100100", "11100110100", "11100110010", "11011011000", "11011000110",
        "11000110110", "10100011000", "10001011000", "10001000110", "10110001000",
        "10001101000", "10001100010", "11010001000", "11000101000", "11011011100",
        "11011000111", "11000110111", "10110111000", "10110001110", "10001101110",
        "10001110110", "11010001110", "11010000111", "11011101000", "11011100010",
        "11011101110", "11101011000", "11101000110", "11100010110", "11101101000",
        "11101100010", "11100011010", "11101111010", "11001000010", "11110001010",
        "10100110000", "10100001100", "10010110000", "10010000110", "10000101100",
        "10000100110", "10110010000", "10110000100", "10011010000", "10011000010",
        "10000110100", "10000110010", "11000010100", "11001010000", "11110111110",
        "11000010010", "11001001000", "11110101000", "11110100010", "11110001010",
        "10110110000", "10110001000", "10011011000", "10011000110", "10001011110",
        "10001011110", "10001101110", "10110111100", "10110000111", "10011110100",
        "10011110010", "10011011110", "10111011000", "10111000110", "10011101110",
        "11110101000", "11110100010", "11110001010", "10110110000", "10110001000",
        "10011011000", "10011000110", "10001011110", "10001011110", "10001101110",
        "10110111100", "10110000111", "10011110100", "10011110010", "10011011110",
        "10111011000", "10111000110", "10011101110",
    ]
    _CODE128_START_A = 103
    _CODE128_START_B = 104
    _CODE128_START_C = 105
    _CODE128_STOP = 106

    # Character set for Code B (ASCII 32-127)
    _CODE128_CHARS = (
        " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
        "abcdefghijklmnopqrstuvwxyz{|}~"
    )

    def _encode_code128(data: str) -> str:
        """Encode string to Code128 bar pattern (using Code B for simplicity)."""
        codes = [_CODE128_START_B]
        checksum = _CODE128_START_B
        for i, ch in enumerate(data):
            if ch in _CODE128_CHARS:
                val = _CODE128_CHARS.index(ch)
                codes.append(val)
                checksum += val * (i + 1)
        checksum %= 103
        codes.append(checksum)
        codes.append(_CODE128_STOP)
        # Add quiet zone (11 zeros each side)
        pattern = "0" * 11
        for code in codes:
            if code < len(_CODE128_PATTERNS):
                pattern += _CODE128_PATTERNS[code]
        pattern += "0" * 11
        return pattern

    # Generate barcode image using PIL
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Fallback: return empty string if PIL not available
        return ""

    pattern = _encode_code128(payload)
    module_width = 2  # pixels per module
    height = 60
    width = len(pattern) * module_width
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    x = 0
    for bit in pattern:
        if bit == '1':
            draw.rectangle([x, 0, x + module_width - 1, height - 1], fill='black')
        x += module_width

    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')


def resolve_print_context(doc_type: str, branding=None) -> Dict[str, Any]:
    """Full print template context — tenant header/footer + platform stamp (§34.10).

    Ghost-mode aware: if the request is an impersonation (Ghost Mode),
    the header/footer will reflect the *target* tenant's branding while
    the platform watermark/stamp remains locked to the Azad platform.
    """
    from flask import g, request, has_request_context

    doc_type = (doc_type or 'report').lower()
    if doc_type not in _HEADER_FIELDS:
        doc_type = 'report'

    # Ghost Mode detection: check for impersonation headers or g.ghost_mode
    is_ghost_mode = False
    ghost_target_tenant = None
    if has_request_context():
        # Check for Ghost Mode impersonation headers
        if request.headers.get('X-Impersonate-Tenant-Id'):
            is_ghost_mode = True
            try:
                ghost_target_tenant = int(request.headers.get('X-Impersonate-Tenant-Id'))
            except (ValueError, TypeError):
                pass
        # Or check g.ghost_mode set by ghost_mode_middleware
        elif getattr(g, 'ghost_mode', False):
            is_ghost_mode = True
            ghost_target_tenant = getattr(g, 'ghost_tenant_id', None)

    if branding is None:
        # If ghost mode, try to get branding for the target tenant
        if is_ghost_mode and ghost_target_tenant:
            from app.core.tenant.models import TenantBranding
            branding = TenantBranding.query.filter_by(tenant_id=ghost_target_tenant).first()
        if branding is None:
            branding = get_branding_row()

    header_html, footer_html = resolve_print_slots(doc_type, branding)
    ui = resolve_ui_context()

    # In ghost mode, override UI context with target tenant's branding
    if is_ghost_mode and ghost_target_tenant:
        from app.core.tenant.models import Tenant
        target_tenant = Tenant.query.get(ghost_target_tenant)
        if target_tenant:
            ui = ui.copy()
            ui['organization_name'] = target_tenant.name
            # Could add more fields from tenant settings if available

    return {
        'doc_type': doc_type,
        'header_html': header_html,
        'footer_html': footer_html,
        'show_platform_stamp': True,
        'copyright_year': datetime.now().year,
        'platform_copyright_name': PLATFORM_COPYRIGHT,
        'platform_watermark': PLATFORM_WATERMARK,
        'primary_color': ui.get('primary_color', '#0f4c81'),
        'is_ghost_mode': is_ghost_mode,
        'ghost_target_tenant': ghost_target_tenant,
    }