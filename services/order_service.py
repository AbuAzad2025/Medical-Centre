"""
OrderService — unified clinical order creation
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.shared.enums import OrderState


class OrderService:
    @staticmethod
    def create_lab_order(visit, doctor_id: int, lab_test_ids: list[int], tenant_id: int | None = None) -> dict:
        from models.lab_request import LabRequest, LabResult
        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        lab_request = LabRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            doctor_id=doctor_id,
            status=OrderState.REQUESTED,
            notes="",
        )
        db.session.add(lab_request)
        db.session.flush()
        for test_id in lab_test_ids:
            result = LabResult(
                tenant_id=tenant_id,
                request_id=lab_request.id,
                test_id=test_id,
                status='pending',
            )
            db.session.add(result)
        db.session.commit()
        return {"order_id": lab_request.id, "type": "lab", "status": OrderState.REQUESTED}

    @staticmethod
    def create_radiology_order(visit, doctor_id: int, radiology_test_ids: list[int], tenant_id: int | None = None) -> dict:
        from models.radiology_request import RadiologyRequest
        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        rad_request = RadiologyRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            doctor_id=doctor_id,
            status=OrderState.REQUESTED,
        )
        db.session.add(rad_request)
        db.session.commit()
        return {"order_id": rad_request.id, "type": "radiology", "status": OrderState.REQUESTED}

    @staticmethod
    def create_prescription(visit, doctor_id: int, items: list[dict], tenant_id: int | None = None) -> dict:
        from models.medication import Prescription, PrescriptionItem
        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        prescription = Prescription(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            doctor_id=doctor_id,
            status='active',
        )
        db.session.add(prescription)
        db.session.flush()
        for item in items:
            pi = PrescriptionItem(
                tenant_id=tenant_id,
                prescription_id=prescription.id,
                medication_id=item.get('medication_id'),
                medication_name=item.get('medication_name', ''),
                dosage=item.get('dosage', ''),
                frequency=item.get('frequency', ''),
                duration=item.get('duration', ''),
                quantity=item.get('quantity', 1),
            )
            db.session.add(pi)
        db.session.commit()
        return {"order_id": prescription.id, "type": "prescription", "status": "active"}

    @staticmethod
    def get_orders_for_visit(visit) -> list[dict]:
        orders = []
        try:
            from models.lab_request import LabRequest
            lab_orders = LabRequest.query.filter_by(visit_id=visit.id).all()
            for o in lab_orders:
                orders.append({"id": o.id, "type": "lab", "status": o.status, "created_at": str(o.created_at)})
        except Exception:
            pass
        try:
            from models.radiology_request import RadiologyRequest
            rad_orders = RadiologyRequest.query.filter_by(visit_id=visit.id).all()
            for o in rad_orders:
                orders.append({"id": o.id, "type": "radiology", "status": o.status, "created_at": str(o.created_at)})
        except Exception:
            pass
        try:
            from models.medication import Prescription
            prescriptions = Prescription.query.filter_by(visit_id=visit.id).all()
            for o in prescriptions:
                orders.append({"id": o.id, "type": "prescription", "status": o.status, "created_at": str(o.created_at)})
        except Exception:
            pass
        return sorted(orders, key=lambda x: x.get("created_at", ""))

    @staticmethod
    def module_aware_create(visit, doctor_id: int, order_type: str, params: dict) -> dict | None:
        from app.core.module.validators import get_active_modules_for_tenant
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id:
            active_modules = get_active_modules_for_tenant(tenant_id)
            if order_type == 'lab' and 'lab' not in active_modules:
                return None
            if order_type == 'radiology' and 'radiology' not in active_modules:
                return None
        if order_type == 'lab':
            return OrderService.create_lab_order(visit, doctor_id, params.get('test_ids', []), tenant_id)
        elif order_type == 'radiology':
            return OrderService.create_radiology_order(visit, doctor_id, params.get('test_ids', []), tenant_id)
        elif order_type == 'prescription':
            return OrderService.create_prescription(visit, doctor_id, params.get('items', []), tenant_id)
        return None