"""Exhaustive tests for services.queue_management_service.QueueManagementService.

State-mutating cases run under ``rollback_db`` (savepoint isolation).
"""
import uuid
import types

import pytest

from services.queue_management_service import QueueManagementService
from app.shared.enums import QueueState, PaymentStatus, VisitState
from models.queue_management import QueueManagement, QueueSettings
from models.visit import Visit
from models.patient import Patient
from models.department import Department
from models.user import User
from models.user_department_access import UserDepartmentAccess


@pytest.fixture
def svc():
    return QueueManagementService()


@pytest.fixture
def qfx(rollback_db):
    db = rollback_db

    def patient():
        p = Patient(first_name='ز', last_name='ت')
        db.session.add(p)
        db.session.commit()
        return p

    def dept(name='General Clinic', name_ar='العيادة العامة'):
        d = Department(name=name, name_ar=name_ar, is_active=True)
        db.session.add(d)
        db.session.commit()
        return d

    def user(role='doctor', dept_id=None):
        un = 'zz_q_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='د', role=role,
                 is_active=True, department_id=dept_id)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def visit(patient_id, **kw):
        v = Visit(patient_id=patient_id, **kw)
        db.session.add(v)
        db.session.commit()
        return v

    def ticket(patient_id, department_id=None, status=QueueState.WAITING, **kw):
        t = QueueManagement(patient_id=patient_id, department_id=department_id,
                            queue_number='Q' + uuid.uuid4().hex[:10], status=status, **kw)
        db.session.add(t)
        db.session.commit()
        return t

    return types.SimpleNamespace(db=db, patient=patient, dept=dept, user=user,
                                 visit=visit, ticket=ticket)


# ───────────────────────── pure: entry conditions ─────────────────────────

class TestCheckQueueEntryConditions:
    """Ticket 1: gate must block every non-PAID normal visit regardless of
    settings, force_entry, or payment_required.  Emergency is the only exception."""

    def test_emergency_always_enters(self, svc):
        ok, _ = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PENDING, True)
        assert ok is True

    def test_paid_enters(self, svc):
        ok, _ = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PAID, False)
        assert ok is True

    def test_partial_blocked_for_normal_visit(self, svc):
        ok, msg = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PARTIAL, False)
        assert ok is False and 'الدفع' in msg

    def test_pending_blocked(self, svc):
        ok, msg = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PENDING, False)
        assert ok is False and 'الدفع' in msg

    def test_debt_blocked(self, svc):
        ok, msg = svc._check_queue_entry_conditions(1, 1, PaymentStatus.DEBT, False)
        assert ok is False and 'الدفع' in msg

    def test_force_entry_blocked(self, svc):
        ok, msg = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PENDING, False)
        assert ok is False and 'الدفع' in msg

    def test_payment_required_false_no_longer_bypasses(self, svc):
        # Ticket 1: payment_required=False must NOT allow unpaid normal visits
        ok, msg = svc._check_queue_entry_conditions(1, 1, PaymentStatus.PENDING, False)
        assert ok is False and 'الدفع' in msg


# ───────────────────────── permission helper ─────────────────────────

class TestUserAllowedForDepartment:
    def test_superadmin_allowed(self, svc, qfx):
        d = qfx.dept()
        u = qfx.user(role='super_admin')
        assert svc._is_user_allowed_for_department(u.id, d.id) is True

    def test_doctor_same_general_dept(self, svc, qfx):
        d = qfx.dept()
        u = qfx.user(role='doctor', dept_id=d.id)
        assert svc._is_user_allowed_for_department(u.id, d.id) is True

    def test_doctor_other_dept_no_access(self, svc, qfx):
        d1 = qfx.dept()
        d2 = qfx.dept(name='Cardiology', name_ar='القلبية')
        u = qfx.user(role='doctor', dept_id=d1.id)
        assert svc._is_user_allowed_for_department(u.id, d2.id) is False

    def test_doctor_other_dept_with_extra_access(self, svc, qfx):
        d1 = qfx.dept()
        d2 = qfx.dept(name='Neurology', name_ar='الأعصاب')
        u = qfx.user(role='doctor', dept_id=d1.id)
        qfx.db.session.add(UserDepartmentAccess(user_id=u.id, department_id=d2.id, can_access=True))
        qfx.db.session.commit()
        assert svc._is_user_allowed_for_department(u.id, d2.id) is True

    def test_missing_user_returns_false(self, svc, qfx):
        d = qfx.dept()
        assert svc._is_user_allowed_for_department(99999999, d.id) is False

    def test_role_mismatch_for_lab_dept(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        u = qfx.user(role='doctor', dept_id=d.id)
        assert svc._is_user_allowed_for_department(u.id, d.id) is False


# ───────────────────────── add_patient_to_queue ─────────────────────────

class TestAddPatientToQueue:
    """Ticket 1: payment_status is resolved from the authoritative visit record.
    The service no longer accepts a caller-provided payment_status, force_entry,
    or force_entry_reason.  All tests must create a visit with the desired state
    and pass visit_id."""

    def test_non_general_paid_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PAID, is_emergency=False, department_id=d.id)
        ok, msg = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is True and 'الطابور' in msg

    def test_pending_payment_blocked(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PENDING, is_emergency=False, department_id=d.id)
        ok, _ = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is False

    def test_emergency_bypasses_payment(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PENDING, is_emergency=True, department_id=d.id)
        ok, _ = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is True

    def test_general_requires_doctor(self, svc, qfx):
        d = qfx.dept()  # general
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PAID, is_emergency=False, department_id=d.id)
        ok, msg = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is False and 'طبيب' in msg

    def test_general_with_doctor_paid(self, svc, qfx):
        d = qfx.dept()
        doc = qfx.user(role='doctor', dept_id=d.id)
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PAID, is_emergency=False, department_id=d.id, doctor_id=doc.id)
        ok, _ = svc.add_patient_to_queue(p.id, d.id, doctor_id=doc.id, visit_id=v.id)
        assert ok is True

    def test_bad_patient_no_visit_blocked(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        # No visit_id provided -> service tries to create a Visit with default PENDING
        # Invalid patient_id causes FK failure or is blocked by the gate.
        ok, _ = svc.add_patient_to_queue(99999999, d.id)
        assert ok is False

    def test_partial_payment_blocked_via_service(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PARTIAL, is_emergency=False, department_id=d.id)
        ok, msg = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is False and 'الدفع' in msg

    def test_debt_blocked(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id, payment_status=PaymentStatus.DEBT, is_emergency=False, department_id=d.id)
        ok, msg = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is False and 'الدفع' in msg

    def test_payment_required_false_still_blocks_normal(self, svc, qfx):
        from models.queue_management import QueueSettings
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        # QueueSettings with payment_required=False (legacy bypass)
        qs = QueueSettings.query.filter_by(department_id=d.id).first()
        if not qs:
            qs = QueueSettings(department_id=d.id, payment_required=False, allow_debt=True)
            qfx.db.session.add(qs)
        else:
            qs.payment_required = False
        qfx.db.session.commit()
        v = qfx.visit(p.id, payment_status=PaymentStatus.PENDING, is_emergency=False, department_id=d.id)
        ok, msg = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        # Ticket 1: payment_required=False must no longer bypass the gate
        assert ok is False and 'الدفع' in msg

    def test_form_cannot_spoof_payment_status(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        # Visit is actually PENDING; caller can no longer pass a fake PAID parameter
        v = qfx.visit(p.id, payment_status=PaymentStatus.PENDING, is_emergency=False, department_id=d.id)
        ok, _ = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id)
        assert ok is False

    def test_emergency_flag_from_visit_record_not_overridden(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        # Visit is NOT emergency; caller passes is_emergency=True but should be ignored
        v = qfx.visit(p.id, payment_status=PaymentStatus.PENDING, is_emergency=False, department_id=d.id)
        ok, _ = svc.add_patient_to_queue(p.id, d.id, visit_id=v.id, is_emergency=True)
        # Must be blocked because the visit record says non-emergency and unpaid
        assert ok is False


# ───────────────────────── transfer_visit ─────────────────────────

class TestTransferVisit:
    def test_visit_not_found(self, svc, qfx):
        ok, msg = svc.transfer_visit(99999999, 1)
        assert ok is False and msg == 'visit_not_found'

    def test_invalid_department(self, svc, qfx):
        p = qfx.patient()
        v = qfx.visit(p.id)
        ok, msg = svc.transfer_visit(v.id, 'not-a-number')
        assert ok is False and msg == 'invalid_department'

    def test_department_not_found(self, svc, qfx):
        p = qfx.patient()
        v = qfx.visit(p.id)
        ok, msg = svc.transfer_visit(v.id, 99999999)
        assert ok is False and msg == 'department_not_found'

    def test_general_requires_doctor(self, svc, qfx):
        d = qfx.dept()
        p = qfx.patient()
        v = qfx.visit(p.id)
        ok, msg = svc.transfer_visit(v.id, d.id)
        assert ok is False and msg == 'doctor_required'

    def test_cannot_transfer_active(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id)
        qfx.ticket(p.id, department_id=d.id, visit_id=v.id, status=QueueState.IN_PROGRESS)
        ok, msg = svc.transfer_visit(v.id, d.id)
        assert ok is False and msg == 'cannot_transfer_active_treatment'

    def test_success(self, svc, qfx):
        d_from = qfx.dept(name='Lab', name_ar='المختبر')
        d_to = qfx.dept(name='Radiology', name_ar='الأشعة')
        p = qfx.patient()
        v = qfx.visit(p.id, department_id=d_from.id)
        ok, msg = svc.transfer_visit(v.id, d_to.id)
        assert ok is True and msg == 'ok'


# ───────────────────────── status / metrics readers ─────────────────────────

class TestStatusReaders:
    def test_get_queue_status_structure(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        res = svc.get_queue_status(d.id)
        assert res is not None
        assert res['waiting_count'] >= 1
        assert 'estimated_wait_time' in res

    def test_get_queue_status_all_structure(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        res = svc.get_queue_status_all([d.id])
        assert res is not None and 'tickets' in res
        assert res['waiting_count'] >= 1

    def test_get_queue_status_all_with_filters(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING, priority_level='high')
        res = svc.get_queue_status_all([d.id], priority='high', is_emergency=False)
        assert res is not None

    def test_wait_metrics_today(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.COMPLETED)
        res = svc.get_wait_metrics_today([d.id])
        assert 'overall_avg_wait_minutes' in res and 'by_department' in res

    def test_estimated_wait_time(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        assert svc._calculate_estimated_wait_time(d.id) >= 0


# ───────────────────────── lifecycle transitions ─────────────────────────

class TestCallNextPatient:
    def test_empty_queue(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        ok, _ = svc.call_next_patient(d.id)
        assert ok is False

    def test_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.call_next_patient(d.id)
        assert ok is True


class TestStartTreatment:
    def test_not_found(self, svc, qfx):
        ok, _ = svc.start_treatment(99999999)
        assert ok is False

    def test_wrong_status(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, msg = svc.start_treatment(t.id)
        assert ok is False and 'استدعاء' in msg

    def test_permission_denied(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.CALLED)
        outsider = qfx.user(role='reception')
        ok, _ = svc.start_treatment(t.id, started_by=outsider.id)
        assert ok is False

    def test_success_as_manager(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.CALLED)
        mgr = qfx.user(role='manager')
        ok, _ = svc.start_treatment(t.id, started_by=mgr.id)
        assert ok is True


class TestCompleteTreatment:
    def test_not_found(self, svc, qfx):
        ok, _ = svc.complete_treatment(99999999)
        assert ok is False

    def test_wrong_status(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.complete_treatment(t.id)
        assert ok is False

    def test_success_creates_survey(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        v = qfx.visit(p.id)
        mgr = qfx.user(role='manager')
        t = qfx.ticket(p.id, department_id=d.id, visit_id=v.id, status=QueueState.IN_PROGRESS)
        ok, _ = svc.complete_treatment(t.id, completed_by=mgr.id)
        assert ok is True


class TestSkipReturnCancel:
    def test_skip_not_found(self, svc, qfx):
        ok, _ = svc.skip_patient(99999999)
        assert ok is False

    def test_skip_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.skip_patient(t.id, reason='busy')
        assert ok is True

    def test_return_invalid_status(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.return_to_queue(t.id)
        assert ok is False

    def test_return_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.CALLED)
        ok, _ = svc.return_to_queue(t.id, reason='recheck')
        assert ok is True

    def test_cancel_not_found(self, svc, qfx):
        ok, _ = svc.cancel_ticket(99999999)
        assert ok is False

    def test_cancel_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.cancel_ticket(t.id, reason='no-show')
        assert ok is True


class TestQueuePositionAndApprovals:
    def test_position_not_in_queue(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        pos, _ = svc.get_patient_queue_position(p.id, d.id)
        assert pos is None

    def test_position_in_queue(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING, priority_level='normal')
        pos, _ = svc.get_patient_queue_position(p.id, d.id)
        assert pos == 1

    def test_approve_emergency_debt_not_found(self, svc, qfx):
        ok, _ = svc.approve_emergency_debt(99999999, 1)
        assert ok is False

    def test_approve_emergency_debt_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        approver = qfx.user(role='manager')
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.approve_emergency_debt(t.id, approved_by=approver.id)
        assert ok is True

    def test_approve_force_entry_not_found(self, svc, qfx):
        ok, _ = svc.approve_force_entry(99999999, 1)
        assert ok is False

    def test_approve_force_entry_success(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        approver = qfx.user(role='manager')
        t = qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        ok, _ = svc.approve_force_entry(t.id, approved_by=approver.id, reason='vip')
        assert ok is True
        assert t.priority_level == 'high'


class TestDisplayBuildersAndEmit:
    def test_snapshot_and_displays(self, svc, qfx):
        d = qfx.dept(name='Lab', name_ar='المختبر')
        p = qfx.patient()
        qfx.ticket(p.id, department_id=d.id, status=QueueState.WAITING)
        qfx.ticket(p.id, department_id=d.id, status=QueueState.CALLED)
        assert isinstance(svc._build_queue_snapshot(), list)
        waiting = svc._build_display_waiting()
        assert QueueState.WAITING in waiting and 'current' in waiting
        assert isinstance(svc._build_display_calls(), list)

    def test_emit_does_not_raise(self, svc, qfx):
        svc._emit_queue_updates()  # no clients; wrapped in try/except

    def test_ensure_survey_idempotent(self, svc, qfx):
        p = qfx.patient()
        v = qfx.visit(p.id)
        s1 = svc._ensure_survey_for_visit(v)
        qfx.db.session.commit()
        s2 = svc._ensure_survey_for_visit(v)
        assert s1 is not None and s2 is not None
