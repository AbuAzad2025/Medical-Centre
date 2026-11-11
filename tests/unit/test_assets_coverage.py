"""Coverage tests for utils.assets.py."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from utils.assets import asset_url, register_asset_helpers, _load_manifest

pytest_plugins = ['tests._isolated_tenant']


class TestLoadManifest:
    def test_existing_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, 'dist')
            os.makedirs(manifest_path)
            with open(os.path.join(manifest_path, 'manifest.json'), 'w') as f:
                json.dump({'/static/js/app.js': '/static/js/app.a1b2c3.js'}, f)

            result = _load_manifest(tmpdir)
            assert result == {'/static/js/app.js': '/static/js/app.a1b2c3.js'}

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _load_manifest(tmpdir)
            assert result == {}


class TestAssetURL:
    def test_no_manifest_returns_source(self, app):
        with app.app_context():
            # No manifest file -> passthrough
            result = asset_url('/static/js/app.js')
            assert result == '/static/js/app.js'

    def test_with_manifest_returns_hashed(self, app):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, 'dist')
            os.makedirs(manifest_path)
            with open(os.path.join(manifest_path, 'manifest.json'), 'w') as f:
                json.dump({'/static/js/app.js': '/static/js/app.a1b2c3.js'}, f)

            with app.app_context():
                app.static_folder = tmpdir
                # Clear the lru_cache
                _load_manifest.cache_clear()
                result = asset_url('/static/js/app.js')
                assert result == '/static/js/app.a1b2c3.js'

    def test_unknown_source_returns_source(self, app):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = os.path.join(tmpdir, 'dist')
            os.makedirs(manifest_path)
            with open(os.path.join(manifest_path, 'manifest.json'), 'w') as f:
                json.dump({'/static/js/app.js': '/static/js/app.a1b2c3.js'}, f)

            with app.app_context():
                app.static_folder = tmpdir
                _load_manifest.cache_clear()
                result = asset_url('/static/js/unknown.js')
                assert result == '/static/js/unknown.js'


class TestRegisterAssetHelpers:
    def test_registers_helper(self, app):
        with app.app_context():
            register_asset_helpers(app)
            assert 'asset_url' in app.jinja_env.globals
