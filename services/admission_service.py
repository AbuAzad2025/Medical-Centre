"""
Inpatient Admission-Discharge-Transfer (ADT) service — Phase 3.3.

Coordinates Bed / Visit / Admission state across the admit -> occupy ->
transfer -> discharge lifecycle. All tenant-scoped lookups go through
``get_tenant_record`` so cross-tenant access is rejected by the same
fail-closed path used service-wide.

Visit.status is never mutated directly: discharge delegates to
``VisitStateMachineService.ensure_completed`` because direct assignment is
blocked by the Visit model validator (P1-001).
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime

from app.extensions import db
from app.shared.enums import AdmissionStatus, BedStatus, DischargeType
from services.visit_state_machine_service import VisitStateMachineService
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class AdmissionService:
    """ADT orchestration for inpatient admissions."""

    @staticmethod
    def create_admission(visit_id: int, bed_id: int, user_id: int, tenant_id: int) -> dict:
        """Admit a patient implicitly assigned to ``visit`` into ``bed``.

        - Occupies the bed (status AVAILABLE -> OCCUPIED, tracks current patient).
        - Marks the Visit inpatient with the owning bed/ward.
        - Opens an Admission record in ADMITTED status.
        """
        from models.bed_management import Admission, Bed
        from models.visit import Visit

        try:
            visit = get_tenant_record(Visit, visit_id, tenant_id)
            bed = get_tenant_record(Bed, bed_id, tenant_id)
        except TenantContextError:
            return {
                'success': False,
                'message': 'الزيارة أو السرير غير موجودين أو غير مصرح لكم بهما',
            }

        if visit.is_inpatient:
            return {'success': False, 'message': 'الزيارة مدخولة حالياً'}

        if bed.status != BedStatus.AVAILABLE.value:
            return {
                'success': False,
                'message': f'السرير {bed.bed_number} غير متاح ( الحالة: {bed.status})',
            }

        ward_id = bed.room.ward_id
        now = datetime.now(UTC)
        admission = Admission(
            tenant_id=tenant_id,
            patient_id=visit.patient_id,
            visit_id=visit.id,
            bed_id=bed.id,
            admitting_doctor_id=user_id,
            admission_datetime=now,
        )
        db.session.add(admission)

        bed.status = BedStatus.OCCUPIED.value
        bed.current_patient_id = visit.patient_id

        visit.is_inpatient = True
        visit.bed_id = bed.id
        visit.ward_id = ward_id
        visit.admission_date = now

        if not safe_commit(db.session, error_message='فشل إنشاء الدخول'):
            return {'success': False, 'message': 'فشل إنشاء الدخول'}

        return {
            'success': True,
            'admission_id': admission.id,
            'visit_id': visit.id,
            'bed_id': bed.id,
            'ward_id': ward_id,
            'status': admission.status,
            'bed_status': bed.status,
        }

    @staticmethod
    def process_discharge(
        admission_id: int,
        discharge_type: str,
        summary_notes: str | None,
        user_id: int,
        tenant_id: int,
    ) -> dict:
        """Discharge an admitted patient.

        - Releases the bed to CLEANING, clears current patient.
        - Closes the Admission (DISCHARGED), computes length_of_stay.
        - Syncs Visit: clears inpatient flags and drives status -> COMPLETED
          through the Visit state machine.
        """
        from models.bed_management import Admission

        try:
            admission = get_tenant_record(Admission, admission_id, tenant_id)
        except TenantContextError:
            return {'success': False, 'message': 'الدخول غير موجود أو غير مصرح به'}

        if admission.status != AdmissionStatus.ADMITTED.value:
            return {
                'success': False,
                'message': f'لا يمكن إرخاء دخول بحالة {admission.status}',
            }

        try:
            dt = DischargeType(discharge_type)
        except ValueError:
            allowed = [d.value for d in DischargeType]
            return {
                'success': False,
                'message': f'نوع الإرخاء غير صالح. المسموح: {allowed}',
            }

        now = datetime.now(UTC)
        bed = admission.bed

        if bed is not None:
            bed.status = BedStatus.CLEANING.value
            bed.current_patient_id = None

        admission.discharge_type = dt.value
        admission.discharge_datetime = now
        admission.discharge_diagnosis = summary_notes
        admission.length_of_stay = admission.compute_length_of_stay()
        admission.status = AdmissionStatus.DISCHARGED.value
        admission.is_active = False

        visit = admission.visit
        if visit is not None:
            visit.is_inpatient = False
            visit.bed_id = None
            visit.ward_id = None
            visit.discharge_date = now
            # Visit not necessarily in a COMPLETED-completable state here;
            # discharge is still recorded on the admission regardless.
            with suppress(ValueError):
                VisitStateMachineService.ensure_completed(visit)

        if not safe_commit(db.session, error_message='فشل إرخاء الدخل'):
            return {'success': False, 'message': 'فشل إرخاء الدخل'}

        return {
            'success': True,
            'admission_id': admission.id,
            'visit_id': admission.visit_id,
            'bed_id': (bed.id if bed else None),
            'length_of_stay': admission.length_of_stay,
            'status': admission.status,
            'bed_status': (bed.status if bed else None),
            'visit_status': (visit.status if visit else None),
        }

    @staticmethod
    def process_transfer(
        admission_id: int,
        target_bed_id: int,
        transfer_reason: str | None,
        user_id: int,
        tenant_id: int,
    ) -> dict:
        """Transfer an admitted patient from their current bed to ``target_bed``.

        - Logs a BedTransfer (from_bed -> to_bed).
        - Releases the old bed to CLEANING, occupies the target bed.
        - Repoints the Admission (and Visit) at the new bed/ward.
        """
        from models.bed_management import Admission, Bed, BedTransfer

        try:
            admission = get_tenant_record(Admission, admission_id, tenant_id)
            target_bed = get_tenant_record(Bed, target_bed_id, tenant_id)
        except TenantContextError:
            return {'success': False, 'message': 'الدخول أو السرير المستهدف غير موجودين'}

        if admission.status != AdmissionStatus.ADMITTED.value:
            return {'success': False, 'message': 'لا يمكن نقل دخل بحالة غير مدخول'}

        if target_bed.status != BedStatus.AVAILABLE.value:
            return {
                'success': False,
                'message': f'السرير المستهدف غير متاح ( الحالة: {target_bed.status})',
            }

        old_bed = admission.bed
        if old_bed is not None and old_bed.id == target_bed.id:
            return {'success': False, 'message': 'لا يمكن نقل السرير إلى نفسه'}

        now = datetime.now(UTC)
        transfer = BedTransfer(
            tenant_id=tenant_id,
            admission_id=admission.id,
            patient_id=admission.patient_id,
            from_bed_id=old_bed.id if old_bed else None,
            to_bed_id=target_bed.id,
            transfer_datetime=now,
            transfer_type='INTERNAL',
            reason=transfer_reason,
            requested_by_id=user_id,
        )
        db.session.add(transfer)

        # Flush the transfer row so the new Bed/Visit state can be committed
        # together with the bed status mutations.
        with db.session.no_autoflush:
            if old_bed is not None:
                old_bed.status = BedStatus.CLEANING.value
                old_bed.current_patient_id = None
            target_bed.status = BedStatus.OCCUPIED.value
            target_bed.current_patient_id = admission.patient_id
            admission.bed_id = target_bed.id
            visit = admission.visit
            if visit is not None:
                visit.bed_id = target_bed.id
                visit.ward_id = target_bed.room.ward_id

        if not safe_commit(db.session, error_message='فشل نقل السرير'):
            return {'success': False, 'message': 'فشل نقل السرير'}

        return {
            'success': True,
            'admission_id': admission.id,
            'visit_id': admission.visit_id,
            'bed_transfer_id': transfer.id,
            'from_bed_id': (old_bed.id if old_bed else None),
            'to_bed_id': target_bed.id,
            'ward_id': target_bed.room.ward_id,
            'bed_status': target_bed.status,
        }
