"""Gunicorn configuration smoke tests."""

import importlib.util
from pathlib import Path


def _load_gunicorn_conf():
    path = Path(__file__).parent.parent / 'gunicorn.conf.py'
    spec = importlib.util.spec_from_file_location('gunicorn_conf', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGunicornConfig:
    def test_config_loads_without_syntax_errors(self):
        conf = _load_gunicorn_conf()
        assert conf.bind
        assert conf.workers >= 1
        assert conf.worker_class in ('gthread', 'gevent', 'eventlet', 'sync')
        assert conf.timeout >= 30

    def test_workers_formula_matches_env_override(self, monkeypatch):
        monkeypatch.setenv('WEB_CONCURRENCY', '9')
        conf = _load_gunicorn_conf()
        assert conf.workers == 9

    def test_async_worker_class_default(self, monkeypatch):
        monkeypatch.delenv('GUNICORN_WORKER_CLASS', raising=False)
        conf = _load_gunicorn_conf()
        assert conf.worker_class == 'gthread'
