"""Tests for services.emergency_service.EmergencyService.

Covers latent bugs fixed in this change (all against the live schema):
  - list_cases: filtered/ordered on the non-existent SQL `priority` (instance-only
    property) instead of the real `severity` column; searched Patient.name (absent);
    filtered EmergencyCase.doctor_id (absent column).
  - get_triage_stats: used `priority` + invalid status "IN_TREATMENT".
  - triage_patient: assigned a dict to the TEXT `vital_signs` column and wrote a
    non-existent `triaged_at`.
  - assign_doctor: wrote to a non-existent `doctor_id` column + invalid status.
All DB work runs under ``rollback_db`` isolation.
"""
import json
import types
import uuid

import pytest

from services.emergency_service import EmergencyService as ES
from models.emergency import EmergencyCase
from models.patient import Patient


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def patient(first='طوارئ', last='حالة'):
        p = Patient(first_name=first, last_name=last)
        db.session.add(p)
        db.session.commit()
        return p

    def case(patient_id=None, severity='MODERATE', status='WAITING',
             chief='ألم', diagnosis=None):
        pid = patient_id or patient().id
        c = EmergencyCase(
            patient_id=pid,
            case_number='ER-' + uuid.uuid4().hex[:10],
            chief_complaint=chief,
            severity=severity,
            status=status,
            diagnosis=diagnosis,
        )
        db.session.add(c)
        db.session.commit()
        return c

    return types.SimpleNamespace(db=db, patient=patient, case=case)


class TestListCases:
    def test_returns_pagination(self, fx):
        fx.case(severity='HIGH')
        page = ES.list_cases(per_page=5)
        assert hasattr(page, 'items') and page.total >= 1

    def test_orders_by_severity_rank(self, fx):
        # severity-based ordering must be applied (CRITICAL -> HIGH -> MODERATE -> rest).
        # Robust to pre-existing rows: assert the returned page is sorted by rank.
        p = fx.patient()
        fx.case(patient_id=p.id, severity='LOW')
        fx.case(patient_id=p.id, severity='CRITICAL')
        page = ES.list_cases(per_page=50)
        rank = {'CRITICAL': 0, 'HIGH': 1, 'MODERATE': 2}
        ranks = [rank.get((c.severity or '').upper(), 3) for c in page.items]
        assert ranks == sorted(ranks)

    def test_filter_by_priority_uses_severity(self, fx):
        p = fx.patient()
        crit = fx.case(patient_id=p.id, severity='CRITICAL')
        fx.case(patient_id=p.id, severity='MODERATE')
        page = ES.list_cases(priority='critical', per_page=50)
        sevs = {c.severity for c in page.items}
        assert sevs == {'CRITICAL'}
        assert crit.id in {c.id for c in page.items}

    def test_filter_by_status(self, fx):
        p = fx.patient()
        fx.case(patient_id=p.id, status='COMPLETED')
        page = ES.list_cases(status='COMPLETED', per_page=50)
        assert all(c.status == 'COMPLETED' for c in page.items)

    def test_search_by_patient_name(self, fx):
        p = fx.patient(first='Zaytooni', last='Xyz')
        c = fx.case(patient_id=p.id)
        page = ES.list_cases(search='Zaytooni', per_page=50)
        assert c.id in {x.id for x in page.items}

    def test_doctor_id_param_is_noop_not_crash(self, fx):
        fx.case()
        # doctor_id has no column; must not raise
        page = ES.list_cases(doctor_id=123, per_page=50)
        assert hasattr(page, 'items')


class TestQueries:
    def test_get_case(self, fx):
        c = fx.case()
        assert ES.get_case(c.id).id == c.id
        assert ES.get_case(99999999) is None

    def test_get_cases_by_status(self, fx):
        c = fx.case(status='WAITING')
        result = ES.get_cases_by_status('WAITING')
        assert c.id in {x.id for x in result}

    def test_get_patient_cases(self, fx):
        p = fx.patient()
        c = fx.case(patient_id=p.id)
        result = ES.get_patient_cases(p.id)
        assert c.id in {x.id for x in result}

    def test_get_triage_stats_shape(self, fx):
        fx.case(severity='CRITICAL', status='WAITING')
        stats = ES.get_triage_stats()
        assert set(stats) == {'critical', 'high', 'medium', 'low', 'total_today'}
        assert stats['critical'] >= 1
        assert all(isinstance(v, int) for v in stats.values())


class TestCaseManagement:
    def test_create_case_success(self, fx):
        p = fx.patient()
        c = ES.create_case(p.id, chief_complaint='صداع', priority='HIGH')
        assert c is not None
        assert c.severity == 'HIGH'
        assert c.status == 'WAITING'
        assert c.case_number.startswith('ER-')

    def test_create_case_default_severity(self, fx):
        p = fx.patient()
        c = ES.create_case(p.id, chief_complaint='x')
        assert c.severity == 'MODERATE'

    def test_create_case_bad_patient_returns_none(self, fx):
        assert ES.create_case(99999999, chief_complaint='x') is None

    def test_update_case_status(self, fx):
        c = fx.case()
        assert ES.update_case_status(c.id, 'COMPLETED') is True
        reloaded = EmergencyCase.query.get(c.id)
        assert reloaded.status == 'COMPLETED'
        assert reloaded.completed_at is not None

    def test_update_case_status_not_found(self, fx):
        assert ES.update_case_status(99999999, 'COMPLETED') is False

    def test_assign_doctor_advances_status(self, fx):
        c = fx.case(status='WAITING')
        assert ES.assign_doctor(c.id, doctor_id=5) is True
        assert EmergencyCase.query.get(c.id).status == 'TREATMENT'

    def test_assign_doctor_not_found(self, fx):
        assert ES.assign_doctor(99999999, doctor_id=1) is False


class TestTriage:
    def test_triage_not_found(self, fx):
        assert ES.triage_patient(99999999, 'CRITICAL') is False

    def test_triage_sets_severity_and_vitals(self, fx):
        c = fx.case(severity='LOW')
        ok = ES.triage_patient(c.id, 'CRITICAL', vital_signs={'hr': 110, 'bp': '120/80'})
        assert ok is True
        reloaded = EmergencyCase.query.get(c.id)
        assert reloaded.severity == 'CRITICAL'
        assert json.loads(reloaded.vital_signs)['hr'] == 110

    def test_triage_with_string_vitals(self, fx):
        c = fx.case()
        assert ES.triage_patient(c.id, 'HIGH', vital_signs='raw text') is True
        assert EmergencyCase.query.get(c.id).vital_signs == 'raw text'


class TestNotification:
    def test_notify_staff_no_raise(self, fx):
        c = fx.case()
        ES.notify_staff(c, event='new_case')
        ES.notify_staff(c, event='priority_change')
