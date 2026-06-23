"""Print document header/footer resolution — tenant branding (phase 5/9)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from app.shared.branding_context import get_branding_row, resolve_ui_context

PLATFORM_COPYRIGHT = 'شركة ازاد للأنظمة الذكية'

DOC_TYPES = ('invoice', 'receipt', 'prescription', 'report', 'queue_ticket', 'lab_result', 'radiology_report', 'emergency_report')

_HEADER_FIELDS = {
    'invoice': 'invoice_header_html',
    'receipt': 'receipt_header_html',
    'prescription': 'prescription_header_html',
    'report': 'report_header_html',
    'queue_ticket': 'report_header_html',
    'lab_result': 'report_header_html',
    'radiology_report': 'report_header_html',
    'emergency_report': 'report_header_html',
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


def resolve_print_context(doc_type: str, branding=None) -> Dict[str, Any]:
    """Full print template context — tenant header/footer + platform stamp (§34.10)."""
    doc_type = (doc_type or 'report').lower()
    if doc_type not in _HEADER_FIELDS:
        doc_type = 'report'

    if branding is None:
        branding = get_branding_row()

    header_html, footer_html = resolve_print_slots(doc_type, branding)
    ui = resolve_ui_context()

    return {
        'doc_type': doc_type,
        'header_html': header_html,
        'footer_html': footer_html,
        'show_platform_stamp': True,
        'copyright_year': datetime.now().year,
        'platform_copyright_name': PLATFORM_COPYRIGHT,
        'primary_color': ui.get('primary_color', '#0f4c81'),
    }
