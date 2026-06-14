from app_factory import create_app, db
from models.user import User


def _create_app(mode="single_install"):
    app = create_app("testing")
    app.config["DEPLOYMENT_MODE"] = mode
    app.config["ENABLE_SAAS_MODE"] = mode == "saas"
    app.config["TENANT_RESOLUTION_MODE"] = "domain"
    app.config["TENANT_BASE_DOMAIN"] = "example.test"
    with app.app_context():
        db.create_all()
    return app


def _login_as(app, client, role="owner"):
    username = f"{role}_user"
    user = User(username=username, email=f"{role}@example.test", full_name=role, role=role)
    user.set_password("pass123")
    with app.app_context():
        db.session.add(user)
        db.session.commit()

    return client.post(
        "/auth/login",
        data={"username": username, "password": "pass123"},
        follow_redirects=False,
    )


def test_owner_tenant_api_disabled_in_single_install():
    app = _create_app("single_install")
    client = app.test_client()
    login_response = _login_as(app, client, "owner")
    assert login_response.status_code in (302, 303)

    response = client.get("/owner/api/tenants")
    assert response.status_code == 404
    assert response.get_json()["error"] == "saas_mode_disabled"


def test_saas_mode_requires_resolved_tenant_before_module_routes():
    app = _create_app("saas")
    client = app.test_client()

    response = client.get("/reception/dashboard", headers={"Host": "unknown.example.test"})
    assert response.status_code == 403
