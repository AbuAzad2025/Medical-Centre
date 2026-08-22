"""
Asset pipeline helpers — resolves fingerprinted files from static/dist/manifest.json.

Dev mode (no build): returns the original /static/... path untouched.
Production (after `npm run build`): returns the hashed path from the manifest.

Template usage:
    <script src="{{ asset_url('/static/js/pages/reception/queue.js') }}"></script>
"""

import functools
import json
import os

from flask import current_app

MANIFEST_REL = 'dist/manifest.json'


@functools.lru_cache(maxsize=1)
def _load_manifest(static_root: str) -> dict:
    manifest_path = os.path.join(static_root, MANIFEST_REL)
    try:
        with open(manifest_path, encoding='utf-8') as f:
            return json.load(f)
    except OSError:
        return {}


def asset_url(source_url: str) -> str:
    """Return hashed asset URL when built; passthrough otherwise."""
    static_root = current_app.static_folder
    manifest = _load_manifest(static_root)
    if not manifest:
        # Dev mode — no build artifacts.
        return source_url
    return manifest.get(source_url, source_url)


def register_asset_helpers(app):
    """Attach asset_url() to the Jinja environment."""
    app.jinja_env.globals['asset_url'] = asset_url
