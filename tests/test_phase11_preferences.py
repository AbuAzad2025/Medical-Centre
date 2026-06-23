"""Tests for phase 11 — user preferences (Gate 11 completion)."""

from app.shared.user_preferences import (
    DEFAULT_USER_PREFERENCES,
    get_user_preferences,
    save_user_preferences,
)


class TestUserPreferencesDefaults:
    def test_defaults_include_density_radius_dashboard(self):
        assert DEFAULT_USER_PREFERENCES['density'] == 'normal'
        assert DEFAULT_USER_PREFERENCES['radius'] == 'md'
        assert 'hidden_widgets' in DEFAULT_USER_PREFERENCES['dashboard']


class TestUserPreferencesAPI:
    def test_save_density_and_radius(self, app, manager_user, db):
        with app.app_context():
            assert save_user_preferences(manager_user, {'density': 'compact', 'radius': 'lg'})
            prefs = get_user_preferences(manager_user)
            assert prefs['density'] == 'compact'
            assert prefs['radius'] == 'lg'

    def test_save_hidden_widgets(self, app, manager_user, db):
        with app.app_context():
            assert save_user_preferences(manager_user, {
                'dashboard': {'hidden_widgets': ['queue_live', 'visits_today']},
            })
            prefs = get_user_preferences(manager_user)
            assert 'queue_live' in prefs['dashboard']['hidden_widgets']

    def test_rejects_invalid_density(self, app, manager_user, db):
        with app.app_context():
            save_user_preferences(manager_user, {'density': 'compact'})
            save_user_preferences(manager_user, {'density': 'invalid'})
            prefs = get_user_preferences(manager_user)
            assert prefs['density'] == 'compact'

    def test_api_preferences_post(self, manager_auth_client, app):
        resp = manager_auth_client.post(
            '/api/user/preferences',
            json={'density': 'comfortable', 'radius': 'sm'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['preferences']['density'] == 'comfortable'

    def test_command_center_has_customize_panel(self, manager_auth_client):
        resp = manager_auth_client.get('/manager/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'تخصيص اللوحة' in text
        assert 'cc-widget-toggle' in text

    def test_ui_preferences_script_in_base(self, auth_client):
        resp = auth_client.get('/medication/dashboard')
        text = resp.get_data(as_text=True)
        assert 'ui-preferences.js' in text
        assert 'uiDensitySelect' in text
