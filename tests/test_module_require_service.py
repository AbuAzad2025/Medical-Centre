"""Tests for service-level module gating (``@require_module`` fail-closed circuit breaker).

Validates that when a tenant does NOT have a required module enabled:
  - ``LabService`` methods raise ``ModuleNotEnabledError`` (module 'lab')
  - ``RadiologyService`` methods raise ``ModuleNotEnabledError`` (module 'radiology')
  - ``PrescriptionService`` methods raise ``ModuleNotEnabledError`` (module 'pharmacy')

The gate is enforced *before* any business logic, so these tests do not depend on
DB row setup — they pin the fail-closed behaviour mandated by the modularity plan.
"""

import types

import pytest

from services.emergency_service import EmergencyService as ER
from services.feature_gate_service import ModuleNotEnabledError
from services.inventory_ledger_service import InventoryLedgerService as INV
from services.lab_service import LabService as LAB
from services.nursing_service import NursingService as NUR
from services.prescription_service import PrescriptionService as RX
from services.radiology_service import RadiologyService as RAD

GATED_METHODS = [
    ('lab', LAB, 'create_request', (1, [])),
    ('lab', LAB, 'get_worklist', ()),
    ('lab', LAB, 'get_request_counts', ()),
    ('radiology', RAD, 'create_request', (1, [])),
    ('radiology', RAD, 'get_worklist', ()),
    ('radiology', RAD, 'get_request_counts', ()),
    ('doctor', RX, 'create_prescription', (1, 1, 'outpatient', [])),
    ('doctor', RX, 'get_active_prescriptions', (1,)),
    ('inventory', INV, 'record_movement', (1, 'purchase', 5)),
    ('inventory', INV, 'current_stock', (1,)),
    ('inventory', INV, 'low_stock_alerts', (10,)),
    ('emergency', ER, 'list_cases', ()),
    ('emergency', ER, 'get_case', (1,)),
    ('emergency', ER, 'get_cases_by_status', ('WAITING',)),
    ('emergency', ER, 'get_patient_cases', (1,)),
    ('emergency', ER, 'get_triage_stats', ()),
    ('emergency', ER, 'update_case_status', (1, 'TREATMENT')),
    ('emergency', ER, 'assign_doctor', (1, 1)),
    ('emergency', ER, 'triage_patient', (1, 'HIGH')),
    (
        'emergency',
        ER,
        'notify_staff',
        (types.SimpleNamespace(id=1, chief_complaint='x', priority='HIGH'), 'new_case'),
    ),
    ('nursing', NUR, 'get_nurse_patients', (1, None)),
    ('nursing', NUR, 'get_vitals', (1, 20)),
    ('nursing', NUR, 'record_vitals', (1, 1)),
    ('nursing', NUR, 'get_notes', (1, 50)),
    ('nursing', NUR, 'add_note', (1, 1, 'note')),
    ('nursing', NUR, 'get_pending_administrations', (1,)),
    ('nursing', NUR, 'record_administration', (1, 1)),
    ('nursing', NUR, 'get_care_plans', (1,)),
    ('nursing', NUR, 'create_care_plan', (1, 1, 'plan', 'desc')),
    ('nursing', NUR, 'get_pending_tasks', (1,)),
    ('nursing', NUR, 'complete_task', (1, 1)),
    ('nursing', NUR, 'get_dashboard_stats', (1,)),
]


@pytest.fixture
def saas_disabled_module(app, monkeypatch):
    """Enable SaaS mode, bind a fake tenant, and force the module OFF."""
    app.config['ENABLE_SAAS_MODE'] = True
    monkeypatch.setattr(
        'services.feature_gate_service.FeatureGateService.module_enabled',
        staticmethod(lambda _tenant_id, _module: False),
    )
    with app.test_request_context():
        import flask

        flask.g.current_tenant = types.SimpleNamespace(id=1, slug='pharmacy-shifa')
        yield


@pytest.mark.parametrize('module,svc,method,args', GATED_METHODS)
def test_gated_service_raises_when_module_disabled(saas_disabled_module, module, svc, method, args):
    func = getattr(svc, method)
    with pytest.raises(ModuleNotEnabledError) as exc:
        func(*args)
    assert exc.value.module_name == module


def test_gate_does_not_trip_when_module_enabled(app, monkeypatch):
    """Sanity: with the module ON, the gate must not raise ModuleNotEnabledError."""
    app.config['ENABLE_SAAS_MODE'] = True
    monkeypatch.setattr(
        'services.feature_gate_service.FeatureGateService.module_enabled',
        staticmethod(lambda _tenant_id, _module: True),
    )
    with app.test_request_context():
        import flask

        flask.g.current_tenant = types.SimpleNamespace(id=1, slug='pharmacy-shifa')
        try:
            RAD.get_worklist()
        except ModuleNotEnabledError:
            pytest.fail('Gate tripped even though module is enabled')


def test_inventory_gate_does_not_trip_when_enabled(app, monkeypatch):
    """The Spell A): inventory read methods must run (not gate) when enabled."""
    app.config['ENABLE_SAAS_MODE'] = True
    monkeypatch.setattr(
        'services.feature_gate_service.FeatureGateService.module_enabled',
        staticmethod(lambda _tenant_id, _module: True),
    )
    with app.test_request_context():
        import flask

        flask.g.current_tenant = types.SimpleNamespace(id=1, slug='pharmacy-shifa')
        try:
            INV.current_stock(1)
            INV.low_stock_alerts(10)
        except ModuleNotEnabledError:
            pytest.fail('Inventory gate tripped even though module is enabled')


def test_emergency_gate_does_not_trip_when_enabled(app, monkeypatch):
    """The Spell A): emergency read methods must run (not gate) when enabled."""
    app.config['ENABLE_SAAS_MODE'] = True
    monkeypatch.setattr(
        'services.feature_gate_service.FeatureGateService.module_enabled',
        staticmethod(lambda _tenant_id, _module: True),
    )
    with app.test_request_context():
        import flask

        flask.g.current_tenant = types.SimpleNamespace(id=1, slug='pharmacy-shifa')
        try:
            ER.get_cases_by_status('WAITING')
            ER.get_triage_stats()
        except ModuleNotEnabledError:
            pytest.fail('Emergency gate tripped even though module is enabled')


def test_nursing_gate_does_not_trip_when_enabled(app, monkeypatch):
    """The Spell A): nursing read methods must run (not gate) when enabled."""
    app.config['ENABLE_SAAS_MODE'] = True
    monkeypatch.setattr(
        'services.feature_gate_service.FeatureGateService.module_enabled',
        staticmethod(lambda _tenant_id, _module: True),
    )
    with app.test_request_context():
        import flask

        flask.g.current_tenant = types.SimpleNamespace(id=1, slug='pharmacy-shifa')
        try:
            NUR.get_vitals(1)
            NUR.get_notes(1, 50)
            NUR.get_pending_administrations(1)
            NUR.get_pending_tasks(1)
            NUR.get_dashboard_stats(1)
        except ModuleNotEnabledError:
            pytest.fail('Nursing gate tripped even though module is enabled')
