"""
PharmacySaleService - manages pharmacy sales and dispensing workflow
"""

from datetime import UTC, datetime
from uuid import uuid4

from flask import g
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.shared.enums import PrescriptionState
from utils.db_safety import safe_commit


class PharmacySaleService:
    """Manages pharmacy sale processing and dispensing."""

    @staticmethod
    def fetch_prescription_for_pos_cart(prescription_id: int, tenant_id: int) -> dict:
        """
        Read-only preview: load prescription items with medications for POS checkout.

        Uses two-step query to avoid N+1. Does NOT modify any state.
        Returns cart payload with medication details, prices, and stock info.
        """
        from models.medication import Prescription, PrescriptionItem

        prescription = (
            db.session.execute(
                select(Prescription).filter(
                    Prescription.id == prescription_id,
                    Prescription.tenant_id == tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not prescription:
            return {'error': 'Prescription not found'}

        if prescription.status not in ('active', 'issued'):
            return {
                'error': f'Prescription status "{prescription.status}" not eligible for POS checkout'
            }

        items = (
            db.session.execute(
                select(PrescriptionItem)
                .options(joinedload(PrescriptionItem.medication))
                .filter(PrescriptionItem.prescription_id == prescription.id)
            )
            .scalars()
            .all()
        )

        cart_items = []
        for item in items:
            medication = item.medication
            if not medication:
                continue

            unit_price = item.unit_price if item.unit_price is not None else medication.price
            line_total = unit_price * item.quantity

            cart_items.append(
                {
                    'prescription_item_id': item.id,
                    'medication_id': medication.id,
                    'name': medication.trade_name or medication.scientific_name,
                    'generic_name': medication.generic_name,
                    'strength': medication.strength,
                    'dosage_form': medication.dosage_form,
                    'quantity': item.quantity,
                    'unit_price': float(unit_price),
                    'total_price': float(line_total),
                    'available_stock': medication.stock_quantity,
                    'dosage': item.dosage,
                    'duration_days': item.duration_days,
                    'instructions': item.instructions,
                }
            )

        return {
            'prescription_id': prescription.id,
            'prescription_number': prescription.prescription_number,
            'patient_id': prescription.patient_id,
            'patient_name': (
                f'{prescription.patient.first_name} {prescription.patient.last_name}'
                if prescription.patient
                else None
            ),
            'doctor_id': prescription.doctor_id,
            'visit_id': prescription.visit_id,
            'items': cart_items,
            'total_amount': sum(item['total_price'] for item in cart_items),
            'status': prescription.status,
        }

    @staticmethod
    def create_sale(
        prescription_id: int, dispensed_by: int, items: list[dict], tenant_id: int | None = None
    ) -> dict:
        from models.medication import (
            Medication,
            PharmacySale,
            PharmacySaleItem,
            Prescription,
            PrescriptionDispenseLog,
        )

        tenant_id = tenant_id or getattr(g, 'tenant_id', None)

        # Lock the prescription row to prevent concurrent dispense
        prescription = (
            db.session.execute(
                select(Prescription)
                .filter(
                    Prescription.id == prescription_id,
                    Prescription.tenant_id == tenant_id,
                )
                .with_for_update()
            )
            .scalars()
            .first()
        )
        if not prescription:
            return {'error': 'Prescription not found'}

        if prescription.status == PrescriptionState.DISPENSED:
            return {'error': 'Prescription already dispensed'}

        sale = PharmacySale(
            tenant_id=tenant_id,
            patient_id=prescription.patient_id,
            sale_number=f'SALE-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}',
            total_amount=0,
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()

        # Lock all medications for this sale to prevent race conditions
        medication_ids = [item.get('medication_id') for item in items if item.get('medication_id')]
        if medication_ids:
            medications = (
                db.session.execute(
                    select(Medication)
                    .filter(
                        Medication.id.in_(medication_ids),
                        Medication.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            med_map = {m.id: m for m in medications}
        else:
            med_map = {}

        total = 0
        total_cost = 0
        for item in items:
            med_id = item.get('medication_id')
            if not med_id:
                safe_commit(db.session, error_message='medication_id required')
                return {'error': 'medication_id required'}

            med = med_map.get(med_id)
            if not med:
                safe_commit(db.session, error_message=f'Medication {med_id} not found')
                return {'error': f'Medication {med_id} not found'}

            qty = int(item.get('quantity', 1))
            unit_price = item.get('unit_price', 0)
            line_total = qty * unit_price

            from app.modules.workflows.pharmacy import PharmacyStockService

            try:
                PharmacyStockService.adjust_stock(
                    medication_id=med_id,
                    quantity_change=-qty,
                    movement_type='sale',
                    reference_type='PharmacySale',
                    reference_id=sale.id,
                    performed_by=dispensed_by,
                )
            except ValueError:
                safe_commit(db.session, error_message=f'Insufficient stock for medication {med_id}')
                return {'error': f'Insufficient stock for medication {med_id}'}

            sale_item = PharmacySaleItem(
                tenant_id=tenant_id,
                sale_id=sale.id,
                medication_id=med_id,
                medication_name=med.trade_name or med.scientific_name or str(med_id),
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.session.add(sale_item)
            total += line_total
            total_cost += _averaged_cost(med_id, qty)

        sale.total_amount = total
        prescription.status = PrescriptionState.DISPENSED

        # Create dispense log
        dispense_log = PrescriptionDispenseLog(
            prescription_id=prescription.id,
            patient_id=prescription.patient_id,
            visit_id=prescription.visit_id,
            dispensed_by=dispensed_by,
            dispensed_at=datetime.now(UTC),
            notes='Dispensed via POS sale',
        )
        db.session.add(dispense_log)

        # Post the GL journal (revenue + COGS) once the sale has an id.
        try:
            from decimal import Decimal

            from services.gl_service import GLService

            GLService.post_pharmacy_sale(sale, Decimal(str(total_cost)))
        except Exception:
            import logging

            logging.exception('GL posting failed for pharmacy sale')

        safe_commit(db.session, error_message='final commit fail', reraise=True)
        return {'sale_id': sale.id, 'total_amount': total}

    @staticmethod
    def process_pharmacy_return(
        sale_item_id: int,
        quantity: int,
        disposition: str,
        reason: str,
        user_id: int,
        tenant_id: int,
    ) -> dict:
        from app.modules.workflows.pharmacy import PharmacyStockService
        from models.medication import PharmacyReturn, PharmacySaleItem

        sale_item = (
            db.session.execute(
                select(PharmacySaleItem)
                .filter(
                    PharmacySaleItem.id == sale_item_id,
                    PharmacySaleItem.sale.has(tenant_id=tenant_id),
                )
                .options(joinedload(PharmacySaleItem.medication))
            )
            .scalars()
            .first()
        )
        if not sale_item:
            return {'error': 'Sale item not found'}

        previously_returned = db.session.execute(
            select(db.func.coalesce(db.func.sum(PharmacyReturn.quantity), 0)).filter(
                PharmacyReturn.sale_item_id == sale_item_id
            )
        ).scalar()
        max_returnable = sale_item.quantity - (previously_returned or 0)
        if quantity <= 0:
            return {'error': 'Return quantity must be positive'}
        if quantity > max_returnable:
            return {'error': f'Return quantity exceeds max returnable ({max_returnable})'}

        if disposition not in ('RESTOCK', 'DISCARD'):
            return {'error': 'Disposition must be RESTOCK or DISCARD'}

        medication_id = sale_item.medication_id

        return_record = PharmacyReturn(
            sale_item_id=sale_item_id,
            medication_id=medication_id,
            quantity=quantity,
            disposition=disposition,
            reason=reason,
            returned_by=user_id,
        )
        db.session.add(return_record)

        if disposition == 'RESTOCK':
            PharmacyStockService.adjust_stock(
                medication_id=medication_id,
                quantity_change=quantity,
                movement_type='ADJUSTMENT',
                reference_type='PharmacyReturn',
                reference_id=return_record.id,
                performed_by=user_id,
                notes=f'Restocked {quantity} units from return',
            )

        safe_commit(db.session, error_message='return commit fail', reraise=True)
        return {
            'return_id': return_record.id,
            'disposition': disposition,
            'quantity': quantity,
        }

    @staticmethod
    def void_sale(sale_id: int, reason: str = '', tenant_id: int | None = None) -> dict:
        from models.medication import PharmacySale

        tenant_id = tenant_id or getattr(g, 'tenant_id', None)

        sale = (
            db.session.execute(
                select(PharmacySale).filter(
                    PharmacySale.id == sale_id,
                    PharmacySale.tenant_id == tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not sale:
            return {'error': 'Sale not found'}

        sale.status = 'cancelled'
        sale.notes = reason

        safe_commit(db.session, error_message='void sale commit fail', reraise=True)
        return {'sale_id': sale.id, 'status': sale.status}

    @staticmethod
    def get_prescription_status(prescription_id: int) -> dict:
        from models.medication import Prescription

        prescription = (
            db.session.execute(select(Prescription).filter(Prescription.id == prescription_id))
            .scalars()
            .first()
        )
        if not prescription:
            return {'error': 'Prescription not found'}

        return {
            'prescription_id': prescription.id,
            'prescription_number': prescription.prescription_number,
            'status': prescription.status,
        }

    @staticmethod
    def create_direct_sale(
        patient_id: int | None,
        dispensed_by: int,
        items: list[dict],
        tenant_id: int | None = None,
    ) -> dict:
        """Create a direct POS sale without a prescription (standalone pharmacy / OTC).

        Dynamic bundle isolation: used when the ``doctor`` module is not active
        and therefore no prescription records exist.
        """
        from uuid import uuid4

        from models.medication import Medication, PharmacySale, PharmacySaleItem

        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        sale = PharmacySale(
            tenant_id=tenant_id,
            patient_id=patient_id,
            sale_number=f'POS-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}',
            total_amount=0,
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()

        medication_ids = [item.get('medication_id') for item in items if item.get('medication_id')]
        if medication_ids:
            medications = (
                db.session.execute(
                    select(Medication)
                    .filter(Medication.id.in_(medication_ids), Medication.tenant_id == tenant_id)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            med_map = {m.id: m for m in medications}
        else:
            med_map = {}

        total = 0
        for item in items:
            med_id = item.get('medication_id')
            if not med_id:
                safe_commit(db.session, error_message='medication_id required')
                return {'error': 'medication_id required'}
            med = med_map.get(med_id)
            if not med:
                safe_commit(db.session, error_message=f'Medication {med_id} not found')
                return {'error': f'Medication {med_id} not found'}
            qty = int(item.get('quantity', 1))
            unit_price = item.get('unit_price', 0)
            line_total = qty * unit_price

            from app.modules.workflows.pharmacy import PharmacyStockService

            try:
                PharmacyStockService.adjust_stock(
                    medication_id=med_id,
                    quantity_change=-qty,
                    movement_type='sale',
                    reference_type='PharmacySale',
                    reference_id=sale.id,
                    performed_by=dispensed_by,
                )
            except Exception as exc:
                safe_commit(db.session, error_message='stock adjustment failed')
                return {'error': f'Stock adjustment failed: {exc}'}

            sale_item = PharmacySaleItem(
                sale_id=sale.id,
                medication_id=med_id,
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.session.add(sale_item)
            total += line_total

        sale.total_amount = total
        if not safe_commit(db.session, error_message='sale commit failed'):
            return {'error': 'sale commit failed'}
        return {'sale_id': sale.id, 'total_amount': total, 'status': 'completed'}


def _averaged_cost(medication_id: int, quantity: int) -> float:
    """Compute the COGS for ``quantity`` units using average purchase cost.

    Falls back to the medication selling price if no purchase records exist.
    """
    from decimal import Decimal

    from models.medication import Medication, MedicationPurchase

    purchases = (
        db.session.execute(select(MedicationPurchase).filter_by(medication_id=medication_id))
        .scalars()
        .all()
    )
    if not purchases:
        med = db.session.get(Medication, medication_id)
        unit = Decimal(str(getattr(med, 'price', 0) or 0)) if med else Decimal(0)
    else:
        total_qty = sum(int(p.quantity or 0) for p in purchases)
        total_cost = sum(
            (Decimal(str(p.purchase_price or 0)) * int(p.quantity or 0)) for p in purchases
        )
        if total_qty <= 0:
            med = db.session.get(Medication, medication_id)
            unit = Decimal(str(getattr(med, 'price', 0) or 0)) if med else Decimal(0)
        else:
            unit = total_cost / Decimal(total_qty)
    return float(unit * Decimal(int(quantity)))
