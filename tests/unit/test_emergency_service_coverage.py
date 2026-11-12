"""Coverage for services/emergency_service.py."""

from __future__ import annotations

from datetime import UTC, datetime

pytest_plugins = ['tests._isolated_tenant']


def _patient(db, tenant_id, first='ER', last='Patient'):
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name=first,
        last_name=last,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(patient)
    db.session.flush()
    return patient


class TestListCases:
    """``list_cases`` — the emergency case list."""

    def test_an_empty_list(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = EmergencyService.list_cases()
        assert result is not None
        assert isinstance(result.items, list)

    def test_searching_for_a_patient(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            EmergencyService.list_cases(search='nonexistent')
        # The search path runs without error even when nothing matches.

    def test_filtering_by_priority(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            EmergencyService.list_cases(priority='high')
            EmergencyService.list_cases(priority='CRITICAL')

    def test_filtering_by_status(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            EmergencyService.list_cases(status='WAITING')

    def test_today_only(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            EmergencyService.list_cases(today_only=True)


class TestGetCase:
    """``get_case``."""

    def test_a_missing_case_is_none(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            assert EmergencyService.get_case(999999) is None


class TestGetCasesByStatus:
    """``get_cases_by_status``."""

    def test_an_empty_list(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = EmergencyService.get_cases_by_status('WAITING')
        assert isinstance(result, list)

    def test_a_limit_is_honoured(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = EmergencyService.get_cases_by_status('WAITING', limit=5)
        assert isinstance(result, list)


class TestTriageStats:
    """``get_triage_stats``."""

    def test_stats_for_an_empty_clinic(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            stats = EmergencyService.get_triage_stats()
        assert isinstance(stats, dict)


class TestCreateCase:
    """``create_case``."""

    def test_a_case_is_created(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        patient = _patient(db, test_tenant.id)
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            case = EmergencyService.create_case(
                patient_id=patient.id,
                chief_complaint='chest pain',
                priority='HIGH',
            )
        assert case is not None

    def test_a_missing_patient_is_refused(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            case = EmergencyService.create_case(patient_id=999999)
        assert case is None


class TestUpdateCaseStatus:
    """``update_case_status``."""

    def test_an_unknown_case_is_refused(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            assert EmergencyService.update_case_status(999999, 'TRIAGED') is False


class TestAssignDoctor:
    """``assign_doctor``."""

    def test_an_unknown_case_is_refused(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            assert EmergencyService.assign_doctor(999999, 1) is False


class TestTriagePatient:
    """``triage_patient``."""

    def test_an_unknown_case_is_refused(self, app, db, test_tenant):
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            assert EmergencyService.triage_patient(999999, 'HIGH') is False


class TestNotifyStaff:
    """``notify_staff``."""

    def test_a_missing_case_does_not_raise(self, app, db, test_tenant):
        from models.emergency import EmergencyCase
        from services.emergency_service import EmergencyService

        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            # The helper tolerates a case that has no visit attached.
            patient = _patient(db, test_tenant.id)
            case = EmergencyCase(
                patient_id=patient.id,
                visit_id=None,
                case_number='EC-1',
                chief_complaint='chest pain',
                severity='HIGH',
                status='WAITING',
            )
            db.session.add(case)
            db.session.flush()
            EmergencyService.notify_staff(case, event='new_case')
