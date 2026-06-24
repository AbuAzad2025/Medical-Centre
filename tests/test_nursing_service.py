"""Tests for services.nursing_service.NursingService.

Covers latent bugs fixed in this change:
  - record_vitals (missing NOT NULL patient_id)
  - create_care_plan (missing NOT NULL patient_id)
  - get_pending_tasks / complete_task (wrong column names + uppercase status enum)
Methods that depend on absent schema (get_nurse_patients -> Visit.assigned_nurse_id,
notes -> missing NursingNote model) degrade to [] / None by design and are asserted as such.
All DB work runs under ``rollback_db`` isolation.
"""
import types
import uuid

import pytest

from services.nursing_service import NursingService as NS
from models.patient import Patient
from models.visit import Visit
from models.nurse import Nurse, VitalSigns, MedicationAdministrationLog
from models.clinical_pathway import PatientCarePlan
from models.task_management import Task
from models.user import User


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def user(role='nurse'):
        un = 'ns_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role=role, is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def patient():
        p = Patient(first_name='ت', last_name='م')
        db.session.add(p)
        db.session.commit()
        return p

    def visit(patient_id=None):
        pid = patient_id or patient().id
        v = Visit(patient_id=pid)
        db.session.add(v)
        db.session.commit()
        return v

    def nurse():
        n = Nurse(user_id=user().id, license_number='LN' + uuid.uuid4().hex[:8])
        db.session.add(n)
        db.session.commit()
        return n

    def task(status='pending', assigned_to=None):
        t = Task(title='T', task_type='patient_care', status=status, priority='medium',
                 assigned_by=user().id, assigned_to=assigned_to)
        db.session.add(t)
        db.session.commit()
        return t

    def admin_log(visit_obj):
        log = MedicationAdministrationLog(patient_id=visit_obj.patient_id, visit_id=visit_obj.id)
        db.session.add(log)
        db.session.commit()
        return log

    return types.SimpleNamespace(db=db, user=user, patient=patient, visit=visit, nurse=nurse,
                                 task=task, admin_log=admin_log)


class TestVitals:
    def test_get_vitals_empty(self, fx):
        assert NS.get_vitals(99999999) == []

    def test_record_vitals_visit_not_found(self, fx):
        assert NS.record_vitals(99999999, recorded_by=None) is None

    def test_record_vitals_success_sets_patient(self, fx):
        v = fx.visit()
        n = fx.nurse()
        rec = NS.record_vitals(v.id, recorded_by=n.id, temperature=37.0, heart_rate=80,
                               blood_pressure_systolic=120, blood_pressure_diastolic=80)
        assert rec is not None
        assert rec.patient_id == v.patient_id
        assert rec.temperature == 37.0
        fetched = NS.get_vitals(v.id)
        assert any(x.id == rec.id for x in fetched)


class TestNotes:
    def test_get_notes_graceful_empty(self, fx):
        # NursingNote model is absent -> degrades to []
        assert NS.get_notes(1) == []

    def test_add_note_graceful_none(self, fx):
        assert NS.add_note(1, 1, 'content') is None


class TestAdministrations:
    def test_get_pending_empty(self, fx):
        assert NS.get_pending_administrations(99999999) == []

    def test_get_pending_for_visit(self, fx):
        v = fx.visit()
        log = fx.admin_log(v)
        pending = NS.get_pending_administrations(v.id)
        assert any(x.id == log.id for x in pending)

    def test_record_administration_not_found(self, fx):
        assert NS.record_administration(99999999, nurse_id=1) is False

    def test_record_administration_success(self, fx):
        v = fx.visit()
        log = fx.admin_log(v)
        assert NS.record_administration(log.id, nurse_id=1, notes='given') is True
        assert MedicationAdministrationLog.query.get(log.id).notes == 'given'


class TestCarePlans:
    def test_get_care_plans_empty(self, fx):
        assert NS.get_care_plans(99999999) == []

    def test_create_care_plan_visit_not_found(self, fx):
        assert NS.create_care_plan(99999999, created_by=fx.user().id,
                                   plan_type='p', description='d') is None

    def test_create_care_plan_success_sets_patient(self, fx):
        v = fx.visit()
        plan = NS.create_care_plan(v.id, created_by=fx.user().id, plan_type='Recovery',
                                   description='desc')
        assert plan is not None
        assert plan.patient_id == v.patient_id
        assert plan.plan_name == 'Recovery'
        assert any(x.id == plan.id for x in NS.get_care_plans(v.id))


class TestTasks:
    def test_get_pending_tasks_excludes_completed(self, fx):
        pending = fx.task(status='pending')
        done = fx.task(status='completed')
        result = NS.get_pending_tasks()
        ids = {t.id for t in result}
        assert pending.id in ids
        assert done.id not in ids

    def test_get_pending_tasks_filtered_by_nurse(self, fx):
        u1, u2 = fx.user(), fx.user()
        mine = fx.task(status='pending', assigned_to=u1.id)
        other = fx.task(status='pending', assigned_to=u2.id)
        result = NS.get_pending_tasks(nurse_id=u1.id)
        ids = {t.id for t in result}
        assert mine.id in ids and other.id not in ids

    def test_complete_task_not_found(self, fx):
        assert NS.complete_task(99999999, completed_by=1) is False

    def test_complete_task_success(self, fx):
        t = fx.task(status='pending')
        assert NS.complete_task(t.id, completed_by=1) is True
        reloaded = Task.query.get(t.id)
        assert reloaded.status == 'completed'
        assert reloaded.completed_at is not None


class TestDashboardAndPatients:
    def test_get_nurse_patients_returns_list(self, fx):
        assert isinstance(NS.get_nurse_patients(1), list)

    def test_dashboard_stats_shape(self, fx):
        stats = NS.get_dashboard_stats(1)
        assert set(stats) == {'assigned_patients', 'pending_tasks', 'pending_administrations'}
        assert all(isinstance(v, int) for v in stats.values())
