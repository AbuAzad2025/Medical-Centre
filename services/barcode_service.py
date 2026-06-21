"""Barcode generation and registration for lab samples."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone

import qrcode
from app_factory import db


def generate_lab_barcode(lab_request_id: int, patient_id: int) -> tuple[str, str]:
    """Generate a QR code for a lab request. Returns (barcode_value, base64_png)."""
    timestamp_hex = format(int(datetime.now(timezone.utc).timestamp() * 1000), 'x')
    barcode_value = f"LAB-{lab_request_id}-{patient_id}-{timestamp_hex}"

    qr = qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(barcode_value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    barcode_image = base64.b64encode(buf.getvalue()).decode('utf-8')

    return barcode_value, barcode_image


def register_in_barcode_registry(
    barcode_value: str,
    lab_request_id: int,
    generated_by_id: int | None = None,
    tenant_id: int | None = None,
):
    """Register a barcode in BarcodeRegistry as entity_type='SPECIMEN'."""
    from models.barcode_tracking import BarcodeRegistry

    registry = BarcodeRegistry(
        tenant_id=tenant_id,
        barcode_value=barcode_value,
        barcode_type='QR_CODE',
        entity_type='SPECIMEN',
        entity_id=lab_request_id,
        generated_by_id=generated_by_id,
        print_count=0,
        is_active=True,
    )
    db.session.add(registry)


def setup_barcode_for_lab_request(lab_request, current_user=None, tenant_id=None):
    """Generate QR barcode and register in BarcodeRegistry.
    Call after lab_request is flushed to DB (has id)."""
    barcode_val, b64_img = generate_lab_barcode(lab_request.id, lab_request.patient_id)
    lab_request.barcode = barcode_val
    lab_request.barcode_image = b64_img
    register_in_barcode_registry(
        barcode_value=barcode_val,
        lab_request_id=lab_request.id,
        generated_by_id=getattr(current_user, 'id', None) if current_user else None,
        tenant_id=tenant_id or getattr(lab_request, 'tenant_id', None),
    )
