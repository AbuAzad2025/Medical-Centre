"""Print document header/footer resolution — tenant branding (phase 5)."""
from __future__ import annotations

from typing import Optional, Tuple

DOC_TYPES = ('invoice', 'receipt', 'prescription', 'report')

_HEADER_FIELDS = {
    'invoice': 'invoice_header_html',
    'receipt': 'receipt_header_html',
    'prescription': 'prescription_header_html',
    'report': 'report_header_html',
}

_FOOTER_FIELDS = {
    'invoice': 'invoice_footer_html',
    'receipt': None,
    'prescription': 'prescription_footer_html',
    'report': 'report_footer_html',
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
