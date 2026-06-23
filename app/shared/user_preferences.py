"""Staff user UI preferences — theme, density, dashboard widgets (phase 11)."""
from __future__ import annotations

from typing import Any

from app_factory import db

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    'theme': 'light',
    'density': 'normal',
    'radius': 'md',
    'dashboard': {
        'hidden_widgets': [],
        'pinned_routes': [],
    },
}

_ALLOWED_THEME = frozenset({'light', 'dark'})
_ALLOWED_DENSITY = frozenset({'compact', 'normal', 'comfortable'})
_ALLOWED_RADIUS = frozenset({'sm', 'md', 'lg'})


def get_user_preferences(user) -> dict[str, Any]:
    if not user:
        return dict(DEFAULT_USER_PREFERENCES)
    merged: dict[str, Any] = {
        'theme': DEFAULT_USER_PREFERENCES['theme'],
        'density': DEFAULT_USER_PREFERENCES['density'],
        'radius': DEFAULT_USER_PREFERENCES['radius'],
        'dashboard': dict(DEFAULT_USER_PREFERENCES['dashboard']),
    }
    raw = getattr(user, 'preferences', None)
    if not isinstance(raw, dict):
        return merged
    if raw.get('theme') in _ALLOWED_THEME:
        merged['theme'] = raw['theme']
    if raw.get('density') in _ALLOWED_DENSITY:
        merged['density'] = raw['density']
    if raw.get('radius') in _ALLOWED_RADIUS:
        merged['radius'] = raw['radius']
    dash = raw.get('dashboard')
    if isinstance(dash, dict):
        hw = dash.get('hidden_widgets')
        if isinstance(hw, list):
            merged['dashboard']['hidden_widgets'] = [str(x) for x in hw if x]
        pr = dash.get('pinned_routes')
        if isinstance(pr, list):
            merged['dashboard']['pinned_routes'] = [str(x) for x in pr if x]
    return merged


def save_user_preferences(user, updates: dict) -> bool:
    if not user or not isinstance(updates, dict):
        return False
    current = get_user_preferences(user)
    if 'theme' in updates and updates['theme'] in _ALLOWED_THEME:
        current['theme'] = updates['theme']
    if 'density' in updates and updates['density'] in _ALLOWED_DENSITY:
        current['density'] = updates['density']
    if 'radius' in updates and updates['radius'] in _ALLOWED_RADIUS:
        current['radius'] = updates['radius']
    if 'dashboard' in updates and isinstance(updates['dashboard'], dict):
        dash_in = updates['dashboard']
        dash = dict(current.get('dashboard') or DEFAULT_USER_PREFERENCES['dashboard'])
        if 'hidden_widgets' in dash_in and isinstance(dash_in['hidden_widgets'], list):
            dash['hidden_widgets'] = [str(x) for x in dash_in['hidden_widgets'] if x]
        if 'pinned_routes' in dash_in and isinstance(dash_in['pinned_routes'], list):
            dash['pinned_routes'] = [str(x) for x in dash_in['pinned_routes'] if x]
        current['dashboard'] = dash
    user.preferences = current
    db.session.commit()
    return True
