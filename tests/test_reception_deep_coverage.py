"""Reception deep coverage. All tests assert status < 500."""

import pytest


@pytest.fixture()
def _rc(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='vis_deep2', role='reception')
    login_test_client(client, u, test_tenant)
    return client


class TestVisitsDeep:
    def test_visits_filtered_by_dept(self, _rc):
        assert _rc.get('/reception/visits?department_id=1').status_code < 500

    def test_visits_filtered_by_status(self, _rc):
        assert _rc.get('/reception/visits?status=OPEN').status_code < 500

    def test_visit_view_nonexistent(self, _rc):
        assert _rc.get('/reception/view_visit/99999').status_code < 500

    def test_edit_visit_nonexistent(self, _rc):
        assert _rc.get('/reception/edit_visit/99999').status_code < 500

    def test_print_receipt_nonexistent(self, _rc):
        assert _rc.get('/reception/print_receipt/99999').status_code < 500


class TestPatientsDeep:
    def test_patients_with_dept_filter(self, _rc):
        assert _rc.get('/reception/patients?department_id=1').status_code < 500

    def test_view_patient_first(self, _rc):
        assert _rc.get('/reception/view_patient/1', follow_redirects=True).status_code < 500

    def test_edit_patient_get(self, _rc):
        assert _rc.get('/reception/edit_patient/1').status_code < 500

    def test_add_patient_page_get(self, _rc):
        assert _rc.get('/reception/add_patient').status_code < 500


class TestQueueDeep:
    def test_calls_display(self, _rc):
        assert _rc.get('/reception/display/calls').status_code < 500

    def test_smart_queue_management(self, _rc):
        assert _rc.get('/reception/smart-queue-management/1').status_code < 500
