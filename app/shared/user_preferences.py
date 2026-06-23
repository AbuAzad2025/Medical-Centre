"""Staff user UI preferences — theme etc. (phase 11)."""
from __future__ import annotations

from typing import Any

from app_factory import db

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    'theme': 'light',
}


def get_user_preferences(user) -> dict[str, Any]:
    if not user:
        return dict(DEFAULT_USER_PREFERENCES)
    raw = getattr(user, 'preferences', None)
    merged = dict(DEFAULT_USER_PREFERENCES)
    if isinstance(raw, dict):
        merged.update(raw)
    return merged


def save_user_preferences(user, updates: dict) -> bool:
    if not user:
        return False
    allowed = {'theme'}
    current = get_user_preferences(user)
    for key, value in updates.items():
        if key not in allowed:
            continue
        if key == 'theme' and value not in ('light', 'dark'):
            continue
        current[key] = value
    user.preferences = current
    db.session.commit()
    return True
