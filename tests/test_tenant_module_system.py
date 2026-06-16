"""
Tests for Tenant, Module, and Permission systems
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_factory import create_app, db
from app.core.tenant.models import Tenant, SubscriptionPlan
from app.core.module.models import ModuleDefinition, TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.core.module.validators import validate_reception_required, can_activate_module
from app.core.permission.service import PermissionService
from app.modules.workflows.visit import VisitWorkflowService, VisitStatus
from app.modules.workflows.lab import LabWorkflowService, LabOrderStatus
from app.modules.workflows.stock_models import StockMovement
from models.user import User


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.rollback()
        db.session.remove()
        db.engine.dispose()
        db.session.rollback()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


def test_tenant_creation(app):
    with app.app_context():
        t = Tenant(slug="test-clinic", name="Test Clinic", contact_email="test@test.com", status="active")
        db.session.add(t)
        db.session.commit()
        assert t.id is not None
        assert t.is_active_and_paid() is True


def test_subscription_plan(app):
    with app.app_context():
        plan = SubscriptionPlan(name="Basic", billing_type="monthly", base_price=99.00)
        db.session.add(plan)
        db.session.commit()
        assert plan.id is not None
        assert plan.currency == "SAR"


def test_module_registry_has_reception():
    assert "reception" in MODULE_REGISTRY
    assert "doctor" in MODULE_REGISTRY
    meta = MODULE_REGISTRY["doctor"]
    assert "reception" in meta.required_modules


def test_reception_required_validator(app):
    with app.app_context():
        t = Tenant(slug="validator-test", name="Validator Test", contact_email="v@test.com", status="active")
        db.session.add(t)
        db.session.commit()

        # Only 2 clinical modules: OK without reception
        validate_reception_required(t.id, ["doctor", "lab"])

        # 3 clinical modules without reception: should raise
        with pytest.raises(Exception):
            validate_reception_required(t.id, ["doctor", "lab", "radiology"])


def test_tenant_user_isolation(app):
    with app.app_context():
        t1 = Tenant(slug="t1", name="T1", contact_email="t1@test.com", status="active")
        t2 = Tenant(slug="t2", name="T2", contact_email="t2@test.com", status="active")
        db.session.add_all([t1, t2])
        db.session.commit()

        u1 = User(tenant_id=t1.id, username="admin", email="a@t1.com", full_name="Admin", role="admin")
        u1.set_password("pass123")
        u2 = User(tenant_id=t2.id, username="admin", email="a@t2.com", full_name="Admin", role="admin")
        u2.set_password("pass123")
        db.session.add_all([u1, u2])
        db.session.commit()

        # Same username, different tenants: allowed
        assert u1.username == u2.username
        assert u1.tenant_id != u2.tenant_id


def test_visit_workflow_state_machine(app):
    with app.app_context():
        assert VisitWorkflowService.can_transition("registered", "waiting") is True
        assert VisitWorkflowService.can_transition("registered", "archived") is False
        assert VisitWorkflowService.can_transition("completed", "archived") is True


def test_lab_workflow_state_machine(app):
    with app.app_context():
        assert LabWorkflowService.can_transition("ordered", "sample_collected") is True
        assert LabWorkflowService.can_transition("ordered", "approved") is False
        assert LabWorkflowService.can_transition("results_entered", "approved") is True


def test_stock_movement_model(app):
    with app.app_context():
        from models.medication import Medication
        med = Medication(trade_name="Test Med", scientific_name="Test", dosage_form="tablet", strength="500mg", stock_quantity=0, price=10.0)
        db.session.add(med)
        db.session.commit()
        sm = StockMovement(
            medication_id=med.id,
            movement_type="purchase",
            quantity=100,
            before_quantity=0,
            after_quantity=100,
        )
        db.session.add(sm)
        db.session.commit()
        assert sm.id is not None
        assert sm.before_quantity == 0
        assert sm.after_quantity == 100


def test_permission_service_fallback(app):
    with app.app_context():
        u = User(username="doc", email="doc@test.com", full_name="Doctor", role="doctor")
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()

        # Doctor should have visit.read permission via fallback
        assert PermissionService.has_permission(u, "visit.read") is True
        # But not user.create
        assert PermissionService.has_permission(u, "user.create") is False
        # Super_admin wildcard
        admin = User(username="superadmin", email="sa@test.com", full_name="SA", role="super_admin")
        admin.set_password("pass")
        db.session.add(admin)
        db.session.commit()
        assert PermissionService.has_permission(admin, "anything.anything") is True


def test_module_guard_on_request(app, client):
    with app.app_context():
        t = Tenant(slug="guarded", name="Guarded", contact_email="g@test.com", status="active")
        db.session.add(t)
        db.session.commit()

        # No reception module activated
        resp = client.get("/reception/dashboard", headers={"Host": "guarded.azad.com"})
        # Without login it redirects to login, not 403
        assert resp.status_code in (302, 403)


def test_owner_blueprint_exists(client):
    resp = client.get("/owner/dashboard")
    assert resp.status_code in (200, 302, 403)
