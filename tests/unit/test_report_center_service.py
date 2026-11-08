"""DB-backed tests for services.report_center_service SQL aggregates."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import select

from app.extensions import db
from models.department import Department
from models.emergency import EmergencyCase
from models.emergency_status_history import EmergencyStatusHistory
from models.online_booking import OnlineBooking
from models.patient import Patient
from models.payment import Payment
from models.radiology_result import RadiologyResult
from models.user import StaffAbsence, StaffWorkSchedule, User
from models.visit import Visit
from models.visit_transfer import VisitTransferLog
from services.report_center_service import ReportCenterService


@pytest.fixture
def deps(app, test_tenant):
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    d1 = Department(
        name=f'ReportCenter-A-{suffix}', name_ar='القسم أ', is_active=True, tenant_id=test_tenant.id
    )
    d2 = Department(
        name=f'ReportCenter-B-{suffix}', name_ar='القسم ب', is_active=True, tenant_id=test_tenant.id
    )
    db.session.add_all([d1, d2])
    db.session.commit()
    return d1, d2


def _patient(tenant_id, suffix):
    p = Patient(
        tenant_id=tenant_id,
        first_name=f'ReportPatient{suffix}',
        last_name='Test',
        phone=f'0519{suffix[-6:]}',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _dt(y, m, d, hh=10, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


class TestComparePeriods:
    def test_delta_and_percent(self, app, test_tenant, db, deps):
        d1, d2 = deps
        patient = _patient(test_tenant.id, datetime.now(UTC).strftime('%H%M%S%f'))
        visit_a = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=None,
            department_id=d1.id,
            visit_date=date(2026, 3, 10),
            visit_time=_dt(2026, 3, 10),
            status='COMPLETED',
        )
        visit_b = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=None,
            department_id=d2.id,
            visit_date=date(2026, 4, 12),
            visit_time=_dt(2026, 4, 12),
            status='COMPLETED',
        )
        db.session.add_all([visit_a, visit_b])
        db.session.flush()
        pay_a = Payment(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            visit_id=visit_a.id,
            method='CASH',
            amount=100,
            currency='ILS',
            status='CONFIRMED',
            payment_date=_dt(2026, 3, 10),
        )
        pay_b = Payment(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            visit_id=visit_b.id,
            method='CASH',
            amount=250,
            currency='ILS',
            status='CONFIRMED',
            payment_date=_dt(2026, 4, 12),
        )
        db.session.add_all([pay_a, pay_b])
        db.session.commit()

        result = ReportCenterService.compare_periods(
            _dt(2026, 3, 1),
            _dt(2026, 3, 31, 23, 59),
            _dt(2026, 4, 1),
            _dt(2026, 4, 30, 23, 59),
        )
        assert result['a']['visits'] == 1
        assert result['a']['revenue'] == 100.0
        assert result['b']['visits'] == 1
        assert result['b']['revenue'] == 250.0
        assert result['delta']['revenue'] == -150.0
        assert result['pct']['revenue'] == -60.0

    def test_department_filter(self, app, test_tenant, db, deps):
        d1, d2 = deps
        patient = _patient(test_tenant.id, datetime.now(UTC).strftime('%H%M%S%f'))
        db.session.add(
            Visit(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                department_id=d1.id,
                visit_date=date(2026, 5, 2),
                visit_time=_dt(2026, 5, 2),
                status='COMPLETED',
            )
        )
        db.session.commit()
        filtered = ReportCenterService.compare_periods(
            _dt(2026, 5, 1),
            _dt(2026, 5, 31, 23, 59),
            _dt(2026, 4, 1),
            _dt(2026, 4, 30, 23, 59),
            department_id=d1.id,
        )
        assert filtered['a']['visits'] == 1
        filtered_other = ReportCenterService.compare_periods(
            _dt(2026, 5, 1),
            _dt(2026, 5, 31, 23, 59),
            _dt(2026, 4, 1),
            _dt(2026, 4, 30, 23, 59),
            department_id=d2.id,
        )
        assert filtered_other['a']['visits'] == 0


class TestDepartmentTransfers:
    def test_empty_window_returns_empty(self, app, test_tenant, db):
        rows = ReportCenterService.department_transfers(_dt(1990, 1, 1), _dt(1990, 1, 2))
        assert rows == []

    def test_grouped_transfers(self, app, test_tenant, db, deps):
        d1, d2 = deps
        patient = _patient(test_tenant.id, datetime.now(UTC).strftime('%H%M%S%f'))
        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            department_id=d1.id,
            visit_date=date(2026, 6, 1),
            visit_time=_dt(2026, 6, 1),
        )
        db.session.add(visit)
        db.session.flush()
        log = VisitTransferLog(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            from_department_id=d1.id,
            to_department_id=d2.id,
            source='reception',
            created_at=_dt(2026, 6, 1),
        )
        db.session.add(log)
        db.session.commit()

        rows = ReportCenterService.department_transfers(_dt(2026, 6, 1), _dt(2026, 6, 30, 23, 59))
        assert len(rows) == 1
        assert rows[0]['count'] == 1
        assert rows[0]['from'] == 'القسم أ'
        assert rows[0]['to'] == 'القسم ب'


class TestBookingReport:
    def test_empty_window(self, app, test_tenant, db):
        out = ReportCenterService.booking_report(_dt(1990, 1, 1), _dt(1990, 1, 2))
        assert out['total'] == 0
        assert out['attendance_rate'] == 0
        assert out['by_status']['completed'] == 0

    def test_rates_and_top_lists(self, app, test_tenant, db, deps):
        d1, _d2 = deps
        suffix = datetime.now(UTC).strftime('%H%M%S%f')

        def booking(ref, status, department_id=None, doctor_id=None):
            return OnlineBooking(
                tenant_id=test_tenant.id,
                booking_reference=ref,
                first_name='Booking',
                last_name='Test',
                phone='0501112223',
                department_id=department_id,
                doctor_id=doctor_id,
                appointment_date=date(2026, 7, 1),
                appointment_time=time(9, 0),
                status=status,
                created_at=_dt(2026, 7, 1),
            )

        db.session.add_all(
            [
                booking(f'BR1{suffix}', 'confirmed', d1.id),
                booking(f'BR2{suffix}', 'completed', d1.id),
                booking(f'BR3{suffix}', 'completed', d1.id),
                booking(f'BR4{suffix}', 'no_show', d1.id),
                booking(f'BR5{suffix}', 'cancelled', d1.id),
            ]
        )
        db.session.commit()

        out = ReportCenterService.booking_report(_dt(2026, 7, 1), _dt(2026, 7, 31, 23, 59))
        assert out['total'] == 5
        assert out['by_status']['completed'] == 2
        # booked = total - cancelled = 4
        assert out['attendance_rate'] == 50.0  # 2/4
        assert out['no_show_rate'] == 25.0  # 1/4
        assert out['top_departments'][0][0] == d1.id


class TestEmergencyStageTimes:
    def test_empty_window(self, app, test_tenant, db):
        out = ReportCenterService.emergency_stage_times(_dt(1990, 1, 1), _dt(1990, 1, 2))
        assert out == {'avg_minutes': {}, 'cases': 0}

    def test_average_transition_minutes(self, app, test_tenant, db):
        patient = _patient(test_tenant.id, datetime.now(UTC).strftime('%H%M%S%f'))
        suffix = datetime.now(UTC).strftime('%H%M%S%f')
        case = EmergencyCase(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            case_number=f'ER{suffix}',
            chief_complaint='test complaint',
            severity='MODERATE',
            status='IN_TRIAGE',
            created_at=_dt(2026, 8, 1),
        )
        db.session.add(case)
        db.session.flush()
        h1 = EmergencyStatusHistory(
            tenant_id=test_tenant.id,
            emergency_id=case.id,
            from_status=None,
            to_status='TRIAGED',
            created_at=_dt(2026, 8, 1, 8, 0),
        )
        h2 = EmergencyStatusHistory(
            tenant_id=test_tenant.id,
            emergency_id=case.id,
            from_status='TRIAGED',
            to_status='TREATMENT',
            created_at=_dt(2026, 8, 1, 8, 30),
        )
        h3 = EmergencyStatusHistory(
            tenant_id=test_tenant.id,
            emergency_id=case.id,
            from_status='TREATMENT',
            to_status='DISCHARGED',
            created_at=_dt(2026, 8, 1, 9, 0),
        )
        db.session.add_all([h1, h2, h3])
        db.session.commit()

        out = ReportCenterService.emergency_stage_times(_dt(2026, 8, 1), _dt(2026, 8, 31, 23, 59))
        assert out['cases'] == 1
        assert out['avg_minutes']['TRIAGED'] == 30.0
        assert out['avg_minutes']['TREATMENT'] == 30.0


class TestRadiologyRevisionRate:
    def test_empty(self, app, test_tenant, db):
        out = ReportCenterService.radiology_revision_rate(_dt(1990, 1, 1), _dt(1990, 1, 2))
        assert out == {'reviewed': 0, 'revised_after_review': 0, 'rate': 0}

    def test_rate_computed(self, app, test_tenant, db):
        from models.radiology_request import RadiologyRequest

        patient = _patient(test_tenant.id, datetime.now(UTC).strftime('%H%M%S%f'))
        req = RadiologyRequest(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            modality='XRay',
            status='DONE',
        )
        db.session.add(req)
        db.session.flush()
        for i, (reviewed, revised) in enumerate([(True, False), (True, True), (False, False)]):
            db.session.add(
                RadiologyResult(
                    tenant_id=test_tenant.id,
                    request_id=req.id,
                    patient_id=patient.id,
                    status='READY',
                    findings=f'finding {i}',
                    reviewed_at=_dt(2026, 9, 1) if reviewed else None,
                    revised_after_review=revised,
                )
            )
        db.session.commit()
        out = ReportCenterService.radiology_revision_rate(_dt(2026, 9, 1), _dt(2026, 9, 30, 23, 59))
        assert out['reviewed'] == 2
        assert out['revised_after_review'] == 1
        assert out['rate'] == 50.0


class TestCapacityImpact:
    def test_empty_window(self, app, test_tenant, db):
        out = ReportCenterService.capacity_impact(date(1990, 1, 1), date(1990, 1, 2))
        assert isinstance(out, list)

    def test_schedule_and_absence(self, app, test_tenant, db, deps):
        d1, _d2 = deps
        suffix = datetime.now(UTC).strftime('%H%M%S%f')
        doctor = User(
            username=f'cap_doc_{suffix}',
            email=f'cap_doc_{suffix}@test.local',
            full_name='Cap Doc',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
            department_id=d1.id,
        )
        doctor.set_password('test123')
        # The after_insert listener auto-creates Mon-Fri 09:00-17:00 schedules
        db.session.add(doctor)
        db.session.commit()

        auto = (
            db.session.execute(select(StaffWorkSchedule).filter_by(user_id=doctor.id))
            .scalars()
            .all()
        )
        assert {s.day_of_week for s in auto} == {0, 1, 2, 3, 4}

        # Extend to weekends so all 7 days carry a schedule
        for dow in (5, 6):
            db.session.add(
                StaffWorkSchedule(
                    tenant_id=test_tenant.id,
                    user_id=doctor.id,
                    day_of_week=dow,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    is_active=True,
                )
            )
        # Absence for 2 of the 7 days (Oct 5-6 2026)
        absence = StaffAbsence(
            tenant_id=test_tenant.id,
            user_id=doctor.id,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 6),
        )
        db.session.add(absence)
        db.session.commit()

        out = ReportCenterService.capacity_impact(date(2026, 10, 1), date(2026, 10, 7))
        dept_row = next((r for r in out if r['department'] == 'القسم أ'), None)
        assert dept_row is not None
        assert dept_row['scheduled_hours'] == 56.0  # 7 days x 8h
        assert dept_row['absence_hours'] == 16.0  # 2 days x 8h
        assert dept_row['impact_percent'] == round(16 / 56 * 100, 2)
